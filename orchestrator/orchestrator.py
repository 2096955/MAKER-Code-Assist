#!/usr/bin/env python3
"""
Orchestrator: Coordinates agents, manages state, handles streaming
"""

import json
import time
import os
import redis
import httpx
import asyncio
from typing import AsyncGenerator, Optional, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

class AgentName(Enum):
    PREPROCESSOR = "preprocessor"
    PLANNER = "planner"
    CODER = "coder"
    REVIEWER = "reviewer"
    VOTER = "voter"

@dataclass
class TaskState:
    """Redis-backed task state"""
    task_id: str
    user_input: str
    preprocessed_input: str
    plan: Optional[dict] = None
    code: Optional[str] = None
    test_results: Optional[dict] = None
    review_feedback: Optional[dict] = None
    status: str = "pending"  # pending, preprocessing, planning, coding, reviewing, complete
    iteration_count: int = 0
    
    def save_to_redis(self, redis_client):
        key = f"task:{self.task_id}"
        redis_client.set(key, json.dumps(asdict(self)))
    
    @staticmethod
    def load_from_redis(task_id: str, redis_client):
        key = f"task:{task_id}"
        data = redis_client.get(key)
        if not data:
            return None
        return TaskState(**json.loads(data))

class Orchestrator:
    def __init__(self, redis_host=None, redis_port=6379, mcp_url=None):
        redis_host = redis_host or os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", redis_port))
        self.redis = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        
        # llama.cpp Metal endpoints (from docker-compose)
        # Each service runs on port 8080 internally, mapped to 8000-8003 externally
        self.endpoints = {
            AgentName.PREPROCESSOR: os.getenv("PREPROCESSOR_URL", "http://localhost:8000/v1/chat/completions"),
            AgentName.PLANNER: os.getenv("PLANNER_URL", "http://localhost:8001/v1/chat/completions"),
            AgentName.CODER: os.getenv("CODER_URL", "http://localhost:8002/v1/chat/completions"),
            AgentName.REVIEWER: os.getenv("REVIEWER_URL", "http://localhost:8003/v1/chat/completions"),
            AgentName.VOTER: os.getenv("VOTER_URL", "http://localhost:8004/v1/chat/completions"),
        }
        
        self.num_candidates = int(os.getenv("MAKER_NUM_CANDIDATES", "5"))
        self.vote_k = int(os.getenv("MAKER_VOTE_K", "3"))
        
        # MCP server URL
        self.mcp_url = mcp_url or os.getenv("MCP_CODEBASE_URL", "http://localhost:9001")
        
        # System prompts (loaded from files in prompts/)
        self.system_prompts = {}
        self.prompts_dir = Path(os.getenv("PROMPTS_DIR", "prompts"))
    
    def _load_system_prompt(self, agent_name: str) -> str:
        """Load system prompt from prompts/ directory"""
        prompt_file = self.prompts_dir / f"{agent_name}-system.md"
        if prompt_file.exists():
            with open(prompt_file) as f:
                return f.read()
        return ""
    
    async def _query_mcp(self, tool: str, args: Dict[str, Any]) -> str:
        """Query MCP server for codebase information"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.mcp_url}/api/mcp/tool",
                    json={"tool": tool, "args": args}
                )
                if response.status_code == 200:
                    result = response.json()
                    return result.get("result", "")
                return f"❌ MCP error: {response.status_code}"
        except Exception as e:
            return f"❌ MCP query failed: {str(e)}"
    
    async def preprocess_input(self, task_id: str, user_input: str) -> str:
        """Convert audio/image/text to clean text"""
        # For now, assume text input
        # In full system: detect type, call appropriate preprocessor
        # Return JSON format for consistency
        return json.dumps({
            "type": "preprocessed_input",
            "original_type": "text",
            "preprocessed_text": user_input,
            "confidence": 1.0,
            "metadata": {}
        })
    
    async def call_agent_sync(self, agent: AgentName, system_prompt: str,
                              user_message: str, temperature: float = 0.7) -> str:
        """Non-streaming call to agent, returns full response"""
        async with httpx.AsyncClient(timeout=300.0) as client:
            payload = {
                "model": "default",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "temperature": temperature,
                "max_tokens": 4096,
                "stream": False
            }
            try:
                response = await client.post(self.endpoints[agent], json=payload)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return f"Error: {response.status_code}"
            except Exception as e:
                return f"Error: {str(e)}"
    
    async def generate_candidates(self, task_desc: str, context: str, n: int = 5) -> list:
        """Generate N candidate solutions in parallel (MAKER decomposition)"""
        coder_prompt = self._load_system_prompt("coder")
        context_truncated = context[:2000] if len(context) > 2000 else context
        coder_request = f"""Task: {task_desc}
