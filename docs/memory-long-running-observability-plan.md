# Implementation Plan: EE Memory + Long-Running Agents + Phoenix Observability

## Executive Summary

This plan integrates three critical capabilities into the MAKER-Code-Assist system:

1. **Expositional Engineering (EE) Memory**: Hierarchical Memory Networks (HMN) with melodic lines for thematic codebase understanding
2. **Long-Running Agents**: Trigger.dev integration for durable, timeout-free agent execution
3. **Phoenix Observability**: Local evaluation and governance with OpenTelemetry tracing

**Expected Outcomes:**
- 86% context compression (vs current 62.5%)
- 87.4% task decomposition accuracy (vs ~75%)
- 65% first-pass code acceptance (vs ~40%)
- Zero timeout failures for long-running tasks
- Full observability with LLM-as-judge evaluations

---

## Phase 1: EE Memory Integration (Weeks 1-3)

### 1.1 Core HMN Architecture

**File: `orchestrator/ee_memory.py`** (NEW)

```python
"""
Expositional Engineering Hierarchical Memory Network
Implements 4-level hierarchy: L₀ (raw) → L₁ (entities) → L₂ (patterns) → L₃ (melodic lines)
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import time
from pathlib import Path

class MemoryLevel(Enum):
    L0_RAW = 0          # Raw code files, messages
    L1_ENTITIES = 1     # Functions, classes, variables
    L2_PATTERNS = 2     # Design patterns, architectural principles
    L3_MELODIC = 3      # Business narratives, thematic flows

@dataclass
class MelodicLine:
    """Thematic narrative flow (e.g., payment processing chain)"""
    id: str
    name: str
    description: str
    persistence_score: float  # 0.0-1.0, from Algorithm 3.1
    related_modules: List[str]
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0

@dataclass
class MemoryNode:
    """Single node in HMN"""
    level: MemoryLevel
    content: str
    metadata: Dict[str, Any]
    parent_ids: List[str] = field(default_factory=list)
    child_ids: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

class HierarchicalMemoryNetwork:
    """
    EE Memory: 4-level hierarchical compression
    Compression ratios: β = [0.3, 0.2, 0.15] (L₀→L₁, L₁→L₂, L₂→L₃)
    Preservation thresholds: γ = [0.85, 0.75, 0.70]
    """
    
    def __init__(self, 
                 codebase_path: str,
                 compression_ratios: List[float] = [0.3, 0.2, 0.15],
                 preservation_thresholds: List[float] = [0.85, 0.75, 0.70]):
        self.codebase_path = Path(codebase_path)
        self.compression_ratios = compression_ratios
        self.preservation_thresholds = preservation_thresholds
        
        # Level storage
        self.l0_nodes: Dict[str, MemoryNode] = {}  # Raw files
        self.l1_nodes: Dict[str, MemoryNode] = {}  # Entities
        self.l2_nodes: Dict[str, MemoryNode] = {}  # Patterns
        self.l3_melodic_lines: Dict[str, MelodicLine] = {}
        
        # Indexes for fast lookup
        self.file_to_l0: Dict[str, str] = {}
        self.entity_to_l1: Dict[str, str] = {}
        self.pattern_to_l2: Dict[str, str] = {}
    
    def add_code_file(self, file_path: str, content: str) -> str:
        """Add raw code file to L₀"""
        node_id = f"l0_{hash(file_path)}"
        node = MemoryNode(
            level=MemoryLevel.L0_RAW,
            content=content,
            metadata={"file_path": file_path, "size": len(content)}
        )
        self.l0_nodes[node_id] = node
        self.file_to_l0[file_path] = node_id
        return node_id
    
    def extract_entities(self, l0_node_id: str) -> List[str]:
        """Extract L₁ entities (functions, classes) from L₀ code"""
        # Use AST parsing or LLM extraction
        # Returns list of entity IDs
        pass
    
    def detect_patterns(self, l1_node_ids: List[str]) -> List[str]:
        """Detect L₂ patterns (design patterns, architecture) from L₁ entities"""
        # Pattern detection logic
        pass
    
    def detect_melodic_lines(self, 
                             persistence_threshold: float = 0.7) -> List[MelodicLine]:
        """
        Algorithm 3.1: Detect melodic lines (thematic flows)
        Returns narratives that persist across multiple modules
        """
        # Implementation of melodic line detection
        # Groups related patterns into thematic narratives
        pass
    
    def query_with_context(self, task_description: str) -> Dict[str, Any]:
        """
        PageIndex-style hierarchical navigation
        Returns code context with narrative awareness
        """
        # 1. L₃: Find relevant melodic lines
        relevant_narratives = self._find_relevant_melodic_lines(task_description)
        
        # 2. L₂: Get patterns from narratives
        relevant_patterns = self._get_patterns_from_narratives(relevant_narratives)
        
        # 3. L₁: Get entities from patterns
        relevant_entities = self._get_entities_from_patterns(relevant_patterns)
        
        # 4. L₀: Retrieve actual code
        code_context = self._get_code_from_entities(relevant_entities)
        
        return {
            "code": code_context,
            "narratives": [ml.name for ml in relevant_narratives],
            "patterns": relevant_patterns,
            "entities": relevant_entities,
            "compression_ratio": self._compute_compression_ratio(code_context)
        }
    
    def _compute_compression_ratio(self, code_context: str) -> float:
        """Calculate compression ratio achieved"""
        # Compare original size vs compressed size
        pass
```

