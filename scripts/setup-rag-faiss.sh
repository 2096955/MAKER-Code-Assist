#!/bin/bash
# Setup RAG with FAISS and nomic-embed-text-v1.5
# No Docker required - everything runs in-memory

set -e

echo "🔍 Setting up Local RAG with FAISS + nomic-embed-text-v1.5"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi

# Check pip
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 not found. Please install pip"
    exit 1
fi

echo "✅ Python environment ready"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install --upgrade pip
pip3 install faiss-cpu sentence-transformers httpx numpy

echo ""
echo "✅ Dependencies installed"
echo ""

# Create data directory for saved indexes
mkdir -p data/rag_indexes

echo "📝 Next steps:"
echo ""
echo "1. Test the RAG service:"
echo "   python3 -c \"from orchestrator.rag_service_faiss import RAGServiceFAISS; print('✅ RAG service ready')\""
echo ""
echo "2. Index your codebase:"
echo "   python3 scripts/index_codebase.py"
echo ""
echo "3. Run the Streamlit UI:"
echo "   streamlit run orchestrator/rag_ui.py"
echo ""
echo "4. Or use in Python:"
echo "   from orchestrator.rag_service_faiss import RAGServiceFAISS"
echo "   rag = RAGServiceFAISS()"
echo "   rag.index_codebase('.')"
echo ""
echo "📚 See docs/rag-limitations.md for limitations and best practices"
echo ""





