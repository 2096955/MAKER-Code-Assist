# Local RAG Setup Guide with Qdrant

This guide explains how to set up local RAG (Retrieval-Augmented Generation) using Qdrant vector database with your existing multi-agent system.

## Overview

**RAG Components:**
1. **Embedding Model**: Converts text to vectors (e.g., `nomic-embed-text-v1.5`)
2. **Vector Database**: Qdrant (stores and searches embeddings)
3. **LLM**: Your existing models (Nemotron Nano 8B or Devstral 24B) for generation

## Quick Start

### 1. Start Qdrant

```bash
# Qdrant is already added to docker-compose.yml
docker compose up -d qdrant

# Verify it's running
curl http://localhost:6333/health
```

### 2. Install Embedding Model

The RAG service uses `sentence-transformers` which will download models automatically. Recommended models:

**Option A: nomic-embed-text-v1.5** (Recommended)
- Size: ~137M parameters
- Dimensions: 768
- Best for: General text, code, documentation
- Download: Auto-downloads on first use

**Option B: bge-small-en-v1.5** (Lightweight)
- Size: ~33M parameters  
- Dimensions: 384
- Best for: Fast indexing, smaller memory footprint
- Download: Auto-downloads on first use

### 3. Index Your Codebase

```python
from orchestrator.rag_service import RAGService

# Initialize RAG service
rag = RAGService(
    qdrant_url="http://localhost:6333",
    embedding_model="nomic-embed-text-v1.5",  # or "bge-small-en-v1.5"
    collection_name="codebase_docs"
)

# Index codebase
rag.index_codebase("/path/to/your/codebase")
```

### 4. Query with RAG

```python
# Simple search
docs = rag.search("How does the orchestrator work?", top_k=5)
for doc in docs:
    print(f"Score: {doc['score']:.3f} - {doc['metadata']['file_path']}")
    print(doc['text'][:200])

# Full RAG query (retrieve + generate)
answer = await rag.query("How does MAKER voting work?")
print(answer)
```

## Integration with Existing System

### Option 1: Add RAG to Planner Agent

The Planner can use RAG to retrieve relevant codebase context before planning:

```python
# In orchestrator.py
from orchestrator.rag_service import RAGService

class Orchestrator:
    def __init__(self, ...):
        # ... existing init ...
        self.rag = RAGService(
            qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "nomic-embed-text-v1.5"),
            llm_url=self.endpoints[AgentName.PLANNER]
        )
    
    async def plan_with_rag(self, task: str, task_id: str):
        # Retrieve relevant context
        context_docs = self.rag.search(task, top_k=5)
        context = "\n".join([doc['text'] for doc in context_docs])
        
        # Use context in planner prompt
        prompt = f"Context from codebase:\n{context}\n\nTask: {task}"
        # ... rest of planning logic ...
```

### Option 2: Standalone RAG Endpoint

Add a RAG endpoint to your API server:

```python
# In api_server.py
from orchestrator.rag_service import RAGService

rag_service = RAGService()

@app.post("/api/rag/query")
async def rag_query(request: RAGQueryRequest):
    answer = await rag_service.query(request.question, top_k=request.top_k)
    return {"answer": answer}
```

## Model Recommendations

### For General RAG (Documentation, Knowledge Base)
- **Embedding**: `nomic-embed-text-v1.5` (768 dim, best quality)
- **LLM**: `Nemotron Nano 8B` (128K context, good reasoning)

### For Code-Specific RAG
- **Embedding**: `nomic-embed-text-v1.5` (works well with code)
- **LLM**: `Devstral 24B` (best for code understanding)

### For Fast/Lightweight RAG
- **Embedding**: `bge-small-en-v1.5` (384 dim, ~33M params)
- **LLM**: `Qwen2.5-1.5B` (fastest, but lower quality)

## Qdrant vs Chroma Comparison

| Feature | Qdrant | Chroma |
|---------|--------|--------|
| **Performance** | ⭐⭐⭐⭐⭐ (Rust-based) | ⭐⭐⭐ (Python) |
| **Scalability** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Filtering** | ⭐⭐⭐⭐⭐ (Advanced) | ⭐⭐⭐ |
| **Ease of Use** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Production Ready** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Docker Support** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

**Recommendation**: Use **Qdrant** for production/local RAG. It's faster, more scalable, and has better filtering capabilities.

## Environment Variables

Add to your `.env` or `docker-compose.yml`:

```bash
QDRANT_URL=http://qdrant:6333  # From Docker network
# or
QDRANT_URL=http://localhost:6333  # From host

EMBEDDING_MODEL=nomic-embed-text-v1.5
RAG_COLLECTION_NAME=codebase_docs
```

## Advanced Usage

### Custom Chunking Strategy

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)

chunks = splitter.split_text(document_text)
```

### Metadata Filtering

```python
# Search with filters
from qdrant_client.models import Filter, FieldCondition, MatchValue

filter_condition = Filter(
    must=[
        FieldCondition(key="file_type", match=MatchValue(value=".py"))
    ]
)

results = rag.client.search(
    collection_name=rag.collection_name,
    query_vector=embedding,
    query_filter=filter_condition
)
```

### Hybrid Search (Keyword + Vector)

Qdrant supports hybrid search combining keyword matching with vector similarity for better results.

## Troubleshooting

**Qdrant not accessible from Docker:**
- Use `http://qdrant:6333` from within Docker containers
- Use `http://localhost:6333` from host machine

**Embedding model download fails:**
- Check internet connection
- Models download to `~/.cache/huggingface/` by default
- Can manually download: `python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('nomic-embed-text-v1.5')"`

**Memory issues:**
- Use smaller embedding model: `bge-small-en-v1.5` (384 dim vs 768)
- Reduce chunk size in indexing
- Use Q4_K quantization for LLM models

## Next Steps

1. Index your codebase: `rag.index_codebase("/path/to/codebase")`
2. Test queries: `rag.search("your question")`
3. Integrate with Planner or create standalone RAG endpoint
4. Monitor Qdrant dashboard: http://localhost:6333/dashboard

