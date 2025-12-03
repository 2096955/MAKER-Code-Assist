# Agent Intelligence & Self-Awareness

## Overview

The MAKER system now features intelligent agents that understand their strengths, know when to delegate, and proactively use each other's capabilities.

## Key Features

### 1. Agent Self-Awareness

Each agent knows:
- **What they're GOOD at** (strengths/capabilities)
- **What they're BAD at** (weaknesses)
- **When to DELEGATE** (who to call for help)

**Implementation**: `orchestrator/agent_coordinator.py`

### 2. Proactive Context Building

Agents proactively use Gemma2-2B (Preprocessor) to build context instead of waiting to be told.

**Pattern**: When agent needs to understand content → Call Preprocessor

**Examples**:
- README extraction → Preprocessor
- Intent detection → Preprocessor
- Content summarization → Preprocessor

### 3. Collective Brain

For complex questions, multiple agents are consulted and their perspectives are synthesized.

**Implementation**: `orchestrator/collective_brain.py`

## Agent Profiles

### Preprocessor (Gemma2-2B)

**Strengths**:
- Multimodal processing (images, audio → text)
- Content understanding (extract meaning from messy content)
- Summarization (condense long text)
- Intent detection (what does user really want?)

**Weaknesses**:
- Code generation
- Complex reasoning
- Long-form planning

**When to Use**:
- Converting messy input to clean understanding
- Images/audio → text
- Extracting meaning from READMEs/docs
- Understanding user intent

**Delegates To**:
- Code questions → Coder
- Planning needed → Planner
- Code review → Reviewer

### Planner (Nemotron Nano 8B)

**Strengths**:
- Task breakdown (break complex tasks into steps)
- Dependency analysis (what needs to happen first?)
- Narrative preservation (maintain business logic flows)
- Strategic thinking (high-level architecture decisions)

**Weaknesses**:
- Writing actual code
- Multimodal processing
- Deep code analysis

**When to Use**:
- Breaking complex tasks into steps
- Understanding dependencies
- Preserving business logic narratives

**Delegates To**:
- Needs code → Coder
- Unclear input → Preprocessor
- Validation needed → Reviewer

### Coder (Devstral 24B)

**Strengths**:
- Code generation (write actual code)
- Code understanding (read and explain existing code)
- Refactoring (improve code structure)
- Debug assistance (help find bugs)

**Weaknesses**:
- Multimodal input
- High-level planning
- Code review (own code)

**When to Use**:
- Writing code
- Explaining code
- Refactoring
- Finding bugs
- Anything code-related

**Delegates To**:
- Needs review → Reviewer
- Unclear requirements → Planner
- Messy input → Preprocessor

### Reviewer (Qwen 32B)

**Strengths**:
- Code review (validate code quality)
- Security audit (find vulnerabilities)
- Test validation (verify tests work)
- Standards compliance (check best practices)

**Weaknesses**:
- Code generation
- Planning
- Multimodal input

**When to Use**:
- Reviewing code quality
- Finding bugs
- Security audits
- Validating tests work

**Delegates To**:
- Needs fixes → Coder
- Needs replan → Planner

### Voter (Qwen 1.5B)

**Strengths**:
- Consensus building (MAKER voting)
- Quality comparison (which code is better?)

**Weaknesses**:
- Everything except voting

**When to Use**:
- MAKER voting: choosing best candidate from multiple options

## Proactive Context Building

### Pattern: Use AI Instead of Regex

**Before** (dumb parsing):
```python
# Regex fails on HTML-heavy READMEs
description = re.search(r'# (.+)', readme_content).group(1)  # ❌
```

**After** (smart AI):
```python
# Use Preprocessor to understand content
description = await call_agent_sync(
    AgentName.PREPROCESSOR,
    "Extract the main purpose of this codebase...",
    readme_content
)  # ✅
```

### Examples

1. **README Extraction**: Preprocessor extracts purpose from messy READMEs
2. **Intent Detection**: Preprocessor understands what user really wants
3. **Content Summarization**: Preprocessor condenses long context

