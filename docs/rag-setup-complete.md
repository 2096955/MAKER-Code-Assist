# Complete RAG Setup: FAISS + nomic-embed-text-v1.5 + Gemma2-2B

## Quick Start

```bash
# 1. Install dependencies
bash scripts/setup-rag-faiss.sh

# 2. Index your codebase
python3 scripts/index_codebase.py

# 3. Test it
python3 examples/rag_example.py

# 4. Or use the UI
streamlit run orchestrator/rag_ui.py
```

## Architecture

```
┌─────────────────┐
│  User Query     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│  nomic-embed    │────▶│  FAISS Index     │
│  text-v1.5      │     │  (in-memory)     │
└─────────────────┘     └────────┬─────────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │  Top-K Docs   │
                         └───────┬───────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │  Nemotron 8B  │
                         │  (Generation) │
                         └───────┬───────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │  Answer       │
                         └───────────────┘

Multi-modal Support:
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ Image/Audio │────▶│ Gemma2-2B    │────▶│ Text        │
│ (base64)    │     │ Preprocessor │     │ (for RAG)   │
└─────────────┘     └──────────────┘     └─────────────┘
```

## Components

### 1. Embedding Model: nomic-embed-text-v1.5
- **Dimensions**: 768
- **Size**: ~137M parameters (~500MB)
- **Purpose**: Convert text → vectors
- **Auto-downloads**: First time you use it

### 2. Vector Search: FAISS
- **Type**: In-memory index (IndexFlatL2)
- **Distance**: L2 with cosine normalization
- **Speed**: <10ms for 100K documents
- **Memory**: ~3KB per document

### 3. LLM Generation: Your Existing Models
- **Nemotron Nano 8B** (port 8001): General RAG
- **Devstral 24B** (port 8002): Code-specific RAG
- **Qwen2.5-1.5B** (port 8004): Fast option

### 4. Multi-modal: Gemma2-2B Preprocessor
- **Purpose**: Image/audio → text
- **Port**: 8000
- **Usage**: Automatically converts multi-modal inputs before embedding

## Key Limitations (Summary)

### ⚠️ Critical Limitations

1. **Memory**: ~400MB per 100K documents. Practical limit: ~1-2M documents on M4 Max 128GB
2. **No Auto-Persistence**: Must manually save/load indexes
3. **Single-Process**: Not suitable for concurrent multi-user access
4. **No Advanced Filtering**: Basic similarity search only (no metadata filters)
5. **Re-indexing Required**: Must rebuild when codebase changes
6. **Embedding Limits**: Max 8192 tokens per document (truncates longer)
7. **Search Quality**: Semantic gaps, no code structure understanding
8. **Multi-modal**: Depends on Gemma2-2B quality, adds latency

### ✅ What It's Good For

- Local development / prototyping
- Small-medium codebases (<500K documents)
- Single-user scenarios
- Fast iteration and experimentation

### ❌ What It's NOT Good For

- Production multi-user systems
- Very large codebases (>1M documents)
- Frequent codebase updates
- Advanced filtering needs
- Multi-process deployments

## Usage Examples

### Basic Search

```python
from orchestrator.rag_service_faiss import RAGServiceFAISS

rag = RAGServiceFAISS()
rag.index_codebase(".")

# Search
results = rag.search("How does orchestrator work?", top_k=5)
for doc in results:
    print(f"Score: {doc['score']:.3f}")
    print(f"File: {doc['metadata']['file_path']}")
    print(doc['text'][:200])
```

### RAG Query (Retrieve + Generate)

```python
import asyncio

answer = asyncio.run(rag.query("Explain MAKER voting", top_k=5))
print(answer)
```

### Multi-modal (Image/Audio)

```python
import base64

# Load image
with open("screenshot.png", "rb") as f:
    image_base64 = base64.b64encode(f.read()).decode()

# Add to index (via Gemma2-2B preprocessing)
await rag.add_multimodal_document(
    content=image_base64,
    content_type="image",
    metadata={"source": "screenshot.png"}
)

# Now searchable as text
results = rag.search("What does the screenshot show?")
```

### Save/Load Index

```python
# Save
rag.save_index("data/rag_indexes/codebase.index")

# Load later
rag = RAGServiceFAISS(index_path="data/rag_indexes/codebase.index")
```

## Integration with Your Multi-Agent System

### Option 1: Enhance Planner with RAG

