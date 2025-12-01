#!/bin/bash
# Switch MAKER mode between High and Low
# Usage: ./switch-maker-mode.sh [high|low]

set -e

MODE=${1:-high}

if [ "$MODE" != "high" ] && [ "$MODE" != "low" ]; then
    echo "❌ Invalid mode: $MODE"
    echo "Usage: $0 [high|low]"
    exit 1
fi

echo "🔄 Switching to MAKER $MODE mode..."
echo ""

# Stop current services
echo "1️⃣ Stopping services..."
bash scripts/stop-llama-servers.sh 2>/dev/null || true
docker compose down 2>/dev/null || true
echo ""

# Set environment and update docker-compose.yml
echo "2️⃣ Configuring $MODE mode..."
export MAKER_MODE=$MODE

# Update docker-compose.yml
if [ "$(uname)" = "Darwin" ]; then
    # macOS
    sed -i '' "s/MAKER_MODE=.*/MAKER_MODE=$MODE/" docker-compose.yml
else
    # Linux
    sed -i "s/MAKER_MODE=.*/MAKER_MODE=$MODE/" docker-compose.yml
fi

echo "   Set MAKER_MODE=$MODE in docker-compose.yml"
echo ""

# Start llama.cpp servers
echo "3️⃣ Starting llama.cpp servers..."
bash scripts/start-llama-servers.sh
echo ""

# Start orchestrator
echo "4️⃣ Starting orchestrator..."
docker compose up -d
sleep 5
echo ""

# Verify
echo "5️⃣ Verifying services..."
echo ""

# Check llama.cpp servers
for port in 8000 8001 8002 8004 8005; do
    if curl -s http://localhost:$port/health > /dev/null 2>&1; then
        echo "   ✅ Port $port: Running"
    else
        echo "   ❌ Port $port: NOT running"
    fi
done

# Check Reviewer (only in High mode)
if [ "$MODE" = "high" ]; then
    if curl -s http://localhost:8003/health > /dev/null 2>&1; then
        echo "   ✅ Port 8003 (Reviewer): Running"
    else
        echo "   ❌ Port 8003 (Reviewer): NOT running"
    fi
else
    echo "   ⏭️  Port 8003 (Reviewer): Skipped (Low mode)"
fi

# Check orchestrator
if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo "   ✅ Orchestrator (8080): Running"
else
    echo "   ❌ Orchestrator (8080): NOT running"
fi

echo ""
echo "✅ MAKER $MODE mode active!"
echo ""

if [ "$MODE" = "high" ]; then
    echo "📊 High Mode:"
    echo "   • All 6 models running"
    echo "   • Reviewer (Qwen 32B) validates code"
    echo "   • RAM usage: ~128GB"
    echo "   • Best for: Production code"
else
    echo "📊 Low Mode:"
    echo "   • 5 models running (Reviewer skipped)"
    echo "   • Planner reflection validates code"
    echo "   • RAM usage: ~40-50GB"
    echo "   • Best for: Development/testing"
fi

echo ""
echo "💡 In Continue extension, both configs will now use $MODE mode"
echo ""
