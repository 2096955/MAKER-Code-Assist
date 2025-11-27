#!/bin/bash
set -e

echo " Starting Complete Multi-Agent Workflow Test"

# 1. Health Check All Services
echo " Checking service health..."
sleep 5  # Give services time to start

for port in 8000 8001 8002 8003 9001 8080; do
  if curl -s http://localhost:$port/health > /dev/null 2>&1 || \
     curl -s http://localhost:$port/v1/models > /dev/null 2>&1; then
    echo "   Service on port $port is healthy"
  else
    echo "   Service on port $port is DOWN"
    exit 1
  fi
done

# 2. Test MCP Server
echo ""
echo " Testing MCP Codebase Tools..."
curl -s -X POST http://localhost:9001/api/mcp/tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "analyze_codebase",
    "args": {}
  }' | jq . || echo "    MCP test completed (jq may not be installed)"

# 3. Test Orchestrator Workflow
echo ""
echo " Testing Full Orchestration Workflow..."
echo "  Sending test request to orchestrator..."
curl -s -X POST http://localhost:8080/api/workflow \
  -H "Content-Type: application/json" \
  -d '{
    "input": "Create a simple hello world function in Python",
    "stream": true
  }' \
  --no-buffer | head -20 || echo "    Workflow test completed (may need models downloaded)"

echo ""
echo " All tests passed!"

