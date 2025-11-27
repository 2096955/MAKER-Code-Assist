# BreakingWind Constitution

## Core Principles

### PRINCIPLE 1: Local-First Execution
- All inference runs locally on Apple Silicon (M4 Max)
- No cloud API dependencies for core functionality
- Privacy by design - code never leaves the machine

### PRINCIPLE 2: Performance Excellence
- llama.cpp Metal backend mandatory (not vLLM)
- Target: <25 seconds end-to-end for complex refactors
- GGUF Q6_K quantization for optimal speed/quality balance

### PRINCIPLE 3: Agentic RAG via MCP
- No traditional embedding/vector DB approaches
- Live codebase queries via MCP tools
- Agents fetch exactly what they need on-demand

### PRINCIPLE 4: Agent Separation of Concerns
- 4 distinct agents with clear responsibilities
- Preprocessor: multimodal → text
- Planner: task decomposition + MCP queries
- Coder: code generation + testing
- Reviewer: quality gate (max 3 iterations)

### PRINCIPLE 5: Resilience & Auto-Recovery
- Health checks with auto-restart on all services
- Graceful degradation on agent failure
- Redis state persistence across restarts

## Architecture Constraints

**Local Infrastructure Only**
- Apple Silicon M4 Max optimization required
- Metal GPU acceleration mandatory
- No external API dependencies for core workflow

**Performance Standards**
- Sub-25 second response times for complex operations
- Memory-efficient GGUF Q6_K model quantization
- Concurrent agent execution where possible

**Agent Coordination**
- MCP-based tool integration
- Redis for state management and inter-agent communication
- Docker containerization for service isolation

## Development Workflow

**Agent Testing Requirements**
- Each agent must be independently testable
- Integration tests required for agent handoffs
- Performance benchmarks for critical paths

**Quality Gates**
- Maximum 3 reviewer iterations per task
- Automated health checks on all services
- Graceful degradation testing required

**Change Management**
- Constitution changes require performance impact analysis
- All modifications must maintain local-first principle
- Breaking changes need migration path documentation

## Governance

Constitution supersedes implementation convenience

Performance regressions require justification

All agents must be independently testable

**Version**: 1.0.0 | **Ratified**: 2025-11-26