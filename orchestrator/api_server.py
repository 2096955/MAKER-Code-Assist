#!/usr/bin/env python3
"""
FastAPI Server: REST API for workflow execution
"""

import os
import json
import time
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from orchestrator.orchestrator import Orchestrator

app = FastAPI(title="Multi-Agent Orchestrator API", version="1.0.0")

# CORS middleware for Windsurf/Cursor integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize orchestrator
orchestrator = Orchestrator(
    redis_host=os.getenv("REDIS_HOST", "localhost"),
    redis_port=int(os.getenv("REDIS_PORT", "6379")),
    mcp_url=os.getenv("MCP_CODEBASE_URL", "http://localhost:9001")
)


class WorkflowRequest(BaseModel):
    input: str
    stream: bool = True
    task_id: Optional[str] = None
    session_id: Optional[str] = None
    resume: bool = False


class CompactRequest(BaseModel):
    session_id: str
    instructions: Optional[str] = None


# OpenAI-compatible request models
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: bool = False
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "multi-agent-orchestrator",
        "version": "1.0.0"
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Multi-Agent Orchestrator",
        "version": "1.0.0",
        "endpoints": {
            "workflow": "/api/workflow",
            "health": "/health",
            "models": "/v1/models",
            "chat": "/v1/chat/completions"
        }
    }


@app.get("/v1/models")
async def list_models():
    """OpenAI-compatible models endpoint"""
    return {
        "object": "list",
        "data": [
            {
                "id": "multi-agent-orchestrator",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "multi-agent-system",
                "permission": [],
                "root": "multi-agent-orchestrator",
                "parent": None
            }
        ]
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI-compatible chat completions endpoint"""
    # Extract user message from messages
    user_message = None
    for msg in reversed(request.messages):
        if msg.role == "user":
            user_message = msg.content
            break
    
    if not user_message:
        raise HTTPException(status_code=400, detail="No user message found in messages")
    
    task_id = f"chat_{int(time.time())}"
    
    if request.stream:
        # Streaming response (SSE format compatible with OpenAI)
        async def generate():
            try:
                async for chunk in orchestrator.orchestrate_workflow(task_id, user_message):
                    # Format as OpenAI-compatible SSE
                    delta = {"role": "assistant", "content": chunk}
                    yield f"data: {json.dumps({'id': task_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': request.model, 'choices': [{'index': 0, 'delta': delta, 'finish_reason': None}]})}\n\n"
                # Final chunk
                yield f"data: {json.dumps({'id': task_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': request.model, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                error_data = {'error': {'message': str(e), 'type': 'internal_error'}}
                yield f"data: {json.dumps(error_data)}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    else:
        result = []
        try:
            async for chunk in orchestrator.orchestrate_workflow(task_id, user_message):
                result.append(chunk)
            
            full_content = "".join(result)
            response = {
                "id": task_id,
                "object": "chat.completion",
                "created": int(time.time()),
                "model": request.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": full_content
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": len(user_message.split()),
                    "completion_tokens": len(full_content.split()),
                    "total_tokens": len(user_message.split()) + len(full_content.split())
                }
            }
            json.dumps(response)
            return response
        except json.JSONDecodeError as e:
            print(f"JSON error in content: {e}")
            print(f"Content preview: {full_content[:500]}")
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/workflow")
async def execute_workflow(request: WorkflowRequest):
    """Execute multi-agent workflow"""
    task_id = request.task_id or f"task_{int(time.time())}"
    
    if request.stream:
        # Streaming response (SSE)
        async def generate():
            try:
                async for chunk in orchestrator.orchestrate_workflow(task_id, request.input):
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    else:
        # Non-streaming response (collect all chunks)
        result = []
        try:
            async for chunk in orchestrator.orchestrate_workflow(task_id, request.input):
                result.append(chunk)
            return {
                "task_id": task_id,
                "status": "complete",
                "output": "".join(result)
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/task/{task_id}")
async def get_task_status(task_id: str):
    """Get task status from Redis"""
    from orchestrator.orchestrator import TaskState
    state = TaskState.load_from_redis(task_id, orchestrator.redis)
    if not state:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id": state.task_id,
        "status": state.status,
        "iteration_count": state.iteration_count,
        "has_plan": state.plan is not None,
        "has_code": state.code is not None,
        "has_review": state.review_feedback is not None,
        "context_stats": state.context_stats
    }


@app.get("/api/context/{session_id}")
async def get_context_stats(session_id: str):
    """Get context compression stats for a session (like /context command)"""
    compressor = orchestrator._context_compressors.get(session_id)
    if not compressor:
        compressor = orchestrator.load_session(session_id)
    if not compressor:
        raise HTTPException(status_code=404, detail="Session not found")
    return compressor.get_stats()


@app.post("/api/compact")
async def compact_context(request: CompactRequest):
    """Compact/compress context with optional custom instructions (like /compact command)"""
    compressor = orchestrator._context_compressors.get(request.session_id)
    if not compressor:
        compressor = orchestrator.load_session(request.session_id)
    if not compressor:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if request.instructions:
        compressor.set_compact_instructions(request.instructions)
    
    before_stats = compressor.get_stats()
    compressed = await compressor.compress_if_needed()
    after_stats = compressor.get_stats()
    
    orchestrator.save_session(request.session_id)
    
    return {
        "compressed": compressed,
        "before": before_stats,
        "after": after_stats
    }


@app.post("/api/clear/{session_id}")
async def clear_session(session_id: str):
    """Clear session context (like /clear command)"""
    compressor = orchestrator._context_compressors.get(session_id)
    if compressor:
        compressor.clear()
        orchestrator.save_session(session_id)
        return {"status": "cleared", "session_id": session_id}
    
    orchestrator.redis.delete(f"session:{session_id}")
    return {"status": "deleted", "session_id": session_id}


@app.get("/api/sessions")
async def list_sessions():
    """List all saved sessions (like --resume picker)"""
    return {"sessions": orchestrator.list_sessions()}


@app.post("/api/session/{session_id}/resume")
async def resume_session(session_id: str):
    """Resume a saved session (like --continue or --resume)"""
    compressor = orchestrator.load_session(session_id)
    if not compressor:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "status": "resumed",
        "session_id": session_id,
        "stats": compressor.get_stats()
    }


@app.post("/api/session/{session_id}/save")
async def save_session(session_id: str):
    """Save current session to Redis"""
    if session_id not in orchestrator._context_compressors:
        raise HTTPException(status_code=404, detail="Active session not found")
    orchestrator.save_session(session_id)
    return {"status": "saved", "session_id": session_id}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)

