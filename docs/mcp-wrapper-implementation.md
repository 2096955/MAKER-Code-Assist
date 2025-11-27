# MCP Wrapper Implementation

## Overview

Claude created a proper MCP (Model Context Protocol) server wrapper for the multi-agent orchestrator. This allows Windsurf to connect to the system via the standard MCP protocol (JSON-RPC 2.0 over stdio), rather than just the OpenAI-compatible REST API.

## What Was Created

### File: `orchestrator/mcp_wrapper.py`

A true MCP server that:
- Uses JSON-RPC 2.0 protocol over stdio transport
- Wraps the orchestrator's functionality
- Exposes tools that Windsurf can call via MCP

### Tools Exposed

1. **code_task** - Submit coding tasks to the multi-agent system
   - Triggers the full Preprocessor → Planner → Coder → Reviewer pipeline
   
2. **read_file** - Read files from codebase
   - Accesses the codebase server's read_file functionality

3. **analyze_codebase** - Get codebase structure
   - Returns file counts, languages, directories, key files

4. **find_references** - Find symbol references
   - AST-based search for Python, regex for other languages

5. **search_docs** - Search documentation
   - Searches markdown/docs files for relevant content

6. **git_diff** - Get git changes
   - Shows recent changes in the codebase

7. **run_tests** - Execute test suite
   - Runs pytest or npm test

## Configuration

### Windsurf MCP Settings

Location: `~/Library/Application Support/Windsurf/User/globalStorage/kilocode.kilo-code/settings/mcp_settings.json`

```json
{
  "mcpServers": {
    "multi-agent": {
      "command": "python",
      "args": ["-m", "orchestrator.mcp_wrapper"],
      "cwd": "/Users/anthonylui/BreakingWind",
      "env": {
        "PYTHONPATH": "/Users/anthonylui/BreakingWind"
      },
      "description": "Multi-agent coding system with Preprocessor, Planner, Coder, and Reviewer agents"
    }
  }
}
```

### Dependencies

Added to `requirements.txt`:
```
mcp>=1.0.0
```

## Architecture

```
Windsurf (MCP Client)
    ↓
stdio transport (JSON-RPC 2.0)
    ↓
orchestrator/mcp_wrapper.py (MCP Server)
    ↓
orchestrator/orchestrator.py (Multi-Agent Logic)
    ↓
llama.cpp servers (ports 8000-8003)
```

## Usage

1. **Restart Windsurf** to load the MCP configuration
2. **Open Cascade Chat** (Cmd+I)
3. **MCP server should appear** in the MCP Marketplace or be active
4. **Use tools** like:
   - "Use the multi-agent system to refactor auth.py"
   - "Analyze the codebase structure"
   - "Find all references to User class"

## Differences from REST API

| Aspect | REST API (port 8080) | MCP Server (stdio) |
|--------|---------------------|---------------------|
| Protocol | HTTP REST | JSON-RPC 2.0 |
| Transport | HTTP/TCP | stdio |
| Format | OpenAI-compatible | MCP protocol |
| Use Case | Direct API calls | Windsurf/Cascade integration |
| Endpoints | `/v1/chat/completions` | MCP tools |

## Status

- ✅ MCP wrapper created
- ✅ Windsurf configuration updated
- ✅ Dependencies added
- ✅ Import tested successfully
- ⏳ Awaiting Windsurf restart and testing

## References

- MCP Specification: https://spec.modelcontextprotocol.io/
- Based on pattern from existing MCP servers (e.g., EmailMCP)
