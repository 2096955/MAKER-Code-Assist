# BreakingWind Multi-Agent Coding System - Project Plan

## 1. Architecture Overview

BreakingWind is a production-ready multi-agent coding system optimized for Apple Silicon (M4 Max) that implements an intelligent workflow for complex coding tasks through specialized AI agents.

### Core Architecture
```
User Input → Preprocessor → Planner → Coder ↔ Reviewer → Output
              (Gemma2-2B)   (Nemotron)  (Devstral)   (Qwen3)
```

### Key Components
- **4 Specialized AI Agents**: Each optimized for specific tasks
- **llama.cpp Metal Backend**: 30-60% faster than vLLM on Apple Silicon
- **Agentic RAG via MCP**: Live codebase queries replacing traditional embeddings
- **Parallel Execution**: All agents run simultaneously for maximum throughput
- **Streaming Architecture**: Token-by-token streaming with real-time feedback
- **Redis State Coordination**: Shared memory and state management across agents
- **Docker Compose Setup**: Containerized deployment with auto-restart capabilities

### Agent Specifications

#### Preprocessor Agent (Gemma2-2B)
- **Purpose**: Multimodal input processing (audio, image, text)
- **Model**: Gemma2-2B (1.5GB RAM, 180+ tokens/sec)
- **Input**: Audio (Whisper STT), Images (vision), Text (passthrough)
- **Output**: Clean text for downstream agents
- **Context**: 8K tokens

#### Planner Agent (Nemotron Nano 8B)
- **Purpose**: Task decomposition and strategic planning
- **Model**: Nemotron Nano 8B (4-5GB RAM, 118-135 tokens/sec)
- **Features**: Agentic-trained for reasoning and tool calling
- **Context**: 128K tokens for complex codebase understanding
- **Tools**: MCP queries for codebase analysis
- **Output**: Structured JSON task breakdown

#### Coder Agent (Devstral 24B)
- **Purpose**: Production-ready code generation
- **Model**: Devstral 24B (14-16GB RAM, 78-92 tokens/sec)
- **Features**: 46.8% SWE-Bench score (best open-source coder)
- **Context**: 128K tokens
- **Tools**: MCP file access, test execution
- **Output**: Streaming code diffs with chunked delivery

#### Reviewer Agent (Qwen3-Coder 32B)
- **Purpose**: Quality validation and testing
- **Model**: Qwen3-Coder 32B (18-20GB RAM, 58-68 tokens/sec)
- **Features**: Full repository visibility for comprehensive review
- **Context**: 256K tokens
- **Tools**: Test execution, security validation, style checking
- **Iteration**: Max 3 cycles with Coder, escalates to Planner if needed

## 2. Technology Stack

### Infrastructure
- **Container Runtime**: Docker & Docker Compose
- **OS Optimization**: Apple Silicon (Metal acceleration)
- **Memory**: 128GB unified memory (40GB peak usage)
- **Storage**: ~50GB for GGUF models

### AI/ML Stack
- **Inference Engine**: llama.cpp with Metal backend
- **Model Format**: GGUF with Q6_K quantization (1-2% quality loss)
- **Docker Image**: `ghcr.io/ggerganov/llama.cpp:server-metal`
- **Acceleration**: Metal GPU layers (--n-gpu-layers 999)

### Backend Services
- **Language**: Python 3.11+
- **API Framework**: FastAPI with async support
- **State Management**: Redis (in-memory database)
- **Communication**: HTTP/REST with Server-Sent Events (SSE)
- **MCP Server**: Custom FastAPI-based tool server

### Development Tools
- **Model Downloads**: Hugging Face CLI
- **Quantization**: Pre-quantized GGUF models from TheBloke
- **Health Monitoring**: Docker healthchecks with auto-restart
- **Testing**: Bash scripts with end-to-end validation

### Integration Points
- **IDE Support**: Windsurf, Cursor via OpenAI-compatible API
- **Spec-Kit Integration**: Custom commands for workflow triggers
- **CORS**: Cross-origin support for web-based IDEs

## 3. Data Model

### TaskState (Primary State Object)
```python
@dataclass
class TaskState:
    task_id: str
    user_input: str
    current_stage: str  # preprocess, plan, code, review, complete
    preprocessed_text: Optional[str]
    plan: Optional[dict]
    code_iterations: List[dict]
    review_results: List[dict]
    final_output: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    redis_key: str
```

