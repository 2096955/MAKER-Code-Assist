# Dual Orchestrator Setup

## Overview

The MAKER system now runs **two separate orchestrator instances** simultaneously, allowing you to instantly switch between High and Low modes just by selecting a different model in Continue.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    llama.cpp Servers                         │
│                  (Native Metal, Shared)                      │
│                                                              │
│  Port 8000: Preprocessor (Gemma2-2B)                        │
│  Port 8001: Planner (Nemotron 8B)                           │
│  Port 8002: Coder (Devstral 24B)                            │
│  Port 8003: Reviewer (Qwen 32B) ← Used by High mode only    │
│  Port 8004: Voter (Qwen2.5-1.5B)                            │
│  Port 8005: GPT-OSS-20B                                      │
└─────────────────────────────────────────────────────────────┘
                          ↑         ↑
                          │         │
         ┌────────────────┘         └────────────────┐
         │                                           │
┌────────┴────────┐                        ┌─────────┴────────┐
│  Orchestrator   │                        │  Orchestrator    │
│   High Mode     │                        │   Low Mode       │
│                 │                        │                  │
│  Port: 8080     │                        │  Port: 8081      │
│  Mode: high     │                        │  Mode: low       │
│  Validation:    │                        │  Validation:     │
│  Reviewer       │                        │  Planner         │
│  (Qwen 32B)     │                        │  Reflection      │
└─────────────────┘                        └──────────────────┘
         ↑                                           ↑
         │                                           │
         └───────────┬───────────────────────────────┘
                     │
         ┌───────────┴────────────┐
         │  Continue Extension    │
         │                        │
         │  Models:               │
         │  • MakerCode - High    │
         │    → http://localhost:8080/v1
         │  • MakerCode - Low     │
         │    → http://localhost:8081/v1
         └────────────────────────┘
```

## How It Works

### Shared Resources

Both orchestrators share:
- **llama.cpp servers** (ports 8000-8005)
- **MCP server** (port 9001) - Codebase tools
- **Redis** (port 6379) - State management
- **Qdrant** (port 6333) - Vector database
- **Phoenix** (port 6006) - Observability

### Different Validation Methods

- **High Mode (port 8080)**: `MAKER_MODE=high`
  - Uses Reviewer (Qwen 32B) for code validation
  - Highest quality, catches subtle bugs
  - Security vulnerability detection
  - Performance optimization suggestions

- **Low Mode (port 8081)**: `MAKER_MODE=low`
  - Uses Planner reflection for validation
  - "Does this code implement my plan?"
  - Faster, uses less resources
  - Reviewer model idle but available

## Benefits

1. **Instant Switching**: Select a different model in Continue - done!
2. **No Restarts**: Both modes ready simultaneously
3. **Resource Efficient**: Models are shared, only validation differs
4. **Flexibility**: Use High for production, Low for development

## Usage in Continue

### Configuration

Both `.continuerc.json` (project config) and `~/.continue/config.json` (global config) now have:

```json
{
  "models": [
    {
      "title": "MakerCode - High (128GB RAM)",
      "apiBase": "http://localhost:8080/v1"
    },
    {
      "title": "MakerCode - Low (40GB RAM)",
      "apiBase": "http://localhost:8081/v1"
    }
  ]
}
```

### Switching Modes

1. Open Continue chat (⌘L / Ctrl+L)
2. Click the model dropdown
3. Select "MakerCode - High" or "MakerCode - Low"
4. Start chatting - you're instantly using that mode!

**No environment variables to change. No services to restart.**

## Starting the System

### Recommended: Both Modes

```bash
bash scripts/start-maker.sh all
```

This starts:
- All 6 llama.cpp models (including Reviewer)
- orchestrator-high on port 8080
- orchestrator-low on port 8081
- All supporting services (MCP, Redis, Qdrant, Phoenix)

### Optional: Single Mode

```bash
# High mode only
bash scripts/start-maker.sh high

# Low mode only
bash scripts/start-maker.sh low
```

## Verification

```bash
# Check both orchestrators
curl http://localhost:8080/health  # High mode
curl http://localhost:8081/health  # Low mode

# Check logs
docker compose logs orchestrator-high | grep "MAKER Mode"
docker compose logs orchestrator-low | grep "MAKER Mode"

