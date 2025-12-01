# RAG with FAISS + nomic-embed-text-v1.5: Limitations & Considerations

## Setup Summary

**Components:**
- **Embedding Model**: `nomic-embed-text-v1.5` (768 dimensions, ~137M parameters)
- **Vector Search**: FAISS (in-memory, L2 distance with cosine normalization)
- **LLM Generation**: Nemotron Nano 8B or Devstral 24B (your existing models)
- **Multi-modal Support**: Gemma2-2B Preprocessor (image/audio → text)

## Hard Limitations

### 1. Memory Constraints ⚠️

**Issue**: FAISS stores everything in RAM. Large codebases can consume significant memory.

**Numbers:**
- **Per document**: ~3KB (768-dim embedding + metadata)
- **10,000 documents**: ~30MB vectors + ~10MB metadata = **~40MB total**
- **100,000 documents**: ~300MB vectors + ~100MB metadata = **~400MB total**
- **1,000,000 documents**: ~3GB vectors + ~1GB metadata = **~4GB total**

**Your M4 Max 128GB**: Can handle **~30M documents** in theory, but practical limit is **~1-2M documents** before performance degrades.

**Mitigation:**
- Use `bge-small-en-v1.5` (384 dim) for 2x memory savings
- Increase chunk size to reduce document count
- Filter file types (only index `.py`, `.md`, skip large files)
- Use Qdrant for >500K documents (disk-based, more efficient)

### 2. No Automatic Persistence 🔄

**Issue**: Index is lost when process restarts. Must manually save/load.

**Workaround:**
```python
# Save after indexing
rag.save_index("data/rag_indexes/codebase.index")

# Load on startup
rag = RAGServiceFAISS(index_path="data/rag_indexes/codebase.index")
```

**Best Practice**: Save index after major codebase changes, load on service startup.

### 3. Single-Process Only 🚫

**Issue**: FAISS index is not thread-safe for concurrent writes. Multiple processes can't share the same index.

**Impact:**
- ❌ Can't use with multiple workers/processes
- ❌ Not suitable for multi-user concurrent access
- ✅ Fine for single-user local development
- ✅ Can use with async/threading for reads (search is safe)

**Alternative**: Use Qdrant for multi-process/multi-user scenarios.

### 4. No Advanced Filtering 🔍

**Issue**: FAISS IndexFlatL2 only supports similarity search. No metadata filtering, date ranges, etc.

**What you CAN'T do:**
- Filter by file type: `search(query, filter={'file_type': '.py'})`
- Filter by date: `search(query, filter={'date': '>2024-01-01'})`
- Filter by path: `search(query, filter={'path': 'orchestrator/'})`

**What you CAN do:**
- Post-filter results in Python after search
- Use multiple indexes for different file types
- Use Qdrant for advanced filtering

**Workaround:**
```python
# Post-filter results
results = rag.search(query, top_k=20)  # Get more results
filtered = [r for r in results if r['metadata']['file_type'] == '.py'][:5]  # Filter
```

### 5. Re-indexing Required on Changes 📝

**Issue**: When codebase changes, index becomes stale. Must rebuild.

**Impact:**
- New files: Not searchable until re-indexed
- Modified files: Old chunks still in index (may return stale results)
- Deleted files: Still in index (wastes memory)

**Best Practice:**
- Re-index after major changes (daily/weekly)
- Use versioned indexes: `codebase-v1.index`, `codebase-v2.index`
- Consider incremental indexing (not implemented, would need custom logic)

### 6. Embedding Model Limitations 📊

**nomic-embed-text-v1.5:**
- **Max sequence length**: 8192 tokens (truncates longer text)
- **Language**: Primarily English (works for code, but optimized for English)
- **Code understanding**: Good, but not specialized for code (unlike CodeBERT)
- **Context**: Doesn't understand file structure, imports, dependencies

**Impact:**
- Very long files may be truncated
- Code-specific queries may not be as accurate as code-specialized embeddings
- No understanding of code semantics (functions, classes, imports)

**Alternatives:**
- `bge-small-en-v1.5`: Faster, smaller, but lower quality
- Code-specific: `sentence-transformers/all-MiniLM-L6-v2` (not recommended, general purpose)
- For code: Consider specialized models like CodeBERT (not available in sentence-transformers)

### 7. Search Quality Limitations 🎯

**Cosine Similarity Issues:**
- **Semantic gaps**: May miss relevant docs if wording differs
- **Code vs text**: Code structure not well captured
- **Context loss**: Chunks lose surrounding context
- **No ranking**: All results scored equally (no relevance ranking beyond similarity)