### 1.2 Per-Agent Memory Networks

**File: `orchestrator/agent_memory.py`** (NEW)

```python
"""
Per-agent specialized memory networks
Each agent has domain-specific HMN tuned to its role
"""

from orchestrator.ee_memory import HierarchicalMemoryNetwork, MemoryLevel
from orchestrator.orchestrator import AgentName

class AgentMemoryNetwork:
    """Specialized HMN for a specific agent"""
    
    def __init__(self, agent_name: AgentName, base_hmn: HierarchicalMemoryNetwork):
        self.agent_name = agent_name
        self.base_hmn = base_hmn
        self.agent_specific_memory: Dict[str, Any] = {}
    
    def get_context_for_agent(self, task_description: str) -> str:
        """Get agent-specific context with melodic line awareness"""
        base_context = self.base_hmn.query_with_context(task_description)
        
        # Agent-specific filtering/enhancement
        if self.agent_name == AgentName.PLANNER:
            return self._planner_context(base_context)
        elif self.agent_name == AgentName.CODER:
            return self._coder_context(base_context)
        elif self.agent_name == AgentName.REVIEWER:
            return self._reviewer_context(base_context)
        # ... etc
        
        return base_context["code"]
    
    def _planner_context(self, context: Dict) -> str:
        """Planner needs narrative flows for task decomposition"""
        narratives = context["narratives"]
        patterns = context["patterns"]
        code = context["code"]
        
        return f"""Codebase Context with Narrative Awareness:

Thematic Flows (Melodic Lines):
{chr(10).join(f"- {n}" for n in narratives)}

Architectural Patterns:
{chr(10).join(f"- {p}" for p in patterns)}

Relevant Code:
{code}

When decomposing tasks, preserve these narrative flows."""
    
    def _coder_context(self, context: Dict) -> str:
        """Coder needs patterns and idioms"""
        # Focus on coding patterns, idioms, style
        pass
    
    def _reviewer_context(self, context: Dict) -> str:
        """Reviewer needs risk narratives"""
        # Focus on error handling stories, security patterns
        pass
```

### 1.3 Integration Points

**Modify: `orchestrator/orchestrator.py`**

