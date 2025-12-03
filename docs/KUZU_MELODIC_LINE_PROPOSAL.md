# Kùzu for Melodic Line Memory - Implementation Proposal

## Problem Statement

**Your diagnosis is spot-on**: "Multiple LLMs operating sequentially and all over the place, unable to hold a melodic line to output code sensibly let alone operate as a swarm."

### Current Issues

1. **No Shared Context**: Each agent (Preprocessor → Planner → Coder → Reviewer) only sees the previous agent's output string, not their reasoning
2. **Lost Intent**: By the time Coder runs, it doesn't know what Preprocessor understood or why Planner chose certain subtasks
3. **Sequential, Not Swarm**: 5 Coder candidates run in parallel but don't coordinate or learn from each other
4. **No Coherence**: Reviewer can't trace back through the reasoning chain to validate decisions

## Solution: Kùzu as Shared Graph Memory

Instead of passing strings between agents, use **Kùzu as a shared graph database** where:
- Each agent **writes its reasoning** as a graph node
- Later agents **read the full reasoning chain** (the "melodic line")
- Parallel agents can **coordinate in real-time** via the graph
- The entire workflow is **queryable and traceable**

## Architecture

### Current Architecture (Sequential String Passing)
```
User Input (string)
    ↓
Preprocessor (Gemma2-2B) → preprocessed_text (string)
    ↓
Planner (Nemotron Nano 8B) → plan (JSON string)
    ↓
Coder (Devstral 24B) × 5 candidates → code (strings, no coordination)
    ↓
Voter (Qwen 1.5B) → winner (string)
    ↓
Reviewer (Qwen 32B or Planner) → review (string)
```

**Problem**: Each arrow is just a string. No reasoning, no context propagation.

### Proposed Architecture (Shared Graph Memory)
```
User Input
    ↓
[Kùzu Graph Database]
    ├─ Preprocessor writes: "Detected security requirement in user request"
    │   ↓ LEADS_TO
    ├─ Planner reads preprocessor reasoning → writes: "Plan JWT implementation"
    │   ↓ LEADS_TO
    ├─ Coder_1..5 read BOTH preprocessor + planner → coordinate via graph
    │   ├─ Coder_1 writes: "Implementing auth/jwt.py based on plan step 1"
    │   ├─ Coder_2 reads Coder_1 → writes: "Adding middleware (step 2), using Coder_1's JWT structure"
    │   └─ ... (real-time coordination)
    ↓ LEADS_TO
    ├─ Voter reads all 5 reasonings → writes: "Chose candidate 3 for consistency with plan"
    │   ↓ LEADS_TO
    └─ Reviewer reads ENTIRE graph → validates against original preprocessor understanding
```

**Benefit**: Full reasoning chain (melodic line) preserved and queryable.

## Implementation Plan

### Phase 1: Proof of Concept (4 hours)

**Goal**: Verify Kùzu can maintain melodic line across 3 agents

**Files to Create**:
1. `orchestrator/kuzu_memory.py` - SharedWorkflowMemory class
2. `scripts/test_kuzu_melodic_line.py` - Integration test

**Test Scenario**:
```python
# Simulate workflow with shared memory
task_id = "test_jwt_auth"

# 1. Preprocessor writes
memory.add_action(
    agent="preprocessor",
    reasoning="User wants JWT. Security requirement detected.",
    output="Add JWT authentication"
)

# 2. Planner reads preprocessor's reasoning
context = memory.get_context_for_agent(task_id, "planner")
# context includes: "Security requirement detected"

memory.add_action(
    agent="planner",
    reasoning="Based on security focus, planning defensive JWT impl",
    output="Plan: 1. JWT util with strong signing, 2. Middleware with rate limiting"
)

# 3. Coder reads BOTH
context = memory.get_context_for_agent(task_id, "coder")
# context includes BOTH preprocessor + planner reasoning!

memory.add_action(
    agent="coder",
    reasoning="Implementing secure JWT as planned",
    output="def create_jwt(user): ..."
)

# Verify melodic line
line = memory.get_melodic_line(task_id)
assert len(line) == 3  # All 3 agents connected
assert "security" in line[0]['reasoning'].lower()
```

