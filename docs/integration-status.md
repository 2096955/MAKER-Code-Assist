# Integration Status & Setup Guide

## Current Integration Status

###  Working Integrations

#### 1. VS Code / Continue.dev (Recommended)
**Status**:  Configured and ready

**Setup**:
- Extension: Continue.dev (already installed)
- Config: `~/.continue/config.json`
- Model: "Multi-Agent System" → http://localhost:8080/v1

**Usage**:
1. Open VS Code-2
2. Press Cmd+L to open Continue chat
3. Select "Multi-Agent System" from model dropdown
4. Chat with full multi-agent workflow + MAKER voting

**Features**:
- Full code context awareness
- Inline edits (Cmd+I)
- Code selection → right-click → "Continue"
- Streaming responses

#### 2. Open WebUI
**Status**:  Running

**Setup**:
- Docker container: `ghcr.io/open-webui/open-webui:main`
- Access: http://localhost:3000
- First user becomes admin

**Usage**:
1. Open http://localhost:3000
2. Create admin account
3. Settings → Connections → OpenAI
4. Select "multi-agent" model in chat

**Features**:
- Full chat interface
- Model switching
- Conversation history
- Streaming support

#### 3. Direct API
**Status**:  Fully functional

**Usage**:
```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "multi-agent", "messages": [{"role": "user", "content": "Hello"}]}'
```

###  Limited Integration

#### Windsurf / Cascade
**Status**:  MCP tools connected but cannot use as primary model

**Issue**:
- Windsurf Cascade only supports built-in models (SWE-1, Claude, GPT) as primary LLM
- MCP tools are available (6/6 tools connected) but cannot replace the main model
- Cannot route chat requests through orchestrator

**What Works**:
- MCP server connection (green indicator)
- Tool availability (code_task, read_file, etc.)
- Tool invocation (when explicitly requested)

**What Doesn't Work**:
- Using orchestrator as primary chat model
- Automatic routing of chat requests
- Model selection in Cascade Chat

**Workaround**:
- Use Continue.dev in VS Code instead
- Use Open WebUI for web interface
- Use direct API calls

## Configuration Files

### Continue.dev
Location: `~/.continue/config.json`
```json
{
  "models": [
    {
      "title": "Multi-Agent System",
      "provider": "openai",
      "model": "multi-agent",
      "apiBase": "http://localhost:8080/v1",
      "apiKey": "local"
    }
  ]
}
```

### Open WebUI
- Access: http://localhost:3000
- Configure in UI: Settings → Connections → OpenAI
- Base URL: http://localhost:8080/v1
- API Key: local

### Windsurf MCP (Limited)
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
      }
    }
  }
}
```

## Recommendations

1. **For IDE Integration**: Use Continue.dev in VS Code
   - Best code context awareness
   - Inline editing
   - Seamless workflow

2. **For Web Interface**: Use Open WebUI
   - Full chat interface
   - Easy model switching
   - Conversation history

3. **For API Access**: Direct curl/HTTP requests
   - Full control
   - Scripting/automation
   - Testing

## Troubleshooting

### Continue.dev not showing model
- Check `~/.continue/config.json` exists
- Restart VS Code
- Check orchestrator is running: `curl http://localhost:8080/health`

### Open WebUI not accessible
- Check container: `docker ps | grep open-webui`
- Check logs: `docker logs open-webui`
- Verify port 3000 is not in use

### Windsurf MCP tools not working
- This is expected - Windsurf cannot use custom models as primary LLM
- Use Continue.dev or Open WebUI instead