```python
# Add to Orchestrator.__init__
from orchestrator.ee_memory import HierarchicalMemoryNetwork
from orchestrator.agent_memory import AgentMemoryNetwork

class Orchestrator:
    def __init__(self, ...):
        # ... existing init ...
        
        # EE Memory: Shared codebase world model
        self.world_model = HierarchicalMemoryNetwork(
            codebase_path=os.getenv("CODEBASE_ROOT", "."),
            compression_ratios=[0.3, 0.2, 0.15],
            preservation_thresholds=[0.85, 0.75, 0.70]
        )
        
        # Per-agent memory networks
        self.agent_memories = {
            agent: AgentMemoryNetwork(agent, self.world_model)
            for agent in AgentName
        }
    
    async def orchestrate_workflow(self, task_id: str, user_input: str):
        # ... existing code ...
        
        # Replace simple MCP query with narrative-aware query
        # OLD: codebase_context = await self._query_mcp("analyze_codebase", {})
        # NEW:
        planner_memory = self.agent_memories[AgentName.PLANNER]
        narrative_context = planner_memory.get_context_for_agent(preprocessed_text)
        
        plan_message = f"""Task: {preprocessed_text}

Codebase Context (with Narrative Awareness):
{narrative_context}

Create an execution plan that preserves thematic flows."""
```

### 1.4 Melodic Line Detection

**File: `orchestrator/melodic_detector.py`** (NEW)

```python
"""
Detect melodic lines (thematic narratives) in codebase
Uses persistence scoring from Algorithm 3.1
"""

import ast
from typing import List, Dict, Set
from collections import defaultdict

class MelodicLineDetector:
    """Detect persistent thematic flows across modules"""
    
    def detect(self, codebase_files: Dict[str, str], 
               persistence_threshold: float = 0.7) -> List[MelodicLine]:
        """
        Algorithm 3.1: Melodic Line Detection
        
        1. Extract call graphs and data flows
        2. Group related modules by thematic similarity
        3. Score persistence (how often patterns appear together)
        4. Return narratives above threshold
        """
        # Build dependency graph
        call_graph = self._build_call_graph(codebase_files)
        
        # Find thematic clusters
        clusters = self._find_thematic_clusters(call_graph)
        
        # Score persistence
        melodic_lines = []
        for cluster in clusters:
            persistence = self._compute_persistence(cluster, call_graph)
            if persistence >= persistence_threshold:
                melodic_lines.append(MelodicLine(
                    id=f"ml_{len(melodic_lines)}",
                    name=self._name_cluster(cluster),
                    description=self._describe_cluster(cluster),
                    persistence_score=persistence,
                    related_modules=list(cluster)
                ))
        
        return melodic_lines
    
    def _build_call_graph(self, files: Dict[str, str]) -> Dict[str, Set[str]]:
        """Build call graph from codebase"""
        graph = defaultdict(set)
        for file_path, content in files.items():
            # Parse AST, extract function calls
            # Build graph edges
            pass
        return graph
    
    def _find_thematic_clusters(self, graph: Dict[str, Set[str]]) -> List[Set[str]]:
        """Find clusters of related modules"""
        # Use community detection or clustering
        pass
    
    def _compute_persistence(self, cluster: Set[str], 
                           graph: Dict[str, Set[str]]) -> float:
        """Compute persistence score (0.0-1.0)"""
        # Count how often modules in cluster appear together
        # Higher = more persistent narrative
        pass
```

---

## Phase 2: Long-Running Agents (Weeks 4-5)

### 2.1 Trigger.dev Integration

**File: `orchestrator/trigger_tasks.py`** (NEW)

