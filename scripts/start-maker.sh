#!/bin/bash
# Start MAKER system with both High and Low mode orchestrators
# Usage: ./start-maker.sh [all|high|low]

set -e

MODE=${1:-all}

if [ "$MODE" != "all" ] && [ "$MODE" != "high" ] && [ "$MODE" != "low" ]; then
    echo "❌ Invalid mode: $MODE"
    echo "Usage: $0 [all|high|low]"
    echo ""
    echo "  all  - Start both High and Low mode orchestrators (default)"
    echo "  high - Start only High mode orchestrator (requires Reviewer running)"
    echo "  low  - Start only Low mode orchestrator (no Reviewer needed)"
    exit 1
fi

echo "🚀 Starting MAKER system..."
echo ""

# Step 1: Start llama.cpp servers
echo "1️⃣ Starting llama.cpp servers..."
if [ "$MODE" = "high" ]; then
    export MAKER_MODE=high
    bash scripts/start-llama-servers.sh
elif [ "$MODE" = "low" ]; then
    export MAKER_MODE=low
    bash scripts/start-llama-servers.sh
else
    # For 'all' mode, start all 6 models (High mode servers)
    export MAKER_MODE=high
    bash scripts/start-llama-servers.sh
fi
echo ""

# Step 2: Start Docker services (orchestrators, MCP, Redis, etc.)
echo "2️⃣ Starting Docker services..."
if [ "$MODE" = "all" ]; then
    docker compose up -d orchestrator-high orchestrator-low mcp-server redis qdrant phoenix
    echo "   Started both High (8080) and Low (8081) orchestrators"
elif [ "$MODE" = "high" ]; then
    docker compose up -d orchestrator-high mcp-server redis qdrant phoenix
    echo "   Started High mode orchestrator (8080)"
elif [ "$MODE" = "low" ]; then
    docker compose up -d orchestrator-low mcp-server redis qdrant phoenix
    echo "   Started Low mode orchestrator (8081)"
fi
sleep 5
echo ""

# Step 3: Verify
echo "3️⃣ Verifying services..."
echo ""

# Check llama.cpp servers
for port in 8000 8001 8002 8004 8005; do
    if curl -s http://localhost:$port/health > /dev/null 2>&1; then
        echo "   ✅ Port $port: Running"
    else
        echo "   ❌ Port $port: NOT running"
    fi
done

# Check Reviewer (only if High mode servers are running)
if [ "$MODE" = "high" ] || [ "$MODE" = "all" ]; then
    if curl -s http://localhost:8003/health > /dev/null 2>&1; then
        echo "   ✅ Port 8003 (Reviewer): Running"
    else
        echo "   ❌ Port 8003 (Reviewer): NOT running"
    fi
else
    echo "   ⏭️  Port 8003 (Reviewer): Skipped (Low mode)"
fi

# Check orchestrators
if [ "$MODE" = "high" ] || [ "$MODE" = "all" ]; then
    if curl -s http://localhost:8080/health > /dev/null 2>&1; then
        echo "   ✅ Orchestrator High (8080): Running"
    else
        echo "   ❌ Orchestrator High (8080): NOT running"
    fi
fi

if [ "$MODE" = "low" ] || [ "$MODE" = "all" ]; then
    if curl -s http://localhost:8081/health > /dev/null 2>&1; then
        echo "   ✅ Orchestrator Low (8081): Running"
    else
        echo "   ❌ Orchestrator Low (8081): NOT running"
    fi
fi

echo ""
echo "✅ MAKER system started!"
echo ""

if [ "$MODE" = "all" ]; then
    echo "📊 Both modes available:"
    echo ""
    echo "   High Mode (port 8080):"
    echo "   • All 6 models running"
    echo "   • Reviewer (Qwen 32B) validates code"
    echo "   • RAM usage: ~128GB"
    echo "   • Best for: Production code"
    echo ""
    echo "   Low Mode (port 8081):"
    echo "   • 5 models running (same as High, Reviewer available but uses Planner reflection)"
    echo "   • Planner reflection validates code"
    echo "   • RAM usage: ~40-50GB active (Reviewer idle)"
    echo "   • Best for: Development/testing"
    echo ""
    echo "💡 In Continue extension:"
    echo "   • Select 'MakerCode - High (128GB RAM)' to use port 8080"
    echo "   • Select 'MakerCode - Low (40GB RAM)' to use port 8081"
elif [ "$MODE" = "high" ]; then
    echo "📊 High Mode (port 8080):"
    echo "   • All 6 models running"
    echo "   • Reviewer (Qwen 32B) validates code"
    echo "   • RAM usage: ~128GB"
    echo "   • Best for: Production code"
elif [ "$MODE" = "low" ]; then
    echo "📊 Low Mode (port 8081):"
    echo "   • 5 models running (Reviewer skipped)"
    echo "   • Planner reflection validates code"
    echo "   • RAM usage: ~40-50GB"
    echo "   • Best for: Development/testing"
fi

echo ""