Context: {context_truncated}

Generate code implementation.
"""
        print(f"[DEBUG] generate_candidates: task_desc={len(task_desc)} chars, context={len(context)} chars, request={len(coder_request)} chars")
        tasks = [
            self.call_agent_sync(AgentName.CODER, coder_prompt, coder_request, temperature=0.3 + (i * 0.1))
            for i in range(n)
        ]
        candidates = await asyncio.gather(*tasks)
        return [c for c in candidates if not c.startswith("Error:")]
    
    async def maker_vote(self, candidates: list, task_desc: str, k: int = 3) -> tuple:
        """MAKER first-to-K voting on candidates. Returns (winner, vote_counts)"""
        if len(candidates) == 0:
            return None, {}
        if len(candidates) == 1:
            return candidates[0], {"A": 1}
        
        voter_prompt = self._load_system_prompt("voter")
        labels = "ABCDE"[:len(candidates)]
        
        candidate_text = "\n\n".join([
            f"Candidate {labels[i]}:\n```\n{c[:2000]}\n```" for i, c in enumerate(candidates)
        ])
        
        vote_request = f"""Task: {task_desc}

{candidate_text}

Vote for the BEST candidate. Reply with only: {', '.join(labels)}
"""
        
        num_voters = 2 * k - 1
        vote_tasks = [
            self.call_agent_sync(AgentName.VOTER, voter_prompt, vote_request, temperature=0.1)
            for _ in range(num_voters)
        ]
        
        votes = await asyncio.gather(*vote_tasks)
        
        vote_counts = {label: 0 for label in labels}
        for vote in votes:
            vote = vote.strip().upper()
            if vote and vote[0] in labels:
                vote_counts[vote[0]] += 1
        
        winner_label = max(vote_counts, key=vote_counts.get)
        winner_idx = labels.index(winner_label)
        
        return candidates[winner_idx], vote_counts
    
    async def call_agent(self, agent: AgentName, system_prompt: str, 
                         user_message: str, temperature: float = 0.7,
                         max_tokens: int = 2048) -> AsyncGenerator[str, None]:
        """Stream response from llama.cpp Metal agent"""
        async with httpx.AsyncClient(timeout=300.0) as client:
            payload = {
                "model": "default",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True
            }
            
            try:
                async with client.stream("POST", self.endpoints[agent], json=payload) as response:
                    if response.status_code != 200:
                        yield f"❌ Agent error: {response.status_code}\n"
                        return
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            try:
                                chunk = json.loads(line[6:])
                                if chunk.get("choices"):
                                    delta = chunk["choices"][0].get("delta", {})
                                    if content := delta.get("content"):
                                        yield content
                            except json.JSONDecodeError:
                                pass
                            except Exception as e:
                                pass
            except Exception as e:
                yield f"❌ Agent call failed: {str(e)}\n"
    
    def _classify_request(self, user_input: str) -> str:
        """Classify request type: 'simple_code', 'question', 'complex_code'"""
        lower = user_input.lower().strip()
        
        question_patterns = [
            "what do i need", "how do i", "how to", "what is", "what are",
            "explain", "why", "can you tell", "looking at", "analyze",
            "deploy", "requirements", "dependencies", "understand",
        ]
        for p in question_patterns:
            if p in lower:
                return "question"
        
        simple_patterns = [
            "hello", "hi", "hey", "test", "ping",
            "write a", "create a", "make a", "generate a",
            "hello world", "fizzbuzz", "fibonacci", "factorial",
            "function", "class", "script",
        ]
        if len(lower.split()) <= 15:
            for p in simple_patterns:
                if p in lower:
                    return "simple_code"
        
        return "complex_code"
    
    async def _simple_code_request(self, task_id: str, user_input: str) -> AsyncGenerator[str, None]:
        """Fast path for simple coding requests - skip planning overhead"""
        direct_prompt = """You are a coding assistant. Output code directly in markdown code blocks.
