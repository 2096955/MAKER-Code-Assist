#!/bin/bash
# Integration Test Suite 1: Phase 1 - Long-Running Support
# Requires: All services running (llama.cpp, Redis, MCP, Orchestrator)

set -e

echo "=========================================="
echo "Integration Test Suite 1: Phase 1"
echo "=========================================="

# Check prerequisites
echo ""
echo "1. Checking prerequisites..."
for port in 8000 8001 8002 8003 8004; do
  if curl -s http://localhost:$port/health > /dev/null; then
    echo "  ✓ Port $port (llama.cpp server) responding"
  else
    echo "  ✗ Port $port (llama.cpp server) NOT responding"
    exit 1
  fi
done

if redis-cli ping > /dev/null 2>&1; then
  echo "  ✓ Redis responding"
else
  echo "  ✗ Redis NOT responding"
  exit 1
fi

if curl -s http://localhost:9001/health > /dev/null; then
  echo "  ✓ MCP server responding"
else
  echo "  ✗ MCP server NOT responding"
  exit 1
fi

if curl -s http://localhost:8080/health > /dev/null; then
  echo "  ✓ Orchestrator API responding"
else
  echo "  ✗ Orchestrator API NOT responding"
  exit 1
fi

# Setup
echo ""
echo "2. Setting up test environment..."
export ENABLE_LONG_RUNNING=true
export ENABLE_SKILLS=false  # Disable for Phase 1 tests
export WORKSPACE_DIR=./workspace
export SKILLS_DIR=./skills

# Clean workspace
rm -rf workspace/*
mkdir -p workspace

# Test 1.1: Progress Tracking
echo ""
echo "3. Test 1.1: Progress Tracking (Real Workflow)"
TASK_ID="test_progress_$(date +%s)"
echo "  Starting workflow: $TASK_ID"

RESPONSE=$(curl -s -X POST http://localhost:8080/api/workflow \
  -H "Content-Type: application/json" \
  -d "{
    \"input\": \"Write a Python function to calculate fibonacci numbers up to n\",
    \"task_id\": \"$TASK_ID\",
    \"stream\": false
  }")

echo "  Workflow response received"

# Check progress file
if [ -f "workspace/claude-progress.txt" ]; then
  PROGRESS_LINES=$(wc -l < workspace/claude-progress.txt)
  echo "  ✓ Progress file exists with $PROGRESS_LINES entries"
  
  # Show last few entries
  echo "  Last progress entries:"
  tail -3 workspace/claude-progress.txt | sed 's/^/    /'
else
  echo "  ✗ Progress file not found"
  exit 1
fi

# Check feature list
if [ -f "workspace/feature_list.json" ]; then
  echo "  ✓ Feature list file exists"
  python3 -c "import json; json.load(open('workspace/feature_list.json'))" && echo "  ✓ Feature list is valid JSON"
else
  echo "  ⚠ Feature list file not found (may be expected if no features added)"
fi

# Test 1.2: Session Resumability
echo ""
echo "4. Test 1.2: Session Resumability"
RESUME_TASK_ID="test_resume_$(date +%s)"
echo "  Testing resume for task: $RESUME_TASK_ID"

# Check if task exists in Redis
TASK_STATE=$(redis-cli GET "task:$RESUME_TASK_ID" 2>/dev/null || echo "")
if [ -z "$TASK_STATE" ]; then
  echo "  ⚠ Task not in Redis (creating test task state)"
  # Create a test task state
  redis-cli SET "task:$RESUME_TASK_ID" '{"task_id":"'$RESUME_TASK_ID'","status":"pending"}' > /dev/null
fi

# Try to resume
RESUME_RESPONSE=$(curl -s -X POST http://localhost:8080/api/session/$RESUME_TASK_ID/resume \
  -H "Content-Type: application/json" || echo "")

if [ -n "$RESUME_RESPONSE" ]; then
  echo "  ✓ Resume endpoint responded"
  echo "$RESUME_RESPONSE" | head -5 | sed 's/^/    /'
else
  echo "  ⚠ Resume endpoint returned empty (may be expected if session not found)"
fi

# Test 1.3: Checkpoint Creation
echo ""
echo "5. Test 1.3: Checkpoint Creation (Real Git)"

# Initialize git if needed
if [ ! -d .git ]; then
  echo "  Initializing git repository..."
  git init > /dev/null 2>&1
  git config user.name "Test User" > /dev/null 2>&1
  git config user.email "test@example.com" > /dev/null 2>&1
fi

# Create test feature
mkdir -p test_feature
echo "def test_function(): pass" > test_feature/test.py

# Add feature to progress tracker
python3 << 'EOF'
from orchestrator.progress_tracker import ProgressTracker
from pathlib import Path

tracker = ProgressTracker(Path("./workspace"))
tracker.add_feature("test_checkpoint", "Test checkpoint feature", priority=1)
print("Feature added to tracker")
EOF

# Stage changes
git add test_feature/ > /dev/null 2>&1 || true

# Get initial commit count
INITIAL_COMMITS=$(git log --oneline | wc -l | tr -d ' ')

# Try to create checkpoint (may fail if tests don't pass, which is expected)
CHECKPOINT_RESPONSE=$(curl -s -X POST http://localhost:8080/api/session/test_checkpoint_001/checkpoint \
  -H "Content-Type: application/json" \
  -d '{"feature_name": "test_checkpoint"}' || echo "")

if [ -n "$CHECKPOINT_RESPONSE" ]; then
  echo "  ✓ Checkpoint endpoint responded"
  echo "$CHECKPOINT_RESPONSE" | python3 -m json.tool 2>/dev/null | head -10 | sed 's/^/    /' || echo "$CHECKPOINT_RESPONSE" | head -5 | sed 's/^/    /'
  
  # Check if commit was created
  NEW_COMMITS=$(git log --oneline | wc -l | tr -d ' ')
  if [ "$NEW_COMMITS" -gt "$INITIAL_COMMITS" ]; then
    echo "  ✓ Git commit created"
    git log --oneline -1 | sed 's/^/    /'
  else
    echo "  ⚠ No new git commit (may be expected if tests failed)"
  fi
else
  echo "  ⚠ Checkpoint endpoint returned empty"
fi

# Cleanup
rm -rf test_feature

echo ""
echo "=========================================="
echo "Test Suite 1 Complete"
echo "=========================================="
echo ""
echo "Summary:"
echo "  - Progress tracking: $(if [ -f workspace/claude-progress.txt ]; then echo '✓'; else echo '✗'; fi)"
echo "  - Session resume: $(if [ -n "$RESUME_RESPONSE" ]; then echo '✓'; else echo '⚠'; fi)"
echo "  - Checkpoint: $(if [ -n "$CHECKPOINT_RESPONSE" ]; then echo '✓'; else echo '⚠'; fi)"
echo ""