# You'll see:
# [Orchestrator] 🎚️  MAKER Mode: HIGH (Reviewer validation, ~128GB RAM)
# [Orchestrator] 🎚️  MAKER Mode: LOW (Planner reflection validation, ~40-50GB RAM)
```

## Docker Compose Changes

The `docker-compose.yml` now defines two services:

```yaml
services:
  orchestrator-high:
    container_name: orchestrator-high
    ports:
      - "8080:8080"
    environment:
      - MAKER_MODE=high
    # ... other config

  orchestrator-low:
    container_name: orchestrator-low
    ports:
      - "8081:8080"  # External 8081 → Internal 8080
    environment:
      - MAKER_MODE=low
    # ... other config
```

## Resource Usage

### RAM Usage

**When running both modes simultaneously:**

- llama.cpp models: ~86GB (shared)
  - Preprocessor: ~4GB
  - Planner: ~10GB
  - Coder: ~30GB
  - Reviewer: ~40GB (used by High, idle in Low)
  - Voter: ~2GB
  - GPT-OSS-20B: ~25GB (optional)

- orchestrator-high: ~2GB
- orchestrator-low: ~2GB
- Supporting services: ~4GB

**Total: ~94GB** (fits in 128GB with room for OS)

### CPU Usage

Both orchestrators can process requests in parallel. If you're:
- Working in High mode → orchestrator-high handles your requests
- Working in Low mode → orchestrator-low handles your requests
- No crosstalk or interference

## Comparison to Old Setup

### Old Setup (Environment Variable Based)

```bash
# Had to manually switch modes
export MAKER_MODE=low
docker compose restart orchestrator

# Wait for restart...
# Now in Low mode

export MAKER_MODE=high
docker compose restart orchestrator

# Wait for restart...
# Now in High mode
```

**Problems:**
- ❌ Required restarting orchestrator
- ❌ Had to remember to change environment variable
- ❌ Couldn't use both modes simultaneously
- ❌ Continue model selection was misleading

### New Setup (Dual Orchestrators)

```
# Both modes always running
# Just select model in Continue dropdown

MakerCode - High → Port 8080 → MAKER_MODE=high
MakerCode - Low  → Port 8081 → MAKER_MODE=low
```

**Benefits:**
- ✅ Instant mode switching in Continue
- ✅ No restarts needed
- ✅ Both modes available simultaneously
- ✅ Continue selection accurately reflects active mode

## Migration Guide

If you were using the old single-orchestrator setup:

1. Stop old services:
   ```bash
   docker compose down
   bash scripts/stop-llama-servers.sh
   ```

2. Update configurations:
   - Continue configs already updated (both `.continuerc.json` and `~/.continue/config.json`)
   - `docker-compose.yml` already has dual orchestrators

3. Start new setup:
   ```bash
   bash scripts/start-maker.sh all
   ```

4. Verify:
   ```bash
   curl http://localhost:8080/health
   curl http://localhost:8081/health
   ```

5. Use in Continue:
   - Select "MakerCode - High" for production work
   - Select "MakerCode - Low" for development/testing

## Troubleshooting

### Only one orchestrator showing in Continue

- Restart VSCode to refresh Continue's model list
- Check `.continuerc.json` exists in project root
- Verify both orchestrators are running: `docker compose ps`

### Can't connect to orchestrator

```bash
# Check if running
docker compose ps | grep orchestrator

# Check logs
docker compose logs orchestrator-high --tail=50
docker compose logs orchestrator-low --tail=50

# Restart if needed
docker compose restart orchestrator-high orchestrator-low
```

### Reviewer not available in Low mode

This is expected. Low mode uses Planner reflection instead of Reviewer to save ~40GB RAM. If you need Reviewer validation, switch to High mode in Continue.

### Both modes using same validation

This was the old problem - fixed now! Each orchestrator has its own `MAKER_MODE` environment variable:
- orchestrator-high: Always uses MAKER_MODE=high (Reviewer)
- orchestrator-low: Always uses MAKER_MODE=low (Planner reflection)

## See Also

- [README_CONTINUE.md](../README_CONTINUE.md) - Quick start guide
- [MAKER_MODES.md](MAKER_MODES.md) - Detailed mode comparison
- [CONTINUE_SETUP.md](CONTINUE_SETUP.md) - Continue configuration
