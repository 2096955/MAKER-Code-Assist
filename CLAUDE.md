# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Localised Code Assistant on Apple Silicon** - Applying Cognizant's MAKER (Multi-Agent Knowledge-Enhanced Reasoning) paper to build a local multi-agent coding system optimized for Apple Silicon (M4 Max 128GB) using llama.cpp Metal backend. Five AI agents (Preprocessor, Planner, Coder, Voter, Reviewer) with parallel candidate generation and first-to-K voting, orchestrated via FastAPI with Redis state management and MCP-based codebase access.

## MAKER Modes

The system supports two modes for different RAM configurations:

- **MakerCode - High** (default): All 6 models, ~128GB RAM, highest quality
- **MakerCode - Low**: 5 models (no Reviewer), ~40-50GB RAM, Planner reflection validation

See [docs/MAKER_MODES.md](docs/MAKER_MODES.md) for detailed comparison.

## Commands

```bash
# Download models (~50GB GGUF files)
bash scripts/download-models.sh

# === MakerCode - High Mode (default, needs 128GB RAM) ===
export MAKER_MODE=high
bash scripts/start-llama-servers.sh  # Starts all 6 models including Reviewer
docker compose up -d

# === MakerCode - Low Mode (works on 40GB RAM) ===
export MAKER_MODE=low
bash scripts/start-llama-servers.sh  # Starts 5 models, skips Reviewer
docker compose restart orchestrator  # Uses Planner reflection instead

# === Switch modes (stop → change → restart) ===
bash scripts/stop-llama-servers.sh
export MAKER_MODE=low  # or high
bash scripts/start-llama-servers.sh
docker compose restart orchestrator

# === Standard operations ===
# Stop llama.cpp servers
bash scripts/stop-llama-servers.sh

# Run workflow test
bash tests/test_workflow.sh

# Test health endpoints
curl http://localhost:8080/health

# Test OpenAI-compatible API
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "multi-agent", "messages": [{"role": "user", "content": "Hello"}]}'

# View llama.cpp logs
tail -f logs/llama-*.log

# Check server health individually
for port in 8000 8001 8002 8003 8004; do curl -s http://localhost:$port/health; done
```

## Architecture

```
# MakerCode - High Mode (all 6 models, ~128GB RAM)
Port 8000: Preprocessor (Gemma2-2B) - Audio/Image → Text
Port 8001: Planner (Nemotron Nano 8B) - Task decomposition
Port 8002: Coder (Devstral 24B) - Code generation with MAKER voting
Port 8003: Reviewer (Qwen Coder 32B) - Validation & testing
Port 8004: Voter (Qwen2.5-1.5B) - MAKER first-to-K voting
Port 8005: GPT-OSS-20B (OpenAI open-weight) - Standalone Codex model

# MakerCode - Low Mode (5 models, ~40-50GB RAM)
Port 8000: Preprocessor (Gemma2-2B) - Audio/Image → Text
Port 8001: Planner (Nemotron Nano 8B) - Task decomposition + reflection validation
Port 8002: Coder (Devstral 24B) - Code generation with MAKER voting
Port 8003: (skipped) - Planner handles validation via reflection
Port 8004: Voter (Qwen2.5-1.5B) - MAKER first-to-K voting
Port 8005: GPT-OSS-20B (OpenAI open-weight) - Standalone Codex model

# Supporting Services
Port 8080: Orchestrator API (FastAPI)
Port 9001: MCP Server (Codebase tools)
Port 6379: Redis (State management)
```

Workflow (High mode): User → Preprocessor → Planner (with MCP queries) → Coder (MAKER parallel candidates) → Voter → Reviewer → iterate or complete

Workflow (Low mode): User → Preprocessor → Planner (with MCP queries) → Coder (MAKER parallel candidates) → Voter → Planner Reflection → iterate or complete

## Key Files

- `orchestrator/orchestrator.py` - Main workflow logic, MAKER voting, agent coordination
- `orchestrator/api_server.py` - FastAPI REST/OpenAI-compatible API
- `orchestrator/mcp_server.py` - Codebase tools (read_file, analyze_codebase, run_tests)
- `agents/*.md` - Agent system prompts with MAKER objectives
- `docker-compose.yml` - Docker services (MCP, Redis, Orchestrator only; llama.cpp runs native)
- `scripts/start-llama-servers.sh` - Native Metal llama.cpp launcher

## MAKER Voting Implementation

The orchestrator implements MAKER's parallel candidate generation and first-to-K voting:
- `generate_candidates()` - Spawns N parallel requests to Coder with varying temperatures (0.3-0.7)
- `maker_vote()` - Runs 2K-1 voter instances, first candidate to K votes wins
- Environment vars: `MAKER_NUM_CANDIDATES=5`, `MAKER_VOTE_K=3`

## Context Compression

Hierarchical context compression with sliding window (like Claude):
- **Recent messages** - kept in full within `RECENT_WINDOW_TOKENS` limit
- **Older messages** - automatically summarized by Preprocessor (Gemma2-2B)
- **Auto-eviction** - oldest content compressed when approaching `MAX_CONTEXT_TOKENS`

Environment vars:
- `MAX_CONTEXT_TOKENS=32000` - Total context budget
- `RECENT_WINDOW_TOKENS=8000` - Recent messages kept in full
- `SUMMARY_CHUNK_SIZE=4000` - Chunk size for summarization

Key methods in `ContextCompressor`:
- `add_message()` - Add message to conversation history
- `compress_if_needed()` - Trigger compression when context exceeds limits
- `get_context()` - Get compressed context string for agents
- `get_stats()` - Returns compression ratio and token counts
- `set_compact_instructions()` - Custom summarization instructions

## Session Management API

```bash
# List saved sessions
curl http://localhost:8080/api/sessions

# Get context stats for session (like /context)
curl http://localhost:8080/api/context/{session_id}

# Resume a saved session (like --continue)
curl -X POST http://localhost:8080/api/session/{session_id}/resume

# Save current session
curl -X POST http://localhost:8080/api/session/{session_id}/save

# Clear session context (like /clear)
curl -X POST http://localhost:8080/api/clear/{session_id}

# Compact with custom instructions (like /compact)
curl -X POST http://localhost:8080/api/compact \
  -H "Content-Type: application/json" \
  -d '{"session_id": "xxx", "instructions": "Keep only code and decisions"}'
```

Sessions persist to Redis with 24h TTL.

## Development Notes

- llama.cpp servers run natively (not Docker) for Metal GPU acceleration
- Models stored in `models/` as GGUF Q6_K quantizations
- Logs in `logs/llama-*.log`
- Agent prompts define MAKER objectives, tools, constraints in `agents/`
- Redis persists task state at `task:{task_id}` keys
- MCP server exposes codebase as tools (no embeddings, live queries)
- Orchestrator uses `host.docker.internal` to reach native llama.cpp servers from Docker
