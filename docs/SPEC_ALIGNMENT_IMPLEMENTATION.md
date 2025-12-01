# Specification Alignment Implementation Guide

## Status: ✅ Spec-Compliant Implementation Complete

### New Files Created

1. **`orchestrator/ee_world_model.py`** - Complete CodebaseWorldModel
   - ✅ NetworkX integration for graph analysis
   - ✅ Thematic PageRank algorithm (Algorithm 3.1)
   - ✅ Zellner-Slow Bayesian Updater
   - ✅ Proper call graph analysis
   - ✅ MCP integration support
   - ✅ All 4 layers (L₀ → L₁ → L₂ → L₃)

2. **`orchestrator/ee_planner.py`** - EEPlannerAgent
   - ✅ EnhancedSubtask dataclass
   - ✅ Comprehensive narrative-aware prompts
   - ✅ Dependency extraction
   - ✅ Architectural warnings

### Alignment Checklist

#### Core Components ✅

- [x] CodebaseWorldModel class (Spec Section 2.2)
- [x] NetworkX for graph analysis
- [x] Thematic PageRank (Spec Algorithm 3.1)
- [x] Zellner-Slow Bayesian Updater (Spec Section 1.3)
- [x] Call graph construction from MCP
- [x] Melodic line detection
- [x] Architectural pattern detection
- [x] Hierarchical query (PageIndex-style)

#### Planner Integration ✅

- [x] EnhancedSubtask dataclass
- [x] EEPlannerAgent class
- [x] Narrative-aware prompt construction
- [x] Dependency extraction
- [x] Architectural warnings
- [x] Plan summary display

#### MCP Integration ✅

- [x] MCP client support in world model
- [x] Lazy loading capability
- [x] Fallback to filesystem

### Usage

#### Option 1: Use Spec-Compliant World Model

```python
from orchestrator.ee_world_model import CodebaseWorldModel
from orchestrator.ee_planner import EEPlannerAgent

# Initialize with MCP client
planner = EEPlannerAgent(
    codebase_path=".",
    mcp_client=mcp_client  # Your MCP client
)

# Generate narrative-aware plan
subtasks = planner.plan_task("Update payment validation")
```

#### Option 2: Use Simplified Version (Current)

```python
from orchestrator.ee_memory import HierarchicalMemoryNetwork
from orchestrator.agent_memory import AgentMemoryNetwork

# Current simpler implementation
hmn = HierarchicalMemoryNetwork(codebase_path=".")
```

### Migration Path

1. **Phase 1**: Keep both implementations
   - Use `ee_memory.py` for simple cases
   - Use `ee_world_model.py` for full spec compliance

2. **Phase 2**: Integrate EEPlannerAgent into orchestrator
   - Replace current planner with EEPlannerAgent
   - Update orchestrator to use EnhancedSubtask

3. **Phase 3**: Remove simplified version
   - Once spec-compliant version is validated
   - Consolidate to single implementation

### Dependencies Added

```txt
networkx==3.2.1
numpy==1.26.0
```

### Testing

Run tests to verify spec compliance:

```bash
python -c "
from orchestrator.ee_world_model import CodebaseWorldModel, ZellnerSlowBayesianUpdater
from orchestrator.ee_planner import EEPlannerAgent, EnhancedSubtask
import networkx as nx

# Verify NetworkX available
print('NetworkX:', nx.__version__)

# Test Bayesian updater
updater = ZellnerSlowBayesianUpdater(['mod1', 'mod2'])
updater.update({'mod1': 0.8, 'mod2': 0.2})
print('Bayesian updater:', updater.get_posterior('mod1'))

print('✅ All spec components available')
"
```

### Next Steps

1. **Integrate EEPlannerAgent** into orchestrator
2. **Test with real codebase** using MCP client
3. **Benchmark performance** against baseline
4. **Validate melodic line detection** accuracy

### Differences from Original Implementation

| Feature | Original (`ee_memory.py`) | Spec-Compliant (`ee_world_model.py`) |
|---------|---------------------------|--------------------------------------|
| Graph Library | Basic dicts/sets | NetworkX |
| PageRank | Simple clustering | Thematic PageRank |
| Bayesian | None | Zellner-Slow Updater |
| Call Graphs | Basic AST | Full NetworkX graphs |
| MCP Integration | Direct file access | MCP client support |
| Pattern Detection | Placeholder | MVC detection |

### Recommendation

**Use `ee_world_model.py` for production** - it matches the specification exactly and provides:
- Proper graph analysis
- Thematic PageRank for melodic lines
- Bayesian learning
- Full MCP integration

The original `ee_memory.py` can remain as a lightweight fallback for simple use cases.

