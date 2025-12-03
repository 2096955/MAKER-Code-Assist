# RAG Quick Start Guide

## Two Options: FAISS (Simple) vs Qdrant (Production)

### Option 1: FAISS (No Docker, In-Memory) ⚡

**Best for:** Local development, prototyping, small codebases

```bash
# Install dependencies
pip install faiss-cpu sentence-transformers streamlit

# Run the UI
streamlit run orchestrator/rag_ui.py
```

**Python API:**
```python
from orchestrator.rag_service_faiss import RAGServiceFAISS

# Initialize (no Docker needed!)
rag = RAGServiceFAISS(
    embedding_model="nomic-embed-text-v1.5",
    llm_url="http://localhost:8001/v1/chat/completions"
)

# Index your codebase
rag.index_codebase(".")

# Search
results = rag.search("How does MAKER voting work?", top_k=5)

# Query with LLM
import asyncio
answer = asyncio.run(rag.query("Explain the orchestrator architecture"))
print(answer)
```

### Option 2: Qdrant (Docker, Persistent) 🐳

**Best for:** Production, large codebases, persistence

```bash
# Start Qdrant
docker compose up -d qdrant

# Verify it's running
curl http://localhost:6333/health

# Run the UI
streamlit run orchestrator/rag_ui.py
```

**Python API:**
```python
from orchestrator.rag_service import RAGService

# Initialize (Qdrant must be running)
rag = RAGService(
    qdrant_url="http://localhost:6333",
    embedding_model="nomic-embed-text-v1.5",
    llm_url="http://localhost:8001/v1/chat/completions"
)

# Index your codebase (persists automatically)
rag.index_codebase(".")

# Search
results = rag.search("How does MAKER voting work?", top_k=5)

# Query with LLM
import asyncio
answer = asyncio.run(rag.query("Explain the orchestrator architecture"))
print(answer)
```

## Which Model to Use?

### For Embeddings (Vector Search)

1. **nomic-embed-text-v1.5** (Recommended)
   - 768 dimensions
   - Best quality for code and text
   - ~137M parameters

2. **bge-small-en-v1.5** (Lightweight)
   - 384 dimensions
   - Faster, less memory
   - ~33M parameters

### For LLM Generation

1. **Nemotron Nano 8B** (`http://localhost:8001`)
   - Best for general RAG
   - 128K context window
   - Good reasoning

2. **Devstral 24B** (`http://localhost:8002`)
   - Best for code-specific RAG
   - Excellent code understanding

3. **Qwen2.5-1.5B** (`http://localhost:8004`)
   - Fastest option
   - Lower quality but very quick

## Streamlit UI Features

The UI (`orchestrator/rag_ui.py`) provides:

- ✅ Choose between FAISS or Qdrant
- ✅ Select embedding model
- ✅ Select LLM endpoint
- ✅ Index codebase with one click
- ✅ Search documents
- ✅ RAG queries (retrieve + generate)
- ✅ View results with scores
- ✅ Save/load FAISS indexes

## Integration with Your Multi-Agent System

### Add RAG to Planner

```python
# In orchestrator.py
from orchestrator.rag_service_faiss import RAGServiceFAISS

class Orchestrator:
    def __init__(self, ...):
        # ... existing code ...
        self.rag = RAGServiceFAISS(
            embedding_model="nomic-embed-text-v1.5",
            llm_url=self.endpoints[AgentName.PLANNER]
        )
    
    async def plan_with_rag(self, task: str):
        # Retrieve relevant codebase context
        context_docs = self.rag.search(task, top_k=5)
        context = "\n".join([doc['text'] for doc in context_docs])
        
        # Use in planner prompt
        enhanced_prompt = f"""Context from codebase:
{context}

Task: {task}"""
        # ... rest of planning ...
```

### Add RAG Endpoint to API

```python
# In api_server.py
from orchestrator.rag_service_faiss import RAGServiceFAISS
import asyncio

rag_service = RAGServiceFAISS()

@app.post("/api/rag/query")
async def rag_query(request: RAGQueryRequest):
    answer = await rag_service.query(request.question, top_k=request.top_k)
    return {"answer": answer}
```

## Performance Tips

1. **Use smaller embedding model** for faster indexing:
   - `bge-small-en-v1.5` instead of `nomic-embed-text-v1.5`

2. **Adjust chunk size** for your use case:
   ```python
   rag.index_codebase(".", chunk_size=500)  # Smaller chunks = more granular
   ```

3. **Filter file types** to reduce index size:
   ```python
   rag.index_codebase(".", file_extensions=['.py', '.md'])  # Only Python and Markdown
   ```

4. **Save FAISS index** to avoid re-indexing:
   ```python
   rag.save_index("./rag_index.index")
   # Later...
   rag = RAGServiceFAISS(index_path="./rag_index.index")
   ```

## Troubleshooting

**FAISS import error:**
```bash
pip install faiss-cpu  # For CPU
# or
pip install faiss-gpu  # For GPU (if available)
```

**Qdrant connection error:**
- Check Qdrant is running: `curl http://localhost:6333/health`
- From Docker: Use `http://qdrant:6333` instead of `localhost`

**Embedding model download:**
- Models auto-download to `~/.cache/huggingface/`
- First run may take a few minutes
- Check internet connection

**Memory issues:**
- Use `bge-small-en-v1.5` (smaller)
- Reduce chunk size
- Index fewer files

## Next Steps

1. **Try FAISS first** - simplest setup, no Docker
2. **Index your codebase** - see how it performs
3. **Switch to Qdrant** - if you need persistence or scale
4. **Integrate with Planner** - enhance task planning with codebase context

See also:
- [FAISS vs Qdrant Comparison](./faiss-vs-qdrant-comparison.md)
- [Full RAG Setup Guide](./rag-setup-guide.md)