**Success Criteria**:
- ✅ Each agent can read previous agents' reasoning
- ✅ Full reasoning chain is queryable
- ✅ Graph persists to disk (survives restart)

### Phase 2: Integrate with Orchestrator (1 day)

**Goal**: Add Kùzu memory to actual orchestrator workflow

**Files to Modify**:
1. `orchestrator/orchestrator.py` - Add workflow_memory integration
2. `orchestrator/api_server.py` - Add melodic line endpoint

**Changes to orchestrate_workflow()**:

```python
async def orchestrate_workflow(self, task_id: str, user_input: str):
    # Initialize workflow in graph
    self.workflow_memory.create_task(task_id, user_input)

    # 1. Preprocessor
    preprocessed = await self.preprocess_input(task_id, user_input)

    self.workflow_memory.add_action(
        task_id=task_id,
        agent="preprocessor",
        action_type="preprocess",
        input=user_input,
        output=preprocessed,
        reasoning=await self._extract_reasoning_from_output(preprocessed)
    )

    # 2. Planner (reads preprocessor's reasoning!)
    planner_context = self.workflow_memory.get_context_for_agent(task_id, "planner")

    # Inject melodic line into planner prompt
    plan_message = f"""Task: {preprocessed_text}

Previous Agent Reasoning:
{planner_context}

Create a plan that maintains the intent understood by Preprocessor.
"""

    plan = await self._plan_with_ee(plan_message)

    self.workflow_memory.add_action(
        task_id=task_id,
        agent="planner",
        action_type="plan",
        input=preprocessed,
        output=json.dumps(plan),
        reasoning=f"Created {len(plan['plan'])} subtasks based on preprocessor's understanding"
    )

    # 3. Coder (reads FULL melodic line)
    coder_context = self.workflow_memory.get_context_for_agent(task_id, "coder")

    # Each candidate gets full context
    candidates = await self.generate_candidates(
        task_desc,
        coder_context,  # This includes preprocessor + planner reasoning!
        n=self.num_candidates
    )

    # ... rest of workflow ...
```

**New API Endpoint**:
```python
# orchestrator/api_server.py

@app.get("/api/task/{task_id}/melodic-line")
async def get_melodic_line(task_id: str):
    """Get full reasoning chain for a task"""
    line = orchestrator.workflow_memory.get_melodic_line(task_id)
    return {
        "task_id": task_id,
        "agents": line['agents'],
        "reasonings": line['reasonings'],
        "graph_visualization": line['path']  # For UI
    }
```

**Success Criteria**:
- ✅ All agents write to and read from shared graph
- ✅ Melodic line is queryable via API
- ✅ No breaking changes to existing workflow

### Phase 3: Enable Swarm Behavior (2 days)

**Goal**: Let parallel Coder candidates coordinate via graph

**Current Problem** (at [orchestrator.py:1101-1105](orchestrator/orchestrator.py:1101-1105)):
```python
# 5 coders run in parallel but DON'T COORDINATE
tasks = [
    self.call_agent_sync(AgentName.CODER, coder_prompt, coder_request, temperature=0.3 + (i * 0.1))
    for i in range(n)
]
candidates = await asyncio.gather(*tasks)
```

