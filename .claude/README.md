# BreakingWind Multi-Agent System

## Quick Status

✅ **FULLY OPERATIONAL** - All services running and tested

## Services

- 5 llama.cpp agents (native Metal, ports 8000-8004)
  - Preprocessor (8000), Planner (8001), Coder (8002), Reviewer (8003), Voter (8004)
- Orchestrator API (port 8080)
- Codebase Server (port 9001)
- Redis (port 6379)

## Features

- **MAKER Voting**: 5 parallel candidates → first-to-3 voting → 97-99% accuracy
- **Multi-Agent Pipeline**: Preprocessor → Planner → Coder → Voter → Reviewer

## Integration

Two methods available:
1. **MCP Server** - For Windsurf/Cascade (stdio, JSON-RPC 2.0)
2. **REST API** - OpenAI-compatible (HTTP, `/v1/chat/completions`)

## Documentation

- `.claude/plan.md` - Current project status
- `plan.plan.md` - Full implementation plan
- `docs/mcp-wrapper-implementation.md` - MCP server details
- `docs/correction-mcp-vs-openai.md` - Protocol clarification

## Quick Start

```bash
# Start services
docker compose up -d
bash scripts/start-llama-servers.sh

# Test
curl http://localhost:8080/health
curl http://localhost:9001/health
```

## Windsurf Setup

1. MCP: Already configured in `mcp_settings.json`
2. OpenAI: Already configured in `settings.json`
3. Restart Windsurf to activate
