#!/usr/bin/env python3
"""
RAG Service: Local RAG using Qdrant vector database
- Embedding model: nomic-embed-text-v1.5 (or bge-small-en-v1.5)
- Vector DB: Qdrant (Docker)
- LLM: Nemotron Nano 8B (or Devstral 24B for code-specific RAG)
"""

import os
import logging
from typing import List, Dict, Optional
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
import httpx

logger = logging.getLogger(__name__)


class RAGService:
    """Local RAG service using Qdrant and sentence-transformers"""
    
    def __init__(
        self,
        qdrant_url: str = None,
        embedding_model: str = "nomic-embed-text-v1.5",
        collection_name: str = "codebase_docs",
        llm_url: str = None
    ):
        """
        Initialize RAG service
        
        Args:
            qdrant_url: Qdrant server URL (default: http://localhost:6333)
            embedding_model: Sentence transformer model name
            collection_name: Qdrant collection name
            llm_url: LLM endpoint for generation (default: Nemotron Nano 8B)
        """
        self.qdrant_url = qdrant_url or os.getenv("QDRANT_URL", "http://localhost:6333")
        self.collection_name = collection_name
        self.llm_url = llm_url or os.getenv("PLANNER_URL", "http://localhost:8001/v1/chat/completions")
        
        # Initialize Qdrant client
        self.client = QdrantClient(url=self.qdrant_url)
        
        # Initialize embedding model
        logger.info(f"Loading embedding model: {embedding_model}...")
        self.embedder = SentenceTransformer(embedding_model)
        self.embedding_dim = self.embedder.get_sentence_embedding_dimension()
        
        # Create collection if it doesn't exist
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Create Qdrant collection if it doesn't exist"""
        try:
            collections = self.client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if self.collection_name not in collection_names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.embedding_dim,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
        except (ValueError, AttributeError, ConnectionError) as e:
            logger.error(f"Error ensuring collection: {e}")
    
    def add_documents(self, documents: List[Dict[str, str]], batch_size: int = 100):
        """
        Add documents to vector database
        
        Args:
            documents: List of dicts with 'id', 'text', and optional 'metadata'
            batch_size: Batch size for insertion
        """
        points = []
        for doc in documents:
            # Generate embedding
            embedding = self.embedder.encode(doc['text']).tolist()
            
            # Create point
            point = PointStruct(
                id=doc.get('id', hash(doc['text'])),
                vector=embedding,
                payload={
                    'text': doc['text'],
                    **doc.get('metadata', {})
                }
            )
            points.append(point)
            
            # Insert in batches
            if len(points) >= batch_size:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                points = []
        
        # Insert remaining points
        if points:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
        
        logger.info(f"Added {len(documents)} documents to {self.collection_name}")
    
    def search(self, query: str, top_k: int = 5, filter_metadata: Optional[Dict] = None) -> List[Dict]:
        """
        Search for similar documents
        
        Args:
            query: Search query
            top_k: Number of results to return
            filter_metadata: Optional metadata filter
            
        Returns:
            List of relevant documents with scores
        """
        # Generate query embedding
        query_embedding = self.embedder.encode(query).tolist()
        
        # Search Qdrant
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=top_k,
            query_filter=None  # Can add filtering here
        )
        
        # Format results
        documents = []
        for result in results:
            documents.append({
                'id': result.id,
                'text': result.payload.get('text', ''),
                'score': result.score,
                'metadata': {k: v for k, v in result.payload.items() if k != 'text'}
            })
        
        return documents
    
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
    
    def index_codebase(self, codebase_root: str, file_extensions: List[str] = None):
        """
        Index codebase files into vector database
        
        Args:
            codebase_root: Root directory of codebase
            file_extensions: List of file extensions to index (default: .py, .md, .txt, .js, .ts)
        """
        if file_extensions is None:
            file_extensions = ['.py', '.md', '.txt', '.js', '.ts', '.tsx', '.jsx']
        
        root = Path(codebase_root)
        excluded = {
            '.git', 'node_modules', 'dist', 'build', '__pycache__', 
            'models', '.venv', 'venv', 'env', '.env', 'vendor', 
            'target', '.docker', 'docker-data', '.cache', 'logs',
            'qdrant_data', 'redis_data'
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
                    
                    # Split into chunks (simple approach - can be improved)
                    chunk_size = 1000
                    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
                    
                    for i, chunk in enumerate(chunks):
                        documents.append({
                            'id': hash(f"{file_path}:{i}"),
                            'text': chunk,
                            'metadata': {
                                'file_path': str(file_path.relative_to(root)),
                                'chunk_index': i,
                                'file_type': file_path.suffix
                            }
                        })
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")
        
        # Add to vector database
        if documents:
            self.add_documents(documents)
            print(f"Indexed {len(documents)} chunks from {codebase_root}")
        else:
            print("No documents found to index")
    
    def get_stats(self) -> Dict:
        """Get statistics about the collection"""
        try:
            collection_info = self.client.get_collection(self.collection_name)
            return {
                'total_documents': collection_info.points_count,
                'total_vectors': collection_info.points_count,
                'embedding_dimension': self.embedding_dim,
                'index_type': 'Qdrant (Database)'
            }
        except (ValueError, AttributeError, ConnectionError):
            return {
                'total_documents': 0,
                'total_vectors': 0,
                'embedding_dimension': self.embedding_dim,
                'index_type': 'Qdrant (Database)'
            }

