# Using MAKER with Continue VSCode Extension

The project includes a native Continue configuration that works automatically when you open the project in VSCode.

## Quick Start

1. **Install Continue extension** in VSCode
   - Search for "Continue" in VSCode extensions
   - Install the Continue extension

2. **Open this project** in VSCode
   ```bash
   code /Users/anthonylui/BreakingWind
   ```

3. **Start MAKER services**
   ```bash
   # Start both High and Low mode orchestrators (recommended)
   bash scripts/start-maker.sh all

   # OR start only High mode (needs all 6 models including Reviewer)
   bash scripts/start-maker.sh high

   # OR start only Low mode (5 models, no Reviewer)
   bash scripts/start-maker.sh low
   ```

4. **Open Continue chat** (⌘L or Ctrl+L)
   - You'll see two models available:
     - **MakerCode - High (128GB RAM)** - Uses port 8080
     - **MakerCode - Low (40GB RAM)** - Uses port 8081

5. **Select the model** you want to use and start chatting!
   - Each model connects to its own dedicated orchestrator
   - Switch between modes just by selecting a different model
   - No need to restart services!

## How It Works

The project includes `.continuerc.json` which Continue automatically detects. The two model configurations point to **separate orchestrator instances**:

- **MakerCode - High**: `http://localhost:8080/v1` → High mode orchestrator (uses Reviewer validation)
- **MakerCode - Low**: `http://localhost:8081/v1` → Low mode orchestrator (uses Planner reflection)

**Key benefit**: You can switch modes instantly by selecting a different model in Continue - no need to restart services!

## Running Both Modes Simultaneously

When you start with `bash scripts/start-maker.sh all`, both orchestrators run at the same time:

- Port 8080: High mode orchestrator (uses Reviewer for validation)
- Port 8081: Low mode orchestrator (uses Planner reflection for validation)

Both share the same llama.cpp servers, MCP server, and Redis instance. The only difference is the validation method used.

## Verification

Check that both orchestrators are running:

```bash
# Check High mode orchestrator (port 8080)
docker compose logs orchestrator-high | grep "MAKER Mode"
# You'll see: [Orchestrator] 🎚️  MAKER Mode: HIGH (Reviewer validation, ~128GB RAM)

# Check Low mode orchestrator (port 8081)
docker compose logs orchestrator-low | grep "MAKER Mode"
# You'll see: [Orchestrator] 🎚️  MAKER Mode: LOW (Planner reflection validation, ~40-50GB RAM)

# Test both endpoints
curl http://localhost:8080/health  # High mode
curl http://localhost:8081/health  # Low mode
```

## Example Workflow

### High Mode (Production Quality)

```
You: "Write a user authentication system with JWT tokens"

[PREPROCESSOR] Converted input to: Write a user authentication system...
[PLANNER] Analyzing task with codebase context...
[MAKER] Generating 5 candidates in parallel...
[MAKER] Got 5 candidates, voting (first-to-3)...
[REVIEWER] Validating code...
✓ Code approved!
```

### Low Mode (Fast Development)

```
You: "Write a user authentication system with JWT tokens"

[PREPROCESSOR] Converted input to: Write a user authentication system...
[PLANNER] Analyzing task with codebase context...
[MAKER] Generating 5 candidates in parallel...
[MAKER] Got 5 candidates, voting (first-to-3)...
[PLANNER REFLECTION] Validating code against plan...
✓ Code approved!
```

## Troubleshooting

### Models not appearing in Continue

1. Restart VSCode
2. Check that `.continuerc.json` exists in project root
3. Open Continue settings and verify models are listed

### Connection errors

1. Verify both orchestrators are running:
   ```bash
   curl http://localhost:8080/health  # High mode
   curl http://localhost:8081/health  # Low mode
   ```

2. Verify llama.cpp servers are running:
   ```bash
   for port in 8000 8001 8002 8004 8005; do
     echo -n "Port $port: "
     curl -s http://localhost:$port/health 2>&1 | jq -r '.status // "NOT RUNNING"'
   done
   ```

3. Check orchestrator logs:
   ```bash
   docker compose logs orchestrator-high --tail=50
   docker compose logs orchestrator-low --tail=50
   ```

### Starting/stopping specific modes

```bash
# Stop all services
docker compose down
bash scripts/stop-llama-servers.sh

# Start only what you need
bash scripts/start-maker.sh all   # Both modes (recommended)
bash scripts/start-maker.sh high  # High mode only
bash scripts/start-maker.sh low   # Low mode only
```

## Advanced: Manual Configuration

If you prefer to configure Continue globally (affects all projects), see [docs/CONTINUE_SETUP.md](docs/CONTINUE_SETUP.md) for detailed instructions.

## Benefits

**Native Project Config**:
- ✅ Zero manual configuration needed
- ✅ Works automatically when project is opened
- ✅ Both modes pre-configured and ready
- ✅ Shared with all team members via git
- ✅ Updates automatically when you pull changes

**High Mode (128GB RAM)**:
- Reviewer validation catches subtle bugs
- Security vulnerability detection
- Performance optimization suggestions
- Best for production code

**Low Mode (40GB RAM)**:
- Works on standard development machines
- Planner reflection validates against plan
- ~20% faster than High mode
- Best for development and testing

## See Also

- [docs/MAKER_MODES.md](docs/MAKER_MODES.md) - Detailed mode comparison
- [docs/CONTINUE_SETUP.md](docs/CONTINUE_SETUP.md) - Advanced configuration
- [CLAUDE.md](CLAUDE.md) - Complete MAKER documentation