### Agent Communication Formats

#### Planner Output
```json
{
  "task_breakdown": [
    {
      "id": "task_1",
      "description": "Implement JWT authentication",
      "priority": 1,
      "dependencies": [],
      "estimated_complexity": "medium"
    }
  ],
  "codebase_context": {
    "relevant_files": ["auth.py", "models/user.py"],
    "architecture_notes": "Flask app with SQLAlchemy",
    "test_requirements": ["unit tests", "integration tests"]
  }
}
```

#### Coder Output
```json
{
  "iteration": 1,
  "files_modified": [
    {
      "path": "auth.py",
      "diff": "...",
      "reasoning": "Added JWT token generation"
    }
  ],
  "tests_created": ["test_jwt_auth.py"],
  "status": "ready_for_review"
}
```

#### Reviewer Output
```json
{
  "review_status": "approved",
  "issues_found": [],
  "test_results": {
    "passed": 15,
    "failed": 0,
    "coverage": "94%"
  },
  "recommendations": ["Consider rate limiting"],
  "next_iteration": null
}
```

### MCP Tool Specifications
- **read_file**: File content retrieval with path validation
- **analyze_codebase**: Structural analysis and dependency mapping
- **search_docs**: Documentation and comment search
- **find_references**: Symbol and function reference discovery
- **git_diff**: Change tracking and version control
- **run_tests**: Test execution with result capture

## 4. Implementation Phases

### Phase 1: Model Downloads & Configuration ✅ COMPLETED
**Status**: All 4 GGUF models downloaded and configured
- Gemma2-2B-IT Q6_K (1.5GB) 
- Nemotron Nano 8B Q6_K (4GB)
- Devstral 24B Q6_K (14GB) 
- Qwen3-Coder 32B Q6_K (18GB)
- Download script with verification and performance metrics
- Quantization strategy optimized for quality/speed balance

### Phase 2: Agent Intelligence Layer ✅ COMPLETED  
**Status**: All system prompts and intelligence layer implemented
- MAKER prompts for all 4 agents with objectives, tools, constraints
- Agent-specific reasoning patterns and output formats
- Context-aware processing with codebase understanding
- Error handling and iteration protocols

### Phase 3: MCP Server Implementation ✅ COMPLETED
**Status**: FastAPI-based MCP server with all tools
- 6 core tools: read_file, analyze_codebase, search_docs, find_references, git_diff, run_tests
- Security: Path traversal protection, safe file access
- API endpoints: /health, /api/mcp/tools, /api/mcp/tool
- Dockerized with health checks and error handling

### Phase 4: Orchestrator Implementation ✅ COMPLETED
**Status**: Full workflow coordination system
- TaskState dataclass with Redis persistence  
- Agent communication via llama.cpp endpoints
- Streaming support with Server-Sent Events
- MCP integration for live codebase queries
- Complete workflow stages with error handling

### Phase 5: Docker Compose Setup ✅ COMPLETED
**Status**: Production-ready containerized deployment
- 7 services: 4 llama.cpp Metal agents + MCP + Redis + Orchestrator
- Metal optimizations: GGML_METAL=1, --n-gpu-layers 999
- Health checks with auto-restart: restart: unless-stopped
- Volume mounts for models and codebase access
- Performance-tuned context sizes per agent

### Phase 6: API Server & Integration (80% COMPLETE)
**Status**: FastAPI server implemented, spec-kit integration pending
- ✅ REST API with /api/workflow endpoint
- ✅ Streaming SSE response support
- ✅ Task status tracking via /api/task/{task_id}
- ✅ CORS middleware for IDE integration
- ⏳ Spec-kit command integration (/speckit.specify, /speckit.plan, /speckit.implement)
- ⏳ Template updates for new workflow

### Phase 7: Testing & Validation (75% COMPLETE)  
**Status**: Core testing implemented, performance validation pending
- ✅ Health check tests for all services
- ✅ End-to-end workflow validation
- ✅ MCP server tool testing
- ⏳ Performance benchmarks (target: <25s complex refactors)
- ⏳ Load testing with multiple concurrent tasks
- ⏳ Integration testing with Windsurf/Cursor

## 5. Technical Constraints

### Hardware Requirements
- **Minimum**: Apple Silicon M-series chip (Metal support required)
- **Recommended**: M4 Max with 128GB unified memory
- **Storage**: 50GB free space for models
- **Network**: Stable internet for model downloads (one-time)

