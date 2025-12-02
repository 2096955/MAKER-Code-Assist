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
import subprocess
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
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
    
    def _get_file_recency_score(self, file_path: str) -> float:
        """
        Get file recency score based on git timestamp (0.0 to 1.0).
        More recent files get higher scores.
        """
        try:
            # Get codebase root from environment (file_path is relative to codebase root)
            codebase_root = os.getenv("CODEBASE_ROOT", os.getcwd())
            
            # Get last modified time from git (run from codebase root)
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%ct', '--', file_path],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=codebase_root
            )
            if result.returncode == 0 and result.stdout.strip():
                timestamp = int(result.stdout.strip())
                # Score based on age: files modified in last 30 days = 1.0, older = lower
                age_days = (datetime.now().timestamp() - timestamp) / 86400
                if age_days <= 30:
                    return 1.0
                elif age_days <= 90:
                    return 0.8
                elif age_days <= 180:
                    return 0.6
                else:
                    return 0.4
        except Exception:
            pass
        
        # Fallback: use file system modification time
        try:
            if os.path.exists(file_path):
                mtime = os.path.getmtime(file_path)
                age_days = (datetime.now().timestamp() - mtime) / 86400
                if age_days <= 30:
                    return 0.9
                elif age_days <= 90:
                    return 0.7
                else:
                    return 0.5
        except Exception:
            pass
        
        return 0.5  # Default neutral score
    
    def _get_file_importance_score(self, file_path: str) -> float:
        """
        Get file importance score based on naming patterns (0.0 to 1.0).
        Main files, core modules get higher scores than tests, examples.
        """
        path_lower = file_path.lower()
        
        # High importance patterns
        if any(pattern in path_lower for pattern in ['main.py', 'app.py', 'index.py', 'core/', 'src/', 'lib/']):
            return 1.0
        
        # Medium importance
        if any(pattern in path_lower for pattern in ['utils/', 'helpers/', 'common/', 'base']):
            return 0.8
        
        # Lower importance
        if any(pattern in path_lower for pattern in ['test_', 'tests/', 'example', 'demo', 'sample']):
            return 0.4
        
        # Default
        return 0.7
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Search for similar documents with enhanced confidence scoring.
        
        Confidence score combines:
        - Semantic similarity (0.5 weight)
        - File recency (0.2 weight)
        - File importance (0.2 weight)
        - Result ranking boost (0.1 weight)
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of relevant documents with enhanced confidence scores
        """
        if self.index.ntotal == 0:
            return []
        
        # Generate query embedding
        query_embedding = self.embedder.encode([query], convert_to_numpy=True)
        
        # Normalize for cosine similarity
        faiss.normalize_L2(query_embedding)
        
        # Search FAISS index (get more results for re-ranking)
        search_k = min(top_k * 2, self.index.ntotal)
        distances, indices = self.index.search(query_embedding.astype('float32'), search_k)
        
        # Format results with enhanced confidence scoring
        results = []
        for rank, (distance, idx) in enumerate(zip(distances[0], indices[0])):
            if idx < len(self.documents):
                doc = self.documents[idx]
                metadata = doc.get('metadata', {})
                file_path = metadata.get('file_path', '')
                
                # Base similarity score (0.0 to 1.0)
                similarity = 1.0 / (1.0 + distance)
                
                # File recency score (0.0 to 1.0)
                recency_score = self._get_file_recency_score(file_path) if file_path else 0.5
                
                # File importance score (0.0 to 1.0)
                importance_score = self._get_file_importance_score(file_path) if file_path else 0.7
                
                # Ranking boost (higher rank = higher score)
                rank_boost = 1.0 - (rank / search_k) * 0.2  # Top result gets 1.0, last gets 0.8
                
                # Combined confidence score (weighted average)
                confidence = (
                    similarity * 0.5 +      # Semantic similarity (primary)
                    recency_score * 0.2 +   # File recency
                    importance_score * 0.2 + # File importance
                    rank_boost * 0.1         # Ranking boost
                )
                
                results.append({
                    'id': int(idx),
                    'text': doc['text'],
                    'score': float(similarity),  # Keep original similarity for backward compatibility
                    'confidence': float(confidence),  # New enhanced confidence score
                    'distance': float(distance),
                    'metadata': {
                        **metadata,
                        'recency_score': float(recency_score),
                        'importance_score': float(importance_score),
                        'rank': rank + 1
                    }
                })
        
        # Sort by confidence (highest first) and return top_k
        results.sort(key=lambda x: x['confidence'], reverse=True)
        return results[:top_k]
    
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