**Example Problem:**
- Query: "How does the orchestrator handle errors?"
- May miss: "orchestrator.py error handling try/except" if chunked differently

**Mitigation:**
- Increase `top_k` and re-rank manually
- Use hybrid search (keyword + vector) - not implemented
- Better chunking strategy (semantic chunking, not just size-based)

### 8. Multi-Modal Limitations 🖼️

**Gemma2-2B Preprocessor:**
- **Image quality**: Depends on model capabilities (may miss fine details)
- **Audio quality**: Transcription accuracy varies
- **Processing time**: Adds latency (image/audio → text → embed)
- **No visual search**: Can't search by visual similarity (only text descriptions)

**Current Implementation:**
- Images: Converted to text description, then embedded
- Audio: Transcribed to text, then embedded
- **No direct image/audio embedding** (would need CLIP-style models)

**Limitations:**
- Screenshots of code: May lose formatting/structure
- Diagrams: Description may miss important details
- Audio: Transcription errors propagate to search

## Performance Characteristics

### Indexing Speed
- **10K documents**: ~2-3 minutes (depends on CPU)
- **100K documents**: ~20-30 minutes
- **Bottleneck**: Embedding generation (CPU-bound, not GPU-accelerated by default)

### Search Speed
- **Query latency**: <10ms for 100K documents
- **Scales well**: O(log n) with FAISS IndexIVF (not implemented, using IndexFlatL2)
- **Bottleneck**: Embedding generation for query (~50-100ms)

### Memory Usage
- **Index size**: ~3KB per document (768-dim)
- **Peak during indexing**: 2x final size (temporary arrays)
- **Search memory**: Minimal (query embedding only)

## When to Use This Setup

### ✅ Good For:
- **Local development**: Personal codebase search
- **Prototyping**: Quick RAG experiments
- **Small-medium codebases**: <500K documents
- **Single-user**: No concurrent access needed
- **Fast iteration**: Easy to rebuild index

### ❌ Not Good For:
- **Production multi-user**: Need Qdrant
- **Very large codebases**: >1M documents (memory issues)
- **Frequent updates**: Re-indexing overhead
- **Advanced filtering**: Need metadata queries
- **Multi-process**: Need shared database

## Recommendations

### For Your Setup (M4 Max 128GB, Local Development)

1. **Start with FAISS**: Simple, fast, no Docker
2. **Monitor memory**: Check `rag.get_stats()['estimated_memory_mb']`
3. **Save indexes**: Use versioned saves (`codebase-v1.index`)
4. **Re-index weekly**: Or after major changes
5. **Use bge-small for speed**: If memory becomes an issue
6. **Switch to Qdrant**: If you need persistence or scale

### Best Practices

```python
# 1. Save index after indexing
rag.save_index("data/rag_indexes/codebase.index")

# 2. Load on startup
rag = RAGServiceFAISS(index_path="data/rag_indexes/codebase.index")

# 3. Monitor memory
stats = rag.get_stats()
print(f"Memory: {stats['estimated_memory_mb']}MB")

# 4. Filter file types to reduce size
rag.index_codebase(".", file_extensions=['.py', '.md'])

# 5. Use larger chunks to reduce document count
rag.index_codebase(".", chunk_size=2000)  # Instead of 1000
```

## Comparison: FAISS vs Qdrant

| Feature | FAISS (Current) | Qdrant (Alternative) |
|---------|----------------|---------------------|
| **Setup** | ✅ `pip install` | ⚠️ Docker service |
| **Memory** | ⚠️ All in RAM | ✅ Disk-based |
| **Persistence** | ❌ Manual | ✅ Automatic |
| **Multi-process** | ❌ No | ✅ Yes |
| **Filtering** | ❌ Basic | ✅ Advanced |
| **Scale** | ⚠️ ~1M docs | ✅ Millions |
| **Speed** | ✅ Very fast | ✅ Fast |
| **Best for** | Dev/Prototype | Production |

## Next Steps

1. **Try it**: Index your codebase and test search quality
2. **Monitor**: Check memory usage with `get_stats()`
3. **Optimize**: Adjust chunk size, file types based on results
4. **Upgrade**: Switch to Qdrant if you hit limitations

See also:
- [RAG Quick Start](./rag-quickstart.md)
- [FAISS vs Qdrant Comparison](./faiss-vs-qdrant-comparison.md)

