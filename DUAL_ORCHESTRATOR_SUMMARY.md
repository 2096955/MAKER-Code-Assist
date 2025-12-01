# Dual Orchestrator Setup - Summary

## What Changed

You asked: **"But if you do that, can you even switch between the setups?"**

You were right - the original Continue config had both models pointing to the same endpoint (port 8080), making model selection meaningless. The backend mode was still controlled by the `MAKER_MODE` environment variable.

## Solution: Dual Orchestrators

Instead of one orchestrator that switches modes, we now run **two orchestrators simultaneously**:

```
Port 8080: orchestrator-high (MAKER_MODE=high) → Uses Reviewer validation
Port 8081: orchestrator-low (MAKER_MODE=low)  → Uses Planner reflection
```

Both share the same backend:
- llama.cpp models (ports 8000-8005)
- MCP server (port 9001)
- Redis (port 6379)
- Qdrant (port 6333)
- Phoenix (port 6006)

## Continue Configuration

Now the model selection **actually works**:

```json
{
  "models": [
    {
      "title": "MakerCode - High (128GB RAM)",
      "apiBase": "http://localhost:8080/v1"  ← orchestrator-high
    },
    {
      "title": "MakerCode - Low (40GB RAM)",
      "apiBase": "http://localhost:8081/v1"  ← orchestrator-low
    }
  ]
}
```

Select "MakerCode - High" → Requests go to port 8080 → Uses Reviewer
Select "MakerCode - Low" → Requests go to port 8081 → Uses Planner reflection

**No environment variables. No restarts. Just works.**

## How to Use

### Starting

```bash
# Start both modes (recommended)
bash scripts/start-maker.sh all

# Or just High mode
bash scripts/start-maker.sh high

# Or just Low mode
bash scripts/start-maker.sh low
```

### In Continue

1. Open Continue chat (⌘L / Ctrl+L)
2. Click model dropdown
3. Select "MakerCode - High" or "MakerCode - Low"
4. Start chatting

**Switching is instant** - just select a different model!

## Verification

```bash
# Check both are running
curl http://localhost:8080/health  # High mode
curl http://localhost:8081/health  # Low mode

# Check logs
docker compose logs orchestrator-high | grep "MAKER Mode"
# [Orchestrator] 🎚️  MAKER Mode: HIGH (Reviewer validation, ~128GB RAM)

docker compose logs orchestrator-low | grep "MAKER Mode"
# [Orchestrator] 🎚️  MAKER Mode: LOW (Planner reflection validation, ~40-50GB RAM)
```

## Files Updated

### Core Config
- `docker-compose.yml` - Two orchestrator services instead of one
- `.continuerc.json` - Project config with correct ports
- `~/.continue/config.json` - Global config with correct ports

### Documentation
- `README_CONTINUE.md` - Updated quick start
- `CLAUDE.md` - Updated architecture and commands
- `docs/CONTINUE_SETUP.md` - Simplified (no mode switching)
- `docs/DUAL_ORCHESTRATOR_SETUP.md` - Complete architecture guide

### Scripts
- `scripts/start-maker.sh` - New unified startup script

## Benefits

| Old Setup | New Setup |
|-----------|-----------|
| ❌ Select model in Continue (doesn't work) | ✅ Select model in Continue (works!) |
| ❌ Change MAKER_MODE env var | ✅ No env vars to change |
| ❌ Restart orchestrator | ✅ No restarts needed |
| ❌ Wait for restart | ✅ Instant switching |
| ❌ Can't use both modes | ✅ Both modes available |

## Resource Usage

Running both orchestrators simultaneously:
- llama.cpp models: ~86GB (shared between both)
- orchestrator-high: ~2GB
- orchestrator-low: ~2GB
- Supporting services: ~4GB
- **Total: ~94GB** (fits in 128GB with headroom)

Both orchestrators share the models, so there's minimal overhead.

## Next Steps

1. Stop any running services:
   ```bash
   docker compose down
   bash scripts/stop-llama-servers.sh
   ```

2. Start new setup:
   ```bash
   bash scripts/start-maker.sh all
   ```

3. Restart VSCode to refresh Continue

4. Test in Continue:
   - Select "MakerCode - High" → Should use Reviewer
   - Select "MakerCode - Low" → Should use Planner reflection

## Documentation

- [docs/DUAL_ORCHESTRATOR_SETUP.md](docs/DUAL_ORCHESTRATOR_SETUP.md) - Complete architecture
- [README_CONTINUE.md](README_CONTINUE.md) - Quick start guide
- [docs/MAKER_MODES.md](docs/MAKER_MODES.md) - Mode comparison

## Commit

```
feat: Implement dual-orchestrator architecture for instant mode switching
Commit: 9df1c4f
Files: 62 changed, 13,874 insertions(+), 130 deletions(-)
```
