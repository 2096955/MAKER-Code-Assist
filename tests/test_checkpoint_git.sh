#!/bin/bash
# Test checkpoint creation with real git operations

set -e

echo "=========================================="
echo "Checkpoint Git Test"
echo "=========================================="
echo ""

# Create test directory
TEST_DIR=$(mktemp -d)
cd "$TEST_DIR"

echo "1. Initializing test git repository..."
git init > /dev/null 2>&1
git config user.name "Test User" > /dev/null 2>&1
git config user.email "test@example.com" > /dev/null 2>&1

echo "   ✓ Git repository initialized"
echo ""

# Create test feature
echo "2. Creating test feature..."
mkdir -p test_feature
cat > test_feature/test.py << 'EOF'
def test_function():
    """Test function for checkpoint"""
    return 42
EOF

git add test_feature/ > /dev/null 2>&1

echo "   ✓ Test feature created"
echo ""

# Initialize workspace
echo "3. Setting up progress tracker..."
WORKSPACE_DIR="$TEST_DIR/workspace"
mkdir -p "$WORKSPACE_DIR"

python3 << EOF
from orchestrator.progress_tracker import ProgressTracker
from pathlib import Path

tracker = ProgressTracker(Path("$WORKSPACE_DIR"))
tracker.add_feature("test_checkpoint", "Test checkpoint feature", priority=1)
tracker.log_progress("Test checkpoint creation")
print("   ✓ Progress tracker initialized")
EOF

echo ""

# Test checkpoint (simulated - actual checkpoint requires orchestrator)
echo "4. Testing checkpoint creation..."
echo "   Note: Full checkpoint requires orchestrator API running"
echo ""

# Verify git state
INITIAL_COMMITS=$(git log --oneline 2>/dev/null | wc -l | tr -d ' ')

if [ "$INITIAL_COMMITS" -eq 0 ]; then
    echo "   ✓ Git repository is clean (no commits yet)"
    echo "   → Checkpoint would create first commit"
else
    echo "   ⚠ Git repository has $INITIAL_COMMITS commits"
fi

# Verify feature list
if [ -f "$WORKSPACE_DIR/feature_list.json" ]; then
    echo "   ✓ Feature list exists"
    python3 << EOF
import json
with open("$WORKSPACE_DIR/feature_list.json") as f:
    data = json.load(f)
    features = data.get("features", [])
    print(f"   → Found {len(features)} features")
    for f in features:
        if f["name"] == "test_checkpoint":
            print(f"   → Feature '{f['name']}' status: passes={f.get('passes', False)}")
EOF
else
    echo "   ✗ Feature list not found"
fi

echo ""
echo "5. Simulating checkpoint..."
echo "   (Full checkpoint requires:)"
echo "   - Orchestrator API running"
echo "   - Tests passing"
echo "   - Git repository initialized"
echo ""

# Cleanup
cd - > /dev/null
rm -rf "$TEST_DIR"

echo "=========================================="
echo "Test Complete"
echo "=========================================="
echo ""
echo "To test full checkpoint:"
echo "  1. Start orchestrator: docker compose up -d orchestrator"
echo "  2. Create task with code"
echo "  3. Call: curl -X POST http://localhost:8080/api/session/{id}/checkpoint"
echo ""

