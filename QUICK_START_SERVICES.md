# Quick Start Services Guide

## The Error You're Seeing

"Connection error" means the Orchestrator API is not running. With the dual-orchestrator setup, you need both:
- High mode orchestrator (port 8080)
- Low mode orchestrator (port 8081)

## Quick Fix (2 Steps)

### Step 1: Start Docker Desktop

```bash
open -a Docker
```

Wait for Docker to fully start (check the Docker icon in menu bar).

### Step 2: Start MAKER System

```bash
cd /Users/anthonylui/BreakingWind

# Start both High and Low mode orchestrators (recommended)
bash scripts/start-maker.sh all

# OR start only High mode
bash scripts/start-maker.sh high

# OR start only Low mode
bash scripts/start-maker.sh low
```

This starts:
- llama.cpp servers (native Metal acceleration)
- Docker services (Redis, MCP Server, Qdrant, Phoenix)
- Orchestrator High (port 8080) - uses Reviewer validation
- Orchestrator Low (port 8081) - uses Planner reflection

## Verify Everything is Running

```bash
# Check all services
./check_services.sh

# Or manually:
curl http://localhost:8080/health  # Orchestrator High
curl http://localhost:8081/health  # Orchestrator Low
curl http://localhost:8000/health  # Preprocessor
redis-cli ping                      # Redis

# Check which mode each orchestrator is using
docker compose logs orchestrator-high | grep "MAKER Mode"
docker compose logs orchestrator-low | grep "MAKER Mode"
```

## If Docker Won't Start

If Docker Desktop won't start, you can run services manually:

### Redis (Local)
```bash
brew install redis
redis-server --daemonize yes
```

### Orchestrator (Local)
```bash
export ENABLE_LONG_RUNNING=true
export ENABLE_SKILLS=true
export REDIS_HOST=localhost
export REDIS_PORT=6379

python3 -m orchestrator.api_server
```

## Troubleshooting

**"Cannot connect to Docker daemon"**
→ Start Docker Desktop: `open -a Docker`

**"Port already in use"**
→ Stop existing services:
```bash
docker compose down
bash scripts/stop-llama-servers.sh
```

**"llama-server not found"**
→ Install llama.cpp:
```bash
brew install llama.cpp
```

**"Models not found"**
→ Download models:
```bash
bash scripts/download-models.sh
```

## One-Command Startup (After Docker is Running)

```bash
# Start everything (both High and Low modes)
bash scripts/start-maker.sh all

# Wait a moment, then verify
sleep 10 && ./check_services.sh
```

