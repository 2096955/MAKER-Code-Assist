#!/usr/bin/env python3
"""
RAG Service: Local RAG using FAISS (in-memory, no vector database)
- Embedding model: nomic-embed-text-v1.5 (or bge-small-en-v1.5)
- Vector Search: FAISS (in-memory index)
- LLM: Nemotron Nano 8B (or Devstral 24B for code-specific RAG)
- Multi-modal: Uses Gemma2-2B Preprocessor for image/audio → text

This is simpler than Qdrant - no Docker service needed, everything runs in memory.
Perfect for local development, prototyping, or smaller codebases.

LIMITATIONS:
- Memory: Index size limited by available RAM (~500MB per 10K docs with 768-dim embeddings)
- Persistence: Must manually save/load indexes (not automatic)
- Single-process: Not suitable for concurrent multi-user access
- No advanced filtering: Basic similarity search only
- Re-indexing: Must rebuild index when codebase changes significantly
"""

import os
import pickle
from typing import List, Dict, Optional
from pathlib import Path
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import httpx
import base64


class RAGServiceFAISS:
    """Local RAG service using FAISS (in-memory, no database)"""
    
    def __init__(
        self,
        embedding_model: str = "nomic-embed-text-v1.5",
        index_path: Optional[str] = None,
        llm_url: str = None,
        preprocessor_url: str = None
    ):
        """
        Initialize RAG service with FAISS
        
        Args:
            embedding_model: Sentence transformer model name
            index_path: Optional path to save/load FAISS index
            llm_url: LLM endpoint for generation (default: Nemotron Nano 8B)
            preprocessor_url: Gemma2-2B endpoint for multi-modal preprocessing
        """
        self.index_path = index_path
        self.llm_url = llm_url or os.getenv("PLANNER_URL", "http://localhost:8001/v1/chat/completions")
        self.preprocessor_url = preprocessor_url or os.getenv("PREPROCESSOR_URL", "http://localhost:8000/v1/chat/completions")
        
        # Initialize embedding model
        print(f"Loading embedding model: {embedding_model}...")
        self.embedder = SentenceTransformer(embedding_model)
        self.embedding_dim = self.embedder.get_sentence_embedding_dimension()
        
        # Initialize FAISS index (L2 distance, normalized for cosine similarity)
        self.index = faiss.IndexFlatL2(self.embedding_dim)
        
        # Store document metadata
        self.documents: List[Dict[str, str]] = []
        
        # Load existing index if path provided
        if self.index_path and os.path.exists(self.index_path):
            self.load_index(self.index_path)
    
    async def _preprocess_multimodal(self, content: str, content_type: str) -> str:
        """
        Use Gemma2-2B Preprocessor to convert multi-modal input to text
        
        Args:
            content: Base64-encoded image/audio or text
            content_type: 'image', 'audio', or 'text'
            
        Returns:
            Preprocessed text
        """
        if content_type == 'text':
            return content
        
        # Use Gemma2-2B Preprocessor for multi-modal conversion
        prompt = {
            'image': 'Describe this image in detail, focusing on any code, diagrams, or technical content.',
            'audio': 'Transcribe this audio to text.'
        }.get(content_type, 'Convert this input to text.')
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # For images: send base64 data
                # For audio: send base64 data
                # Note: Actual implementation depends on llama.cpp server capabilities
                # This is a placeholder - you may need to adjust based on your setup
                response = await client.post(
                    self.preprocessor_url,
                    json={
                        "model": "default",
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {"type": content_type, content_type: content}
                                ] if content_type != 'text' else prompt
                            }
                        ],
                        "temperature": 0.1,
                        "max_tokens": 500
                    }
                )
                if response.status_code == 200:
                    result = response.json()
                    return result.get("choices", [{}])[0].get("message", {}).get("content", content)
        except Exception as e:
            print(f"Warning: Multi-modal preprocessing failed: {e}")
        
        return content
    
    def add_documents(self, documents: List[Dict[str, str]]):
        """
        Add documents to FAISS index
        
        Args:
            documents: List of dicts with 'text' and optional 'metadata'
        """
        if not documents:
            return
        
        # Generate embeddings
        texts = [doc['text'] for doc in documents]
        embeddings = self.embedder.encode(texts, show_progress_bar=True, convert_to_numpy=True)
        
        # Normalize for cosine similarity (recommended for nomic-embed)
        faiss.normalize_L2(embeddings)
        
        # Add to FAISS index
        self.index.add(embeddings.astype('float32'))
        
        # Store document metadata
        for doc in documents:
            self.documents.append({
                'text': doc['text'],
                'metadata': doc.get('metadata', {})
            })
        
        print(f"Added {len(documents)} documents to FAISS index (total: {self.index.ntotal})")
    
    async def add_multimodal_document(self, content: str, content_type: str, metadata: Dict = None):
        """
        Add multi-modal document (image/audio) via Gemma2-2B preprocessing
        
        Args:
            content: Base64-encoded image/audio or text
            content_type: 'image', 'audio', or 'text'
            metadata: Optional metadata dict
        """
        # Preprocess to text using Gemma2-2B
        text = await self._preprocess_multimodal(content, content_type)
        
        # Add as regular text document
        self.add_documents([{
            'text': text,
            'metadata': {
                **(metadata or {}),
                'original_type': content_type,
                'preprocessed': True
            }
        }])
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Search for similar documents
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of relevant documents with scores
        """
        if self.index.ntotal == 0:
            return []
        
        # Generate query embedding
        query_embedding = self.embedder.encode([query], convert_to_numpy=True)
        
        # Normalize for cosine similarity
        faiss.normalize_L2(query_embedding)
        
        # Search FAISS index
        distances, indices = self.index.search(query_embedding.astype('float32'), top_k)
        
        # Format results (convert L2 distance to similarity score)
        results = []
        for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
            if idx < len(self.documents):
                # Convert L2 distance to similarity (1 / (1 + distance))
                # For normalized vectors, distance range is [0, 2], similarity is [0.33, 1.0]
                similarity = 1.0 / (1.0 + distance)
                results.append({
                    'id': int(idx),
                    'text': self.documents[idx]['text'],
                    'score': float(similarity),
                    'distance': float(distance),
                    'metadata': self.documents[idx].get('metadata', {})
                })
        
        return results
    
    async def query(self, question: str, top_k: int = 5) -> str:
        """
        RAG query: Retrieve relevant context and generate answer
        
        Args:
            question: User question
            top_k: Number of documents to retrieve
            
        Returns:
            Generated answer
        """
        # Retrieve relevant documents
        docs = self.search(question, top_k=top_k)
        
        if not docs:
            return "No relevant documents found in the knowledge base."
        
        # Build context
        context = "\n\n".join([f"[{i+1}] {doc['text']}" for i, doc in enumerate(docs)])
        
        # Generate answer using LLM
        prompt = f"""Based on the following context, answer the question. If the answer cannot be found in the context, say so.

