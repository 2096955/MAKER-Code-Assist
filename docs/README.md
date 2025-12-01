# MAKER Documentation

Complete documentation for the MAKER (Multi-Agent Knowledge-Enhanced Reasoning) multi-agent coding system.

## Quick Start

- **[README_CONTINUE.md](../README_CONTINUE.md)** - Get started with Continue VSCode extension (easiest way to use MAKER)
- **[QUICK_START_SERVICES.md](../QUICK_START_SERVICES.md)** - Quick reference for starting/stopping services
- **[SERVICE_STARTUP_GUIDE.md](SERVICE_STARTUP_GUIDE.md)** - Detailed service startup guide

## Setup & Configuration

### Continue Extension (Recommended)
- **[CONTINUE_SETUP.md](CONTINUE_SETUP.md)** - Complete Continue extension setup guide
- **[MAKER_MODES.md](MAKER_MODES.md)** - High vs Low mode comparison and usage

### Core Setup
- **[DUAL_ORCHESTRATOR_SETUP.md](DUAL_ORCHESTRATOR_SETUP.md)** - Dual-orchestrator architecture details

## Architecture & Design

- **[assets/ARCHITECTURE_DIAGRAM_PROMPT.md](assets/ARCHITECTURE_DIAGRAM_PROMPT.md)** - System architecture prompt for diagram generation
- **[assets/highlowmaker.png](assets/highlowmaker.png)** - Dual-orchestrator architecture diagram
- **[assets/maker-architecture.png](assets/maker-architecture.png)** - Original MAKER architecture diagram

## Features & Capabilities

### Observability & Monitoring
- **[PHOENIX_OBSERVABILITY.md](PHOENIX_OBSERVABILITY.md)** - Phoenix dashboard usage and trace analysis
- **[quickstart-memory-observability.md](quickstart-memory-observability.md)** - Memory and observability quick start

### RAG Integration
- **[rag-quickstart.md](rag-quickstart.md)** - RAG (Retrieval-Augmented Generation) quick start
- **[rag-agentic-design.md](rag-agentic-design.md)** - RAG architecture for agentic systems
- **[rag-limitations.md](rag-limitations.md)** - Known RAG limitations

### Advanced Features
- **[swe-bench-integration.md](swe-bench-integration.md)** - SWE-bench evaluation integration
- **[reviewer-optional-plan.md](reviewer-optional-plan.md)** - How Low mode works without Reviewer
- **[context-engineering-skills-analysis.md](context-engineering-skills-analysis.md)** - Context engineering patterns
- **[skills-framework-clarification.md](skills-framework-clarification.md)** - Skills framework design

## Known Issues & Limitations

- **[KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)** - Current limitations and workarounds

## Main Documentation

- **[CLAUDE.md](../CLAUDE.md)** - Main project documentation for Claude Code
- **[CHANGELOG.md](../CHANGELOG.md)** - Project changelog
- **[CONTRIBUTORS.md](../CONTRIBUTORS.md)** - Contributor information

## Documentation Organization

```
docs/
├── README.md                              # This file
├── CONTINUE_SETUP.md                      # Continue VSCode setup
├── DUAL_ORCHESTRATOR_SETUP.md             # Architecture details
├── MAKER_MODES.md                         # High vs Low modes
├── PHOENIX_OBSERVABILITY.md               # Observability guide
├── SERVICE_STARTUP_GUIDE.md               # Service management
├── KNOWN_LIMITATIONS.md                   # Known issues
├── rag-quickstart.md                      # RAG quick start
├── rag-agentic-design.md                  # RAG architecture
├── rag-limitations.md                     # RAG limitations
├── swe-bench-integration.md               # SWE-bench integration
├── reviewer-optional-plan.md              # Low mode design
├── context-engineering-skills-analysis.md # Context patterns
├── skills-framework-clarification.md      # Skills framework
├── quickstart-memory-observability.md     # Memory & observability
└── assets/                                # Architecture diagrams
    ├── README.md
    ├── ARCHITECTURE_DIAGRAM_PROMPT.md
    ├── highlowmaker.png
    └── maker-architecture.png
```

## For Developers

- Agent system prompts: [`agents/`](../agents/)
- Orchestrator code: [`orchestrator/`](../orchestrator/)
- Docker setup: [`docker-compose.yml`](../docker-compose.yml)
- Scripts: [`scripts/`](../scripts/)

## Getting Help

1. Check the relevant documentation above
2. Review [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)
3. Check [Phoenix observability dashboard](http://localhost:6006) for traces
4. Open an issue on GitHub

## Contributing

See [CONTRIBUTORS.md](../CONTRIBUTORS.md) for contribution guidelines.
