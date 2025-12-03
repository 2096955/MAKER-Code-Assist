#!/usr/bin/env python3
"""
Example: Using RAG with FAISS + nomic-embed-text-v1.5
Demonstrates basic usage and multi-modal support via Gemma2-2B
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.rag_service_faiss import RAGServiceFAISS


async def main():
    print("🔍 RAG Example with FAISS + nomic-embed-text-v1.5")
    print("=" * 60)
    print()
    
    # Initialize RAG service
    print("1. Initializing RAG service...")
    rag = RAGServiceFAISS(
        embedding_model="nomic-embed-text-v1.5",
        llm_url="http://localhost:8001/v1/chat/completions",  # Nemotron Nano 8B
        preprocessor_url="http://localhost:8000/v1/chat/completions"  # Gemma2-2B
    )
    print("   ✅ RAG service ready")
    print()
    
    # Option 1: Load existing index
    index_path = "data/rag_indexes/codebase.index"
    if Path(index_path).exists():
        print(f"2. Loading existing index from {index_path}...")
        rag.load_index(index_path)
        print("   ✅ Index loaded")
    else:
        print("2. No existing index found. Indexing codebase...")
        print("   (This may take a few minutes)")
        rag.index_codebase(".", chunk_size=1000)
        print("   ✅ Indexing complete")
        
        # Save index
        print(f"3. Saving index to {index_path}...")
        Path(index_path).parent.mkdir(parents=True, exist_ok=True)
        rag.save_index(index_path)
        print("   ✅ Index saved")
    
    print()
    
    # Display stats
    stats = rag.get_stats()
    print("📊 Index Statistics:")
    print(f"   Documents: {stats['total_documents']}")
    print(f"   Vectors: {stats['total_vectors']}")
    print(f"   Dimension: {stats['embedding_dimension']}")
    print(f"   Memory: ~{stats['estimated_memory_mb']}MB")
    print()
    
    # Example 1: Simple search
    print("4. Example: Simple Search")
    print("   Query: 'How does the orchestrator work?'")
    results = rag.search("How does the orchestrator work?", top_k=3)
    for i, doc in enumerate(results, 1):
        print(f"   Result {i} (score: {doc['score']:.3f}):")
        print(f"      File: {doc['metadata'].get('file_path', 'N/A')}")
        print(f"      Preview: {doc['text'][:100]}...")
    print()
    
    # Example 2: RAG query (retrieve + generate)
    print("5. Example: RAG Query (Retrieve + Generate)")
    print("   Question: 'What is MAKER voting?'")
    answer = await rag.query("What is MAKER voting?", top_k=5)
    print(f"   Answer: {answer[:200]}...")
    print()
    
    # Example 3: Multi-modal (if you have an image)
    print("6. Example: Multi-modal Document (Image)")
    print("   Note: This requires base64-encoded image data")
    print("   Uncomment and provide image data to test:")
    # image_base64 = "..."  # Your base64 image
    # await rag.add_multimodal_document(
    #     content=image_base64,
    #     content_type="image",
    #     metadata={"source": "screenshot.png"}
    # )
    print("   (Skipped - no image provided)")
    print()
    
    print("✅ Examples complete!")
    print()
    print("💡 Next steps:")
    print("   - Try different queries")
    print("   - Integrate with your Planner agent")
    print("   - Use Streamlit UI: streamlit run orchestrator/rag_ui.py")


if __name__ == "__main__":
    asyncio.run(main())





