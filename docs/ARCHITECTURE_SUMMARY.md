# MAKER Architecture Summary

**Quick Reference**: Where things are and why they matter.

---

## 1. Agent System Prompts

**Location**: `agents/*.md`

**Why They're There**: Each agent has specialized instructions that define its role, objectives, and constraints.

### Files:

- **`preprocessor-system.md`** - Input understanding & multimodal processing
  - Converts user input (text/images/audio) to clean task descriptions
  - Detects intent and security requirements
  - Summarizes context for compression

- **`planner-system.md`** - Strategic thinking & task decomposition
  - Breaks tasks into subtasks with dependencies
  - Uses MCP tools to query codebase before planning
  - In Low mode: Also performs reflection validation

- **`coder-system.md`** - Code generation
  - Generates code candidates with MAKER voting
  - Parallel generation with temperature variation (0.3-0.7)
  - First-to-K voting determines winner

- **`reviewer-system.md`** - Quality assurance & testing (High mode only)
  - Validates code quality
  - Runs tests and checks security
  - Provides detailed feedback for iteration

- **`voter-system.md`** - MAKER voting consensus
  - Runs 2K-1 voter instances
  - First candidate to reach K votes wins
  - Fast consensus mechanism

**Key Point**: These prompts are the "DNA" of each agent. They define MAKER objectives, tool usage, and constraints.

---

## 2. Memory Systems

**Location**: `orchestrator/` directory

### Melodic Line Memory (Kùzu Graph)

**File**: `orchestrator/kuzu_memory.py`

**What It Does**: Maintains coherent reasoning chain across agents using Kùzu graph database.

**How It Works**:
```python
# Preprocessor writes reasoning
memory.add_action(
    agent="preprocessor",
    reasoning="User wants JWT auth. Security requirement detected.",
    output="Add JWT authentication to API"
)

# Planner reads Preprocessor's reasoning
context = memory.get_context_for_agent(task_id, "planner")
# context includes: "Security requirement detected"

# Coder reads BOTH Preprocessor + Planner
context = memory.get_context_for_agent(task_id, "coder")
# context includes BOTH reasonings - the "melodic line"
```

**Why It Matters**: Without this, agents forget what earlier agents understood. With it, they maintain intent throughout the workflow.

**Storage**: Docker volume `kuzu_workflow_db_high` or `kuzu_workflow_db_low`

### Agent Memory (NetworkX Graph)

**File**: `orchestrator/agent_memory.py`

**What It Does**: Each agent maintains its own memory graph for cross-task learning.

**How It Works**:
- Stores task patterns, successful approaches, failure modes
- Builds narrative connections between related tasks
- Enables agents to learn from past experiences

**Why It Matters**: Agents get smarter over time by remembering what worked.

### EE Memory (Expositional Engineering)

**File**: `orchestrator/ee_memory.py`

**What It Does**: Hierarchical memory network for maintaining narrative coherence.

**How It Works**:
- Tracks narrative entities (variables, functions, business logic)
- Maintains coherence across multi-step tasks
- Prevents losing the thread on complex workflows

**Why It Matters**: Long tasks don't drift off-topic or forget context.

### Context Compression

**File**: `orchestrator/orchestrator.py` (ContextCompressor class)

**What It Does**: Hierarchical compression like Claude's context management.

**How It Works**:
- Recent messages: Kept in full
- Older messages: Automatically summarized by Preprocessor
- Auto-eviction: Oldest content compressed when approaching limits

**Why It Matters**: Stays within token limits while preserving important context.

---

## 3. RAG (Retrieval-Augmented Generation)

**Location**: `orchestrator/hybrid_search.py`

### How RAG Works

**Three-Stage Hybrid Search**:

1. **Semantic Search** (Qdrant vector DB)
   - Embeds query with `sentence-transformers`
   - Finds semantically similar code chunks
   - Returns top-K results with relevance scores

2. **Keyword Search** (BM25)
   - Exact keyword matching
   - Good for API names, function names, specific terms
   - Complements semantic search

3. **Community Detection** (Graph RAG)
   - File**: `orchestrator/code_graph.py`
   - Groups related code files into communities (Louvain algorithm)
   - Returns entire community when one file matches
   - 5-10x faster queries by reducing search space

**Hybrid Fusion**:
```python
# Combine all three search methods
results = hybrid_search(
    query="authentication logic",
    semantic_weight=0.5,   # Semantic similarity
    keyword_weight=0.3,    # Exact keyword match
    community_weight=0.2   # Related files in same community
)
```

