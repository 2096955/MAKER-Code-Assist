#!/bin/bash
set -e

echo "🚀 SWE-bench Lite Evaluation for MAKER"
echo "======================================"
echo ""

# Configuration
NUM_INSTANCES=${1:-10}
OUTPUT_DIR=${2:-"results/swe_bench_$(date +%Y%m%d_%H%M%S)"}
ORCHESTRATOR_URL=${ORCHESTRATOR_URL:-"http://localhost:8080"}

echo "Configuration:"
echo "  Instances: $NUM_INSTANCES"
echo "  Output: $OUTPUT_DIR"
echo "  Orchestrator: $ORCHESTRATOR_URL"
echo ""

# Check dependencies
echo "📦 Checking dependencies..."
python3 -c "import datasets, httpx, numpy" 2>/dev/null || {
  echo "❌ Missing dependencies. Installing..."
  pip install datasets httpx numpy matplotlib
}

# Check services
echo ""
echo "🔍 Checking MAKER services..."

# Check orchestrator
if curl -s "$ORCHESTRATOR_URL/health" > /dev/null 2>&1; then
  echo "  ✅ Orchestrator ($ORCHESTRATOR_URL)"
else
  echo "  ❌ Orchestrator not running at $ORCHESTRATOR_URL"
  echo ""
  echo "  Start services with:"
  echo "    bash scripts/start-llama-servers.sh"
  echo "    docker compose up -d"
  exit 1
fi

# Check llama.cpp servers
for port in 8000 8001 8002 8003 8004; do
  if curl -s http://localhost:$port/health > /dev/null 2>&1 || \
     curl -s http://localhost:$port/v1/models > /dev/null 2>&1; then
    echo "  ✅ Agent on port $port"
  else
    echo "  ⚠️  Agent on port $port not responding (may not be critical)"
  fi
done

# Check MCP server
if curl -s http://localhost:9001/health > /dev/null 2>&1; then
  echo "  ✅ MCP Server (port 9001)"
else
  echo "  ⚠️  MCP Server not running (EE Memory may not work)"
fi

echo ""
echo "======================================"
echo "Starting evaluation..."
echo "======================================"
echo ""

# Run evaluation
python3 tests/swe_bench_harness.py \
  --num_instances "$NUM_INSTANCES" \
  --orchestrator_url "$ORCHESTRATOR_URL" \
  --output_dir "$OUTPUT_DIR" \
  --ee_mode

HARNESS_EXIT=$?

if [ $HARNESS_EXIT -ne 0 ]; then
  echo ""
  echo "❌ Evaluation failed with exit code $HARNESS_EXIT"
  exit $HARNESS_EXIT
fi

echo ""
echo "======================================"
echo "Computing metrics..."
echo "======================================"
echo ""

# Compute metrics
python3 tests/swe_bench_metrics.py "$OUTPUT_DIR/predictions.jsonl"

METRICS_EXIT=$?

if [ $METRICS_EXIT -ne 0 ]; then
  echo ""
  echo "⚠️  Metrics computation had issues (exit code $METRICS_EXIT)"
fi

echo ""
echo "======================================"
echo "✅ Evaluation Complete!"
echo "======================================"
echo ""
echo "Results saved to: $OUTPUT_DIR"
echo ""
echo "Key files:"
echo "  - predictions.jsonl         (MAKER predictions)"
echo "  - evaluation_report.md      (Human-readable report)"
echo "  - metrics.json              (Detailed metrics)"
echo "  - visualizations/           (Charts and graphs)"
echo ""

# Display quick summary
if [ -f "$OUTPUT_DIR/metrics.json" ]; then
  echo "Quick Summary:"
  echo "=============="
  python3 -c "
import json
with open('$OUTPUT_DIR/metrics.json', 'r') as f:
    metrics = json.load(f)
    core = metrics.get('core_metrics', {})
    print(f\"  Total Instances: {core.get('total_instances', 0)}\")
    print(f\"  Resolved: {core.get('resolved', 0)}\")
    print(f\"  Resolve Rate: {core.get('resolve_rate', 0):.1%}\")

    ee = metrics.get('ee_memory', {})
    print(f\"  EE Narratives: {ee.get('avg_narratives', 0):.1f} avg\")

    maker = metrics.get('maker_metrics', {})
    print(f\"  MAKER Confidence: {maker.get('avg_confidence', 0):.3f}\")
"
  echo ""
fi

echo "Next steps:"
echo "  1. Review report: cat $OUTPUT_DIR/evaluation_report.md"
echo "  2. View visualizations: open $OUTPUT_DIR/visualizations/"
echo "  3. Run official evaluation: python tests/swe_bench_harness.py --evaluate_only --predictions_path $OUTPUT_DIR/predictions.jsonl"
echo ""
echo "Compare to baselines:"
echo "  GPT-4 Turbo: 53.3%"
echo "  Claude 3.5 Sonnet: 49.3%"
echo "  GPT-4o: 47.7%"
echo "  Target: >30% (competitive)"
echo ""
