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
from typing import AsyncGenerator, Optional, Dict, Any, List
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path


@dataclass
class ConversationMessage:
    """Single message in conversation history"""
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)
    token_estimate: int = 0
    
    def __post_init__(self):
        if self.token_estimate == 0:
            self.token_estimate = len(self.content) // 4


class ContextCompressor:
    """
    Hierarchical context compression with sliding window.
    Mimics Claude's approach: recent messages in full, older messages summarized.
    """
    
    def __init__(self, orchestrator: 'Orchestrator',
                 max_context_tokens: int = 32000,
                 recent_window_tokens: int = 8000,
                 summary_chunk_size: int = 4000,
                 session_id: Optional[str] = None):
        self.orchestrator = orchestrator
        self.max_context_tokens = max_context_tokens
        self.recent_window_tokens = recent_window_tokens
        self.summary_chunk_size = summary_chunk_size
        self.conversation_history: List[ConversationMessage] = []
        self.compressed_history: str = ""
        self.compressed_token_count: int = 0
        self.session_id = session_id or f"session_{int(time.time())}"
        self.custom_compact_instructions: Optional[str] = None
    
    def add_message(self, role: str, content: str):
        """Add a message to conversation history"""
        msg = ConversationMessage(role=role, content=content)
        self.conversation_history.append(msg)
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimate (4 chars per token)"""
        return len(text) // 4
    
    def _get_recent_messages(self) -> tuple[List[ConversationMessage], List[ConversationMessage]]:
        """Split history into recent (keep full) and older (to compress)"""
        total_tokens = 0
        recent = []
        older = []
        
        for msg in reversed(self.conversation_history):
            if total_tokens + msg.token_estimate <= self.recent_window_tokens:
                recent.insert(0, msg)
                total_tokens += msg.token_estimate
            else:
                older.insert(0, msg)
        
        return recent, older
    
    def set_compact_instructions(self, instructions: str):
        """Set custom instructions for compression (like /compact custom message)"""
        self.custom_compact_instructions = instructions
    
    async def _summarize_chunk(self, messages: List[ConversationMessage]) -> str:
        """Use Preprocessor (Gemma2-2B) to summarize a chunk of messages"""
        if not messages:
            return ""
        
        chunk_text = "\n".join([
            f"{msg.role}: {msg.content[:1000]}" for msg in messages
        ])
        
        if self.custom_compact_instructions:
            summary_prompt = f"""Summarize this conversation following these instructions:
{self.custom_compact_instructions}

Be brief but retain critical technical details."""
        else:
            summary_prompt = """Summarize this conversation concisely, preserving:
1. Key decisions and conclusions
2. Important code snippets or file references
3. Current task state and requirements

