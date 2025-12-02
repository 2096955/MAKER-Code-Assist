# Missing Capabilities Analysis

Comparison of our MAKER system against leading AI coding assistants to identify gaps and enhancement opportunities.

## References

- **[open-docs](https://github.com/bgauryy/open-docs)** - RAG system for documentation with intelligent chunking
- **[kilocode](https://github.com/Kilo-Org/kilocode)** - AI-powered code editor with multi-mode architecture

---

## 1. Documentation & RAG Capabilities (vs open-docs)

### ❌ Missing: Intelligent Chunking Strategy
- **What they have**: Semantic-aware chunking that respects code structure (function/class boundaries)
- **What we have**: Basic file reading without intelligent chunking (truncate at 3000 chars)
- **Impact**: Large files overwhelm context windows; agents can't focus on relevant sections
- **Location**: [orchestrator/orchestrator.py:1041](../orchestrator/orchestrator.py#L1041)

**Implementation Needed:**
```python
def read_file_chunked(self, path: str, chunk_size: int = 100) -> List[Dict[str, Any]]:
    """
    Read file with semantic-aware chunking (respects function/class boundaries)
    Returns: [{text, start_line, end_line, chunk_type: "function|class|module"}]
    """
```

### ⚠️ Partial: Multi-Level Retrieval
- **What they have**: Hybrid search combining lexical (keyword) + semantic (embeddings)
- **What we have**: RAG semantic search only ([orchestrator/rag_service_faiss.py](../orchestrator/rag_service_faiss.py))
- **Impact**: Miss exact keyword matches when semantic search fails

**Enhancement Needed:**
```python
def hybrid_search(query: str, top_k: int = 5):
    # 1. Semantic search (RAG)
    semantic_results = rag.search(query, top_k=top_k*2)
    # 2. Keyword search (grep-based MCP)
    keyword_results = find_references(query)
    # 3. Re-rank and merge with confidence scores
    return merge_and_rerank(semantic_results, keyword_results, top_k)
```

### ⚠️ Partial: Query Intent Classification
- **What they have**: Classifies into: factual, how-to, conceptual, troubleshooting
- **What we have**: Only: question, simple_code, complex_code ([orchestrator/orchestrator.py:862](../orchestrator/orchestrator.py#L862))
- **Impact**: Can't optimize retrieval strategy based on question type

### ❌ Missing: Source Attribution & Confidence Scores
- **What they have**: Confidence scores for each retrieved chunk with source citations
- **What we have**: No confidence scoring on MCP results
- **Impact**: Can't filter low-quality results; no citation tracking

**Implementation Needed:**
- Add confidence field to RAG results based on:
  - Semantic similarity score
  - File recency (git timestamp)
  - File importance ranking (main.py > test.py)
  - Context overlap with previous queries

### ❌ Missing: Contextual Re-ranking
- **What they have**: Re-ranks results based on conversation context and task history
- **What we have**: Static RAG results without task-aware re-ranking
- **Impact**: Might retrieve correct files but in suboptimal order

### ❌ Missing: Caching Layer
- **What they have**: Caches embeddings and frequent queries
- **What we have**: No caching; re-computes everything
- **Impact**: Slow repeated queries, unnecessary compute

**Implementation Needed:**
- Redis-based cache for:
  - File embeddings (invalidate on git changes)
  - Frequent query results (TTL: 1 hour)
  - MCP tool results (invalidate on file changes)

---

## 2. Editor Integration & UX (vs kilocode)

### ❌ Missing: Multi-Mode Architecture
- **What they have**: Specialized modes (Architect, Coder, Debugger, Custom)
- **What we have**: Single workflow for all tasks
- **Impact**: Same behavior for planning vs implementation vs debugging

**Our Current Approach:**
- High mode (Reviewer validation) vs Low mode (Planner reflection)
- But both follow identical workflow steps

**Enhancement Needed:**
```python
class WorkflowMode(Enum):
    ARCHITECT = "architect"  # High-level design, use Planner heavily
    CODER = "coder"          # Implementation, use Coder + MAKER voting
    DEBUGGER = "debugger"    # Investigation, use MCP tools + Reviewer
    REFACTOR = "refactor"    # Code improvement, use Reviewer feedback loops
```

### ❌ Missing: Self-Verification Loop
- **What they have**: "Checks its own work" - automatic validation before returning
- **What we have**: Reviewer runs once per iteration (max 3 iterations)
- **Impact**: May return code that doesn't compile or pass basic tests

**Enhancement Needed:**
- Add pre-flight checks before presenting code:
  - Syntax validation (AST parsing)
  - Basic type checking
  - Import resolution
  - Test execution (if test file exists)

### ❌ Missing: Terminal Integration
- **What they have**: Can execute terminal commands directly
- **What we have**: MCP `run_tests()` only ([orchestrator/mcp_server.py:270](../orchestrator/mcp_server.py#L270))
- **Impact**: Can't build projects, install dependencies, run migrations

**Implementation Needed:**
```python
# Add to mcp_server.py
def run_command(self, command: str, cwd: Optional[str] = None) -> str:
    """Execute arbitrary terminal command (with safety checks)"""
    # Whitelist allowed commands: npm, pip, pytest, cargo, go, etc.
    # Block dangerous commands: rm -rf, sudo, dd, etc.
```

### ❌ Missing: Browser Automation
- **What they have**: Can automate browser for testing web apps
- **What we have**: No browser automation
- **Impact**: Can't test frontend changes, validate UI behavior

**Priority**: Low (nice-to-have, not core coding assistant feature)

### ❌ Missing: MCP Server Marketplace Integration
- **What they have**: Built-in marketplace to discover and install MCP servers
- **What we have**: Hardcoded MCP server ([orchestrator/mcp_server.py](../orchestrator/mcp_server.py))
- **Impact**: Can't extend capabilities without code changes

**Enhancement Needed:**
- Dynamic MCP server registry
- Auto-discovery of available tools
- Runtime loading of new capabilities

### ❌ Missing: Automated Refactoring Agent
- **What they have**: Dedicated refactoring mode
- **What we have**: Refactoring happens through normal coding workflow
- **Impact**: No specialized prompts/strategies for refactoring tasks

**Implementation Needed:**
- Add Refactorer agent with prompts optimized for:
  - Extract function/class
  - Rename variable/function (with find-references)
  - Inline function
  - Convert to modern patterns (e.g., async/await)

---

## 3. What We Have That They Don't ✅

### 1. MAKER Voting System
- Parallel candidate generation with first-to-K voting
- Paper-backed approach: [MAKER Paper](https://arxiv.org/abs/2511.09030)
- **Unique to us**: [orchestrator/orchestrator.py:686-785](../orchestrator/orchestrator.py#L686-L785)

### 2. Dual-Orchestrator Architecture
- Instant switching between High (128GB) and Low (40GB) RAM modes
- Shared backend models for efficiency
- **Documentation**: [docs/DUAL_ORCHESTRATOR_SETUP.md](DUAL_ORCHESTRATOR_SETUP.md)

### 3. Hierarchical Context Compression
- Claude-style sliding window with automatic summarization
- Preserves recent messages, compresses older context
- **Implementation**: [orchestrator/orchestrator.py:55-257](../orchestrator/orchestrator.py#L55-L257)

### 4. Expositional Engineering Memory
- Narrative-aware code understanding (L₀-L₃ hierarchy)
- Melodic line detection for thematic flows
- **Implementation**: [orchestrator/ee_memory.py](../orchestrator/ee_memory.py)

### 5. Local-First Architecture
- 100% on-device inference (no API costs)
- llama.cpp Metal acceleration (2-3x faster than vLLM)
- Works offline

### 6. Phoenix Observability
- Complete trace visibility for all agent interactions
- Performance metrics, success rates
- **Guide**: [docs/PHOENIX_OBSERVABILITY.md](PHOENIX_OBSERVABILITY.md)

---

## Priority Ranking for Implementation

### 🔴 Critical (Immediate Impact)

1. **Intelligent File Chunking** (open-docs)
   - Biggest quality improvement for large files
   - Implementation: 4-6 hours
   - Files: `orchestrator/mcp_server.py`, `orchestrator/orchestrator.py`

2. **Confidence Scoring** (open-docs)
   - Filter low-quality retrieval results
   - Implementation: 2-3 hours
   - Files: `orchestrator/rag_service_faiss.py`

3. **Self-Verification Loop** (kilocode)
   - Prevent broken code from being returned
   - Implementation: 3-4 hours
   - Files: `orchestrator/orchestrator.py`

### 🟡 High Priority (Quality Improvements)

4. **Hybrid Retrieval** (open-docs)
   - Combine semantic + keyword search
   - Implementation: 4-5 hours
   - Files: `orchestrator/mcp_server.py`, `orchestrator/rag_service_faiss.py`

5. **Multi-Mode Architecture** (kilocode)
   - Specialized workflows for different tasks
   - Implementation: 8-10 hours
   - Files: `orchestrator/orchestrator.py`, `agents/*.md`

6. **Terminal Integration** (kilocode)
   - Execute build/test commands
   - Implementation: 3-4 hours
   - Files: `orchestrator/mcp_server.py`

### 🟢 Medium Priority (Nice-to-Have)

7. **Caching Layer** (open-docs)
   - Speed up repeated queries
   - Implementation: 4-5 hours
   - Files: `orchestrator/mcp_server.py`, `orchestrator/rag_service_faiss.py`

8. **Contextual Re-ranking** (open-docs)
   - Task-aware result ordering
   - Implementation: 3-4 hours
   - Files: `orchestrator/rag_service_faiss.py`

9. **Automated Refactoring Agent** (kilocode)
   - Dedicated refactoring workflows
   - Implementation: 6-8 hours
   - Files: `orchestrator/orchestrator.py`, `agents/refactorer-system.md`

### 🔵 Low Priority (Future Enhancements)

10. **MCP Server Marketplace** (kilocode)
    - Dynamic capability loading
    - Implementation: 12-16 hours
    - Requires: Architecture redesign

11. **Browser Automation** (kilocode)
    - Web testing integration
    - Implementation: 8-10 hours
    - Requires: Playwright/Puppeteer integration

---

## Recommended Next Steps

1. **Week 1**: Implement intelligent file chunking + confidence scoring
2. **Week 2**: Add self-verification loop + hybrid retrieval
3. **Week 3**: Implement multi-mode architecture
4. **Week 4**: Add terminal integration + caching

This would bring us to feature parity with leading AI coding assistants while maintaining our unique MAKER voting and local-first advantages.

---

## References

- [open-docs GitHub](https://github.com/bgauryy/open-docs)
- [kilocode GitHub](https://github.com/Kilo-Org/kilocode)
- [MAKER Paper](https://arxiv.org/abs/2511.09030)
- [Our Architecture Docs](DUAL_ORCHESTRATOR_SETUP.md)
