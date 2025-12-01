# Service Startup Guide for Integration Tests

## Current Status

**Docker is not running** - Docker services cannot be started until Docker Desktop is running.

## Required Services

### 1. Docker Services (via docker-compose)
- Redis (port 6379)
- MCP Server (port 9001)
- Orchestrator API (port 8080)
- Phoenix (port 6006) - optional

### 2. Native Services (via scripts)
- llama.cpp servers (ports 8000-8004)
  - Preprocessor (8000)
  - Planner (8001)
  - Coder (8002)
  - Reviewer (8003)
  - Voter (8004)

## Startup Steps

### Step 1: Start Docker Desktop

```bash
# On macOS, open Docker Desktop application
open -a Docker

# Wait for Docker to be ready
while ! docker info > /dev/null 2>&1; do
  echo "Waiting for Docker..."
  sleep 2
done
echo "Docker is ready"
```

### Step 2: Start Docker Services

```bash
cd /Users/anthonylui/BreakingWind

# Start all Docker services
docker compose up -d

# Wait for services to be healthy
echo "Waiting for services to be healthy..."
sleep 10

# Check status
docker compose ps
```

### Step 3: Start llama.cpp Servers

```bash
cd /Users/anthonylui/BreakingWind

# Start all llama.cpp servers
bash scripts/start-llama-servers.sh

# Wait for servers to initialize (30 seconds)
# Check logs if needed
tail -f logs/llama-*.log
```

### Step 4: Verify All Services

```bash
# Check llama.cpp servers
for port in 8000 8001 8002 8003 8004; do
  curl -s http://localhost:$port/health && echo "✓ Port $port" || echo "✗ Port $port"
done

# Check Redis
redis-cli ping && echo "✓ Redis" || echo "✗ Redis"

# Check MCP Server
curl -s http://localhost:9001/health && echo "✓ MCP Server" || echo "✗ MCP Server"

# Check Orchestrator
curl -s http://localhost:8080/health && echo "✓ Orchestrator" || echo "✗ Orchestrator"
```

## Running Integration Tests

Once all services are running:

```bash
# Quick test (Phase 1)
bash tests/integration_test_suite_1.sh

# Skills test (Phase 2)
bash tests/integration_test_suite_2.sh

# Full test suite
bash tests/run_all_integration_tests.sh
```

## Troubleshooting

### Docker Not Running
- **Error**: `Cannot connect to the Docker daemon`
- **Solution**: Start Docker Desktop application

### llama.cpp Servers Not Starting
- **Error**: `llama-server not found`
- **Solution**: Install llama.cpp via Homebrew: `brew install llama.cpp`

### Models Not Found
- **Error**: `Model not found: models/...`
- **Solution**: Download models using `bash scripts/download-models.sh`

### Port Already in Use
- **Error**: `Address already in use`
- **Solution**: Stop existing services:
  ```bash
  docker compose down
  bash scripts/stop-llama-servers.sh
  ```

## Alternative: Manual Service Startup

If Docker is not available, you can run services manually:

### Redis (Local)
```bash
# Install Redis
brew install redis

# Start Redis
redis-server --daemonize yes
```

### MCP Server (Local)
```bash
# Run MCP server directly (if Python script exists)
python3 orchestrator/mcp_server.py
```

### Orchestrator (Local)
```bash
# Set environment variables
export ENABLE_LONG_RUNNING=true
export ENABLE_SKILLS=true
export WORKSPACE_DIR=./workspace
export SKILLS_DIR=./skills
export REDIS_HOST=localhost
export REDIS_PORT=6379

# Run orchestrator
python3 -m orchestrator.api_server
```

## Next Steps

1. **Start Docker Desktop** (if not running)
2. **Run startup commands** above
3. **Verify all services** are healthy
4. **Run integration tests**

