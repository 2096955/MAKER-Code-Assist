#!/usr/bin/env python3
"""
Index codebase for RAG using FAISS + nomic-embed-text-v1.5
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.rag_service_faiss import RAGServiceFAISS

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Index codebase for RAG")
    parser.add_argument(
        "--path",
        type=str,
        default=".",
        help="Path to codebase root (default: current directory)"
    )
    parser.add_argument(
        "--save",
        type=str,
        default=None,
        help="Path to save FAISS index (default: data/rag_indexes/codebase.index)"
    )
    parser.add_argument(
        "--embedding-model",
        type=str,
        default="nomic-embed-text-v1.5",
        choices=["nomic-embed-text-v1.5", "bge-small-en-v1.5"],
        help="Embedding model to use"
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Chunk size for documents (default: 1000)"
    )
    
    args = parser.parse_args()
    
    # Default save path
    if args.save is None:
        codebase_name = Path(args.path).name or "codebase"
        os.makedirs("data/rag_indexes", exist_ok=True)
        args.save = f"data/rag_indexes/{codebase_name}.index"
    
    print(f"🔍 Initializing RAG service with {args.embedding_model}...")
    rag = RAGServiceFAISS(
        embedding_model=args.embedding_model,
        index_path=None  # Will save after indexing
    )
    
    print(f"📚 Indexing codebase: {args.path}")
    print(f"   Chunk size: {args.chunk_size}")
    print(f"   This may take a few minutes...")
    print()
    
    rag.index_codebase(args.path, chunk_size=args.chunk_size)
    
    print()
    print(f"💾 Saving index to {args.save}...")
    rag.save_index(args.save)
    
    stats = rag.get_stats()
    print()
    print("✅ Indexing complete!")
    print(f"   Documents: {stats['total_documents']}")
    print(f"   Vectors: {stats['total_vectors']}")
    print(f"   Dimension: {stats['embedding_dimension']}")
    print(f"   Saved to: {args.save}")
    print()
    print("📝 To load this index later:")
    print(f"   rag = RAGServiceFAISS(index_path='{args.save}')")

if __name__ == "__main__":
    main()