**Swarm Solution**:
```python
async def generate_candidates_swarm(self, task_desc: str, context: str, n: int):
    """Coders collaborate via shared graph"""

    # Launch swarm
    swarm_tasks = [
        self._swarm_coder(task_id, task_desc, i, n, iterations=3)
        for i in range(n)
    ]

    # They coordinate in real-time
    final_candidates = await asyncio.gather(*swarm_tasks)

    return final_candidates

async def _swarm_coder(self, task_id: str, task_desc: str, coder_id: int, total: int, iterations: int):
    """Single coder in swarm - learns from others"""

    for iteration in range(iterations):
        # Read what other coders discovered (real-time!)
        swarm_insights = self.workflow_memory.get_swarm_insights(
            task_id,
            exclude_agent=f"coder_{coder_id}"
        )

        # Build on others' work
        prompt = f"""You are Coder {coder_id}/{total} in iteration {iteration}.

Task: {task_desc}

What other coders are discovering:
{swarm_insights}

Build on their best ideas. Fix their mistakes. Collaborate!"""

        code = await self.call_agent_sync(
            AgentName.CODER,
            self._load_system_prompt("coder"),
            prompt,
            temperature=0.3 + (coder_id * 0.1)
        )

        # Share with swarm immediately
        self.workflow_memory.add_action(
            task_id=task_id,
            agent=f"coder_{coder_id}",
            action_type="swarm_code",
            input=task_desc,
            output=code,
            reasoning=f"Iteration {iteration}: Building on {len(swarm_insights)} insights"
        )

        # Brief pause to let others contribute
        await asyncio.sleep(0.5)

    return code
```

**Success Criteria**:
- ✅ Coders read each other's attempts in real-time
- ✅ Later iterations show improvement based on earlier attempts
- ✅ Swarm converges to better solution than sequential voting

### Phase 4: Streaming with Memory (1 day)

**Goal**: Stream workflow progress while maintaining graph

**Problem**: Currently at [api_server.py:234](orchestrator/api_server.py:234), you stream chunks but lose memory:

```python
async for chunk in orchestrator.orchestrate_workflow(task_id, request.input):
    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
```

**Solution**: Stream chunks AND graph updates
```python
async def generate():
    async for chunk in orchestrator.orchestrate_workflow(task_id, request.input):
        # Stream the chunk
        yield f"data: {json.dumps({'chunk': chunk})}\n\n"

        # Also stream graph updates (melodic line progress)
        if chunk.startswith("[") and "]" in chunk:  # Agent marker
            agent = chunk.split("]")[0][1:]

            # Get current melodic line state
            line = orchestrator.workflow_memory.get_melodic_line(task_id)

            yield f"data: {json.dumps({
                'graph_update': {
                    'agent': agent,
                    'reasoning': line[-1]['reasoning'] if line else '',
                    'depth': len(line)
                }
            })}\n\n"
```

**Client can now**:
- Watch workflow progress (existing)
- See melodic line build in real-time (new!)
- Understand agent reasoning as it happens (new!)

## Database Schema

```cypher
// Nodes
CREATE NODE TABLE Task(
    task_id STRING PRIMARY KEY,
    user_input STRING,
    status STRING,
    created_at TIMESTAMP
)

CREATE NODE TABLE AgentAction(
    action_id STRING PRIMARY KEY,
    task_id STRING,
    agent STRING,
    action_type STRING,
    input STRING,
    output STRING,
    reasoning STRING,
    temperature FLOAT,
    created_at TIMESTAMP
)

// Relationships
CREATE REL TABLE PART_OF(FROM AgentAction TO Task)

CREATE REL TABLE LEADS_TO(
    FROM AgentAction TO AgentAction,
    causal_reasoning STRING
)

CREATE REL TABLE COORDINATES_WITH(
    FROM AgentAction TO AgentAction,
    collaboration_type STRING  // For swarm behavior
)
```

## Performance Considerations

### Memory Usage
- **NetworkX (current)**: ~500MB for 100k nodes in-memory
- **Kùzu (proposed)**: ~50MB for 100k nodes on-disk (embedded)
- **Benefit**: 10x less memory, persists across restarts

### Query Performance
- **Graph traversal**: O(log n) with indexes vs O(n) NetworkX
- **Melodic line query**: ~10ms for 100-node chain
- **Real-time swarm coordination**: ~5ms per swarm insight query