**Why It Matters**:
- Semantic search finds conceptually similar code
- Keyword search finds exact API usage
- Community detection finds all related files at once

### Indexing Pipeline

**Script**: `scripts/index_codebase.py`

**What It Does**:
1. Reads all code files from codebase
2. Chunks into semantic blocks (~500 tokens)
3. Generates embeddings with `nomic-embed-text-v1.5`
4. Stores in Qdrant vector database
5. Builds community graph for fast retrieval

**Run Indexing**:
```bash
# Index codebase for RAG
bash scripts/setup-rag-faiss.sh
```

**Storage**:
- Qdrant database: `qdrant_data` Docker volume
- Community graph: Persisted with code graph

---

## 4. MCP Tools (Model Context Protocol)

**Location**: `orchestrator/mcp_server.py`

### What MCP Provides

**MCP** = Standardized way for agents to call codebase tools.

### Available Tools

1. **`read_file`** - Read file contents
   ```python
   result = await mcp_client.call_tool("read_file", {"path": "orchestrator/orchestrator.py"})
   ```

2. **`analyze_codebase`** - Get codebase overview
   ```python
   result = await mcp_client.call_tool("analyze_codebase", {})
   # Returns: file count, language breakdown, structure
   ```

3. **`run_tests`** - Execute test suite
   ```python
   result = await mcp_client.call_tool("run_tests", {"test_path": "tests/"})
   ```

4. **`search_code`** - Search codebase (uses RAG)
   ```python
   result = await mcp_client.call_tool("search_code", {"query": "authentication"})
   ```

5. **`get_file_structure`** - Get directory tree
   ```python
   result = await mcp_client.call_tool("get_file_structure", {"path": "orchestrator/"})
   ```

### How Agents Use MCP

**Planner's Workflow**:
```python
# 1. Planner receives task: "Add JWT auth"

# 2. Planner queries codebase BEFORE planning
mcp_result = await call_tool("search_code", {"query": "authentication"})

# 3. Planner sees existing auth code, creates informed plan
plan = {
    "plan": [
        {"description": "Create JWT utility (new file)", ...},
        {"description": "Add middleware (update existing auth.py)", ...},
        {"description": "Update endpoints (modify api_server.py)", ...}
    ]
}
```

**Why It Matters**: Planner doesn't hallucinate paths or assume structure. It QUERIES the actual codebase first.

### MCP Server

**Port**: 9001
**Protocol**: REST API
**Container**: `mcp-server`

**Wrapper**: `orchestrator/mcp_client_wrapper.py` - Simplified interface for orchestrator

---

## 5. Collective Brain (Multi-Agent Consensus)

**Location**: `orchestrator/collective_brain.py`

### What It Does

For complex questions, consult multiple agents in parallel and synthesize their answers.

### Expert Panels

**Architecture Questions**:
- Agents: Planner (strategy) + Coder (implementation) + Reviewer (quality)
- Example: "Should I use GraphQL or REST?"
- Output: Consensus considering all three perspectives

**Debugging Questions**:
- Agents: Coder (code knowledge) + Reviewer (security/testing)
- Example: "Why is this endpoint failing?"
- Output: Combined technical + security analysis

**Planning Questions**:
- Agents: Preprocessor (understanding) + Planner (dependencies)
- Example: "How should I architect this feature?"
- Output: Intent + strategic plan

### How It Works

```python
# User asks complex question
question = "Should I use microservices or monolith?"

# Collective brain consults multiple agents
result = await collective_brain.consult_collective(
    problem=question,
    problem_type="architecture"
)

# Returns:
# - Consensus: Synthesized answer from all agents
# - Perspectives: Individual agent views
# - Dissenting: Important disagreements
# - Confidence: Agreement level (0-1)
```

**Why It Matters**: Complex questions benefit from multiple expert viewpoints. Single-agent answers miss important trade-offs.

---

## 6. Phoenix Evaluations (Validation)

**Location**: `tests/phoenix_evaluator.py`

### What It Does

Quantitative A/B testing to prove melodic memory and collective brain actually work.

### Experiments

1. **Melodic Memory A/B Test**
   - Control: Agents WITHOUT shared reasoning
   - Treatment: Agents WITH Kùzu melodic line
   - Metrics: QA correctness, hallucination rate, relevance

2. **Collective Brain A/B Test**
   - Control: Single-agent answers
   - Treatment: Multi-agent consensus
   - Metrics: Answer quality, trade-off coverage

