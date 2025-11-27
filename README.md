# Localised Code Assistant on Apple Silicon

Applying Cognizant's MAKER paper to build a production-ready local multi-agent coding system optimized for Apple Silicon (M4 Max) with llama.cpp Metal backend.

## Features

- **MAKER Architecture**: Multi-Agent Knowledge-Enhanced Reasoning with parallel candidate generation and first-to-K voting
- **4 Specialized Agents**: Preprocessor (Gemma2-2B), Planner (Nemotron Nano 8B), Coder (Devstral 24B), Reviewer (Qwen3-Coder 32B)
- **llama.cpp Metal Backend**: 2-3x faster than vLLM on Apple Silicon (18-25s end-to-end)
- **Agentic RAG via MCP**: Live codebase queries via REST API (no embeddings, no reindexing)
- **Parallel Execution**: All agents run simultaneously with Redis state coordination
- **OpenAI-Compatible API**: Works with Continue.dev, Open WebUI, or any OpenAI client

## Quick Start

### 1. Download Models

```bash
bash scripts/download-models.sh
```

Downloads all GGUF models (~50GB) to `./models/`

### 2. Start llama.cpp Servers (Native Metal)

```bash
bash scripts/start-llama-servers.sh
```

### 3. Start Docker Services

```bash
docker compose up -d
```

Starts MCP Server + Redis + Orchestrator

### 4. Verify Health

```bash
bash tests/test_workflow.sh
```

### 5. Connect to IDE

**Option 1: VS Code / Continue.dev (Recommended)**
- Install Continue.dev extension
- Config: `~/.continue/config.json`
- Usage: Cmd+L → Select model → Chat

**Option 2: Open WebUI**
- Access: http://localhost:3000
- Settings → Connections → OpenAI → Base URL: http://localhost:8080

**Option 3: Direct API**
```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "multi-agent", "messages": [{"role": "user", "content": "Hello"}]}'
```

## MAKER Implementation

This project implements Cognizant's MAKER (Multi-Agent Knowledge-Enhanced Reasoning) paper:

1. **Parallel Candidate Generation**: Coder agent generates N candidates simultaneously with varying temperatures
2. **First-to-K Voting**: Voter agent evaluates candidates; first to receive K votes wins
3. **Iterative Refinement**: Reviewer validates; failed code loops back to Coder (max 3 iterations)
4. **Escalation**: Persistent failures escalate to Planner for re-decomposition

## Architecture

![Continue.dev Integration](docs/assets/continue-dev-integration.png)

```
+------------------+     +-------------------+     +------------------+
|    IDE Client    |     |   Orchestrator    |     |   MCP Server     |
|  (Continue.dev)  |     |   (FastAPI)       |     |   (Codebase)     |
|                  |     |   Port 8080       |     |   Port 9001      |
+--------+---------+     +--------+----------+     +--------+---------+
         |                        |                         |
         | OpenAI-compatible API  |    Agentic RAG queries  |
         | POST /v1/chat/complete |    read_file, run_tests |
         v                        v                         v
+--------+------------------------+-------------------------+---------+
|                                                                      |
|                        MAKER REASONING PIPELINE                      |
|                                                                      |
|  +----------------+    +----------------+    +-------------------+   |
|  |  1. PREPROCESS |    |   2. PLAN      |    |  3. GENERATE      |   |
|  |                |    |                |    |     (MAKER)       |   |
|  |  Gemma2-2B     |--->|  Nemotron 8B   |--->|                   |   |
|  |  Port 8000     |    |  Port 8001     |    |  Coder generates  |   |
|  |                |    |                |    |  N candidates in  |   |
|  |  Audio/Image   |    |  Decomposes    |    |  parallel with    |   |
|  |  to Text       |    |  task + queries|    |  varying temps    |   |
|  +----------------+    |  MCP for       |    |                   |   |
|                        |  codebase      |    |  Devstral 24B     |   |
|                        +----------------+    |  Port 8002        |   |
|                                              +--------+----------+   |
|                                                       |              |
|                                                       v              |
|                                              +--------+----------+   |
|                                              |  4. VOTE          |   |
|                                              |     (MAKER)       |   |
|                                              |                   |   |
|                                              |  Qwen2.5-1.5B     |   |
|                                              |  Port 8004        |   |
|                                              |                   |   |
|                                              |  First-to-K       |   |
|                                              |  voting selects   |   |
|                                              |  best candidate   |   |
|                                              +--------+----------+   |
|                                                       |              |
|                                                       v              |
|  +----------------+                          +--------+----------+   |
|  |  6. OUTPUT     |                          |  5. REVIEW        |   |
|  |                |<-------------------------|                   |   |
|  |  Stream back   |       If approved        |  Qwen3-Coder 32B  |   |
|  |  to IDE        |                          |  Port 8003        |   |
|  |                |                          |                   |   |
|  +----------------+                          |  Validates code,  |   |
|         ^                                    |  runs tests,      |   |
|         |                                    |  security check   |   |
|         |         If rejected (max 3x)       +--------+----------+   |
|         +--------------------------------------------+               |
|                    Loop back to GENERATE                             |
|                                                                      |
+----------------------------------------------------------------------+
                                   |
                                   v
                    +-----------------------------+
                    |      Shared State (Redis)   |
                    |         Port 6379           |
                    |                             |
                    |  - Task progress tracking   |
                    |  - Iteration count          |
                    |  - Plan/Code/Review state   |
                    +-----------------------------+
```

### Workflow Summary

1. **IDE** (Continue.dev/Open WebUI) sends request via OpenAI-compatible API
2. **Preprocessor** converts any audio/image input to text
3. **Planner** queries MCP for codebase context, decomposes task into subtasks
4. **Coder** generates N candidate solutions in parallel (MAKER)
5. **Voter** evaluates candidates using first-to-K voting (MAKER)
6. **Reviewer** validates winning code, runs tests, checks security
7. If rejected, loops back to Coder (max 3 iterations)
8. **Output** streams back to IDE

## Performance

| Agent | Model | Speed (Metal) | RAM |
|-------|-------|---------------|-----|
| Preprocessor | Gemma2-2B | 180+ t/s | 1.5GB |
| Planner | Nemotron Nano 8B | 118-135 t/s | 4-5GB |
| Coder | Devstral 24B | 78-92 t/s | 14-16GB |
| Reviewer | Qwen3-Coder 32B | 58-68 t/s | 18-20GB |
| Voter | Qwen2.5-1.5B | 200+ t/s | 1GB |

**End-to-end**: 18-25 seconds for complex refactors  
**Peak RAM**: ~40GB (leaves 88GB headroom on M4 Max 128GB)

## Documentation

- [Implementation Plan](multi-agent-system-implementation.plan.md)
- [Blueprint Reference](docs/multi-agent-system-blueprint.md)
- [Agent Prompts](prompts/) - MAKER-style prompts with objectives, tools, constraints
- [Model-Specific Prompt Design](docs/model-specific-prompts.md)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Slow speed (<100 t/s) | Verify `--n-gpu-layers 999` in start script |
| OOM on large tasks | Reduce `--ctx-size` or use Q4_K_M quant |
| Service keeps crashing | Check logs: `tail -f logs/llama-*.log` |
| Models not downloading | Verify HF token: `huggingface-cli login` |

## References

- [MAKER Paper (Cognizant)](https://arxiv.org/abs/2410.02052) - Multi-Agent Knowledge-Enhanced Reasoning
- [llama.cpp](https://github.com/ggerganov/llama.cpp) - Inference engine with Metal support

## License

MIT
