# Collective Brain: Multi-Agent Consensus

## Overview

The Collective Brain enables multi-agent consensus for complex decisions. Instead of relying on a single agent, multiple agents are consulted and their perspectives are synthesized into a comprehensive answer.

## When to Use

The Collective Brain is automatically triggered for:

- **Architecture decisions**: "Should we use Redis or PostgreSQL?"
- **Debugging complex issues**: "Why is this failing?"
- **Unclear requirements**: "What does the user really want?"
- **Code review disagreements**: "Is this approach correct?"
- **"Should I do X or Y?" questions**: Strategic choices

## Expert Panels

Different problem types consult different expert panels:

### Architecture (`architecture`)

**Panel**: Planner + Coder + Reviewer

**Why**: All three perspectives needed
- Planner: Strategic/architectural view
- Coder: Implementation feasibility
- Reviewer: Quality/security concerns

**Example**: "Should we refactor to microservices?"

### Debugging (`debugging`)

**Panel**: Coder + Reviewer

**Why**: Technical expertise from both
- Coder: Code understanding, implementation knowledge
- Reviewer: Quality assurance, edge cases

**Example**: "Why is authentication failing?"

### Planning (`planning`)

**Panel**: Preprocessor + Planner

**Why**: Understanding + strategy
- Preprocessor: Intent detection, what user really wants
- Planner: Strategic breakdown, dependencies

**Example**: "How should we implement this feature?"

### Understanding (`understanding`)

**Panel**: Preprocessor + Planner + Coder

**Why**: All perspectives
- Preprocessor: Content understanding
- Planner: Strategic context
- Coder: Technical context

**Example**: "What does this codebase do?"

### Security (`security`)

**Panel**: Reviewer + Coder

**Why**: Audit + implementation
- Reviewer: Security audit, vulnerabilities
- Coder: Implementation knowledge, constraints

**Example**: "Is this authentication secure?"

## How It Works

### 1. Question Classification

The orchestrator detects complex questions and determines problem type:

```python
# Detect complex question
if is_complex_question(user_input):
    problem_type = classify_problem_type(user_input)
    # architecture, debugging, planning, understanding, security
```

### 2. Parallel Agent Consultation

All agents in the expert panel are consulted simultaneously:

```python
# Ask all agents in parallel
perspectives = await asyncio.gather(*[
    collective_brain._ask_agent(agent, problem, context, user_question)
    for agent in expert_panel
])
```

### 3. Per-Agent Prompts

Each agent receives a prompt tailored to their strengths:

**Preprocessor**:
```
Your strength is UNDERSTANDING and INTENT DETECTION.
What does the user REALLY want? What's the core issue?
```

**Planner**:
```
Your strength is STRATEGIC THINKING and DEPENDENCIES.
From a strategic/architectural perspective, what's the best approach?
```

**Coder**:
```
Your strength is CODE UNDERSTANDING and IMPLEMENTATION.
From a code implementation perspective, what's the solution?
```

**Reviewer**:
```
Your strength is QUALITY ASSURANCE and SECURITY.
From a quality/security perspective, what should we watch out for?
```

### 4. Synthesis

Planner (best at strategic thinking) synthesizes all perspectives:

```python
synthesis_prompt = f"""
You are synthesizing multiple agent perspectives into a clear answer.

User's question: {user_question}

Different agents analyzed this from their expertise:

{perspectives_text}

Your task: Synthesize these perspectives into ONE clear, actionable answer.
- Combine complementary insights
- Resolve contradictions (favor higher confidence)
- Give direct answer to user's question
"""
```

### 5. Output Format

**Consensus**: Synthesized answer (2-3 sentences)

**Individual Perspectives**: Each agent's view with confidence

**Dissenting Opinions**: Important disagreements flagged

**Confidence Score**: Overall confidence (0-1) based on agent agreement

## Example Output

**Question**: "Should we use async/await for this API?"

**Response**:
```
[COLLECTIVE BRAIN] Consulting multiple agents...

**Consensus**: Yes, use async/await. The API makes multiple I/O calls (database, external APIs), and async will improve throughput. However, ensure all dependencies support async.

**Agent Perspectives**:
- PLANNER (Nemotron Nano 8B): Async/await fits this use case - multiple I/O operations benefit from concurrent execution. (Confidence: 85%)
- CODER (Devstral 24B): Implementation is straightforward - httpx and redis both support async. Just need to update function signatures. (Confidence: 90%)
- REVIEWER (Qwen 32B): Async is good, but watch for error handling - async exceptions need proper await chains. (Confidence: 80%)

⚠️ REVIEWER has concerns: Ensure async error handling is properly implemented with await chains.
```

## Implementation

### File: `orchestrator/collective_brain.py`

**Key Classes**:
- `CollectiveBrain`: Main consensus system
- `AgentPerspective`: Individual agent's view

**Key Methods**:
- `consult_collective()`: Main entry point
- `_ask_agent()`: Query individual agent
- `_synthesize_perspectives()`: Combine views
- `_find_dissent()`: Detect disagreements
- `_calculate_confidence()`: Overall confidence score

### Integration: `orchestrator/orchestrator.py`

**Location**: Lines 1749-1800

**Trigger**: Complex questions detected in `_answer_question()`

**Flow**:
1. Detect complex question
2. Initialize CollectiveBrain (if melodic memory enabled)
3. Consult expert panel
4. Stream consensus + perspectives to user

## Configuration

### Prerequisites

- **Kùzu melodic memory enabled**: `ENABLE_MELODIC_MEMORY=true`
- **Kùzu database path**: `KUZU_DB_PATH=/app/kuzu_workflow_db`
- **Docker volumes**: Kùzu database volumes mounted

### Environment Variables

```bash
# Enable melodic memory (required for collective brain)
ENABLE_MELODIC_MEMORY=true

# Kùzu database path
KUZU_DB_PATH=/app/kuzu_workflow_db
```

### Docker Configuration

```yaml
orchestrator-high:
  environment:
    - ENABLE_MELODIC_MEMORY=true
    - KUZU_DB_PATH=/app/kuzu_workflow_db
  volumes:
    - kuzu_workflow_db_high:/app/kuzu_workflow_db
```

## Benefits

1. **Multiple Perspectives**: Different models see problems differently
2. **Higher Confidence**: Consensus from multiple agents
3. **Comprehensive Answers**: Strategic + technical + quality views
4. **Disagreement Detection**: Important concerns flagged
5. **Better Decisions**: Synthesized insights better than single view

## Performance

**Latency**: ~2-3x single agent (parallel queries, then synthesis)

**Trade-off**: Slightly slower but much more comprehensive

**When to Use**: Complex/important questions only (automatic detection)

## Limitations

1. **Requires Melodic Memory**: Kùzu must be enabled
2. **Higher Latency**: Multiple agent calls take longer
3. **Resource Usage**: More LLM calls = more RAM/CPU

## Related Documentation

- [Agent Intelligence](AGENT_INTELLIGENCE.md) - Agent self-awareness and delegation
- [Melodic Line Memory](KUZU_MELODIC_LINE_PROPOSAL.md) - Coherent reasoning chain
- [Intelligent Codebase Analysis](INTELLIGENT_CODEBASE_ANALYSIS.md) - Smart codebase analysis