## Collective Brain

### When to Use

For complex/important questions, consult multiple agents and synthesize:

- **Architecture decisions**: Planner + Coder + Reviewer
- **Debugging**: Coder + Reviewer
- **Planning**: Preprocessor + Planner
- **Understanding**: Preprocessor + Planner + Coder
- **Security**: Reviewer + Coder

### How It Works

1. **Detect complex question** (architecture, debugging, etc.)
2. **Consult expert panel** (ask multiple agents in parallel)
3. **Collect perspectives** (each agent's view from their expertise)
4. **Synthesize** (use Planner to combine insights)
5. **Show consensus** + individual views + dissenting opinions

### Example

**Question**: "Should we use Redis or PostgreSQL for session storage?"

**Collective Brain Response**:
```
[COLLECTIVE BRAIN] Consulting multiple agents...

**Consensus**: Use Redis for session storage because it's faster for key-value lookups and has built-in TTL support. PostgreSQL is better for complex queries but overkill for simple session data.

**Agent Perspectives**:
- PLANNER (Nemotron Nano 8B): Redis fits the use case better - sessions are temporary, need fast access, and TTL is built-in. (Confidence: 85%)
- CODER (Devstral 24B): Redis is simpler to implement - just set/get with TTL. PostgreSQL requires schema design. (Confidence: 90%)
- REVIEWER (Qwen 32B): Redis is fine, but ensure persistence is enabled for production. (Confidence: 80%)

⚠️ REVIEWER has concerns: Ensure Redis persistence is enabled for production reliability.
```

## Integration Points

### Agent Coordinator

**File**: `orchestrator/agent_coordinator.py`

**Usage**:
```python
from orchestrator.agent_coordinator import coordinator

# Check if agent should handle task
should_handle, delegate_to = coordinator.should_agent_handle(
    agent_name="preprocessor",
    task_type="understand_content"
)

if not should_handle:
    # Delegate to appropriate agent
    delegate_to_agent(delegate_to)
```

### Collective Brain

**File**: `orchestrator/collective_brain.py`

**Usage**:
```python
from orchestrator.collective_brain import CollectiveBrain

collective_brain = CollectiveBrain(orchestrator)

# Consult multiple agents
result = await collective_brain.consult_collective(
    problem="Should we refactor this to use async/await?",
    problem_type="architecture",
    context=codebase_context,
    user_question="How should I refactor this code?"
)

# Result contains:
# - consensus: Synthesized answer
# - perspectives: Individual agent views
# - dissenting: Important disagreements
# - confidence: Overall confidence (0-1)
```

## Configuration

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

1. **Smarter Agents**: Agents know their roles and delegate intelligently
2. **Better Context**: Proactive use of AI instead of dumb parsing
3. **Collective Intelligence**: Multiple perspectives for complex questions
4. **Coherent Reasoning**: Melodic line memory maintains context across agents

## Examples

### Example 1: Proactive README Extraction

**Before**: Regex parsing fails on HTML  
**After**: Preprocessor intelligently extracts description

### Example 2: Collective Architecture Decision

**Question**: "Should we use microservices or monolith?"

**Response**: 
- Planner: Strategic perspective (scalability, complexity)
- Coder: Implementation perspective (development speed, maintenance)
- Reviewer: Quality perspective (testing, deployment)

**Synthesized**: Clear recommendation based on all perspectives

### Example 3: Agent Delegation

**Scenario**: Preprocessor receives code question

**Action**: Delegates to Coder (code is Coder's strength)

**Result**: Right agent handles the task

## Related Documentation

- [Intelligent Codebase Analysis](INTELLIGENT_CODEBASE_ANALYSIS.md) - Smart codebase analysis with memory
- [Collective Brain](COLLECTIVE_BRAIN.md) - Multi-agent consensus system
- [Melodic Line Memory](KUZU_MELODIC_LINE_PROPOSAL.md) - Coherent reasoning chain

