# Changelog

All notable changes to the MAKER multi-agent coding system will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed - Code Quality (January 2026)

- Replace all `print()` statements with proper `logging` module usage across orchestrator
- Replace bare `except:` clauses with specific exception types (OSError, IOError, etc.)
- Remove all emoji characters from Python source files (replaced with text markers)
- Add `logging` imports and logger initialization to files missing them

**Files affected**: orchestrator.py, mcp_server.py, ee_planner.py, ee_world_model.py, rag_service.py, api_server.py, hybrid_search.py, agent_memory_enhanced.py, checkpoint_manager.py, code_verifier.py, skill_extractor.py

### Added - Melodic Line Memory & Collective Brain (December 2025)

**Major Intelligence Upgrade**: Added Kùzu-based melodic line memory and multi-agent collective brain for coherent reasoning and consensus.

#### Melodic Line Memory (Kùzu Graph Database)

**Problem Solved**: Agents were operating sequentially without shared context. By the time Reviewer ran, it didn't know what Preprocessor understood or why Planner chose certain subtasks.

**Solution**: Kùzu graph database where each agent writes its reasoning. Later agents read the full reasoning chain (the "melodic line") to maintain coherent intent.

**How It Works**:
1. Preprocessor writes: "Detected security requirement in user request"
2. Planner reads Preprocessor's reasoning → writes: "Based on security focus, planning JWT implementation"
3. Coder reads BOTH → writes: "Implementing secure JWT as planned"
4. Reviewer reads ENTIRE chain → validates against original intent

**Files**:
- `orchestrator/kuzu_memory.py` - SharedWorkflowMemory implementation
- `docker-compose.yml` - Added persistent Kùzu database volumes

**Enable/Disable**: Set `ENABLE_MELODIC_MEMORY=true/false` in environment

#### Collective Brain (Multi-Agent Consensus)

**Problem Solved**: Single-agent answers miss other perspectives. Complex questions (architecture, design, security) benefit from multiple expert viewpoints.

**Solution**: For complex questions, consult multiple agents in parallel and synthesize their answers.

**Expert Panels by Problem Type**:
- **Architecture**: Planner (strategy) + Coder (implementation) + Reviewer (quality)
- **Debugging**: Coder (code knowledge) + Reviewer (security/testing)
- **Planning**: Preprocessor (understanding) + Planner (dependencies)
- **Security**: Reviewer (audit) + Coder (implementation knowledge)

**Output Format**:
- **Consensus**: Synthesized answer from all agents
- **Perspectives**: Individual agent views with confidence scores
- **Dissenting Opinions**: Important disagreements flagged

**Files**:
- `orchestrator/collective_brain.py` - CollectiveBrain implementation
- `orchestrator/orchestrator.py` - Integration into question-answering workflow

#### Phoenix Evaluations Framework

**Purpose**: Quantitative validation that melodic memory and collective brain actually work (data-driven metrics, not just intuition).

**Evaluation Experiments**:

1. **Melodic Memory A/B Test**
   - Control: Agents WITHOUT melodic line memory
   - Treatment: Agents WITH melodic line memory
   - Metrics: QA correctness lift, hallucination reduction, relevance improvement

2. **Collective Brain A/B Test**
   - Control: Single-agent answers (Preprocessor only)
   - Treatment: Multi-agent consensus
   - Metrics: Answer quality, trade-off coverage, consensus confidence

3. **SWE-bench Evaluation**
   - Test code generation on real GitHub issues
   - Validate with Playwright code execution
   - Metrics: Patch correctness, test pass rate, execution errors

**LLM-as-Judge Evaluators**:
- **HallucinationEvaluator**: Detects unsupported claims
- **QAEvaluator**: Measures answer correctness vs reference
- **RelevanceEvaluator**: Checks if response is on-topic

**Files**:
- `tests/phoenix_evaluator.py` - Evaluation harness
- `docs/PHOENIX_EVALUATIONS.md` - Complete usage guide