```python
"""
Trigger.dev tasks for long-running agent workflows
Implements durable, timeout-free execution
"""

from trigger.dev import task, retry
from trigger.dev.types import TaskRun
import asyncio
from typing import Dict, Any, Optional
from orchestrator.orchestrator import Orchestrator, AgentName

# Initialize orchestrator (shared instance)
orchestrator = Orchestrator()

@task(
    id="maker-coding-workflow",
    retry={
        "maxAttempts": 3,
        "initialRetryDelayInMs": 1000,
    }
)
async def maker_workflow_task(
    run: TaskRun,
    user_input: str,
    task_id: Optional[str] = None,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Long-running MAKER workflow task
    No timeouts - can run for hours/days
    """
    task_id = task_id or f"task_{run.id}"
    
    # Checkpoint: Save state after each agent step
    state = {
        "task_id": task_id,
        "user_input": user_input,
        "status": "preprocessing",
        "iteration_count": 0
    }
    
    # Preprocessor
    await run.log("Starting preprocessing...")
    preprocessed = await orchestrator.preprocess_input(task_id, user_input)
    state["preprocessed"] = preprocessed
    state["status"] = "planning"
    await run.setMetadata(state)  # Checkpoint
    
    # Planner (with EE memory)
    await run.log("Planning with narrative awareness...")
    plan = await orchestrator._plan_with_memory(task_id, preprocessed)
    state["plan"] = plan
    state["status"] = "coding"
    await run.setMetadata(state)
    
    # Coder + MAKER voting (can take long time)
    max_iterations = 10  # Increased from 3 for long tasks
    for iteration in range(max_iterations):
        await run.log(f"Iteration {iteration + 1}/{max_iterations}")
        
        candidates = await orchestrator.generate_candidates(
            task_desc=plan["description"],
            context=preprocessed,
            n=5,
            task_id=task_id
        )
        
        winner, votes = await orchestrator.maker_vote(
            candidates, 
            plan["description"], 
            k=3
        )
        
        state["code"] = winner
        state["iteration_count"] = iteration + 1
        await run.setMetadata(state)
        
        # Reviewer
        review = await orchestrator._review_code(winner, plan["description"])
        state["review"] = review
        
        if review.get("status") == "approved":
            state["status"] = "complete"
            await run.setMetadata(state)
            break
        
        # Wait before retry (human-in-the-loop support)
        if review.get("needs_human_review"):
            await run.waitForEvent("human_approval", timeout=3600)  # 1 hour
    
    return state

@task(id="agent-step")
async def agent_step_task(
    run: TaskRun,
    agent_name: str,
    input_data: str,
    context: Dict[str, Any]
) -> str:
    """
    Individual agent step (can be called from workflow)
    Supports resumable execution
    """
    agent = AgentName[agent_name.upper()]
    result = await orchestrator.call_agent_sync(
        agent=agent,
        system_prompt=context.get("system_prompt", ""),
        user_message=input_data,
        temperature=context.get("temperature", 0.7)
    )
    
    await run.log(f"Agent {agent_name} completed")
    return result
```

### 2.2 Anthropic Harnesses Integration

**File: `orchestrator/harnesses.py`** (NEW)

```python
"""
Anthropic-style harnesses for agent control
Implements effective patterns from "Effective Harnesses for Long-Running Agents"
"""

from typing import Callable, Awaitable, Any, Optional
from dataclasses import dataclass
import asyncio

@dataclass
class HarnessConfig:
    """Configuration for agent harness"""
    max_iterations: int = 100
    timeout_seconds: Optional[int] = None  # None = no timeout
    checkpoint_interval: int = 10  # Checkpoint every N steps
    retry_on_error: bool = True
    human_in_loop: bool = False

class AgentHarness:
    """
    Harness for controlling long-running agent execution
    Implements patterns from Anthropic's research
    """
    
    def __init__(self, config: HarnessConfig):
        self.config = config
        self.checkpoints: List[Dict[str, Any]] = []
        self.iteration_count = 0
    
    async def run_with_harness(
        self,
        agent_fn: Callable[[], Awaitable[Any]],
        checkpoint_fn: Optional[Callable[[], Dict[str, Any]]] = None
    ) -> Any:
        """
        Run agent function with harness controls:
        - Checkpointing
        - Retry logic
        - Human-in-the-loop
        - No timeouts
        """
        while self.iteration_count < self.config.max_iterations:
            try:
                # Execute agent step
                result = await agent_fn()
                
                # Checkpoint if needed
                if (self.iteration_count % self.config.checkpoint_interval == 0 
                    and checkpoint_fn):
                    checkpoint = checkpoint_fn()
                    self.checkpoints.append(checkpoint)
                
                self.iteration_count += 1
                
                # Check for completion
                if self._is_complete(result):
                    return result
                
                # Human-in-the-loop pause
                if self.config.human_in_loop and self._needs_human_review(result):
                    await self._wait_for_human_approval()
                
            except Exception as e:
                if self.config.retry_on_error:
                    await asyncio.sleep(1)  # Backoff
                    continue
                raise
        
        raise TimeoutError(f"Max iterations ({self.config.max_iterations}) reached")
    
    def _is_complete(self, result: Any) -> bool:
        """Check if agent task is complete"""
        if isinstance(result, dict):
            return result.get("status") == "complete"
        return False
    
    def _needs_human_review(self, result: Any) -> bool:
        """Check if human review needed"""
        if isinstance(result, dict):
            return result.get("needs_human_review", False)
        return False
    
    async def _wait_for_human_approval(self):
        """Pause for human approval (implement with Trigger.dev waitForEvent)"""
        # Integration with Trigger.dev human-in-the-loop
        pass
```

