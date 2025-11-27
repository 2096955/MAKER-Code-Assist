# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Localised Code Assistant on Apple Silicon** - Applying Cognizant's MAKER (Multi-Agent Knowledge-Enhanced Reasoning) paper to build a local multi-agent coding system optimized for Apple Silicon (M4 Max 128GB) using llama.cpp Metal backend. Four AI agents (Preprocessor, Planner, Coder, Reviewer) with parallel candidate generation and first-to-K voting, orchestrated via FastAPI with Redis state management and MCP-based codebase access.

## Commands

```bash
# Download models (~50GB GGUF files)
bash scripts/download-models.sh

# Start llama.cpp servers natively (Metal acceleration)
bash scripts/start-llama-servers.sh

# Stop llama.cpp servers
bash scripts/stop-llama-servers.sh

# Start Docker services (MCP, Redis, Orchestrator)
docker compose up -d

# Run workflow test
bash tests/test_workflow.sh

# Test health endpoints
curl http://localhost:8080/health

# Test OpenAI-compatible API
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "multi-agent", "messages": [{"role": "user", "content": "Hello"}]}'
```

## Architecture

```
Port 8000: Preprocessor (Gemma2-2B) - Audio/Image → Text
Port 8001: Planner (Nemotron Nano 8B) - Task decomposition, 128K context
Port 8002: Coder (Devstral 24B) - Code generation with MAKER voting
Port 8003: Reviewer (Qwen3-Coder 32B) - Validation, 256K context
Port 8004: Voter (Qwen2.5-1.5B) - MAKER first-to-K voting
Port 8080: Orchestrator API (FastAPI)
Port 9001: MCP Server (Codebase tools)
Port 6379: Redis (State management)
```

Workflow: User → Preprocessor → Planner (with MCP queries) → Coder (MAKER parallel candidates) → Voter → Reviewer → iterate or complete

## Key Files

- `orchestrator/orchestrator.py` - Main workflow logic, MAKER voting, agent coordination
- `orchestrator/api_server.py` - FastAPI REST/OpenAI-compatible API
- `orchestrator/mcp_server.py` - Codebase tools (read_file, analyze_codebase, run_tests)
- `agents/*.md` - Agent system prompts with MAKER objectives
- `docker-compose.yml` - Docker services (MCP, Redis, Orchestrator only; llama.cpp runs native)
- `scripts/start-llama-servers.sh` - Native Metal llama.cpp launcher

## Development Notes

- llama.cpp servers run natively (not Docker) for Metal GPU acceleration
- Models stored in `models/` as GGUF Q6_K quantizations
- Logs in `logs/llama-*.log`
- Agent prompts define MAKER objectives, tools, constraints in `agents/`
- Redis persists task state at `task:{task_id}` keys
- MCP server exposes codebase as tools (no embeddings, live queries)
