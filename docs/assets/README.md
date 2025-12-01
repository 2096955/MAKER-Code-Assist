# Assets Directory

This directory contains images and other assets for documentation.

## Architecture Diagrams

- **maker-architecture.png** - Original single-orchestrator MAKER pipeline diagram (preserved for reference)
- **highlowmaker.png** - Current dual-orchestrator architecture diagram (High & Low modes)
- **ARCHITECTURE_DIAGRAM_PROMPT.md** - Detailed prompt used to generate the dual-orchestrator diagram

### Diagram Versions

1. **Original (maker-architecture.png)**: 
   - Single orchestrator with MAKER_MODE environment variable switching
   - Shows complete 6-step MAKER pipeline with Reviewer (Qwen3-Coder 32B)
   - Preserved for reference in CHANGELOG.md
   - Used in README.md before dual-orchestrator migration

2. **Current (highlowmaker.png)**: 
   - Dual-orchestrator architecture with High/Low modes running simultaneously
   - High mode: Full pipeline with Reviewer (port 8080)
   - Low mode: Same pipeline but uses Planner Reflection instead of Reviewer (port 8081)
   - Currently displayed in README.md
   - Generated from [ARCHITECTURE_DIAGRAM_PROMPT.md](ARCHITECTURE_DIAGRAM_PROMPT.md) specifications

## Images

- `continue-dev-integration.png` - Screenshot of VS Code with Continue.dev showing the multi-agent system integration

## Adding Images

To add the Continue.dev screenshot:

1. Take a screenshot of VS Code showing Continue.dev with the multi-agent system
2. Save it as `continue-dev-integration.png` in this directory
3. The image should show:
   - VS Code interface with Continue.dev panel
   - Multi-agent system integration
   - Example interaction (e.g., "Write a fibonacci function in python")
   - The `[DIRECT] Simple request detected, generating code...` message
   - Generated code output