3. **SWE-bench Evaluation**
   - Test on real GitHub issues
   - Validate code execution with Playwright
   - Metrics: Patch correctness, test pass rate

### LLM-as-Judge Evaluators

- **HallucinationEvaluator**: Detects unsupported claims
- **QAEvaluator**: Measures answer correctness
- **RelevanceEvaluator**: Checks if on-topic

### Usage

```bash
# Run melodic memory A/B test
python tests/phoenix_evaluator.py --experiment melodic_memory_ab

# View results in Phoenix UI
open http://localhost:6006
```

**Why It Matters**: Provides data-driven proof (not just vibes) that the system actually works better.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                   IDE (Continue.dev)                         │
│                                                              │
│  Model Selection:                                           │
│  ┌────────────────────┐      ┌────────────────────┐        │
│  │ MakerCode - High   │      │ MakerCode - Low    │        │
│  │ (Port 8080)        │      │ (Port 8081)        │        │
│  └─────────┬──────────┘      └─────────┬──────────┘        │
└────────────┼──────────────────────────┼────────────────────┘
             │                           │
    ┌────────▼─────────┐      ┌─────────▼────────┐
    │ Orchestrator     │      │ Orchestrator      │
    │ High             │      │ Low               │
    │                  │      │                   │
    │ • Melodic Memory │      │ • Melodic Memory  │
    │ • Collective Brain│     │ • Collective Brain│
    │ • MCP Tools      │      │ • MCP Tools       │
    │ • RAG Hybrid     │      │ • RAG Hybrid      │
    │ • Reviewer       │      │ • Planner Reflect │
    └────────┬─────────┘      └─────────┬─────────┘
             │                           │
             └──────────┬────────────────┘
                        │
        ┌───────────────▼──────────────────┐
        │   Shared Backend Services        │
        │                                   │
        │  llama.cpp Servers (Native)      │
        │  ├─ Preprocessor (8000)          │
        │  ├─ Planner (8001)               │
        │  ├─ Coder (8002)                 │
        │  ├─ Reviewer (8003)              │
        │  └─ Voter (8004)                 │
        │                                   │
        │  MCP Server (9001)               │
        │  ├─ read_file                    │
        │  ├─ analyze_codebase             │
        │  ├─ run_tests                    │
        │  └─ search_code (RAG)            │
        │                                   │
        │  Memory Systems                  │
        │  ├─ Kùzu (Melodic Line)          │
        │  ├─ Redis (State)                │
        │  ├─ NetworkX (Agent Memory)      │
        │  └─ Qdrant (RAG Vectors)         │
        │                                   │
        │  Observability                   │
        │  └─ Phoenix (6006)               │
        └───────────────────────────────────┘
```

---

## Key Files Reference

| Component | File | Purpose |
|-----------|------|---------|
| **Agent Prompts** | `agents/*.md` | Agent instructions & objectives |
| **Melodic Memory** | `orchestrator/kuzu_memory.py` | Shared reasoning chain (Kùzu) |
| **Collective Brain** | `orchestrator/collective_brain.py` | Multi-agent consensus |
| **MCP Tools** | `orchestrator/mcp_server.py` | Codebase tool server |
| **RAG Hybrid** | `orchestrator/hybrid_search.py` | Semantic + keyword + community search |
| **Code Graph** | `orchestrator/code_graph.py` | Community detection for fast RAG |
| **Orchestrator** | `orchestrator/orchestrator.py` | Main workflow coordination |
| **Evaluations** | `tests/phoenix_evaluator.py` | A/B testing framework |
| **Docker Config** | `docker-compose.yml` | Service definitions |
| **Startup** | `scripts/start-maker.sh` | Launch all services |

---

## Quick Mental Model

1. **Prompts** (`agents/*.md`) = Agent DNA
2. **Melodic Memory** (Kùzu) = Shared reasoning chain
3. **Collective Brain** = Multi-agent consultation for complex questions
4. **RAG** = Hybrid search (semantic + keyword + communities)
5. **MCP** = Codebase tools API
6. **Phoenix** = A/B testing & validation

**Flow**: User → Preprocessor (understand) → Planner (plan using MCP) → Coder (generate with MAKER) → Reviewer/Reflection (validate) → User

**Key Insight**: Melodic memory ensures each agent sees previous reasoning. Collective brain brings multiple perspectives. RAG ensures agents work with actual code, not hallucinations.
