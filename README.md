# Localised Code Assistant on Apple Silicon

Applying Cognizant's MAKER paper to build a production-ready local multi-agent coding system optimized for Apple Silicon (M4 Max) with llama.cpp Metal backend.

## Features

- **MAKER Architecture**: Multi-Agent Knowledge-Enhanced Reasoning with parallel candidate generation and first-to-K voting
- **5 Specialized Agents**: Preprocessor (Gemma2-2B), Planner (Nemotron Nano 8B), Coder (Devstral 24B), Reviewer (Qwen3-Coder 32B), Voter (Qwen2.5-1.5B)
- **llama.cpp Metal Backend**: 2-3x faster than vLLM on Apple Silicon (18-25s end-to-end)
- **Agentic RAG via MCP**: Live codebase queries via REST API (no embeddings, no reindexing)
- **Parallel Execution**: All agents run simultaneously with Redis state coordination
- **Context Compression**: Hierarchical compression with sliding window (recent messages in full, older messages summarized)
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

**Option 3: OpenAI Codex CLI**
```bash
# Setup (one-time)
bash codex/setup.sh

# Run Codex with MAKER backend
MAKER_API_KEY=local codex
```

**Option 4: Direct API**
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

![MAKER Reasoning Pipeline Architecture](docs/assets/maker-architecture.png)

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

## Context Compression

The system implements **hierarchical context compression** (similar to Claude's approach) to efficiently use full context windows:

- **Recent messages** (default: 8000 tokens) - Kept in full for immediate context
- **Older messages** - Automatically summarized by Preprocessor (Gemma2-2B) when context exceeds limits
- **Auto-compression** - Triggers when total context approaches `MAX_CONTEXT_TOKENS` (default: 32000)
- **Per-task history** - Each task maintains its own conversation history and compression state

**Configuration** (via environment variables):
- `MAX_CONTEXT_TOKENS=32000` - Total context budget before compression
- `RECENT_WINDOW_TOKENS=8000` - Recent messages kept in full
- `SUMMARY_CHUNK_SIZE=4000` - Chunk size for summarization

This replaces the previous hard 2000-character truncation, allowing the system to use the full context window (128K for Planner/Coder, 256K for Reviewer) while managing long conversations efficiently.

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

- [MAKER Paper](https://arxiv.org/abs/2511.09030) - Solving a Million-Step LLM Task with Zero Errors
- [llama.cpp](https://github.com/ggerganov/llama.cpp) - Inference engine with Metal support

## License

MIT
