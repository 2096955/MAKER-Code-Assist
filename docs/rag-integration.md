# RAG Integration with Preprocessor & Planner

## Overview

RAG (Retrieval-Augmented Generation) has been integrated into the multi-agent workflow to enhance context retrieval. The system uses FAISS + nomic-embed-text-v1.5 for semantic search.

## Integration Points

### 1. Preprocessor Enhancement

The `preprocess_input()` method now optionally uses RAG to enhance user queries with relevant codebase context:

```python
# In orchestrator.py
async def preprocess_input(self, task_id: str, user_input: str) -> str:
    # If RAG enabled and input is a question, retrieve context
    if self.rag_enabled:
        rag_docs = rag.search(user_input, top_k=3)
        # Enhance preprocessed text with RAG context
        preprocessed_text = f"{user_input}\n\n[Relevant codebase context:\n{rag_context}\n]"
```

**When it triggers:**
- RAG is enabled (`RAG_ENABLED=true`)
- Input contains question indicators: "how", "what", "why", "explain", etc.
- RAG index exists and is loaded

**What it does:**
- Searches codebase for relevant context
- Appends top 3 relevant code snippets to the preprocessed input
- Planner receives enhanced context automatically

### 2. Planner Enhancement

The Planner receives RAG context in two places:

#### A. Question Answering (`_answer_question`)

```python
# Gets both MCP context and RAG context
codebase_context = await self._query_mcp("analyze_codebase", {})
rag_docs = rag.search(user_input, top_k=5)  # RAG enhancement
```

#### B. Task Planning (`orchestrate_workflow`)

```python
# Planner gets enhanced context with RAG snippets
plan_message = f"""Task: {preprocessed_text}

Codebase Context (from MCP):
{codebase_context}
{rag_context}  # <-- RAG enhancement
"""
```

## Configuration

### Enable RAG

```bash
# In docker-compose.yml or .env
RAG_ENABLED=true
RAG_INDEX_PATH=/app/data/rag_indexes/codebase.index
EMBEDDING_MODEL=nomic-embed-text-v1.5
```

### Setup Steps

1. **Install dependencies:**
   ```bash
   bash scripts/setup-rag-faiss.sh
   ```

2. **Index your codebase:**
   ```bash
   python3 scripts/index_codebase.py
   ```

3. **Enable RAG:**
   ```bash
   # In docker-compose.yml
   RAG_ENABLED=true
   ```

4. **Restart orchestrator:**
   ```bash
   docker compose restart orchestrator
   ```

## How It Works

### Workflow with RAG Enabled

```
User Input: "How does the orchestrator handle errors?"
    │
    ▼
[PREPROCESSOR]
    │
    ├─→ Detect question → RAG Search
    │   └─→ Find relevant code snippets
    │
    └─→ Enhanced Input:
        "How does the orchestrator handle errors?
        
        [Relevant codebase context from RAG:
        From orchestrator.py: try/except blocks...
        From api_server.py: error handling...
        ]"
    │
    ▼
[PLANNER]
    │
    ├─→ MCP Context (codebase structure)
    ├─→ RAG Context (relevant snippets)
    └─→ Enhanced planning with both
    │
    ▼
[CODER / REVIEWER / etc.]
```

### Without RAG

```
User Input → Preprocessor → Planner (MCP only) → Agents
```

### With RAG

```
User Input → Preprocessor (RAG-enhanced) → Planner (MCP + RAG) → Agents
```

## Benefits

1. **Better Context**: Planner gets both structural (MCP) and semantic (RAG) context
2. **Question Enhancement**: Questions automatically get relevant code snippets
3. **Automatic**: No manual intervention needed once enabled
4. **Fallback**: If RAG fails, system continues with MCP only

## Limitations

1. **Index Required**: Must index codebase first (`python3 scripts/index_codebase.py`)
2. **Memory**: RAG index loaded in memory (~400MB per 100K docs)
3. **Latency**: Adds ~100-150ms for RAG search (acceptable for better context)
4. **Stale Data**: Must re-index when codebase changes significantly

## Monitoring

Check if RAG is working:

```python
# In orchestrator logs
✅ RAG service loaded from data/rag_indexes/codebase.index
[PREPROCESSOR] Converted input to: ... [Relevant codebase context from RAG: ...]
```

Or check metadata in preprocessed output:

```json
{
  "preprocessed_text": "...",
  "metadata": {
    "rag_enhanced": true,
    "rag_context_length": 1234
  }
}
```

## Disabling RAG

If you want to disable RAG temporarily:

```bash
# In docker-compose.yml
RAG_ENABLED=false

# Restart
docker compose restart orchestrator
```

The system will continue working with MCP-only context.

## Performance Impact

- **Indexing**: One-time cost (2-30 min depending on codebase size)
- **Search latency**: +100-150ms per query (acceptable for better results)
- **Memory**: ~400MB for 100K documents (your M4 Max 128GB can handle this easily)
- **Overall**: Minimal impact, significant context quality improvement

## Best Practices

1. **Re-index regularly**: After major codebase changes
2. **Monitor memory**: Check `rag.get_stats()['estimated_memory_mb']`
3. **Use versioned indexes**: `codebase-v1.index`, `codebase-v2.index`
4. **Combine with MCP**: RAG complements MCP, doesn't replace it

## Troubleshooting

**RAG not working:**
- Check `RAG_ENABLED=true` in environment
- Verify index exists: `ls data/rag_indexes/codebase.index`
- Check logs for: `✅ RAG service loaded from...`

**RAG search slow:**
- Normal: ~100-150ms is acceptable
- Check index size: Large indexes are slower
- Consider using `bge-small-en-v1.5` for faster embeddings

**Memory issues:**
- Use smaller embedding model: `bge-small-en-v1.5`
- Increase chunk size to reduce document count
- Filter file types when indexing

See also:
- [RAG Limitations](./rag-limitations.md)
- [RAG Quick Start](./rag-quickstart.md)
- [Complete Setup](./rag-setup-complete.md)

