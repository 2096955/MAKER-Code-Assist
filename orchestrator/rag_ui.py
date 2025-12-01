#!/usr/bin/env python3
"""
Simple Streamlit UI for RAG Service (FAISS or Qdrant)
Based on: https://dzone.com/articles/local-rag-app-with-ui-no-vector-database
"""

import streamlit as st
import os
from pathlib import Path
from typing import Optional

# Try to import both RAG services
try:
    from orchestrator.rag_service_faiss import RAGServiceFAISS
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

try:
    from orchestrator.rag_service import RAGService
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False


def main():
    st.set_page_config(
        page_title="Local RAG Assistant",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 Local RAG Assistant")
    st.markdown("Query your codebase using RAG (Retrieval-Augmented Generation)")
    
    # Sidebar configuration
    with st.sidebar:
        st.header("Configuration")
        
        # Choose RAG backend
        if FAISS_AVAILABLE and QDRANT_AVAILABLE:
            backend = st.radio(
                "Vector Store",
                ["FAISS (In-Memory)", "Qdrant (Database)"],
                help="FAISS: No Docker needed, in-memory. Qdrant: Persistent, scalable."
            )
        elif FAISS_AVAILABLE:
            backend = "FAISS (In-Memory)"
            st.info("Using FAISS (Qdrant not available)")
        elif QDRANT_AVAILABLE:
            backend = "Qdrant (Database)"
            st.info("Using Qdrant (FAISS not available)")
        else:
            st.error("No RAG backend available. Install: pip install faiss-cpu sentence-transformers")
            st.stop()
        
        # Embedding model selection
        embedding_model = st.selectbox(
            "Embedding Model",
            ["nomic-embed-text-v1.5", "bge-small-en-v1.5"],
            help="nomic-embed: Better quality (768 dim). bge-small: Faster (384 dim)."
        )
        
        # LLM selection
        llm_url = st.selectbox(
            "LLM Endpoint",
            [
                "http://localhost:8001/v1/chat/completions",  # Nemotron Nano 8B
                "http://localhost:8002/v1/chat/completions",  # Devstral 24B
                "http://localhost:8004/v1/chat/completions",  # Qwen2.5-1.5B
            ],
            format_func=lambda x: {
                "http://localhost:8001/v1/chat/completions": "Nemotron Nano 8B (General)",
                "http://localhost:8002/v1/chat/completions": "Devstral 24B (Code)",
                "http://localhost:8004/v1/chat/completions": "Qwen2.5-1.5B (Fast)",
            }.get(x, x)
        )
        
        st.divider()
        
        # Indexing section
        st.subheader("Index Codebase")
        codebase_path = st.text_input(
            "Codebase Path",
            value=str(Path.cwd()),
            help="Path to your codebase directory"
        )
        
        if st.button("📚 Index Codebase", type="primary"):
            with st.spinner("Indexing codebase..."):
                try:
                    if "FAISS" in backend:
                        rag = RAGServiceFAISS(
                            embedding_model=embedding_model,
                            llm_url=llm_url
                        )
                    else:
                        rag = RAGService(
                            embedding_model=embedding_model,
                            llm_url=llm_url
                        )
                    
                    rag.index_codebase(codebase_path)
                    st.success(f"Indexed codebase! ({rag.get_stats()['total_documents']} documents)")
                    st.session_state['rag'] = rag
                except Exception as e:
                    st.error(f"Error indexing: {e}")
        
        # Load saved index (FAISS only)
        if "FAISS" in backend:
            index_file = st.file_uploader("Load Saved Index", type=['index'])
            if index_file:
                with st.spinner("Loading index..."):
                    try:
                        # Save uploaded file temporarily
                        temp_path = f"/tmp/{index_file.name}"
                        with open(temp_path, 'wb') as f:
                            f.write(index_file.read())
                        
                        rag = RAGServiceFAISS(
                            embedding_model=embedding_model,
                            index_path=temp_path,
                            llm_url=llm_url
                        )
                        st.session_state['rag'] = rag
                        st.success("Index loaded!")
                    except Exception as e:
                        st.error(f"Error loading index: {e}")
    
    # Main content area
    if 'rag' not in st.session_state:
        st.info("👈 Please index your codebase first using the sidebar")
        return
    
    rag = st.session_state['rag']
    
    # Display stats
    stats = rag.get_stats()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Documents", stats['total_documents'])
    with col2:
        st.metric("Vectors", stats['total_vectors'])
    with col3:
        st.metric("Backend", stats.get('index_type', backend))
    
    st.divider()
    
    # Query interface
    query = st.text_input(
        "Ask a question about your codebase:",
        placeholder="e.g., How does the orchestrator work?",
        key="query_input"
    )
    
    col1, col2 = st.columns([1, 4])
    with col1:
        top_k = st.slider("Top K", 1, 20, 5)
    with col2:
        search_button = st.button("🔍 Search", type="primary", use_container_width=True)
        rag_button = st.button("💬 RAG Query (Generate Answer)", use_container_width=True)
    
    if search_button and query:
        with st.spinner("Searching..."):
            results = rag.search(query, top_k=top_k)
            
            if results:
                st.subheader(f"Search Results ({len(results)} found)")
                for i, doc in enumerate(results, 1):
                    with st.expander(f"Result {i} (Score: {doc['score']:.3f}) - {doc['metadata'].get('file_path', 'N/A')}"):
                        st.code(doc['text'], language=doc['metadata'].get('file_type', '').lstrip('.'))
                        st.json(doc['metadata'])
            else:
                st.warning("No results found")
    
    if rag_button and query:
        with st.spinner("Generating answer..."):
            import asyncio
            answer = asyncio.run(rag.query(query, top_k=top_k))
            st.subheader("Answer")
            st.write(answer)
            
            # Show sources
            with st.expander("View Sources"):
                results = rag.search(query, top_k=top_k)
                for i, doc in enumerate(results, 1):
                    st.markdown(f"**Source {i}** (Score: {doc['score']:.3f})")
                    st.text(doc['metadata'].get('file_path', 'N/A'))
                    st.code(doc['text'][:500] + "...", language=doc['metadata'].get('file_type', '').lstrip('.'))
    
    # Save index (FAISS only)
    if "FAISS" in backend and st.button("💾 Save Index"):
        save_path = st.text_input("Save path:", value="./rag_index.index")
        if save_path:
            rag.save_index(save_path)
            st.success(f"Index saved to {save_path}")


if __name__ == "__main__":
    main()

