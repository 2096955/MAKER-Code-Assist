# Changelog

All notable changes to the MAKER multi-agent coding system will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added - Dual Orchestrator Architecture

**Date**: December 2025

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