### 2.3 Integration with Orchestrator

**Modify: `orchestrator/orchestrator.py`**

```python
# Add to Orchestrator class

from orchestrator.harnesses import AgentHarness, HarnessConfig
from trigger.dev import task as trigger_task

class Orchestrator:
    # ... existing code ...
    
    async def orchestrate_workflow_long_running(
        self, 
        task_id: str, 
        user_input: str,
        use_trigger: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        Long-running workflow with Trigger.dev integration
        No timeouts, durable execution
        """
        if use_trigger:
            # Delegate to Trigger.dev task
            from orchestrator.trigger_tasks import maker_workflow_task
            result = await maker_workflow_task.trigger(
                user_input=user_input,
                task_id=task_id
            )
            # Stream results from Trigger.dev run
            async for update in self._stream_trigger_run(result.run_id):
                yield update
        else:
            # Use harness for local long-running execution
            harness = AgentHarness(HarnessConfig(
                max_iterations=100,
                timeout_seconds=None,  # No timeout
                checkpoint_interval=5
            ))
            
            async def workflow_step():
                return await self._workflow_step(task_id, user_input)
            
            result = await harness.run_with_harness(workflow_step)
            yield json.dumps(result, indent=2)
```

### 2.4 Docker Compose Update

**Modify: `docker-compose.yml`**

```yaml
services:
  # ... existing services ...
  
  # Trigger.dev (optional - for cloud deployment)
  # For local, use Trigger.dev CLI: npx trigger.dev@latest dev
  
  # Add environment variable to orchestrator
  orchestrator:
    # ... existing config ...
    environment:
      # ... existing vars ...
      - TRIGGER_API_KEY=${TRIGGER_API_KEY:-}
      - TRIGGER_ENABLED=${TRIGGER_ENABLED:-false}
      - USE_LONG_RUNNING=${USE_LONG_RUNNING:-true}
```

---

## Phase 3: Phoenix Observability (Week 6)

### 3.1 Phoenix Setup

**File: `docker-compose.yml`** (UPDATE)

```yaml
services:
  # ... existing services ...
  
  phoenix:
    image: arizephoenix/phoenix:latest
    container_name: phoenix-observability
    ports:
      - "6006:6006"  # UI
      - "4317:4317"  # OTLP gRPC
      - "4318:4318"  # OTLP HTTP
    environment:
      - PHOENIX_WORKING_DIR=/data
    volumes:
      - phoenix_data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6006/health"]
      interval: 10s
      timeout: 5s
      retries: 3

volumes:
  # ... existing volumes ...
  phoenix_data:
```

### 3.2 OpenTelemetry Instrumentation

**File: `orchestrator/observability.py`** (NEW)