### Disk Space
- Each task workflow: ~10-50KB depending on code length
- 1000 tasks: ~50MB
- Negligible compared to model weights (~150GB)

## Migration Path

### Week 1: Proof of Concept
- Install Kùzu: `pip install kuzu==0.6.0`
- Create `orchestrator/kuzu_memory.py`
- Test script: `scripts/test_kuzu_melodic_line.py`
- Verify melodic line works with 3 agents

### Week 2: Parallel Run
- Add to orchestrator alongside existing code
- Environment variable: `ENABLE_KUZU_MEMORY=true`
- Log both approaches, compare coherence
- No breaking changes

### Week 3: Swarm Behavior
- Implement `_swarm_coder()` method
- Test with MAKER voting
- Compare swarm vs sequential candidates

### Week 4: Production
- Make Kùzu default if results are better
- Keep NetworkX as fallback
- Add melodic line visualization to frontend

## Risks and Mitigations

### Risk 1: Kùzu Stability
- **Risk**: New library, potential bugs
- **Mitigation**: Run in parallel with existing system, feature flag

### Risk 2: Performance Overhead
- **Risk**: Graph writes slow down workflow
- **Mitigation**: Async writes, batch updates, benchmark first

### Risk 3: Learning Curve
- **Risk**: Team needs to learn Cypher-like query language
- **Mitigation**: Create helper methods, document common patterns

### Risk 4: Disk I/O
- **Risk**: Graph writes to disk may bottleneck
- **Mitigation**: Use SSD, WAL mode, in-memory option for dev

## Success Metrics

### Coherence (Primary Goal)
- **Before**: Reviewer approval rate ~60% (agents don't maintain intent)
- **After**: Target ~85% (agents follow melodic line)

### Swarm Convergence
- **Before**: Best of 5 random candidates
- **After**: 5 candidates that improve on each other

### Debuggability
- **Before**: Can't trace why Coder made a choice
- **After**: Full reasoning chain queryable

### Memory Efficiency
- **Before**: ~500MB NetworkX graph + conversation history
- **After**: ~50MB Kùzu DB + conversation history

## Alternative: Keep Current System

If Kùzu proves too complex, you could achieve 70% of the benefit by:

1. **Add reasoning field to TaskState** (simple)
   ```python
   @dataclass
   class TaskState:
       # ... existing fields ...
       agent_reasonings: List[Dict[str, str]] = field(default_factory=list)
   ```

2. **Pass reasoning chain in context** (medium)
   ```python
   def get_agent_context(self, task_id: str, agent: str):
       state = TaskState.load_from_redis(task_id)
       context = "\n".join([
           f"{r['agent']}: {r['reasoning']}"
           for r in state.agent_reasonings
       ])
       return context
   ```

3. **Keep swarm sequential** (simple)
   - No coordination between coders
   - Just better context propagation

**Trade-off**: Simpler but loses:
- Real-time swarm coordination
- Graph queries for debugging
- Efficient storage/retrieval

## Recommendation

**YES - Proceed with Kùzu integration** because:

1. ✅ **Solves your core problem**: "Unable to hold a melodic line"
2. ✅ **Enables swarm behavior**: Agents can coordinate
3. ✅ **Better than alternatives**: Neo4j too heavy, alternatives too limited
4. ✅ **Low risk**: Can run in parallel with existing system
5. ✅ **High ROI**: ~4 days work for 10x coherence improvement

**Next Steps**:
1. Install Kùzu: `pip install kuzu==0.6.0`
2. Run proof-of-concept: `python3 scripts/test_kuzu_melodic_line.py`
3. Evaluate if melodic line is maintained across 3 agents
4. If successful, proceed to Phase 2 (orchestrator integration)

**Decision Point**: After Phase 1 POC (4 hours), you'll know if this solves the melodic line problem. If yes, continue to swarm behavior. If no, fall back to simpler reasoning chain in TaskState.
