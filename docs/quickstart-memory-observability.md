# Quick Start: EE Memory + Phoenix Observability

## Prerequisites

- Docker and Docker Compose
- Python 3.10+
- M4 Max with 128GB RAM (for local llama.cpp)

## Step 1: Start Phoenix (Observability)

```bash
# Add Phoenix to docker-compose.yml (see updated file)
docker compose up -d phoenix

# Verify Phoenix is running
curl http://localhost:6006/health

# Access Phoenix UI
open http://localhost:6006
```

## Step 2: Install Dependencies

```bash
pip install -r requirements.txt

# Add Phoenix dependencies
pip install opentelemetry-api opentelemetry-sdk \
  opentelemetry-exporter-otlp-proto-http \
  opentelemetry-instrumentation-httpx
```

## Step 3: Initialize EE Memory

```python
# Run once to build melodic lines
python -c "
from orchestrator.ee_memory import HierarchicalMemoryNetwork
hmn = HierarchicalMemoryNetwork(codebase_path='.')
melodic_lines = hmn.detect_melodic_lines(persistence_threshold=0.7)
print(f'Detected {len(melodic_lines)} melodic lines')
"
```

## Step 4: Start Services

```bash
# Start llama.cpp servers (native, not Docker)
bash scripts/start-llama-servers.sh

# Start Docker services (MCP, Redis, Orchestrator, Phoenix)
docker compose up -d

# Verify all services
curl http://localhost:8080/health  # Orchestrator
curl http://localhost:9001/health  # MCP
curl http://localhost:6006/health  # Phoenix
```

## Step 5: Test with Tracing

```python
# Test script with observability
import asyncio
from orchestrator.orchestrator import Orchestrator

async def test():
    orch = Orchestrator()
    
    # This will be traced in Phoenix
    result = await orch.preprocess_input("test_123", "Hello world")
    print(result)

asyncio.run(test())
```

## Step 6: View Traces in Phoenix

1. Open http://localhost:6006
2. Navigate to "Traces" tab
3. Filter by `service.name="maker-orchestrator"`
4. See all agent calls, MAKER voting, memory queries

## Step 7: Run Long-Running Task

```python
# Test long-running workflow (no timeout)
import asyncio
from orchestrator.orchestrator import Orchestrator

async def test_long_running():
    orch = Orchestrator()
    
    large_task = "Refactor authentication system to use OAuth2"
    
    async for chunk in orch.orchestrate_workflow_long_running(
        task_id="long_test",
        user_input=large_task,
        use_trigger=False  # Use local harness
    ):
        print(chunk, end="", flush=True)

asyncio.run(test_long_running())
```

## Verification Checklist

- [ ] Phoenix UI accessible at http://localhost:6006
- [ ] Traces appear in Phoenix for agent calls
- [ ] EE Memory compression ratio > 0.86
- [ ] Long-running tasks complete without timeout
- [ ] Melodic lines detected in codebase
- [ ] Evaluations running in Phoenix

## Troubleshooting

**Phoenix not receiving traces:**
- Check `PHOENIX_ENDPOINT` env var
- Verify port 6006 is accessible
- Check OpenTelemetry exporter logs

**EE Memory not compressing:**
- Run melodic line detection first
- Check `codebase_path` is correct
- Verify codebase has sufficient structure

**Long-running tasks timing out:**
- Ensure `USE_LONG_RUNNING=true`
- Check Trigger.dev config (if using cloud)
- Verify harness config allows no timeout

