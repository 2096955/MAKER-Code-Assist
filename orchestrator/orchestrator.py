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

# EE Memory imports
from orchestrator.ee_memory import HierarchicalMemoryNetwork
from orchestrator.agent_memory import AgentMemoryNetwork
from orchestrator.melodic_detector import MelodicLineDetector

# EE Planner (Spec-compliant)
from orchestrator.ee_planner import EEPlannerAgent, EnhancedSubtask
from orchestrator.ee_world_model import CodebaseWorldModel
from orchestrator.mcp_client_wrapper import MCPClientWrapper

# Observability imports
from orchestrator.observability import get_tracer, trace_agent_call, trace_maker_voting

# Long-running support imports
from orchestrator.progress_tracker import ProgressTracker
from orchestrator.session_manager import SessionManager
from orchestrator.checkpoint_manager import CheckpointManager

# Skills framework imports
from orchestrator.skill_loader import SkillLoader
from orchestrator.skill_matcher import SkillMatcher
from orchestrator.skill_extractor import SkillExtractor
from orchestrator.skill_registry import SkillRegistry


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

# Export AgentName for use in other modules
__all__ = ['AgentName', 'Orchestrator', 'ContextCompressor', 'TaskState']

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

        # MAKER mode: "high" (with Reviewer, needs 128GB RAM) or "low" (Planner reflection, works on 40GB RAM)
        self.maker_mode = os.getenv("MAKER_MODE", "high").lower()

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
        
        # Note: RAG is now agentic - exposed as MCP tools (rag_search, rag_query)
        # Agents call it when needed, no automatic injection
        # RAG_ENABLED env var is no longer used - RAG tools appear in /api/mcp/tools if index exists
        
        # EE Mode: Enable/disable Expositional Engineering planner
        self.ee_mode = os.getenv("EE_MODE", "true").lower() == "true"
        
        # EE Memory: Shared codebase world model (simplified version)
        codebase_root = os.getenv("CODEBASE_ROOT", ".")
        self.world_model = HierarchicalMemoryNetwork(
            codebase_path=codebase_root,
            compression_ratios=[0.3, 0.2, 0.15],
            preservation_thresholds=[0.85, 0.75, 0.70]
        )
        
        # Initialize world model if not already done
        self._initialize_world_model()
        
        # Per-agent memory networks
        self.agent_memories = {
            agent: AgentMemoryNetwork(agent, self.world_model)
            for agent in AgentName
        }
        
        # EE Planner (Spec-compliant) - lazy initialization
        self._ee_planner = None
        self._mcp_client_wrapper = None
        
        # Long-running support (Phase 1)
        self.enable_long_running = os.getenv("ENABLE_LONG_RUNNING", "false").lower() == "true"
        if self.enable_long_running:
            workspace_dir = os.getenv("WORKSPACE_DIR", "./workspace")
            workspace_path = Path(workspace_dir)
            self.progress_tracker = ProgressTracker(workspace_path)
            self.session_manager = SessionManager(self.progress_tracker)
            self.checkpoint_manager = CheckpointManager(self.progress_tracker, self.redis)
            print("[Orchestrator] Long-running support enabled")
        else:
            self.progress_tracker = None
            self.session_manager = None
            self.checkpoint_manager = None
        
        # Skills framework (Phase 2)
        self.enable_skills = os.getenv("ENABLE_SKILLS", "false").lower() == "true"
        if self.enable_skills:
            skills_dir = os.getenv("SKILLS_DIR", "./skills")
            skills_path = Path(skills_dir)
            self.skill_loader = SkillLoader(skills_path)
            # RAG service for skills (use existing RAG if available, or create new)
            # For now, skills use simple keyword matching (RAG optional)
            self.skill_matcher = SkillMatcher(self.skill_loader, rag_service=None)
            # Index skills in RAG if RAG is available
            # Note: RAG integration can be added later when RAG service is initialized
            print("[Orchestrator] Skills framework enabled")
        else:
            self.skill_loader = None
            self.skill_matcher = None
        
        # Skill learning (Phase 3)
        self.enable_skill_learning = os.getenv("ENABLE_SKILL_LEARNING", "false").lower() == "true"
        if self.enable_skill_learning and self.enable_skills:
            skills_dir = os.getenv("SKILLS_DIR", "./skills")
            skills_path = Path(skills_dir)
            self.skill_extractor = SkillExtractor(skills_path, self.skill_loader)
            self.skill_registry = SkillRegistry(self.redis)
            print("[Orchestrator] Skill learning enabled")
        else:
            self.skill_extractor = None
            self.skill_registry = None

        # Log MAKER mode for visibility
        if self.maker_mode == "low":
            print(f"[Orchestrator] 🎚️  MAKER Mode: LOW (Planner reflection validation, ~40-50GB RAM)")
        else:
            print(f"[Orchestrator] 🎚️  MAKER Mode: HIGH (Reviewer validation, ~128GB RAM)")
    
    def _load_system_prompt(self, agent_name: str) -> str:
        """Load system prompt from prompts/ directory"""
        prompt_file = self.prompts_dir / f"{agent_name}-system.md"
        if prompt_file.exists():
            with open(prompt_file) as f:
                return f.read()
        return ""
    
    def _get_ee_planner(self) -> Optional[EEPlannerAgent]:
        """Get or create EE Planner (lazy initialization)"""
        if not self.ee_mode:
            return None
        
        if self._ee_planner is None:
            try:
                # Create MCP client wrapper
                if self._mcp_client_wrapper is None:
                    self._mcp_client_wrapper = MCPClientWrapper(mcp_url=self.mcp_url)
                
                # Initialize EE Planner
                codebase_root = os.getenv("CODEBASE_ROOT", ".")
                self._ee_planner = EEPlannerAgent(
                    codebase_path=codebase_root,
                    mcp_client=self._mcp_client_wrapper,
                    model_name="nemotron-nano-8b"
                )
                print("[Orchestrator] EE Planner initialized")
            except Exception as e:
                print(f"[Orchestrator] Failed to initialize EE Planner: {e}")
                print("[Orchestrator] Falling back to standard planner")
                self.ee_mode = False
                return None
        
        return self._ee_planner
    
    async def _plan_with_ee(self, task_description: str) -> Dict:
        """
        Plan task using EE Planner (Spec-compliant)
        Uses actual MAKER Planner LLM with narrative-aware prompts
        Returns plan in format compatible with orchestrator
        """
        ee_planner = self._get_ee_planner()
        if not ee_planner:
            return None
        
        try:
            # Get enhanced subtasks from EE Planner (uses actual LLM)
            enhanced_subtasks = await ee_planner.plan_task_async(
                task_description,
                self,
                AgentName.PLANNER
            )
            
            # Convert EnhancedSubtask to orchestrator format
            plan_items = []
            for i, subtask in enumerate(enhanced_subtasks):
                plan_items.append({
                    "id": f"ee_subtask_{i+1}",
                    "description": subtask.description,
                    "assigned_to": "coder",
                    "target_modules": subtask.target_modules,
                    "preserves_narratives": subtask.relevant_narratives,
                    "dependencies": subtask.dependencies,
                    "warnings": subtask.warnings,
                    "confidence": subtask.confidence,
                    "preserves_patterns": subtask.preserves_patterns
                })
            
            return {
                "plan": plan_items,
                "ee_mode": True,
                "narrative_count": len(set(
                    narrative 
                    for subtask in enhanced_subtasks 
                    for narrative in subtask.relevant_narratives
                )),
                "average_confidence": sum(s.confidence for s in enhanced_subtasks) / len(enhanced_subtasks) if enhanced_subtasks else 0.0
            }
        except Exception as e:
            print(f"[Orchestrator] EE Planner error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _initialize_world_model(self):
        """Initialize world model by indexing codebase"""
        # Check if already initialized (could load from cache)
        if self.world_model.stats["l0_count"] > 0:
            return
        
        # Index codebase files
        codebase_root = Path(os.getenv("CODEBASE_ROOT", "."))
        excluded = {
            '.git', 'node_modules', 'dist', 'build', '__pycache__', '.specify', '.claude',
            'models', '.venv', 'venv', 'env', '.env', 'vendor', 'target',
            '.docker', 'docker-data', '.cache', '.npm', '.yarn', 'coverage',
            '.idea', '.vscode', '.DS_Store', 'tmp', 'temp', 'logs',
            'weaviate_data', 'redis_data', 'postgres_data', '.genkit'
        }
        
        codebase_files = {}
        max_files = 100  # Limit for initial indexing
        
        for root, dirs, files in os.walk(codebase_root):
            dirs[:] = [d for d in dirs if d not in excluded]
            
            for file in files:
                if len(codebase_files) >= max_files:
                    break
                
                if file.startswith('.'):
                    continue
                
                file_path = Path(root) / file
                if file_path.suffix in ['.py', '.js', '.ts', '.jsx', '.tsx', '.md']:
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            if len(content) < 1_000_000:  # 1MB limit
                                rel_path = str(file_path.relative_to(codebase_root))
                                codebase_files[rel_path] = content
                    except Exception:
                        pass
        
        # Add files to L₀
        for file_path, content in codebase_files.items():
            l0_id = self.world_model.add_code_file(file_path, content)
            # Extract entities to L₁
            self.world_model.extract_entities(l0_id)
        
        # Detect patterns (L₂)
        l1_ids = list(self.world_model.l1_nodes.keys())
        if l1_ids:
            self.world_model.detect_patterns(l1_ids)
        
        # Detect melodic lines (L₃)
        if self.world_model.l2_nodes:
            detector = MelodicLineDetector(persistence_threshold=0.7)
            melodic_lines = detector.detect_from_codebase(
                codebase_files,
                self.world_model.l0_nodes,
                self.world_model.l1_nodes,
                self.world_model.l2_nodes
            )
            
            # Add to world model
            for ml in melodic_lines:
                self.world_model.l3_melodic_lines[ml.id] = ml
        
        print(f"[EE Memory] Initialized: {self.world_model.stats['l0_count']} files, "
              f"{self.world_model.stats['l1_count']} entities, "
              f"{self.world_model.stats['l2_count']} patterns, "
              f"{self.world_model.stats['l3_count']} melodic lines")
    
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
    
    @trace_agent_call("preprocessor", "gemma-2-2b")
    async def preprocess_input(self, task_id: str, user_input: str) -> str:
        """Convert audio/image/text to clean text"""
        tracer = get_tracer()
        with tracer.start_as_current_span("preprocess") as span:
            span.set_attribute("input_type", "text")  # Detect actual type
            span.set_attribute("input_length", len(user_input))
            
            # Basic preprocessing (multi-modal conversion via Gemma2-2B)
            # For now, assume text input
            # In full system: detect type, call appropriate preprocessor
            # RAG is NOT automatically applied here - agents call it as a tool when needed
            
            # Return JSON format for consistency
            result = json.dumps({
                "type": "preprocessed_input",
                "original_type": "text",
                "preprocessed_text": user_input,
                "confidence": 1.0,
                "metadata": {}
            })
            span.set_attribute("output_length", len(result))
            return result
    
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
        tracer = get_tracer()
        with tracer.start_as_current_span("maker.generate_candidates") as span:
            span.set_attribute("maker.num_candidates", n)
            span.set_attribute("maker.temperature_range", f"0.3-{0.3 + (n-1)*0.1}")
            
            coder_prompt = self._load_system_prompt("coder")
            
            # Get narrative-aware context for Coder
            coder_memory = self.agent_memories[AgentName.CODER]
            narrative_context = coder_memory.get_context_for_agent(task_desc)
            
            if task_id:
                compressor = self.get_context_compressor(task_id)
                compressed_context = await compressor.get_context()
                stats = compressor.get_stats()
                print(f"[DEBUG] Context compression stats: {stats}")
                # Combine narrative context with compressed context
                full_context = f"{narrative_context}\n\n[Conversation History]\n{compressed_context}"
            else:
                full_context = narrative_context if narrative_context else context
            
            coder_request = f"""Task: {task_desc}
Context: {full_context}

Generate code implementation.
"""
            print(f"[DEBUG] generate_candidates: task_desc={len(task_desc)} chars, context={len(full_context)} chars, request={len(coder_request)} chars")
            tasks = [
                self.call_agent_sync(AgentName.CODER, coder_prompt, coder_request, temperature=0.3 + (i * 0.1))
                for i in range(n)
            ]
            candidates = await asyncio.gather(*tasks)
            valid_candidates = [c for c in candidates if not c.startswith("Error:")]
            span.set_attribute("maker.valid_candidates", len(valid_candidates))
            return valid_candidates
    
    async def maker_vote(self, candidates: list, task_desc: str, k: int = 3) -> tuple:
        """MAKER first-to-K voting on candidates. Returns (winner, vote_counts)"""
        tracer = get_tracer()
        span_context = trace_maker_voting(candidates, k)
        with span_context as span:
            # Set initial attributes after entering context
            span.set_attribute("maker.num_candidates", len(candidates))
            span.set_attribute("maker.k_value", k)
            span.set_attribute("maker.num_voters", 2 * k - 1)
            
            if len(candidates) == 0:
                span.set_attribute("maker.winner", "none")
                return None, {}
            if len(candidates) == 1:
                span.set_attribute("maker.winner", "A")
                span.set_attribute("maker.vote_distribution", json.dumps({"A": 1}))
                return candidates[0], {"A": 1}
            
            # Get narrative-aware context for Voter
            voter_memory = self.agent_memories[AgentName.VOTER]
            narrative_context = voter_memory.get_context_for_agent(task_desc)
            
            voter_prompt = self._load_system_prompt("voter")
            labels = "ABCDE"[:len(candidates)]
            
            candidate_text = "\n\n".join([
                f"Candidate {labels[i]}:\n```\n{c[:2000]}\n```" for i, c in enumerate(candidates)
            ])
            
            vote_request = f"""Task: {task_desc}

Context (Narrative Awareness):
{narrative_context}

Candidates:
{candidate_text}

Vote for the BEST candidate that preserves narrative coherence. Reply with only: {', '.join(labels)}
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
            
            span.set_attribute("maker.winner", winner_label)
            span.set_attribute("maker.vote_distribution", json.dumps(vote_counts))
            
            return candidates[winner_idx], vote_counts
    
    async def call_agent(self, agent: AgentName, system_prompt: str, 
                         user_message: str, temperature: float = 0.7,
                         max_tokens: int = 2048) -> AsyncGenerator[str, None]:
        """Stream response from llama.cpp Metal agent"""
        
        # Find relevant skills if enabled
        if self.enable_skills and self.skill_matcher:
            skills = self.skill_matcher.find_relevant_skills(user_message, top_k=2)
            
            if skills:
                # Augment system prompt with skills
                skills_section = "\n\n## Available Proven Patterns\n"
                skills_section += "The following proven coding patterns may be helpful for this task:\n\n"
                for skill in skills:
                    skills_section += f"### {skill.name}\n"
                    skills_section += f"{skill.description}\n\n"
                    # Include key instructions (truncated for context)
                    instructions_preview = skill.instructions[:800]  # Limit length
                    if len(skill.instructions) > 800:
                        instructions_preview += "\n\n[... see full skill for complete instructions ...]"
                    skills_section += f"{instructions_preview}\n\n---\n\n"
                
                system_prompt = system_prompt + skills_section
                
                # Log skill usage
                for skill in skills:
                    self._log_skill_usage(skill.name)
        
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
    
    def _log_skill_usage(self, skill_name: str):
        """
        Log skill usage in Redis for tracking.
        
        Args:
            skill_name: Name of the skill that was used
        """
        try:
            key = f"skills:usage:{skill_name}"
            self.redis.incr(key)
            self.redis.expire(key, 86400 * 30)  # 30 day TTL
        except Exception as e:
            print(f"Warning: Failed to log skill usage for {skill_name}: {e}")
    
    async def _classify_request(self, user_input: str) -> str:
        """
        Classify request type using LLM intelligence: 'simple_code', 'question', 'complex_code'

        This ensures accurate classification even with variations in phrasing.
        """
        classification_prompt = """You are a request classifier. Classify the user's request into ONE of these categories:

1. "question" - User is asking for information, explanation, guidance, or analysis
   Examples: "What would I need to do...", "How does X work?", "Could you explain...", "Tell me about..."

2. "simple_code" - User wants a simple, straightforward code snippet (< 50 lines)
   Examples: "Write a hello world", "Create a function to...", "Generate a simple..."

3. "complex_code" - User wants code implementation, refactoring, or feature development
   Examples: "Implement authentication", "Refactor this module", "Add error handling"

Respond with ONLY the category name: question, simple_code, or complex_code"""

        classification_request = f"""Classify this request:

"{user_input}"

Category:"""

        # Use Preprocessor for fast classification
        try:
            response = ""
            async for chunk in self.call_agent(AgentName.PREPROCESSOR, classification_prompt, classification_request, temperature=0.1, max_tokens=20):
                response += chunk

            classification = response.strip().lower()
            # Extract just the category if LLM added extra text
            if "question" in classification:
                return "question"
            elif "simple_code" in classification or "simple" in classification:
                return "simple_code"
            elif "complex_code" in classification or "complex" in classification:
                return "complex_code"
            else:
                # Fallback to pattern matching if LLM response is unclear
                return self._classify_request_fallback(user_input)
        except Exception as e:
            print(f"[Warning] Classification failed: {e}, using fallback")
            return self._classify_request_fallback(user_input)

    def _classify_request_fallback(self, user_input: str) -> str:
        """Fallback pattern-based classification if LLM classification fails"""
        lower = user_input.lower().strip()

        # Question keywords (broader patterns)
        question_keywords = [
            "what", "how", "why", "when", "where", "which", "who",
            "explain", "tell me", "could you", "can you", "would you",
            "describe", "analyze", "understand", "show me",
            "is there", "are there", "does this", "do i", "should i",
        ]
        if any(kw in lower for kw in question_keywords) and "?" not in lower:
            # Likely a question if has question word
            return "question"

        if "?" in lower:
            # Explicit question mark
            return "question"

        # Code generation keywords
        code_keywords = ["write", "create", "make", "generate", "implement", "add", "build", "develop"]
        if any(kw in lower for kw in code_keywords):
            # Check if it's a simple request (< 15 words)
            if len(lower.split()) <= 15:
                return "simple_code"
            return "complex_code"

        # Default to complex code for ambiguous requests
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
        """
        Handle questions intelligently without hallucinations.

        Uses Preprocessor for direct question answering (fast, no tool calling).
        For codebase-specific questions, provides context from MCP.
        """
        # Check if question is vague and needs clarification
        vague_patterns = ["check", "look at", "try again", "fix this", "help"]
        lower_input = user_input.lower().strip()

        if len(user_input.split()) <= 5 and any(p in lower_input for p in vague_patterns):
            yield f"[ANALYST] Your question seems unclear.\n\n"
            yield f"Could you please clarify what you'd like me to help with? For example:\n\n"
            yield f"- \"Explain how the orchestrator workflow works\"\n"
            yield f"- \"What files handle authentication?\"\n"
            yield f"- \"How do I add a new agent?\"\n"
            yield f"- \"What would I need to translate this Python code to Rust?\"\n\n"
            return

        # Get codebase context for codebase-related questions
        codebase_keywords = ["codebase", "file", "code", "function", "class", "module", "how does", "where is"]
        needs_context = any(kw in lower_input for kw in codebase_keywords)

        codebase_info = ""
        if needs_context:
            try:
                codebase_context = await self._query_mcp("analyze_codebase", {})
                codebase_info = f"\n\nCodebase Context:\n{codebase_context[:1000]}"
            except Exception as e:
                print(f"[Warning] Failed to get codebase context: {e}")

        # Use Preprocessor for direct, concise answers (no tool calling, no hallucinations)
        analyst_prompt = """You are a helpful technical assistant. Answer questions directly and clearly.

CRITICAL RULES:
1. DO NOT make up file paths or try to read files
2. DO NOT use tools or execute commands
3. DO NOT repeat yourself in loops
4. If you don't have enough information, say so and ask for clarification
5. Provide direct, actionable guidance based on what you know

Format your response in clear markdown."""

        question = f"""Question: {user_input}{codebase_info}

Provide a direct, helpful answer. If you need more specific information to answer properly, ask the user for clarification instead of making assumptions."""

        yield f"[ANALYST] Answering your question...\n\n"

        response_text = ""
        async for chunk in self.call_agent(AgentName.PREPROCESSOR, analyst_prompt, question, temperature=0.4, max_tokens=1500):
            response_text += chunk
            yield chunk

        # Detect if response contains hallucinated tool calls or file paths
        hallucination_indicators = ["read_file", "```bash", "2096955/", "<think>"]
        if any(indicator in response_text for indicator in hallucination_indicators):
            yield f"\n\n---\n\n**Note**: I apologize, but I started to hallucinate file paths or commands. "
            yield f"Could you rephrase your question more specifically? For example:\n"
            yield f"- \"What are the steps to translate Python async code to Rust?\"\n"
            yield f"- \"Which Rust frameworks are equivalent to FastAPI?\"\n"

        yield "\n"

    async def _planner_reflection(self, code_output: str, task_desc: str, plan: dict) -> str:
        """
        Use Planner to reflect on whether code meets the original plan (Low mode alternative to Reviewer).

        This leverages the Planner's existing context about the task and plan to validate
        that the generated code actually implements what was planned.

        Args:
            code_output: Generated code to validate
            task_desc: Original task description
            plan: The plan created by Planner earlier

        Returns:
            JSON string with review feedback (same format as Reviewer for compatibility)
        """
        planner_prompt = self._load_system_prompt("planner")

        # Get narrative-aware context
        planner_memory = self.agent_memories[AgentName.PLANNER]
        narrative_context = planner_memory.get_context_for_agent(task_desc)

        # Format plan for readability
        plan_text = ""
        if plan and "plan" in plan:
            for i, item in enumerate(plan["plan"], 1):
                plan_text += f"{i}. {item.get('description', 'No description')}\n"

        reflection_request = f"""You created this plan earlier:

{plan_text}

Original task: {task_desc}

Now reflect: Does this generated code successfully implement the plan?

Generated Code:
```
{code_output[:4000]}
```

Context (Narrative Awareness):
{narrative_context}

Validate:
1. Does the code implement all planned subtasks?
2. Does it preserve narrative coherence (business logic flows)?
3. Are there any obvious bugs or missing pieces?
4. Does it match the original task intent?

Respond in JSON format:
{{"status": "approved", "feedback": "Code successfully implements the plan"}}
OR
{{"status": "failed", "feedback": "Missing implementation for X, Y needs fixing", "suggestions": ["Add X", "Fix Y"]}}
"""

        reflection_output = await self.call_agent_sync(
            AgentName.PLANNER,
            planner_prompt,
            reflection_request,
            temperature=0.2  # Low temperature for consistent validation
        )

        return reflection_output

    async def orchestrate_workflow(self, task_id: str, user_input: str) -> AsyncGenerator[str, None]:
        """Main orchestration loop: preprocess → plan → code → review"""

        request_type = await self._classify_request(user_input)
        
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
        
        # Phase 3: Check for highly relevant skills (Auto-apply)
        if self.enable_skills and self.skill_matcher:
            similar_skills = self.skill_matcher.find_relevant_skills(user_input, top_k=1)
            if similar_skills:
                top_skill = similar_skills[0]
                relevance = self.skill_matcher.calculate_relevance(user_input, top_skill)
                
                if relevance > 0.85:
                    # Get skill stats if registry available
                    skill_stats = None
                    if self.skill_registry:
                        skill_stats = self.skill_registry.get_skill_stats(top_skill.name)
                    
                    yield f"[SKILL] Found highly relevant skill: {top_skill.name}\n"
                    if skill_stats:
                        yield f"[SKILL] This pattern solved {skill_stats.get('usage_count', 0)} similar tasks before\n"
                        yield f"[SKILL] Success rate: {skill_stats.get('success_rate', 0.5):.0%}\n"
                    yield "\n"
        
        compressor = self.get_context_compressor(task_id)
        compressor.add_message("user", user_input)
        
        preprocessed_json = await self.preprocess_input(task_id, user_input)
        preprocessed_data = json.loads(preprocessed_json)
        preprocessed_text = preprocessed_data.get("preprocessed_text", user_input)
        
        state.preprocessed_input = preprocessed_text
        state.status = "planning"
        state.save_to_redis(self.redis)
        yield f"[PREPROCESSOR] Converted input to: {preprocessed_text}\n"
        
        # Try EE Planner first if enabled
        if self.ee_mode:
            yield "[PLANNER] Using EE Planner (narrative-aware)...\n"
            ee_plan = await self._plan_with_ee(preprocessed_text)
            
            if ee_plan:
                state.plan = ee_plan
                yield f"[EE PLANNER] Generated {len(ee_plan['plan'])} subtasks with narrative awareness\n"
                yield f"[EE PLANNER] Preserving {ee_plan['narrative_count']} business narratives\n"
                yield f"[EE PLANNER] Average confidence: {ee_plan['average_confidence']:.2f}\n"
                
                # Display subtasks
                for subtask in ee_plan['plan']:
                    yield f"  • {subtask['description']}\n"
                    if subtask.get('warnings'):
                        for warning in subtask['warnings']:
                            yield f"    ⚠️  {warning}\n"
            else:
                # Fallback to standard planner
                yield "[PLANNER] EE Planner failed, falling back to standard planner...\n"
                self.ee_mode = False
        
        # Standard planner (if EE mode disabled or failed)
        if not self.ee_mode or not state.plan:
            planner_prompt = self._load_system_prompt("planner")
            
            # Get narrative-aware context from EE Memory (simplified version)
            planner_memory = self.agent_memories[AgentName.PLANNER]
            narrative_context = planner_memory.get_context_for_agent(preprocessed_text)
            
            # Also get basic MCP context for fallback
            codebase_context = await self._query_mcp("analyze_codebase", {})
            git_context = await self.get_git_context()
            
            plan_message = f"""Task: {preprocessed_text}

Codebase Context (with Narrative Awareness):
{narrative_context}

Additional Context (from MCP):
{codebase_context}

{git_context}

Create an execution plan with tasks that preserves thematic flows. Use MCP tools (read_file, search_docs, find_references) or RAG tools (rag_search, rag_query) if you need more context.
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

            # 4. REVIEW (mode-dependent)
            review_output = ""

            if self.maker_mode == "low":
                # Low mode: Use Planner reflection (no extra RAM needed)
                yield f"\n[PLANNER REFLECTION] Validating code against plan...\n"
                review_output = await self._planner_reflection(code_output, task_desc, state.plan)
                yield review_output + "\n"
            else:
                # High mode: Use dedicated Reviewer (Qwen 32B)
                reviewer_prompt = self._load_system_prompt("reviewer")

                review_request = f"""Review this code:

{code_output}

Original task: {task_desc}

Run tests and validate code quality.
"""

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
                
                # Phase 3: Extract new skill if learning enabled
                if self.enable_skill_learning and self.skill_extractor:
                    try:
                        new_skill = await self.skill_extractor.extract_skill_from_task(
                            task_id, state, self.redis
                        )
                        if new_skill:
                            yield f"[LEARNING] Extracted new skill: {new_skill.name}\n"
                            # Register in registry
                            if self.skill_registry:
                                self.skill_registry.register_skill(new_skill)
                            # Reload skills in matcher
                            if self.skill_matcher:
                                self.skill_matcher.skill_loader.reload_skill(new_skill.name)
                    except Exception as e:
                        yield f"[LEARNING] Error extracting skill: {e}\n"
                
                # Update skill usage stats (if skills were used)
                if self.enable_skills and self.skill_registry:
                    # Find which skills were used (from Redis usage tracking)
                    for skill_name in self.skill_matcher.skill_loader.get_skill_names():
                        usage_key = f"skills:usage:{skill_name}"
                        if self.redis.exists(usage_key):
                            # Skill was used, update stats
                            self.skill_registry.update_skill_stats(skill_name, success=True)
                
                break
            else:
                yield f"\n Iteration {state.iteration_count}: Feedback to Coder\n"
                
                # Update skill stats for failed iteration (if skills were used)
                if self.enable_skills and self.skill_registry and state.iteration_count >= max_iterations:
                    # Task failed after max iterations
                    for skill_name in self.skill_matcher.skill_loader.get_skill_names():
                        usage_key = f"skills:usage:{skill_name}"
                        if self.redis.exists(usage_key):
                            self.skill_registry.update_skill_stats(skill_name, success=False)
        
        if state.iteration_count >= max_iterations:
            yield f"\n Max iterations ({max_iterations}) reached. Escalating to Planner.\n"
            state.status = "failed"
            state.save_to_redis(self.redis)
            
            # Phase 3: Extract anti-patterns from failed task
            if self.enable_skill_learning and self.skill_extractor:
                try:
                    # Check if worth extracting as anti-pattern
                    if self.skill_extractor.is_skill_worthy(state):
                        new_skill = await self.skill_extractor.extract_skill_from_task(
                            task_id, state, self.redis
                        )
                        if new_skill:
                            yield f"[LEARNING] Extracted anti-pattern skill: {new_skill.name}\n"
                            if self.skill_registry:
                                self.skill_registry.register_skill(new_skill)
                except Exception as e:
                    yield f"[LEARNING] Error extracting anti-pattern: {e}\n"
        
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
    
    async def resume_session(self, session_id: str) -> AsyncGenerator[str, None]:
        """
        Resume a long-running session.
        
        Creates resume context and continues workflow from where it left off.
        
        Args:
            session_id: Session identifier (used as task_id)
        
        Yields:
            Streaming output from workflow
        """
        if not self.enable_long_running:
            yield json.dumps({
                "error": "Long-running support not enabled. Set ENABLE_LONG_RUNNING=true and WORKSPACE_DIR environment variable"
            })
            return
        
        if not self.session_manager:
            yield json.dumps({
                "error": "SessionManager not initialized. Ensure ENABLE_LONG_RUNNING=true and WORKSPACE_DIR is set"
            })
            return
        
        # Create resume context
        resume_context = self.session_manager.create_resume_context()
        
        # Log resumption
        self.progress_tracker.log_progress(f"Resuming session {session_id}")
        
        # Continue workflow with resume context
        async for output in self.orchestrate_workflow(session_id, resume_context):
            yield output
    
    async def checkpoint_session(self, session_id: str, feature_name: str) -> Dict[str, Any]:
        """
        Create a clean checkpoint for a completed feature.
        
        Args:
            session_id: Session identifier (used as task_id)
            feature_name: Name of the feature being checkpointed
        
        Returns:
            Dictionary with checkpoint results
        """
        if not self.enable_long_running:
            return {
                "success": False,
                "error": "Long-running support not enabled. Set ENABLE_LONG_RUNNING=true and WORKSPACE_DIR environment variable"
            }
        
        if not self.checkpoint_manager:
            return {
                "success": False,
                "error": "CheckpointManager not initialized. Ensure ENABLE_LONG_RUNNING=true and WORKSPACE_DIR is set"
            }
        
        # Get code from task state (per spec requirement)
        state = TaskState.load_from_redis(session_id, self.redis)
        if not state:
            return {
                "success": False,
                "error": f"Task state not found for session {session_id}. Task may not exist in Redis."
            }
        
        code = state.code
        if not code:
            return {
                "success": False,
                "error": f"No code found in task state for session {session_id}. Code generation may not have completed."
            }
        
        # Create checkpoint with actual code
        result = await self.checkpoint_manager.create_checkpoint(
            feature_name=feature_name,
            code=code,
            session_id=session_id
        )
        
        return result

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