```python
# In orchestrator.py
from orchestrator.rag_service_faiss import RAGServiceFAISS

class Orchestrator:
    def __init__(self, ...):
        self.rag = RAGServiceFAISS(
            embedding_model="nomic-embed-text-v1.5",
            llm_url=self.endpoints[AgentName.PLANNER]
        )
        # Load existing index if available
        if os.path.exists("data/rag_indexes/codebase.index"):
            self.rag.load_index("data/rag_indexes/codebase.index")
    
    async def plan_with_rag(self, task: str):
        # Retrieve relevant context
        context_docs = self.rag.search(task, top_k=5)
        context = "\n".join([doc['text'] for doc in context_docs])
        
        # Enhanced planning prompt
        enhanced_prompt = f"""Context from codebase:
{context}

Task: {task}"""
        # ... rest of planning logic ...
```

### Option 2: Add RAG Endpoint

```python
# In api_server.py
from orchestrator.rag_service_faiss import RAGServiceFAISS
import asyncio

rag_service = RAGServiceFAISS()

@app.post("/api/rag/query")
async def rag_query(request: RAGQueryRequest):
    answer = await rag_service.query(request.question, top_k=request.top_k)
    return {"answer": answer}

@app.post("/api/rag/search")
async def rag_search(request: RAGSearchRequest):
    results = rag_service.search(request.query, top_k=request.top_k)
    return {"results": results}
```

## Performance Expectations

### Indexing
- **10K documents**: 2-3 minutes
- **100K documents**: 20-30 minutes
- **Bottleneck**: Embedding generation (CPU-bound)

### Search
- **Query latency**: <10ms (100K docs)
- **Embedding time**: ~50-100ms per query
- **Total**: ~100-150ms end-to-end

### Memory
- **Per document**: ~3KB
- **100K documents**: ~400MB
- **1M documents**: ~4GB

## Best Practices

1. **Index Management**
   - Save indexes after major changes
   - Use versioned indexes: `codebase-v1.index`, `codebase-v2.index`
   - Re-index weekly or after major refactors

2. **Memory Optimization**
   - Filter file types: Only index `.py`, `.md` (skip large files)
   - Increase chunk size: 2000 instead of 1000 (fewer documents)
   - Use `bge-small-en-v1.5` if memory is tight (2x savings)

3. **Search Quality**
   - Increase `top_k` and post-filter if needed
   - Use semantic chunking (not just size-based)
   - Combine with keyword search for hybrid results

4. **Multi-modal**
   - Preprocess images/audio before indexing (use Gemma2-2B)
   - Store original files separately (index only text descriptions)
   - Consider specialized models for code screenshots

## When to Upgrade to Qdrant

Switch to Qdrant if you need:
- ✅ Automatic persistence
- ✅ Multi-process/multi-user access
- ✅ Advanced metadata filtering
- ✅ Very large scale (>1M documents)
- ✅ Production deployment

## Files Created

- `orchestrator/rag_service_faiss.py` - Main RAG service
- `scripts/setup-rag-faiss.sh` - Setup script
- `scripts/index_codebase.py` - Indexing script
- `orchestrator/rag_ui.py` - Streamlit UI
- `examples/rag_example.py` - Usage examples
- `docs/rag-limitations.md` - Detailed limitations
- `docs/rag-quickstart.md` - Quick start guide
- `docs/faiss-vs-qdrant-comparison.md` - Comparison guide

## Next Steps

1. ✅ Run setup: `bash scripts/setup-rag-faiss.sh`
2. ✅ Index codebase: `python3 scripts/index_codebase.py`
3. ✅ Test: `python3 examples/rag_example.py`
4. ✅ Try UI: `streamlit run orchestrator/rag_ui.py`
5. ✅ Integrate with Planner or add API endpoints
6. ⚠️ Monitor memory usage and switch to Qdrant if needed

## Troubleshooting

**Import errors:**
```bash
pip install faiss-cpu sentence-transformers httpx numpy
```

**Memory issues:**
- Use `bge-small-en-v1.5` instead
- Increase chunk size
- Filter file types

**Slow indexing:**
- Normal for large codebases
- Consider indexing only important directories
- Run in background

**Search quality:**
- Increase `top_k` and manually filter
- Adjust chunk size
- Try different embedding models

See [rag-limitations.md](./rag-limitations.md) for detailed limitations and solutions.

