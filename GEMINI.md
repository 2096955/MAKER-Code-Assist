# Project Overview

This project is a **production-ready multi-agent coding system** optimized specifically for **Apple Silicon (M4 Max)**. It utilizes the `llama.cpp` Metal backend to achieve 2-3x faster inference than vLLM, enabling a local swarm of AI agents to plan, code, and review software tasks.

**Key Optimizations (from Implementation Plan):**
*   **Inference Engine:** `llama.cpp` with Metal backend (Native GPU acceleration).
*   **Context:** Agentic RAG via MCP (Live codebase queries instead of static embeddings).
*   **Architecture:** Parallel agent execution with Redis-based state management.

# System Architecture

The system consists of four specialized AI agents orchestrated by a central Python service:

1.  **Preprocessor (Gemma2-2B):** Handles multimodal input (Audio/Image) and converts it to text.
2.  **Planner (Nemotron Nano 8B):** Decomposes complex requests into atomic sub-tasks using MCP tools to analyze the codebase.
3.  **Coder (Devstral 24B):** Generates production-ready code implementation (optimized for SWE-Bench performance).
4.  **Reviewer (Qwen3-Coder 32B):** Acts as a quality gate, running tests and checking for security/style issues before approval.

**Supporting Services:**
*   **Orchestrator:** FastAPI Python service managing the workflow loop and agent communication.
*   **MCP Server:** Exposes the codebase as "tools" (read_file, run_tests, etc.) to the agents.
*   **Redis:** Persists task state, conversation history, and agent iteration tracking.

# Building and Running

**1. Download Models (GGUF Q6_K):**
```bash
bash scripts/download-models.sh
```

**2. Start the Swarm:**
```bash
docker compose up -d
```
*Wait ~60s for health checks to pass and models to load into Metal context.*

**3. Run Verification:**
```bash
bash tests/test_workflow.sh
```

# Development Conventions

*   **Reference Plan:** See `multi-agent-system-implementation.plan.md` for the detailed architectural blueprint.
*   **Containerization:** All services are Dockerized; `docker-compose.yml` handles networking and volume mounts.
*   **State Management:** Redis is the source of truth for task progress; do not rely on in-memory variable persistence across restarts.
*   **Agent Prompts:** System prompts are defined in `prompts/*.md` and include specific "MAKER" objectives and constraints.
*   **Tools:** Agents interact with the system via the MCP Server (`orchestrator/mcp_server.py`); new tools should be added there.