No JSON wrapping. No explanations unless asked. Just working code."""
        direct_request = f"""Write code for: {user_input}

Be direct. Output working code in a markdown code block. No questions."""
        yield f"[DIRECT] Simple request detected, generating code...\n"
        code_output = ""
        async for chunk in self.call_agent(AgentName.CODER, direct_prompt, direct_request, temperature=0.3, max_tokens=2048):
            code_output += chunk
            yield chunk
        yield "\n"
    
    async def _answer_question(self, task_id: str, user_input: str) -> AsyncGenerator[str, None]:
        """Handle questions/analysis - use Planner for reasoning, not coding"""
        codebase_context = await self._query_mcp("analyze_codebase", {})
        
        analyst_prompt = """You are a helpful technical analyst. Answer questions directly and concisely.
Use the codebase context provided to give accurate, specific answers.
Format your response in clear markdown. No JSON output needed."""
        
        question = f"""Question: {user_input}

Codebase Context:
{codebase_context}

Provide a direct, helpful answer. If you need to reference files, mention them specifically."""
        
        yield f"[ANALYST] Analyzing your question...\n\n"
        async for chunk in self.call_agent(AgentName.PLANNER, analyst_prompt, question, temperature=0.3, max_tokens=2048):
            yield chunk
        yield "\n"
    
    async def orchestrate_workflow(self, task_id: str, user_input: str) -> AsyncGenerator[str, None]:
        """Main orchestration loop: preprocess → plan → code → review"""
        
        request_type = self._classify_request(user_input)
        
        if request_type == "simple_code":
            async for chunk in self._simple_code_request(task_id, user_input):
                yield chunk
            return
        
        if request_type == "question":
            async for chunk in self._answer_question(task_id, user_input):
                yield chunk
            return
        
        state = TaskState(task_id=task_id, user_input=user_input, preprocessed_input="")
        state.status = "preprocessing"
        state.save_to_redis(self.redis)
        
        preprocessed_json = await self.preprocess_input(task_id, user_input)
        preprocessed_data = json.loads(preprocessed_json)
        preprocessed_text = preprocessed_data.get("preprocessed_text", user_input)
        
        state.preprocessed_input = preprocessed_text
        state.status = "planning"
        state.save_to_redis(self.redis)
        yield f"[PREPROCESSOR] Converted input to: {preprocessed_text}\n"
        
        planner_prompt = self._load_system_prompt("planner")
        
        # Query MCP for codebase context
        codebase_context = await self._query_mcp("analyze_codebase", {})
        
        plan_message = f"""Task: {preprocessed_text}

Codebase Context:
{codebase_context}

