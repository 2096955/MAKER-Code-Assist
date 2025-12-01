# Quick Start: Testing EE Planner

## Prerequisites

```bash
# Ensure dependencies installed
pip install -r requirements.txt

# Verify NetworkX and NumPy
python -c "import networkx; import numpy; print('✓ Dependencies OK')"
```

## Start Services

```bash
# Start all services (including Phoenix)
docker compose up -d

# Verify services
curl http://localhost:8080/health  # Orchestrator
curl http://localhost:9001/health  # MCP
curl http://localhost:6006/health  # Phoenix (if available)
```

## Test EE Planner

### Basic Test

```bash
curl -X POST http://localhost:8080/api/workflow \
  -H "Content-Type: application/json" \
  -d '{"input": "Add error handling to payment processing", "stream": false}'
```

### Expected Output

You should see:
```
[PLANNER] Using EE Planner (narrative-aware)...
[EE PLANNER] Generated X subtasks with narrative awareness
[EE PLANNER] Preserving Y business narratives
[EE PLANNER] Average confidence: 0.XX
```

### Verify EE Mode

```python
from orchestrator.orchestrator import Orchestrator

orch = Orchestrator()
print(f"EE Mode: {orch.ee_mode}")
print(f"EE Planner: {orch._get_ee_planner() is not None}")
```

## Troubleshooting

### EE Planner Not Initializing

**Check MCP server:**
```bash
curl http://localhost:9001/health
```

**Check logs:**
```bash
docker logs orchestrator | grep "EE Planner"
```

**Fallback to standard planner:**
- Set `EE_MODE=false` if EE fails
- System automatically falls back

### No Melodic Lines Detected

**Possible causes:**
- Codebase too small (< 3 modules)
- No call graph connections
- Files not indexed

**Check world model:**
```python
from orchestrator.ee_world_model import CodebaseWorldModel
from orchestrator.mcp_client_wrapper import MCPClientWrapper

mcp = MCPClientWrapper()
world_model = CodebaseWorldModel(".", mcp_client=mcp)
print(f"Modules: {len(world_model.L1_module_registry)}")
print(f"Melodic lines: {len(world_model.L3_melodic_lines)}")
```

### Performance Issues

**Reduce limits:**
```bash
EE_MAX_FILES=50
EE_MAX_FILE_SIZE=500000
```

**Check initialization time:**
- Should be 5-30 seconds
- Large codebases may take longer

## Next Steps

1. **Test with your codebase** - See if melodic lines are detected
2. **Monitor logs** - Check for any errors
3. **Tune parameters** - Adjust persistence thresholds if needed
4. **Report issues** - Document any problems encountered

---

**Ready to test!** The EE Planner is integrated and operational.

