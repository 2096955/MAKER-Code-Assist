#!/usr/bin/env python3
"""
FastAPI Server: REST API for workflow execution
"""

import os
import json
import time
import aiofiles
from pathlib import Path
from typing import Optional, AsyncGenerator
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
    output_file: Optional[str] = None  # Path to save streamed output (e.g., "output.md")


class CompactRequest(BaseModel):
    session_id: str
    instructions: Optional[str] = None


class ClarificationRequest(BaseModel):
    answers: dict  # Dict mapping question numbers/keys to answers


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
    output_file: Optional[str] = None  # Path to save streamed output (e.g., "output.md")


async def stream_with_file_backup(
    generator: AsyncGenerator[str, None],
    output_file: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """
    Stream chunks from generator and optionally save to file for crash recovery.

    Args:
        generator: Async generator yielding string chunks
        output_file: Optional file path to save output (e.g., "output.md")

    Yields:
        String chunks from generator
    """
    if output_file:
        # Ensure output directory exists
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Open file in append mode for crash recovery
        async with aiofiles.open(output_path, 'a') as f:
            async for chunk in generator:
                # Write to file first (for crash recovery)
                await f.write(chunk)
                await f.flush()  # Ensure written to disk immediately
                # Then yield for HTTP response
                yield chunk
    else:
        # No file backup, just pass through
        async for chunk in generator:
            yield chunk


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
                    sse_data = f"data: {json.dumps({'id': task_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': request.model, 'choices': [{'index': 0, 'delta': delta, 'finish_reason': None}]})}\n\n"
                    yield sse_data
                # Final chunk
                yield f"data: {json.dumps({'id': task_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': request.model, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                error_data = {'error': {'message': str(e), 'type': 'internal_error'}}
                yield f"data: {json.dumps(error_data)}\n\n"

        return StreamingResponse(
            stream_with_file_backup(generate(), request.output_file),
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
            stream_with_file_backup(generate(), request.output_file),
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
    """
    Resume a saved session (like --continue or --resume).
    
    If long-running support is enabled, uses progress tracking.
    Otherwise, resumes context compression session.
    """
    # Check if long-running is enabled - use that if available
    if orchestrator.enable_long_running and orchestrator.session_manager:
        return StreamingResponse(
            orchestrator.resume_session(session_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    
    # Fallback to context compression session
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


@app.post("/api/session/{session_id}/checkpoint")
async def checkpoint_session(session_id: str, feature_name: str):
    """
    Create a clean checkpoint for a completed feature.
    
    Verifies tests pass, creates git commit, and updates feature status.
    """
    if not orchestrator.enable_long_running:
        raise HTTPException(
            status_code=400,
            detail="Long-running support not enabled. Set ENABLE_LONG_RUNNING=true"
        )
    
    result = await orchestrator.checkpoint_session(session_id, feature_name)
    return result


@app.post("/api/clarify/{task_id}")
async def clarify_task(task_id: str, request: ClarificationRequest):
    """
    Provide answers to planner clarification questions and resume workflow.
    
    Args:
        task_id: Task identifier
        request: Answers to clarification questions
        
    Returns:
        Streaming response with resumed workflow output
    """
    # Load clarification state from Redis
    clarification_data = orchestrator.redis.get(f"clarification:{task_id}")
    if not clarification_data:
        raise HTTPException(
            status_code=404,
            detail=f"Clarification state not found for task {task_id}. May have expired (1h TTL) or task doesn't need clarification."
        )
    
    try:
        clarification_state = json.loads(clarification_data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid clarification state format")
    
    # Inject answers into original task
    original_task = clarification_state.get("original_task", "")
    questions = clarification_state.get("questions", [])
    answers = request.answers
    
    # Format clarified context
    clarified_context = ""
    for i, question in enumerate(questions, 1):
        answer = answers.get(str(i)) or answers.get(f"question_{i}") or answers.get(question) or "Not specified"
        clarified_context += f"Q{i}: {question}\nA{i}: {answer}\n\n"
    
    # Clear clarification state
    orchestrator.redis.delete(f"clarification:{task_id}")
    
    # Load existing plan and resume from CODING phase
    async def generate():
        try:
            from orchestrator.orchestrator import TaskState
            state = TaskState.load_from_redis(task_id, orchestrator.redis)
            
            if not state:
                yield f"data: {json.dumps({'error': f'Task state not found for {task_id}'})}\n\n"
                return
            
            if not state.plan:
                yield f"data: {json.dumps({'error': 'No plan found in task state. Cannot resume from coding phase.'})}\n\n"
                return
            
            # Inject clarifications into plan context
            if "clarified_context" not in state.plan:
                state.plan["clarified_context"] = {}
            state.plan["clarified_context"] = clarified_context
            state.status = "coding"  # Skip replanning
            state.save_to_redis(orchestrator.redis)
            
            resume_msg = '[SYSTEM] Resuming workflow from coding phase with clarifications...\n'
            yield f"data: {json.dumps({'chunk': resume_msg})}\n\n"
            
            # Resume from coding phase (skip preprocessing and planning)
            async for chunk in orchestrator._resume_from_coding(state, clarified_context):
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            import traceback
            yield f"data: {json.dumps({'error': str(e), 'traceback': traceback.format_exc()})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.get("/api/task/{task_id}/melodic-line")
async def get_melodic_line(task_id: str):
    """
    Get the complete melodic line (reasoning chain) for a task.

    The melodic line shows how each agent built on previous agents' reasoning,
    creating a coherent chain from preprocessor → planner → coder → reviewer.

    Returns:
        List of actions in chronological order with reasoning
    """
    if not orchestrator.workflow_memory or not orchestrator.workflow_memory.enabled:
        raise HTTPException(
            status_code=503,
            detail="Melodic line memory not enabled. Set ENABLE_MELODIC_MEMORY=true and install kuzu"
        )

    melodic_line = orchestrator.workflow_memory.get_melodic_line(task_id)

    if not melodic_line:
        raise HTTPException(
            status_code=404,
            detail=f"No melodic line found for task {task_id}. Task may not exist or melodic memory was disabled."
        )

    return {
        "task_id": task_id,
        "melodic_line": melodic_line,
        "length": len(melodic_line),
        "agents": [action["agent"] for action in melodic_line],
        "summary": f"Workflow chain: {' → '.join([action['agent'] for action in melodic_line])}"
    }


@app.get("/api/melodic-memory/stats")
async def get_melodic_memory_stats():
    """
    Get statistics about the melodic line memory system.

    Returns:
        Statistics including total tasks, actions, and melodic line links
    """
    if not orchestrator.workflow_memory:
        return {"enabled": False, "message": "Melodic memory not initialized"}

    stats = orchestrator.workflow_memory.get_stats()
    return stats


@app.get("/api/task/{task_id}/agent/{agent}/context")
async def get_agent_context(task_id: str, agent: str):
    """
    Get the melodic line context that a specific agent sees.

    This shows what reasoning chain the agent had access to when making decisions.

    Args:
        task_id: Task identifier
        agent: Agent name (preprocessor, planner, coder, reviewer)

    Returns:
        The formatted melodic line context string
    """
    if not orchestrator.workflow_memory or not orchestrator.workflow_memory.enabled:
        raise HTTPException(
            status_code=503,
            detail="Melodic line memory not enabled"
        )

    context = orchestrator.workflow_memory.get_context_for_agent(task_id, agent)

    if not context:
        return {
            "task_id": task_id,
            "agent": agent,
            "context": "",
            "message": "No context available (agent hasn't run yet or task doesn't exist)"
        }

    return {
        "task_id": task_id,
        "agent": agent,
        "context": context,
        "length": len(context)
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)