Create an execution plan with tasks. Use MCP tools if you need more context.
"""
        
        plan_json = ""
        yield "[PLANNER] Analyzing task with codebase context...\n"
        async for chunk in self.call_agent(AgentName.PLANNER, planner_prompt, plan_message, temperature=0.3, max_tokens=1024):
            plan_json += chunk
            yield chunk
        
        try:
            state.plan = json.loads(plan_json)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', plan_json, re.DOTALL)
            if json_match:
                try:
                    state.plan = json.loads(json_match.group())
                except json.JSONDecodeError:
                    state.plan = {"plan": [{"id": "task_1", "description": preprocessed_text, "assigned_to": "coder"}]}
            else:
                state.plan = {"plan": [{"id": "task_1", "description": preprocessed_text, "assigned_to": "coder"}]}
        
        state.status = "coding"
        state.save_to_redis(self.redis)
        
        # 3. CODE (iterate with Reviewer until approved)
        coder_prompt = self._load_system_prompt("coder")
        
        max_iterations = 3
        while state.iteration_count < max_iterations:
            state.iteration_count += 1
            
            if state.plan and "plan" in state.plan and len(state.plan["plan"]) > 0:
                task = state.plan["plan"][0]
                task_desc = task.get("description", preprocessed_text)
            else:
                task_desc = preprocessed_text
            
            yield f"\n[MAKER] Generating {self.num_candidates} candidates in parallel...\n"
            candidates = await self.generate_candidates(task_desc, preprocessed_text, self.num_candidates)
            
            if len(candidates) == 0:
                yield "❌ No valid candidates generated\n"
                break
            
            yield f"[MAKER] Got {len(candidates)} candidates, voting (first-to-{self.vote_k})...\n"
            code_output, vote_counts = await self.maker_vote(candidates, task_desc, self.vote_k)
            
            if code_output is None:
                yield "❌ Voting failed\n"
                break
            
            yield f"[MAKER] Votes: {vote_counts}\n"
            yield f"[CODER] Winner output:\n{code_output[:500]}...\n"
            
            state.code = code_output
            state.status = "reviewing"
            state.save_to_redis(self.redis)
            
            # 4. REVIEW
            reviewer_prompt = self._load_system_prompt("reviewer")
            
            review_request = f"""Review this code:

{code_output}

Original task: {task_desc}

Run tests and validate code quality.
"""
            
            review_output = ""
            yield f"\n[REVIEWER] Validating code...\n"
            async for chunk in self.call_agent(AgentName.REVIEWER, reviewer_prompt, review_request, temperature=0.1):
                review_output += chunk
                yield chunk
            
            # Try to parse review as JSON
            try:
                state.review_feedback = json.loads(review_output)
            except json.JSONDecodeError:
                # Extract status from text
                if "approved" in review_output.lower() or "✅" in review_output:
                    state.review_feedback = {"status": "approved"}
                else:
                    state.review_feedback = {"status": "failed", "feedback": review_output}
            
            state.save_to_redis(self.redis)
            
            # Check if approved
            if state.review_feedback.get("status") == "approved":
                state.status = "complete"
                state.save_to_redis(self.redis)
                yield "\n✅ Code approved!\n"
                break
            else:
                yield f"\n⚠️ Iteration {state.iteration_count}: Feedback to Coder\n"
        
        if state.iteration_count >= max_iterations:
            yield f"\n❌ Max iterations ({max_iterations}) reached. Escalating to Planner.\n"
            state.status = "failed"
            state.save_to_redis(self.redis)
        
        # Final output
        yield json.dumps({
            "task_id": task_id,
            "status": state.status,
            "code": state.code,
            "iterations": state.iteration_count,
            "review_feedback": state.review_feedback
        }, indent=2)

# Usage
async def main():
    orch = Orchestrator()
    
    task_id = f"task_{int(time.time())}"
    user_input = "Refactor auth.py to use JWT instead of sessions"
    
    async for output in orch.orchestrate_workflow(task_id, user_input):
        print(output, end="", flush=True)

if __name__ == "__main__":
    import sys
    if "--serve" in sys.argv:
        # Will be served via api_server.py
        print("Orchestrator ready (use api_server.py to serve)")
    else:
        asyncio.run(main())