Context:
{context}

Question: {question}

Answer:"""
        
        # Call LLM (Nemotron Nano 8B or Devstral 24B)
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self.llm_url,
                json={
                    "model": "local",
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant that answers questions based on provided context."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1000
                }
            )
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
    
    def index_codebase(self, codebase_root: str, file_extensions: List[str] = None, chunk_size: int = 1000):
        """
        Index codebase files into FAISS index
        
        Args:
            codebase_root: Root directory of codebase
            file_extensions: List of file extensions to index
            chunk_size: Size of text chunks
        """
        if file_extensions is None:
            file_extensions = ['.py', '.md', '.txt', '.js', '.ts', '.tsx', '.jsx', '.json', '.yaml', '.yml']
        
        root = Path(codebase_root)
        excluded = {
            '.git', 'node_modules', 'dist', 'build', '__pycache__', 
            'models', '.venv', 'venv', 'env', '.env', 'vendor', 
            'target', '.docker', 'docker-data', '.cache', 'logs',
            'qdrant_data', 'redis_data', '.genkit', 'data'
        }
        
        documents = []
        for file_path in root.rglob('*'):
            if file_path.is_file():
                # Skip excluded directories
                if any(excluded_dir in file_path.parts for excluded_dir in excluded):
                    continue
                
                # Check file extension
                if file_path.suffix not in file_extensions:
                    continue
                
                try:
                    # Read file
                    text = file_path.read_text(encoding='utf-8', errors='ignore')
                    
                    # Skip empty files
                    if not text.strip():
                        continue
                    
                    # Split into chunks
                    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
                    
                    for i, chunk in enumerate(chunks):
                        documents.append({
                            'text': chunk,
                            'metadata': {
                                'file_path': str(file_path.relative_to(root)),
                                'chunk_index': i,
                                'file_type': file_path.suffix
                            }
                        })
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
        
        # Add to FAISS index
        if documents:
            self.add_documents(documents)
            print(f"Indexed {len(documents)} chunks from {codebase_root}")
        else:
            print("No documents found to index")
    
    def save_index(self, path: str):
        """Save FAISS index and documents to disk"""
        # Save FAISS index
        faiss.write_index(self.index, path)
        
        # Save documents metadata
        metadata_path = path + ".metadata"
        with open(metadata_path, 'wb') as f:
            pickle.dump(self.documents, f)
        
        print(f"Saved index to {path} and metadata to {metadata_path}")
    
    def load_index(self, path: str):
        """Load FAISS index and documents from disk"""
        # Load FAISS index
        self.index = faiss.read_index(path)
        
        # Load documents metadata
        metadata_path = path + ".metadata"
        if os.path.exists(metadata_path):
            with open(metadata_path, 'rb') as f:
                self.documents = pickle.load(f)
        
        print(f"Loaded index from {path} ({self.index.ntotal} vectors)")
    
    def get_stats(self) -> Dict:
        """Get statistics about the index"""
        # Estimate memory usage (rough calculation)
        # Each vector: embedding_dim * 4 bytes (float32)
        # Metadata: variable, estimate ~1KB per document
        vector_memory_mb = (self.index.ntotal * self.embedding_dim * 4) / (1024 * 1024)
        metadata_memory_mb = (len(self.documents) * 1024) / (1024 * 1024)
        total_memory_mb = vector_memory_mb + metadata_memory_mb
        
        return {
            'total_documents': len(self.documents),
            'total_vectors': self.index.ntotal,
            'embedding_dimension': self.embedding_dim,
            'index_type': 'FAISS (in-memory)',
            'estimated_memory_mb': round(total_memory_mb, 2),
            'vector_memory_mb': round(vector_memory_mb, 2),
            'metadata_memory_mb': round(metadata_memory_mb, 2)
        }
