# Continue (VSCode Extension) Setup for MAKER

This guide shows how to use MAKER with the Continue VSCode extension in both High and Low modes.

## Prerequisites

1. Install Continue extension in VSCode
2. MAKER system running (orchestrator + llama.cpp servers)

## Configuration

### Option 1: Continue config.json (Recommended)

Create or edit `~/.continue/config.json`:

```json
{
  "models": [
    {
      "title": "MakerCode - High (128GB RAM)",
      "provider": "openai",
      "model": "multi-agent",
      "apiBase": "http://localhost:8080/v1",
      "apiKey": "local",
      "description": "All 6 models, Reviewer validation, highest quality"
    },
    {
      "title": "MakerCode - Low (40GB RAM)",
      "provider": "openai",
      "model": "multi-agent",
      "apiBase": "http://localhost:8080/v1",
      "apiKey": "local",
      "description": "5 models, Planner reflection, works on 40GB RAM"
    }
  ],
  "contextProviders": [
    {
      "name": "code",
      "params": {}
    },
    {
      "name": "codebase",
      "params": {}
    }
  ]
}
```

**To switch modes:**

1. Stop current services:
```bash
bash scripts/stop-llama-servers.sh
docker compose down
```

2. Set mode and restart:
```bash
# For High mode (128GB RAM)
export MAKER_MODE=high
bash scripts/start-llama-servers.sh
docker compose up -d

# OR for Low mode (40GB RAM)
export MAKER_MODE=low
bash scripts/start-llama-servers.sh
docker compose up -d
```

3. In Continue, select the model that matches your mode
4. The orchestrator will automatically use the correct validation method

### Option 2: Environment Variable in docker-compose.yml

Edit `docker-compose.yml`:

```yaml
services:
  orchestrator:
    environment:
      # Change this line:
      - MAKER_MODE=low  # or high
```

Then:
```bash
bash scripts/stop-llama-servers.sh
export MAKER_MODE=low  # Must match docker-compose.yml
bash scripts/start-llama-servers.sh
docker compose up -d
```

## Verification

Check that the correct mode is active:

```bash
# Check which models are running
for port in 8000 8001 8002 8003 8004 8005; do
  echo -n "Port $port: "
  curl -s http://localhost:$port/health 2>&1 | jq -r '.status // "NOT RUNNING"'
done

# Expected in High mode:
# Port 8000: ok (Preprocessor)
# Port 8001: ok (Planner)
# Port 8002: ok (Coder)
# Port 8003: ok (Reviewer)
# Port 8004: ok (Voter)
# Port 8005: ok (GPT-OSS)

# Expected in Low mode:
# Port 8000: ok (Preprocessor)
# Port 8001: ok (Planner)
# Port 8002: ok (Coder)
# Port 8003: NOT RUNNING (Reviewer skipped)
# Port 8004: ok (Voter)
# Port 8005: ok (GPT-OSS)

# Check orchestrator logs for mode
docker compose logs orchestrator | grep "MAKER_MODE\|Planner Reflection\|Reviewer"
```

## Using MAKER in Continue

### High Mode Workflow

When you ask MAKER to write code in High mode, you'll see:

```
[PREPROCESSOR] Converted input to: <your request>
[PLANNER] Analyzing task with codebase context...
[MAKER] Generating 5 candidates in parallel...
[MAKER] Got 5 candidates, voting (first-to-3)...
[REVIEWER] Validating code...           ← Qwen 32B validates
✓ Code approved!
```

### Low Mode Workflow

When you ask MAKER to write code in Low mode, you'll see:

```
[PREPROCESSOR] Converted input to: <your request>
[PLANNER] Analyzing task with codebase context...
[MAKER] Generating 5 candidates in parallel...
[MAKER] Got 5 candidates, voting (first-to-3)...
[PLANNER REFLECTION] Validating code against plan...  ← Planner validates
✓ Code approved!
```

## Quality Comparison

| Aspect | High Mode | Low Mode |
|--------|-----------|----------|
| **Validation** | Reviewer (Qwen 32B) | Planner Reflection (Nemotron 8B) |
| **Quality** | Highest | Good |
| **Speed** | Slower | ~20% faster |
| **RAM** | 128GB | 40-50GB |
| **Best For** | Production code | Development/testing |

## Troubleshooting

### "Connection refused" error

- Check if orchestrator is running: `curl http://localhost:8080/health`
- Check if llama.cpp servers are running: See verification section above
- Restart services if needed

### Wrong mode being used

1. Check environment variable:
```bash
echo $MAKER_MODE
```

2. Check docker-compose.yml matches:
```bash
grep MAKER_MODE docker-compose.yml
```

3. Ensure both are set to same value (high or low)

4. Restart orchestrator:
```bash
docker compose restart orchestrator
```

### Reviewer timeout in High mode

- You may be in Low mode but system is trying to use Reviewer
- Verify Reviewer is running: `curl http://localhost:8003/health`
- If not running, restart in High mode:
```bash
export MAKER_MODE=high
bash scripts/stop-llama-servers.sh
bash scripts/start-llama-servers.sh
docker compose restart orchestrator
```

## Tips

1. **Start in Low mode** for faster iteration during development
2. **Switch to High mode** before committing production code
3. **Keep llama.cpp servers running** between mode switches if possible
4. **Monitor RAM usage** with Activity Monitor / `top`
5. **Check logs** if behavior seems wrong: `docker compose logs orchestrator -f`

## Example: Complete Setup

```bash
# 1. Choose your mode
export MAKER_MODE=low  # or high

# 2. Start llama.cpp servers
bash scripts/start-llama-servers.sh

# Output shows:
# 🎚️  MAKER_MODE: low
#    Low mode: Skipping Reviewer (uses Planner reflection instead)
#    RAM requirement: ~40-50GB (vs 128GB in High mode)

# 3. Start orchestrator
docker compose up -d

# 4. Verify
curl http://localhost:8080/health

# 5. Open VSCode with Continue extension

# 6. In Continue chat, select "MakerCode - Low (40GB RAM)"

# 7. Start coding!
```

## Advanced: Programmatic Mode Switching

If you want to switch modes programmatically:

```bash
#!/bin/bash
# switch_maker_mode.sh

MODE=${1:-high}  # Default to high if no argument

echo "Switching to MAKER $MODE mode..."

# Stop services
bash scripts/stop-llama-servers.sh
docker compose down

# Set environment
export MAKER_MODE=$MODE

# Start services
bash scripts/start-llama-servers.sh
docker compose up -d

echo "MAKER $MODE mode active"
```

Usage:
```bash
./switch_maker_mode.sh low   # Switch to Low mode
./switch_maker_mode.sh high  # Switch to High mode
```
