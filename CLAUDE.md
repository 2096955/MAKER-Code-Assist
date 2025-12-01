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

# === Start MAKER system ===
# Start both High and Low mode orchestrators (recommended)
bash scripts/start-maker.sh all

# OR start only High mode (needs all 6 models including Reviewer)
bash scripts/start-maker.sh high

# OR start only Low mode (5 models, no Reviewer needed)
bash scripts/start-maker.sh low

# === Stop services ===
docker compose down
bash scripts/stop-llama-servers.sh

# === Test endpoints ===
# High mode (port 8080)
curl http://localhost:8080/health
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "multi-agent", "messages": [{"role": "user", "content": "Hello"}]}'

# Low mode (port 8081)
curl http://localhost:8081/health
curl -X POST http://localhost:8081/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "multi-agent", "messages": [{"role": "user", "content": "Hello"}]}'

# === Monitoring ===
# View llama.cpp logs
tail -f logs/llama-*.log

# View orchestrator logs
docker compose logs orchestrator-high --tail=50
docker compose logs orchestrator-low --tail=50

# Check server health
for port in 8000 8001 8002 8003 8004 8005; do curl -s http://localhost:$port/health; done

# === Phoenix Observability ===
# Access Phoenix UI (evaluations and traces)
open http://localhost:6006

# Or verify Phoenix is running
curl http://localhost:6006/health

# View traces for both modes:
# - High mode traces show Reviewer validation
# - Low mode traces show Planner reflection
# See docs/PHOENIX_OBSERVABILITY.md for complete guide
```

## Architecture

```
# llama.cpp Servers (Native Metal, shared by both orchestrators)
Port 8000: Preprocessor (Gemma2-2B) - Audio/Image → Text
Port 8001: Planner (Nemotron Nano 8B) - Task decomposition
Port 8002: Coder (Devstral 24B) - Code generation with MAKER voting
Port 8003: Reviewer (Qwen Coder 32B) - Validation & testing (used by High mode only)
Port 8004: Voter (Qwen2.5-1.5B) - MAKER first-to-K voting
Port 8005: GPT-OSS-20B (OpenAI open-weight) - Standalone Codex model

# Orchestrators (Docker, separate instances for each mode)
Port 8080: Orchestrator High (MAKER_MODE=high, uses Reviewer for validation)
Port 8081: Orchestrator Low (MAKER_MODE=low, uses Planner reflection for validation)

# Supporting Services
Port 9001: MCP Server (Codebase tools)
Port 6379: Redis (State management, shared)
Port 6333: Qdrant (Vector DB, shared)
Port 6006: Phoenix (Observability, shared)
```

**Workflow (High mode - port 8080)**: User → Preprocessor → Planner (with MCP queries) → Coder (MAKER parallel candidates) → Voter → Reviewer → iterate or complete

**Workflow (Low mode - port 8081)**: User → Preprocessor → Planner (with MCP queries) → Coder (MAKER parallel candidates) → Voter → Planner Reflection → iterate or complete

**Key advantage**: Both orchestrators run simultaneously, sharing the same backend models. Switch between modes instantly in Continue by selecting a different model configuration.

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
