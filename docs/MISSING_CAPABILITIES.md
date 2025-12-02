# Missing Capabilities Analysis

Comparison of our MAKER system against leading AI coding assistants to identify gaps and enhancement opportunities.

## References

- **[open-docs](https://github.com/bgauryy/open-docs)** - RAG system for documentation with intelligent chunking
- **[kilocode](https://github.com/Kilo-Org/kilocode)** - AI-powered code editor with multi-mode architecture
- **[Claude Code](https://github.com/ghuntley/claude-code-source-code-deobfuscation)** - Anthropic's official agentic coding CLI
- **[System Prompts](https://github.com/asgeirtj/system_prompts_leaks)** - Leaked system prompts revealing Claude Code design patterns
- **[OpenCode](https://github.com/opencode-ai/opencode)** - Terminal AI agent with auto-compact context (archived, moved to Crush)
- **[Crush](https://github.com/charmbracelet/crush)** - Multi-model terminal agent with LSP integration and mid-session model switching

---

## 1. OpenCode/Crush Advanced Features (terminal AI agents)

Based on analysis of OpenCode (archived) and its successor Crush by Charmbracelet:

### ✅ Already Implemented

1. **Session Management**
   - Our system: Session persistence via Redis with resume capability
   - Status: ✅ Implemented ([orchestrator/session_manager.py](../orchestrator/session_manager.py))

2. **MCP Integration**
   - Our system: MCP server with codebase tools
   - Status: ✅ Implemented ([orchestrator/mcp_server.py](../orchestrator/mcp_server.py))

### ❌ Missing: Critical Features

3. **Auto-Compact Context Management** (OpenCode)
   - **What they have**: Monitors token usage, auto-triggers summarization at 95% of context window
   - **Our system**: Manual compression via ContextCompressor, no automatic threshold
   - **Impact**: Risk of hitting context limits unexpectedly
   - **Implementation**:
     ```python
     async def compress_if_needed(self) -> bool:
         # Current: Only compresses if exceeds max_context_tokens
         # Need: Auto-compress at 95% threshold proactively
         usage_percent = (total_tokens / self.max_context_tokens)
         if usage_percent >= 0.95:  # Auto-compact threshold
             await self._compress_now()
     ```

4. **LSP Integration** (Crush)
   - **What they have**: Language Server Protocol for semantic code understanding
   - **Our system**: File reading only, no LSP
   - **Impact**: No type information, definitions, or references beyond grep
   - **Value**: Semantic code intelligence (go-to-definition, find-references, type hints)
   - **Implementation**: 12-16 hours

5. **Mid-Session Model Switching** (Crush)
   - **What they have**: Switch between models while preserving conversation context
   - **Our system**: Fixed model per agent, requires restart to change
   - **Impact**: Can't adapt to task complexity changes during conversation
   - **Use case**: Start with fast model, switch to powerful model for complex subtask

6. **Per-Agent Model Configuration** (OpenCode)
   - **What they have**: Different models for coder, task, title agents
   - **Our system**: Fixed models per agent type (hardcoded in start script)
   - **Current**: All agents use same quantization/size within their role
   - **Enhancement**: Allow runtime model selection per agent

7. **Declarative Tool Permissions** (Crush)
   - **What they have**: Project-level `allowed_tools` configuration
   - **Our system**: No tool whitelisting/blacklisting
   - **Impact**: Can't restrict dangerous operations per project
   - **Implementation**:
     ```json
     {
       "allowed_tools": ["read_file", "search_docs"],
       "blocked_tools": ["run_tests"]
     }
     ```

8. **Non-Interactive/Scripting Mode** (OpenCode)
   - **What they have**: `--quiet` flag, JSON output, auto-approve permissions
   - **Our system**: Always interactive via API
   - **Impact**: Can't use in CI/CD pipelines
   - **Use case**: Automated code reviews, batch processing

### ⚠️ Partial Implementation

9. **Configuration Hierarchy** (Crush)
   - **What they have**: Project `.crush.json` → Root `crush.json` → Global `~/.config/crush/`
   - **Our system**: Only environment variables and docker-compose.yml
   - **Status**: ⚠️ Partial (no project-level config files)
   - **Enhancement**: Support `.maker.json` in project root

10. **Attribution System** (Crush)
    - **What they have**: Configurable git attribution (assisted-by, co-authored-by, none)
    - **Our system**: No automatic attribution
    - **Status**: ⚠️ Could add via git commit templates

### 🔵 Not Applicable to Our Architecture

- **Terminal UI (Bubble Tea)**: We're API-focused, not TUI
- **Vim keybindings**: Not applicable to API
- **External editor integration**: Not relevant for Continue.dev integration

---

## 2. Claude Code Design Patterns (from leaked prompts)

Based on analysis of Claude Code's system prompts and architecture, here are key patterns we should adopt:

### ✅ Already Implemented

1. **Read-Before-Write Pattern**
   - Our system: Edit tool requires prior Read ([orchestrator/orchestrator.py](../orchestrator/orchestrator.py))
   - Status: ✅ Implemented in CLAUDE.md instructions

2. **Parallel Tool Execution**
   - Our system: TodoWrite instructions specify parallel execution for independent tools
   - Status: ✅ Documented pattern (but agents don't always follow it)

3. **Git Safety Rules**
   - Our system: Git workflow documented with safety checks
   - Status: ✅ Documented in CLAUDE.md

### ❌ Missing: Advanced Patterns

4. **Tool Call Scaling**
   - **Claude Code**: "Scale the number of tool calls to query complexity"
   - **Our system**: Fixed MAKER candidate count (N=5)
   - **Impact**: Waste compute on simple tasks, underutilize on complex tasks
   - **Implementation**:
     ```python
     def get_candidate_count(task_complexity: str) -> int:
         return {"simple": 2, "medium": 5, "complex": 8}[task_complexity]
     ```

5. **Avoid Unnecessary Tool Calls**
   - **Claude Code**: "Avoid tool calls if not needed" (explicit instruction)
   - **Our system**: No explicit guidance to avoid unnecessary MCP calls
   - **Impact**: Planner always calls MCP even for simple questions
   - **Fix**: Add to Planner prompt: "Only use MCP tools when you need codebase-specific information"

6. **Behavioral Guidelines Structure**
   - **Claude Code**: Hierarchical prompts (identity → tools → safety → context)
   - **Our system**: Flat system prompts in `agents/*.md`
   - **Impact**: Hard to override safety rules without rewriting entire prompts
   - **Enhancement**: Restructure prompts with clear sections

7. **Long-Running Command Support**
   - **Claude Code**: Explicit support for long-running commands (noted as improvement area)
   - **Our system**: Has ENABLE_LONG_RUNNING but limited implementation
   - **Status**: ⚠️ Partial (Phase 1 implemented, needs expansion)

8. **Plan Mode**
   - **Claude Code**: Has dedicated `claude-code-plan-mode.md` prompt
   - **Our system**: Planning happens in normal workflow
   - **Impact**: No distinction between exploration and implementation
   - **Link to**: Multi-mode architecture (kilocode similarity)

### 🔵 Claude Code Unique Features Not Applicable

- **Artifacts**: Web UI feature for rendering code/documents (we're CLI-focused)
- **Web Search/Fetch**: We're codebase-focused, not web-focused
- **Google Integrations**: Not applicable to coding assistant

---

## 2. Documentation & RAG Capabilities (vs open-docs)

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

1. **Auto-Compact Context** (OpenCode)
   - Proactive compression at 95% threshold
   - Implementation: 1-2 hours
   - Files: `orchestrator/orchestrator.py` (ContextCompressor)
   - **Why first**: Prevents context overflow errors

2. **Tool Call Scaling** (Claude Code)
   - Scale MAKER candidates based on task complexity
   - Implementation: 1-2 hours
   - Files: `orchestrator/orchestrator.py`
   - **Why critical**: Low effort, immediate compute savings

3. **Intelligent File Chunking** (open-docs)
   - Biggest quality improvement for large files
   - Implementation: 4-6 hours
   - Files: `orchestrator/mcp_server.py`, `orchestrator/orchestrator.py`

4. **Avoid Unnecessary Tool Calls** (Claude Code)
   - Add prompt guidance to skip MCP when not needed
   - Implementation: 30 minutes
   - Files: `agents/planner-system.md`
   - **Why critical**: Reduces latency on simple questions

5. **Confidence Scoring** (open-docs)
   - Filter low-quality retrieval results
   - Implementation: 2-3 hours
   - Files: `orchestrator/rag_service_faiss.py`

6. **Self-Verification Loop** (kilocode)
   - Prevent broken code from being returned
   - Implementation: 3-4 hours
   - Files: `orchestrator/orchestrator.py`

### 🟡 High Priority (Quality Improvements)

7. **Hybrid Retrieval** (open-docs)
   - Combine semantic + keyword search
   - Implementation: 4-5 hours
   - Files: `orchestrator/mcp_server.py`, `orchestrator/rag_service_faiss.py`

8. **Declarative Tool Permissions** (Crush)
   - Project-level allowed/blocked tools configuration
   - Implementation: 2-3 hours
   - Files: `orchestrator/orchestrator.py`, add `.maker.json` support
   - **Benefit**: Safety controls per project

9. **Hierarchical Prompt Structure** (Claude Code)
   - Restructure agent prompts with clear sections
   - Implementation: 3-4 hours
   - Files: `agents/*.md`
   - **Benefit**: Easier to maintain and override specific behaviors

10. **Multi-Mode Architecture** (kilocode + Claude Code Plan Mode)
    - Specialized workflows (Architect, Coder, Debugger, Plan)
    - Implementation: 8-10 hours
    - Files: `orchestrator/orchestrator.py`, `agents/*.md`

11. **Terminal Integration** (kilocode)
    - Execute build/test commands
    - Implementation: 3-4 hours
    - Files: `orchestrator/mcp_server.py`

### 🟢 Medium Priority (Nice-to-Have)

12. **Caching Layer** (open-docs)
    - Speed up repeated queries
    - Implementation: 4-5 hours
    - Files: `orchestrator/mcp_server.py`, `orchestrator/rag_service_faiss.py`

13. **Contextual Re-ranking** (open-docs)
    - Task-aware result ordering
    - Implementation: 3-4 hours
    - Files: `orchestrator/rag_service_faiss.py`

14. **Non-Interactive/Scripting Mode** (OpenCode)
    - API flags for quiet mode, JSON output, auto-approve
    - Implementation: 3-4 hours
    - Files: `orchestrator/api_server.py`
    - **Use case**: CI/CD integration

15. **Configuration Hierarchy** (Crush)
    - Support `.maker.json` at project/root/global levels
    - Implementation: 4-5 hours
    - Files: `orchestrator/orchestrator.py`

16. **Automated Refactoring Agent** (kilocode)
    - Dedicated refactoring workflows
    - Implementation: 6-8 hours
    - Files: `orchestrator/orchestrator.py`, `agents/refactorer-system.md`

17. **Expand Long-Running Support** (Claude Code)
    - Full support for long-running commands with streaming
    - Implementation: 6-8 hours
    - Files: `orchestrator/orchestrator.py`, `orchestrator/session_manager.py`

### 🔵 Low Priority (Future Enhancements)

18. **LSP Integration** (Crush)
    - Language Server Protocol for semantic intelligence
    - Implementation: 12-16 hours
    - Requires: LSP client library, per-language server configs
    - **High value** but significant effort

19. **Mid-Session Model Switching** (Crush)
    - Switch models mid-conversation with context preservation
    - Implementation: 8-10 hours
    - Requires: Dynamic model loading architecture

20. **MCP Server Marketplace** (kilocode)
    - Dynamic capability loading
    - Implementation: 12-16 hours
    - Requires: Architecture redesign

21. **Browser Automation** (kilocode)
    - Web testing integration
    - Implementation: 8-10 hours
    - Requires: Playwright/Puppeteer integration

---

## Recommended Next Steps

### Quick Wins (Week 1 - 11 hours total)

1. **Auto-Compact Context** (1-2 hours) - OpenCode - Prevents context overflow
2. **Tool Call Scaling** (1-2 hours) - Claude Code - Immediate compute savings
3. **Avoid Unnecessary Tool Calls** (30 min) - Claude Code - Add prompt guidance
4. **Intelligent File Chunking** (4-6 hours) - open-docs - Major quality improvement
5. **Confidence Scoring** (2-3 hours) - open-docs - Filter low-quality results

### Quality Improvements (Week 2 - 14 hours total)

6. **Self-Verification Loop** (3-4 hours) - kilocode - Prevent broken code
7. **Hybrid Retrieval** (4-5 hours) - open-docs - Semantic + keyword search
8. **Declarative Tool Permissions** (2-3 hours) - Crush - Project safety controls
9. **Hierarchical Prompt Structure** (3-4 hours) - Claude Code - Easier maintenance

### Advanced Features (Week 3-4 - 24 hours total)

10. **Multi-Mode Architecture** (8-10 hours) - kilocode + Claude Code - Specialized workflows
11. **Terminal Integration** (3-4 hours) - kilocode - Build/test execution
12. **Non-Interactive Mode** (3-4 hours) - OpenCode - CI/CD integration
13. **Configuration Hierarchy** (4-5 hours) - Crush - Project-level configs
14. **Caching Layer** (4-5 hours) - open-docs - Speed optimization

This implementation plan incorporates learnings from **6 leading AI coding tools** (Claude Code, open-docs, kilocode, OpenCode, Crush, system prompts) while maintaining our unique MAKER voting, EE Memory, and local-first advantages.

**Total: 21 prioritized enhancements** across Critical (6), High Priority (5), Medium Priority (6), Low Priority (4).

---

## References

- [open-docs GitHub](https://github.com/bgauryy/open-docs)
- [kilocode GitHub](https://github.com/Kilo-Org/kilocode)
- [MAKER Paper](https://arxiv.org/abs/2511.09030)
- [Our Architecture Docs](DUAL_ORCHESTRATOR_SETUP.md)