Be brief but retain critical technical details."""
        
        summary = await self.orchestrator.call_agent_sync(
            AgentName.PREPROCESSOR,
            summary_prompt,
            f"Conversation to summarize:\n{chunk_text}",
            temperature=0.1
        )
        
        return summary if not summary.startswith("Error:") else chunk_text[:500]
    
    async def compress_if_needed(self) -> bool:
        """Compress older messages if context is getting too large. Returns True if compression occurred."""
        total_tokens = sum(m.token_estimate for m in self.conversation_history)
        total_tokens += self.compressed_token_count
        
        if total_tokens <= self.max_context_tokens:
            return False
        
        recent, older = self._get_recent_messages()
        
        if not older:
            return False
        
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for msg in older:
            if current_tokens + msg.token_estimate > self.summary_chunk_size:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = [msg]
                current_tokens = msg.token_estimate
            else:
                current_chunk.append(msg)
                current_tokens += msg.token_estimate
        
        if current_chunk:
            chunks.append(current_chunk)
        
        summaries = await asyncio.gather(*[
            self._summarize_chunk(chunk) for chunk in chunks
        ])
        
        new_compressed = "\n---\n".join(summaries)
        if self.compressed_history:
            self.compressed_history = f"{self.compressed_history}\n---\n{new_compressed}"
        else:
            self.compressed_history = new_compressed
        
        self.compressed_token_count = self._estimate_tokens(self.compressed_history)
        self.conversation_history = recent
        
        return True
    
    async def get_context(self, include_system: bool = True) -> str:
        """Get the full context string for sending to an agent"""
        await self.compress_if_needed()
        
        parts = []
        
        if self.compressed_history:
            parts.append(f"[Previous conversation summary]\n{self.compressed_history}")
        
        if self.conversation_history:
            recent_text = "\n".join([
                f"{msg.role}: {msg.content}" for msg in self.conversation_history
            ])
            parts.append(f"[Recent conversation]\n{recent_text}")
        
        return "\n\n".join(parts)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get compression statistics"""
        recent_tokens = sum(m.token_estimate for m in self.conversation_history)
        total = recent_tokens + self.compressed_token_count
        return {
            "session_id": self.session_id,
            "total_messages": len(self.conversation_history),
            "recent_tokens": recent_tokens,
            "compressed_tokens": self.compressed_token_count,
            "total_tokens": total,
            "max_tokens": self.max_context_tokens,
            "used_percent": round((total / self.max_context_tokens) * 100, 1),
            "compression_ratio": round(self.compressed_token_count / max(1, total), 3)
        }
    
    def clear(self):
        """Clear all history"""
        self.conversation_history = []
        self.compressed_history = ""
        self.compressed_token_count = 0
        self.custom_compact_instructions = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize compressor state for Redis persistence"""
        return {
            "session_id": self.session_id,
            "max_context_tokens": self.max_context_tokens,
            "recent_window_tokens": self.recent_window_tokens,
            "summary_chunk_size": self.summary_chunk_size,
            "conversation_history": [
                {"role": m.role, "content": m.content, "timestamp": m.timestamp, "token_estimate": m.token_estimate}
                for m in self.conversation_history
            ],
            "compressed_history": self.compressed_history,
            "compressed_token_count": self.compressed_token_count,
            "custom_compact_instructions": self.custom_compact_instructions
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], orchestrator: 'Orchestrator') -> 'ContextCompressor':
        """Deserialize compressor state from Redis"""
        compressor = cls(
            orchestrator=orchestrator,
            max_context_tokens=data.get("max_context_tokens", 32000),
            recent_window_tokens=data.get("recent_window_tokens", 8000),
            summary_chunk_size=data.get("summary_chunk_size", 4000),
            session_id=data.get("session_id")
        )
        compressor.conversation_history = [
            ConversationMessage(
                role=m["role"],
                content=m["content"],
                timestamp=m.get("timestamp", time.time()),
                token_estimate=m.get("token_estimate", 0)
            )
            for m in data.get("conversation_history", [])
        ]
        compressor.compressed_history = data.get("compressed_history", "")
        compressor.compressed_token_count = data.get("compressed_token_count", 0)
        compressor.custom_compact_instructions = data.get("custom_compact_instructions")
        return compressor


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
    status: str = "pending"
    iteration_count: int = 0
    context_stats: Optional[dict] = None
    
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
        self.prompts_dir = Path(os.getenv("PROMPTS_DIR", "agents"))
        
        # Context compression settings
        self.max_context_tokens = int(os.getenv("MAX_CONTEXT_TOKENS", "32000"))
        self.recent_window_tokens = int(os.getenv("RECENT_WINDOW_TOKENS", "8000"))
        self.summary_chunk_size = int(os.getenv("SUMMARY_CHUNK_SIZE", "4000"))
        
        # Per-task context compressors (keyed by task_id)
        self._context_compressors: Dict[str, ContextCompressor] = {}
        
        # Configurable timeouts
        self.agent_timeout = float(os.getenv("AGENT_TIMEOUT_MS", "300000")) / 1000
        self.mcp_timeout = float(os.getenv("MCP_TIMEOUT_MS", "30000")) / 1000
    
    def _load_system_prompt(self, agent_name: str) -> str:
        """Load system prompt from prompts/ directory"""
        prompt_file = self.prompts_dir / f"{agent_name}-system.md"
        if prompt_file.exists():
            with open(prompt_file) as f:
                return f.read()
        return ""
    
    def get_context_compressor(self, task_id: str) -> ContextCompressor:
        """Get or create a context compressor for a task"""
        if task_id not in self._context_compressors:
            self._context_compressors[task_id] = ContextCompressor(
                orchestrator=self,
                max_context_tokens=self.max_context_tokens,
                recent_window_tokens=self.recent_window_tokens,
                summary_chunk_size=self.summary_chunk_size
            )
        return self._context_compressors[task_id]
    
    def cleanup_context(self, task_id: str):
        """Clean up context compressor for completed task"""
        if task_id in self._context_compressors:
            del self._context_compressors[task_id]
    
    def save_session(self, session_id: str):
        """Save session state to Redis for later resume"""
        if session_id in self._context_compressors:
            compressor = self._context_compressors[session_id]
            self.redis.set(f"session:{session_id}", json.dumps(compressor.to_dict()))
            self.redis.expire(f"session:{session_id}", 86400)  # 24h TTL
    
    def load_session(self, session_id: str) -> Optional[ContextCompressor]:
        """Load session state from Redis"""
        data = self.redis.get(f"session:{session_id}")
        if data:
            compressor = ContextCompressor.from_dict(json.loads(data), self)
            self._context_compressors[session_id] = compressor
            return compressor
        return None
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all saved sessions"""
        sessions = []
        for key in self.redis.scan_iter("session:*"):
            session_id = key.replace("session:", "")
            data = self.redis.get(key)
            if data:
                session_data = json.loads(data)
                sessions.append({
                    "session_id": session_id,
                    "total_messages": len(session_data.get("conversation_history", [])),
                    "compressed_tokens": session_data.get("compressed_token_count", 0)
                })
        return sessions
    
    async def get_git_context(self) -> str:
        """Get git diff context for planner"""
        try:
            result = await self._query_mcp("run_command", {"command": "git diff --stat HEAD~5"})
            if result and not result.startswith(" "):
                return f"Recent git changes:\n{result}"
        except Exception:
            pass
        return ""
    
    async def _query_mcp(self, tool: str, args: Dict[str, Any]) -> str:
        """Query MCP server for codebase information"""
        try:
            async with httpx.AsyncClient(timeout=self.mcp_timeout) as client:
                response = await client.post(
                    f"{self.mcp_url}/api/mcp/tool",
                    json={"tool": tool, "args": args}
                )
                if response.status_code == 200:
                    result = response.json()
                    return result.get("result", "")
                return f" MCP error: {response.status_code}"
        except Exception as e:
            return f" MCP query failed: {str(e)}"
    
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
        async with httpx.AsyncClient(timeout=self.agent_timeout) as client:
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
    
    async def generate_candidates(self, task_desc: str, context: str, n: int = 5, 
                                    task_id: Optional[str] = None) -> list:
        """Generate N candidate solutions in parallel (MAKER decomposition)"""
        coder_prompt = self._load_system_prompt("coder")
        
        if task_id:
            compressor = self.get_context_compressor(task_id)
            compressed_context = await compressor.get_context()
            stats = compressor.get_stats()
            print(f"[DEBUG] Context compression stats: {stats}")
        else:
            compressed_context = context
        
        coder_request = f"""Task: {task_desc}
Context: {compressed_context}

Generate code implementation.
"""
        print(f"[DEBUG] generate_candidates: task_desc={len(task_desc)} chars, context={len(compressed_context)} chars, request={len(coder_request)} chars")
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
        async with httpx.AsyncClient(timeout=self.agent_timeout) as client:
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
                        yield f" Agent error: {response.status_code}\n"
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
                yield f" Agent call failed: {str(e)}\n"
    
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
        
        compressor = self.get_context_compressor(task_id)
        compressor.add_message("user", user_input)
        
        preprocessed_json = await self.preprocess_input(task_id, user_input)
        preprocessed_data = json.loads(preprocessed_json)
        preprocessed_text = preprocessed_data.get("preprocessed_text", user_input)
        
        state.preprocessed_input = preprocessed_text
        state.status = "planning"
        state.save_to_redis(self.redis)
        yield f"[PREPROCESSOR] Converted input to: {preprocessed_text}\n"
        
        planner_prompt = self._load_system_prompt("planner")
        
        codebase_context = await self._query_mcp("analyze_codebase", {})
        git_context = await self.get_git_context()
        
        plan_message = f"""Task: {preprocessed_text}

Codebase Context:
{codebase_context}

{git_context}

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
            candidates = await self.generate_candidates(task_desc, preprocessed_text, self.num_candidates, task_id)
            
            if len(candidates) == 0:
                yield " No valid candidates generated\n"
                break
            
            yield f"[MAKER] Got {len(candidates)} candidates, voting (first-to-{self.vote_k})...\n"
            code_output, vote_counts = await self.maker_vote(candidates, task_desc, self.vote_k)
            
            if code_output is None:
                yield " Voting failed\n"
                break
            
            yield f"[MAKER] Votes: {vote_counts}\n"
            yield f"[CODER] Winner output:\n{code_output[:500]}...\n"
            
            compressor.add_message("assistant", f"Generated code:\n{code_output[:2000]}")
            
            state.code = code_output
            state.status = "reviewing"
            state.context_stats = compressor.get_stats()
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
            
            compressor.add_message("reviewer", review_output[:1000])
            
            try:
                state.review_feedback = json.loads(review_output)
            except json.JSONDecodeError:
                if "approved" in review_output.lower() or "" in review_output:
                    state.review_feedback = {"status": "approved"}
                else:
                    state.review_feedback = {"status": "failed", "feedback": review_output}
            
            state.context_stats = compressor.get_stats()
            state.save_to_redis(self.redis)
            
            # Check if approved
            if state.review_feedback.get("status") == "approved":
                state.status = "complete"
                state.save_to_redis(self.redis)
                yield "\n Code approved!\n"
                break
            else:
                yield f"\n Iteration {state.iteration_count}: Feedback to Coder\n"
        
        if state.iteration_count >= max_iterations:
            yield f"\n Max iterations ({max_iterations}) reached. Escalating to Planner.\n"
            state.status = "failed"
            state.save_to_redis(self.redis)
        
        final_stats = compressor.get_stats()
        self.save_session(task_id)
        self.cleanup_context(task_id)
        
        yield json.dumps({
            "task_id": task_id,
            "status": state.status,
            "code": state.code,
            "iterations": state.iteration_count,
            "review_feedback": state.review_feedback,
            "context_stats": final_stats
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

