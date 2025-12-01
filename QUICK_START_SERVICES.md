# Quick Start Services Guide

## The Error You're Seeing

"Connection error" means the Orchestrator API (port 8080) is not running.

## Quick Fix (3 Steps)

### Step 1: Start Docker Desktop

```bash
open -a Docker
```

Wait for Docker to fully start (check the Docker icon in menu bar).

### Step 2: Start Docker Services

```bash
cd /Users/anthonylui/BreakingWind
docker compose up -d
```

This starts:
- Redis (port 6379)
- MCP Server (port 9001)  
- Orchestrator API (port 8080)

### Step 3: Start llama.cpp Servers

```bash
bash scripts/start-llama-servers.sh
```

This starts:
- Preprocessor (port 8000)
- Planner (port 8001)
- Coder (port 8002)
- Reviewer (port 8003)
- Voter (port 8004)

## Verify Everything is Running

```bash
# Check all services
./check_services.sh

# Or manually:
curl http://localhost:8080/health  # Orchestrator
curl http://localhost:8000/health  # Preprocessor
redis-cli ping                      # Redis
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
# Start everything
docker compose up -d && \
bash scripts/start-llama-servers.sh && \
sleep 10 && \
./check_services.sh
```