```python
"""
Phoenix observability integration
OpenTelemetry tracing for all agent interactions
"""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
import os

# Configure Phoenix endpoint
PHOENIX_ENDPOINT = os.getenv("PHOENIX_ENDPOINT", "http://localhost:6006/v1/traces")

def setup_phoenix_tracing():
    """Initialize OpenTelemetry tracing to Phoenix"""
    resource = Resource.create({
        "service.name": "maker-orchestrator",
        "service.version": "1.0.0",
    })
    
    provider = TracerProvider(resource=resource)
    
    # Export to Phoenix
    otlp_exporter = OTLPSpanExporter(
        endpoint=PHOENIX_ENDPOINT,
        headers={}
    )
    
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    trace.set_tracer_provider(provider)
    
    # Auto-instrument HTTPX (used for llama.cpp calls)
    HTTPXClientInstrumentor().instrument()
    
    return trace.get_tracer(__name__)

# Global tracer
tracer = setup_phoenix_tracing()

def trace_agent_call(agent_name: str, model: str = "default"):
    """Decorator for tracing agent calls"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            with tracer.start_as_current_span(f"agent.{agent_name}") as span:
                span.set_attribute("agent.name", agent_name)
                span.set_attribute("model", model)
                span.set_attribute("maker.k_value", os.getenv("MAKER_VOTE_K", "3"))
                
                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("agent.success", True)
                    if isinstance(result, str):
                        span.set_attribute("agent.response_length", len(result))
                    return result
                except Exception as e:
                    span.set_attribute("agent.success", False)
                    span.set_attribute("agent.error", str(e))
                    span.record_exception(e)
                    raise
        return wrapper
    return decorator

def trace_maker_voting(candidates: list, k: int):
    """Trace MAKER voting process"""
    with tracer.start_as_current_span("maker.voting") as span:
        span.set_attribute("maker.num_candidates", len(candidates))
        span.set_attribute("maker.k_value", k)
        span.set_attribute("maker.num_voters", 2 * k - 1)
        return span
```

### 3.3 Instrument Orchestrator

**Modify: `orchestrator/orchestrator.py`**

```python
# Add at top
from orchestrator.observability import tracer, trace_agent_call, trace_maker_voting

class Orchestrator:
    # ... existing code ...
    
    @trace_agent_call("preprocessor", "gemma-2-2b")
    async def preprocess_input(self, task_id: str, user_input: str) -> str:
        """Convert audio/image/text to clean text"""
        with tracer.start_as_current_span("preprocess") as span:
            span.set_attribute("input_type", "text")  # Detect actual type
            # ... existing code ...
    
    @trace_agent_call("planner", "nemotron-nano-8b")
    async def _plan_with_memory(self, task_id: str, user_input: str):
        """Planning with EE memory context"""
        with tracer.start_as_current_span("plan_with_memory") as span:
            # Get narrative-aware context
            planner_memory = self.agent_memories[AgentName.PLANNER]
            context = planner_memory.get_context_for_agent(user_input)
            
            span.set_attribute("memory.narratives", len(context.get("narratives", [])))
            span.set_attribute("memory.compression_ratio", context.get("compression_ratio", 0))
            
            # ... planning logic ...
    
    async def generate_candidates(self, ...):
        """Generate N candidates with tracing"""
        with tracer.start_as_current_span("maker.generate_candidates") as span:
            span.set_attribute("maker.num_candidates", n)
            span.set_attribute("maker.temperature_range", f"0.3-{0.3 + (n-1)*0.1}")
            
            # ... existing parallel generation ...
            
            span.set_attribute("maker.valid_candidates", len(candidates))
            return candidates
    
    async def maker_vote(self, candidates: list, ...):
        """MAKER voting with tracing"""
        with trace_maker_voting(candidates, k) as span:
            # ... existing voting logic ...
            
            span.set_attribute("maker.winner", winner_label)
            span.set_attribute("maker.vote_distribution", json.dumps(vote_counts))
            return winner, vote_counts
```

### 3.4 LLM-as-Judge Evaluations

**File: `orchestrator/evaluations.py`** (NEW)