### Performance Constraints
- **Memory Usage**: Peak 40GB RAM (leaves 88GB headroom on M4 Max 128GB)
- **Context Limits**: 
  - Preprocessor: 8K tokens
  - Planner: 128K tokens  
  - Coder: 128K tokens
  - Reviewer: 256K tokens
- **Iteration Limits**: Max 3 Coder ↔ Reviewer cycles per task
- **Timeout**: 5 minutes per workflow stage

### Quality Constraints
- **Model Quantization**: Q6_K maximum (1-2% quality loss acceptable)
- **Test Coverage**: Minimum 80% for generated code
- **Security**: All file operations sandboxed to project directory
- **Error Handling**: Graceful degradation with informative error messages

### Scalability Constraints  
- **Concurrent Tasks**: Limited by available GPU memory
- **Model Loading**: Hot-swapping not supported (requires restart)
- **Context Growth**: Redis cleanup required for long-running sessions

## 6. Integration Points

### Windsurf/Cursor Integration
**Connection Method**: OpenAI-compatible API endpoint
- **Base URL**: `http://localhost:8080/v1`
- **API Key**: `local` (placeholder for local deployment)
- **Model Name**: Any string (orchestrator handles routing)
- **Protocol**: HTTP with streaming support

**Workflow Trigger**: 
1. User types Cmd+I in IDE with natural language prompt
2. IDE sends request to orchestrator API
3. Orchestrator routes through agent pipeline
4. Streaming response returns to IDE in real-time

### Spec-Kit Integration  
**Command Mappings**:
- `/speckit.specify` → Preprocessor + Planner (requirement analysis)
- `/speckit.plan` → Planner with MCP queries (architecture planning)  
- `/speckit.implement` → Coder + Reviewer loop (implementation)

**Template Updates**:
- Modify existing spec-kit scripts to call orchestrator API
- Preserve existing workflow patterns while adding multi-agent intelligence
- Maintain backward compatibility with single-agent workflows

### MCP Integration
**Tool Categories**:
- **File Operations**: read_file, analyze_codebase
- **Search Operations**: search_docs, find_references  
- **Development Operations**: git_diff, run_tests

**Security Model**:
- Path validation and sanitization
- Project directory sandboxing
- Safe execution environment for tests

## 7. Risk Mitigation

### Technical Risks

#### Model Performance Degradation
**Risk**: Quantized models may produce lower quality output
**Mitigation**: 
- Use Q6_K quantization (only 1-2% quality loss)
- Implement quality monitoring in Reviewer agent
- Fallback to Q8_0 quantization if quality issues detected

#### Memory Exhaustion  
**Risk**: Large models may exceed available GPU memory
**Mitigation**:
- Monitor memory usage with Docker stats
- Implement graceful degradation (reduce context size)
- Auto-restart services on OOM events

#### Metal Context Loss
**Risk**: Apple Silicon may lose Metal context on sleep/wake
**Mitigation**:
- Health checks every 15 seconds
- Auto-restart on failed health checks
- Start period of 60 seconds for initialization

### Operational Risks

#### Service Dependencies
**Risk**: Single point of failure in Redis or MCP server
**Mitigation**:
- Health checks on all critical services
- Auto-restart policies (restart: unless-stopped)
- Fallback mechanisms for temporary service unavailability

#### Model Download Failures
**Risk**: Large model downloads may fail or be corrupted
**Mitigation**:
- Checksum verification in download script
- Retry mechanism with exponential backoff
- Progressive download with resume capability

#### Integration Compatibility
**Risk**: IDE integration may break with updates
**Mitigation**:
- Standard OpenAI API compatibility layer
- Comprehensive API documentation
- Version pinning for critical dependencies

### Performance Risks

#### Latency Degradation
**Risk**: Workflow may become slower than expected
**Mitigation**:
- Performance benchmarks in test suite
- Monitoring and alerting on response times
- Optimization options (context reduction, model swapping)

#### Concurrent Load Issues
**Risk**: Multiple simultaneous tasks may overwhelm system
**Mitigation**:
- Queue-based task management
- Resource monitoring and throttling
- Horizontal scaling options documented

The BreakingWind system addresses these risks through comprehensive monitoring, automatic recovery mechanisms, and careful resource management to ensure reliable operation in production environments.