**Usage**:
```bash
# Run melodic memory A/B test
python tests/phoenix_evaluator.py --experiment melodic_memory_ab

# Run collective brain A/B test
python tests/phoenix_evaluator.py --experiment collective_brain_ab

# Run SWE-bench evaluation (10 instances)
python tests/phoenix_evaluator.py --experiment swe_bench --num_instances 10
```

**View Results**: http://localhost:6006 (Phoenix UI)

#### Dependencies Added
- `kuzu==0.6.0` - Graph database for melodic line memory
- `arize-phoenix==4.33.0` - Observability platform
- `arize-phoenix-evals==0.17.0` - LLM evaluation framework
- `playwright==1.48.0` - Code execution validation
- `pytest-playwright==0.6.2` - Testing integration

#### Docker Configuration Changes
- Added persistent volumes: `kuzu_workflow_db_high` and `kuzu_workflow_db_low`
- Environment variables: `ENABLE_MELODIC_MEMORY=true`, `KUZU_DB_PATH=/app/kuzu_workflow_db`
- Separate Kùzu databases for High and Low orchestrators

#### Documentation Added
- `docs/PHOENIX_EVALUATIONS.md` - Phoenix evaluations guide (setup, usage, interpretation)
- `docs/KUZU_MELODIC_LINE_PROPOSAL.md` - Melodic memory architecture and implementation

#### Documentation Updated
- `CLAUDE.md` - Added Phoenix evaluations commands
- `docs/README.md` - Added link to Phoenix evaluations
- `docs/PHOENIX_OBSERVABILITY.md` - Added reference to evaluations framework

---

### Added - Dual Orchestrator Architecture (December 2025)

**Major Architecture Change**: Migrated from single orchestrator to dual orchestrator architecture for instant mode switching.

#### What Changed

- **Before**: Single orchestrator on port 8080, required environment variable changes and service restarts to switch between High/Low modes
- **After**: Two orchestrators run simultaneously:
  - `orchestrator-high` on port 8080 (MAKER_MODE=high, uses Reviewer validation)
  - `orchestrator-low` on port 8081 (MAKER_MODE=low, uses Planner reflection)

#### Benefits

- **Instant Mode Switching**: Select different model in Continue extension - no restarts needed
- **Better User Experience**: No technical knowledge required to switch modes
- **Resource Efficient**: Both orchestrators share the same backend (llama.cpp servers, MCP, Redis, Qdrant)
- **Broader Accessibility**: Enables users with 40GB RAM to use the system alongside 128GB users

#### Architecture Evolution

**Previous Architecture (Single Orchestrator)**:

```
┌─────────────────────────────────────────────────────────┐
│                    IDE (Continue.dev)                    │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │   Orchestrator API    │
         │    (Port 8080)        │
         │  MAKER_MODE env var   │
         └───────────┬───────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    ┌────▼────┐            ┌─────▼─────┐
    │  High   │            │   Low     │
    │ (Review)│            │(Planner   │
    │         │            │Reflection) │
    └─────────┘            └───────────┘
         │                       │
         └───────────┬───────────┘
                     │
         ┌───────────▼───────────┐
         │   llama.cpp Servers   │
         │   (Native Metal)      │
         └───────────────────────┘
```

**New Architecture (Dual Orchestrator)**:

```
┌─────────────────────────────────────────────────────────┐
│                    IDE (Continue.dev)                    │
│                                                           │
│  ┌──────────────────┐      ┌──────────────────┐         │
│  │ MakerCode - High │      │ MakerCode - Low  │         │
│  │  (Port 8080)     │      │  (Port 8081)     │         │
│  └────────┬─────────┘      └────────┬─────────┘         │
└───────────┼──────────────────────────┼───────────────────┘
            │                          │
    ┌───────▼────────┐        ┌────────▼────────┐
    │ Orchestrator   │        │ Orchestrator     │
    │ High           │        │ Low              │
    │ (Reviewer)     │        │ (Planner         │
    │                │        │  Reflection)     │
    └───────┬────────┘        └────────┬─────────┘
            │                          │
            └──────────┬───────────────┘
                       │
        ┌──────────────▼──────────────┐
        │   Shared Backend Services   │
        │                             │
        │  • llama.cpp Servers        │
        │    (Native Metal)           │
        │  • MCP Server (9001)       │
        │  • Redis (6379)             │
        │  • Qdrant (6333)            │
        │  • Phoenix (6006)           │
        └─────────────────────────────┘
```

**Key Difference**: Both orchestrators run simultaneously, sharing the same backend. Mode selection happens at the API endpoint level, not via environment variables.

#### Files Changed

**New Files**:
- `scripts/start-maker.sh` - Unified startup script for dual orchestrators
- `docs/DUAL_ORCHESTRATOR_SETUP.md` - Complete architecture documentation
- `.continuerc.json` - Native Continue configuration (auto-detected)
- `.vscode/extensions.json` - Recommends Continue extension

**Modified Files**:
- `docker-compose.yml` - Split single orchestrator into `orchestrator-high` and `orchestrator-low`
- `orchestrator/orchestrator.py` - Added `_planner_reflection()` method for Low mode
- `scripts/start-llama-servers.sh` - Conditional Reviewer startup based on mode
- `README.md` - Updated Quick Start and architecture sections
- `CLAUDE.md` - Updated commands and architecture documentation
- `docs/MAKER_MODES.md` - Updated setup and switching instructions
- `QUICK_START_SERVICES.md` - Simplified startup process

**Configuration Files**:
- `~/.continue/config.json` - Updated with dual port configuration (8080/8081)
- `.continuerc.json` - Project-level Continue config (auto-detected)

#### Migration Guide

**For Existing Users**:

1. **Update Continue Configuration**:
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

2. **New Startup Command**:
   ```bash
   # Old way (still works but deprecated)
   export MAKER_MODE=high
   bash scripts/start-llama-servers.sh
   docker compose up -d
   
   # New way (recommended)
   bash scripts/start-maker.sh all
   ```

3. **Mode Switching**:
   - **Old**: Change `MAKER_MODE` env var, restart services
   - **New**: Just select different model in Continue - instant switch!

#### Breaking Changes

- **Port Changes**: Low mode now uses port 8081 (was 8080 with MAKER_MODE=low)
- **Service Names**: Docker services renamed from `orchestrator` to `orchestrator-high` and `orchestrator-low`
- **Startup Script**: New unified `start-maker.sh` script replaces manual orchestration

#### Backward Compatibility

- Old single-orchestrator setup still works if you manually set `MAKER_MODE` and use `docker compose up`
- All existing API endpoints remain the same
- Continue configuration format unchanged (just port numbers)

#### Reference: Original Architecture Diagram

The original architecture diagram is preserved at `docs/assets/maker-architecture.png` and shows the single-orchestrator workflow. This diagram remains valid for understanding the core MAKER workflow, but the deployment architecture has evolved to support dual orchestrators.

---

## Previous Versions

### Single Orchestrator Architecture (Pre-December 2025)

The system originally used a single orchestrator that switched modes based on the `MAKER_MODE` environment variable:

- **Port**: 8080 (single endpoint)
- **Mode Switching**: Required environment variable change + service restart
- **Configuration**: `MAKER_MODE=high` or `MAKER_MODE=low` in docker-compose.yml
- **Continue Setup**: Manual configuration in `~/.continue/config.json`

This architecture is documented in the original `docs/assets/maker-architecture.png` diagram.

---

## Future Enhancements

- [ ] Automatic mode detection based on available RAM
- [ ] Load balancing between orchestrators
- [ ] Per-orchestrator resource limits
- [ ] Mode-specific model configurations
- [ ] Analytics dashboard for mode usage