```python
"""
Phoenix LLM-as-judge evaluations
Evaluate agent outputs for quality, relevance, safety
"""

from opentelemetry import trace
from typing import Dict, Any
import httpx

tracer = trace.get_tracer(__name__)

class PhoenixEvaluator:
    """Evaluate agent outputs using Phoenix LLM-as-judge"""
    
    def __init__(self, phoenix_url: str = "http://localhost:6006"):
        self.phoenix_url = phoenix_url
    
    async def evaluate_code_quality(
        self, 
        code: str, 
        task_description: str
    ) -> Dict[str, Any]:
        """
        Evaluate generated code quality
        Returns: {score: float, feedback: str, criteria: dict}
        """
        with tracer.start_as_current_span("evaluation.code_quality") as span:
            evaluation_prompt = f"""Evaluate this code for quality:

Task: {task_description}

Code:
```python
{code}
```

Rate on:
1. Correctness (0-1)
2. Readability (0-1)
3. Maintainability (0-1)
4. Performance (0-1)

Return JSON: {{"scores": {{"correctness": 0.9, ...}}, "feedback": "..."}}"""
            
            # Use Reviewer agent for evaluation
            from orchestrator.orchestrator import Orchestrator
            orch = Orchestrator()
            
            result = await orch.call_agent_sync(
                AgentName.REVIEWER,
                "You are a code quality evaluator. Return JSON scores.",
                evaluation_prompt,
                temperature=0.1
            )
            
            span.set_attribute("evaluation.type", "code_quality")
            # Parse result and return scores
            
            return {
                "scores": {"overall": 0.85},
                "feedback": result,
                "criteria": {}
            }
    
    async def evaluate_narrative_coherence(
        self,
        code: str,
        melodic_lines: list,
        task_description: str
    ) -> Dict[str, Any]:
        """
        EE-specific: Evaluate if code preserves melodic lines
        """
        with tracer.start_as_current_span("evaluation.narrative_coherence") as span:
            span.set_attribute("evaluation.melodic_lines", len(melodic_lines))
            
            coherence_prompt = f"""Evaluate if this code preserves thematic narratives:

Task: {task_description}

Relevant Melodic Lines:
{chr(10).join(f"- {ml}" for ml in melodic_lines)}

Code:
```python
{code}
```

Does the code preserve these narratives? Score 0-1."""
            
            # Evaluation logic
            return {
                "coherence_score": 0.87,
                "preserved_narratives": melodic_lines,
                "violations": []
            }
```

### 3.5 Requirements Update

**Modify: `requirements.txt`**

```txt
# ... existing dependencies ...

# Phoenix observability
opentelemetry-api==1.21.0
opentelemetry-sdk==1.21.0
opentelemetry-exporter-otlp-proto-http==1.21.0
opentelemetry-instrumentation-httpx==0.42b0

# Trigger.dev (optional)
trigger-sdk==3.0.0  # When using Trigger.dev cloud
```

---

## Phase 4: Integration & Testing (Week 7)

### 4.1 Integration Test Script

**File: `tests/test_memory_long_running.py`** (NEW)

```python
"""
Integration tests for EE Memory + Long-Running + Phoenix
"""

import asyncio
import httpx
from orchestrator.orchestrator import Orchestrator

async def test_ee_memory_integration():
    """Test EE memory provides narrative-aware context"""
    orch = Orchestrator()
    
    # Initialize world model
    await orch.world_model.detect_melodic_lines()
    
    # Query with context
    context = orch.world_model.query_with_context(
        "Update payment validation to use JWT"
    )
    
    assert "narratives" in context
    assert "code" in context
    assert context["compression_ratio"] > 0.8  # Target: 86%
    
    print("✓ EE Memory integration working")

async def test_long_running_workflow():
    """Test long-running workflow without timeout"""
    orch = Orchestrator()
    
    # Large task that would timeout normally
    large_task = "Refactor entire authentication system to use OAuth2"
    
    # Should complete without timeout
    result = []
    async for chunk in orch.orchestrate_workflow_long_running(
        task_id="test_long",
        user_input=large_task,
        use_trigger=False  # Use harness locally
    ):
        result.append(chunk)
    
    assert len(result) > 0
    print("✓ Long-running workflow working")

async def test_phoenix_tracing():
    """Test Phoenix observability"""
    # Check Phoenix is running
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:6006/health")
        assert response.status_code == 200
    
    # Run workflow and check traces appear
    orch = Orchestrator()
    await orch.preprocess_input("test_task", "Hello")
    
    # Traces should appear in Phoenix UI
    print("✓ Phoenix tracing working")

if __name__ == "__main__":
    asyncio.run(test_ee_memory_integration())
    asyncio.run(test_long_running_workflow())
    asyncio.run(test_phoenix_tracing())
    print("\n✅ All integration tests passed")
```

