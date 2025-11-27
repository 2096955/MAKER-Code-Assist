# Critical Correction: MCP vs OpenAI-Compatible API

## The Issue

The system was incorrectly described as using "MCP (Model Context Protocol)" when it actually implements an **OpenAI-compatible REST API**.

## What Was Wrong

| Component | Incorrectly Labeled As | Actually Is |
|-----------|------------------------|-------------|
| Orchestrator (port 8080) | MCP Server | OpenAI-compatible REST API |
| Codebase Server (port 9001) | MCP Server | FastAPI REST endpoints |
| Protocol | MCP (JSON-RPC 2.0) | HTTP REST |
| Format | MCP messages | OpenAI `/v1/chat/completions` |

## The Reality

### Orchestrator (Port 8080)
- ✅ OpenAI-compatible REST API
- ✅ Endpoints: `/v1/models`, `/v1/chat/completions`
- ✅ Uses HTTP REST, not JSON-RPC 2.0
- ❌ NOT an MCP server

### Codebase Server (Port 9001)
- ✅ FastAPI REST server
- ✅ Endpoints: `/api/mcp/tool`, `/api/mcp/tools`
- ✅ Provides codebase tools via HTTP REST
- ❌ NOT an MCP server (despite naming)

## Correct Configuration

### Windsurf Integration
- **Method**: Configure as OpenAI provider (NOT MCP)
- **Location**: `~/Library/Application Support/Windsurf/User/settings.json`
- **Format**: `windsurf.models` array with `provider: "openai"`
- **Removed**: Incorrect MCP configuration from `mcp_settings.json`

### Why This Matters
- Windsurf MCP expects JSON-RPC 2.0 protocol
- Our system uses HTTP REST (OpenAI format)
- They are incompatible protocols
- Configuration must match the actual protocol

## Terminology Correction

**Before (Incorrect)**:
- "Agentic RAG via MCP"
- "MCP server"
- "MCP tools"

**After (Correct)**:
- "Agentic RAG via Codebase Server REST API"
- "Codebase Server" or "OpenAI-compatible API"
- "Codebase tools via REST API"

## References

- OpenAI API Format: https://platform.openai.com/docs/api-reference
- MCP Protocol: https://modelcontextprotocol.io/
- Windsurf OpenAI Provider: Configure via `windsurf.models` in settings.json
