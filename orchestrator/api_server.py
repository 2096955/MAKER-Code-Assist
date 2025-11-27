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
        "has_review": state.review_feedback is not None
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)