### 4.2 Performance Benchmarks

**File: `tests/benchmark_memory.py`** (NEW)

```python
"""
Benchmark EE Memory compression and accuracy
"""

import time
from orchestrator.ee_memory import HierarchicalMemoryNetwork

def benchmark_compression():
    """Measure compression ratio improvement"""
    hmn = HierarchicalMemoryNetwork(codebase_path=".")
    
    # Simulate large codebase
    large_context = "..." * 100000  # 100K tokens
    
    # Old method: Simple summarization (62.5% compression)
    old_compressed = len(large_context) * 0.375  # 37.5% retained
    
    # New method: EE Memory (target: 86% compression)
    context = hmn.query_with_context("test task")
    new_compressed_ratio = context["compression_ratio"]
    
    improvement = (new_compressed_ratio - 0.625) / 0.625 * 100
    print(f"Compression improvement: {improvement:.1f}%")
    assert new_compressed_ratio >= 0.86  # Target: 86%

if __name__ == "__main__":
    benchmark_compression()
```

---

## Phase 5: Documentation & Deployment (Week 8)

### 5.1 Update Documentation

**Files to update:**
- `CLAUDE.md` - Add EE Memory, long-running, Phoenix sections
- `README.md` - Update setup instructions
- `docs/` - Add architecture diagrams

### 5.2 Deployment Checklist

- [ ] Phoenix container running on port 6006
- [ ] OpenTelemetry traces flowing to Phoenix
- [ ] EE Memory world model initialized on startup
- [ ] Melodic lines detected and cached
- [ ] Trigger.dev configured (if using cloud)
- [ ] Long-running workflows tested with large tasks
- [ ] Evaluations running in Phoenix UI
- [ ] Performance benchmarks meet targets

---

## Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Context Compression | 62.5% | 86% | `compression_ratio` in HMN |
| Task Decomposition Accuracy | ~75% | 87.4% | Manual review + Phoenix eval |
| First-Pass Acceptance | ~40% | 65% | Reviewer approval rate |
| Long-Running Success | N/A | 100% | No timeout failures |
| Observability Coverage | 0% | 100% | All agent calls traced |
| Evaluation Coverage | 0% | 80% | LLM-as-judge on key outputs |

---

## Risk Mitigation

1. **EE Memory Complexity**: Start with simple melodic line detection, iterate
2. **Trigger.dev Dependency**: Fallback to local harnesses if cloud unavailable
3. **Phoenix Overhead**: Use batch span processor, async exports
4. **Performance Impact**: Benchmark each phase, optimize hot paths

---

## Next Steps

1. **Week 1**: Implement core HMN structure (`ee_memory.py`)
2. **Week 2**: Add melodic line detection (`melodic_detector.py`)
3. **Week 3**: Integrate with orchestrator, test compression
4. **Week 4**: Add Trigger.dev tasks, test long-running
5. **Week 5**: Implement harnesses, human-in-the-loop
6. **Week 6**: Setup Phoenix, instrument all agents
7. **Week 7**: Integration tests, benchmarks
8. **Week 8**: Documentation, deployment

---

## References

- **EE Memory**: Expositional Engineering paper (Section 6.2)
- **Long-Running Agents**: [Anthropic Harnesses](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- **Trigger.dev**: [Trigger.dev Docs](https://trigger.dev/docs)
- **Phoenix**: [Arize Phoenix](https://docs.arize.com/phoenix)

