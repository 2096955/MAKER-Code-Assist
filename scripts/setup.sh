#!/bin/bash
# Setup helper script for multi-agent system

set -e

echo "🚀 Multi-Agent System Setup"
echo "============================"
echo ""

# Check Docker
echo "📦 Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker Desktop."
    exit 1
fi

if ! docker ps > /dev/null 2>&1; then
    echo "⚠️  Docker is not running. Starting Docker Desktop..."
    open -a Docker 2>/dev/null || echo "Please start Docker Desktop manually"
    echo "⏳ Waiting for Docker to start (30 seconds)..."
    sleep 30
    
    # Check again
    if ! docker ps > /dev/null 2>&1; then
        echo "❌ Docker still not running. Please start Docker Desktop and try again."
        exit 1
    fi
fi
echo "✅ Docker is running"
echo ""

# Check HuggingFace
echo "🤗 Checking HuggingFace CLI..."
if ! command -v huggingface-cli &> /dev/null; then
    echo "⚠️  huggingface-cli not found. Installing..."
    pip install huggingface_hub[cli]
fi

if ! huggingface-cli whoami &> /dev/null 2>&1; then
    echo "⚠️  Not logged in to HuggingFace"
    echo ""
    echo "Please log in:"
    echo "1. Get your token from: https://huggingface.co/settings/tokens"
    echo "2. Run: huggingface-cli login"
    echo ""
    read -p "Press Enter after you've logged in, or Ctrl+C to cancel..."
fi
echo "✅ HuggingFace CLI ready"
echo ""

# Check models
echo "📥 Checking models..."
MODEL_COUNT=$(ls -1 models/*.gguf 2>/dev/null | wc -l | tr -d ' ')
if [ "$MODEL_COUNT" -lt 4 ]; then
    echo "⚠️  Models not fully downloaded ($MODEL_COUNT/4 found)"
    echo ""
    read -p "Download models now? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "📥 Downloading models (this will take a while, ~50GB)..."
        bash scripts/download-models.sh
    else
        echo "⏭️  Skipping model download"
        exit 0
    fi
else
    echo "✅ All models found"
fi
echo ""

# Start services
echo "🐳 Starting Docker services..."
docker compose up -d

echo ""
echo "⏳ Waiting for services to be healthy (60 seconds)..."
sleep 60

echo ""
echo "📊 Service status:"
docker compose ps

echo ""
echo "🧪 Running tests..."
bash tests/test_workflow.sh

echo ""
echo "✅ Setup complete!"
echo ""
echo "📝 Next steps:"
echo "1. Connect Windsurf/Cursor:"
echo "   Settings → Models → Add Custom OpenAI"
echo "   Base URL: http://localhost:8080/v1"
echo "   API Key: local"
echo ""
echo "2. Try it:"
echo "   Cmd+I: 'Plan and code a JWT auth system with tests'"
echo ""

