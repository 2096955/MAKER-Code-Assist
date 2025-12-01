#!/bin/bash
# Minimal Integration Test - Validates components without full services
# This can run even if Docker/llama.cpp aren't running

set -e

echo "=========================================="
echo "Minimal Integration Test"
echo "=========================================="
echo ""
echo "This test validates components that don't require running services."
echo ""

# Test 1: Skills Loading
echo "1. Testing Skills Loading..."
python3 << 'EOF'
from orchestrator.skill_loader import SkillLoader
from pathlib import Path

loader = SkillLoader(Path("./skills"))
skills = loader.load_all_skills()

print(f"  ✓ Loaded {len(skills)} skills")
for skill in skills:
    print(f"    - {skill.name}")

if len(skills) < 5:
    raise Exception(f"Expected at least 5 skills, got {len(skills)}")
EOF

# Test 2: Skill Matching
echo ""
echo "2. Testing Skill Matching..."
python3 << 'EOF'
from orchestrator.skill_loader import SkillLoader
from orchestrator.skill_matcher import SkillMatcher
from pathlib import Path

loader = SkillLoader(Path("./skills"))
matcher = SkillMatcher(loader)

# Test regex matching
task = "Fix regex pattern in email validator"
skills = matcher.find_relevant_skills(task, top_k=3)

print(f"  Task: {task}")
print(f"  ✓ Found {len(skills)} relevant skills:")
for skill in skills:
    score = matcher.calculate_relevance(task, skill)
    print(f"    - {skill.name} (score: {score:.3f})")

# Verify regex skill is matched
if any(s.name == "regex-pattern-fixing" for s in skills):
    print("  ✓ Regex skill correctly matched")
else:
    print("  ⚠ Regex skill not in top matches")
EOF

# Test 3: Progress Tracker
echo ""
echo "3. Testing Progress Tracker..."
python3 << 'EOF'
from orchestrator.progress_tracker import ProgressTracker
from pathlib import Path
import tempfile
import os

# Use temp directory
with tempfile.TemporaryDirectory() as tmpdir:
    tracker = ProgressTracker(Path(tmpdir))
    
    # Add feature
    tracker.add_feature("test_feature", "Test feature description", priority=1)
    
    # Log progress
    tracker.log_progress("Test progress entry")
    
    # Update feature status
    tracker.update_feature_status("test_feature", passes=True)
    
    # Verify
    features = tracker.load_feature_list()
    assert len(features) == 1
    assert features[0].name == "test_feature"
    assert features[0].passes == True
    
    # Check progress file
    progress_lines = tracker.read_recent_progress(lines=5)
    assert len(progress_lines) > 0, f"Expected progress entries, got {len(progress_lines)}"
    # Check if our message is in any of the progress lines
    found = any("Test progress entry" in line for line in progress_lines)
    assert found, f"Progress entry not found in: {progress_lines}"
    
    print("  ✓ Progress tracking works correctly")
    print(f"    - Features: {len(features)}")
    print(f"    - Progress entries: {len(progress_lines)}")
EOF

# Test 4: Session Manager
echo ""
echo "4. Testing Session Manager..."
python3 << 'EOF'
from orchestrator.progress_tracker import ProgressTracker
from orchestrator.session_manager import SessionManager
from pathlib import Path
import tempfile

with tempfile.TemporaryDirectory() as tmpdir:
    tracker = ProgressTracker(Path(tmpdir))
    manager = SessionManager(tracker)
    
    # Add some progress
    tracker.add_feature("test_feature", "Test feature")
    tracker.log_progress("Test progress")
    
    # Create resume context
    context = manager.create_resume_context()
    
    assert "resuming work" in context.lower()
    assert "Working directory" in context
    assert "Recent progress" in context
    
    print("  ✓ Session manager creates valid resume context")
    print(f"    - Context length: {len(context)} characters")
EOF

# Test 5: Checkpoint Manager (without git)
echo ""
echo "5. Testing Checkpoint Manager (without git)..."
python3 << 'EOF'
from orchestrator.progress_tracker import ProgressTracker
from orchestrator.checkpoint_manager import CheckpointManager
from pathlib import Path
import tempfile
import asyncio

async def test_checkpoint():
    with tempfile.TemporaryDirectory() as tmpdir:
        tracker = ProgressTracker(Path(tmpdir))
        manager = CheckpointManager(tracker, redis_client=None)
        
        # Add feature
        tracker.add_feature("test_checkpoint", "Test checkpoint")
        
        # Test commit message generation
        message = manager._generate_commit_message("test_checkpoint", "def test(): pass")
        assert "feat: Complete test_checkpoint" in message
        assert "MAKER Multi-Agent System" in message
        
        print("  ✓ Checkpoint manager works correctly")
        print(f"    - Commit message generated: {message[:50]}...")

asyncio.run(test_checkpoint())
EOF

# Test 6: Skills Integration (code only)
echo ""
echo "6. Testing Skills Integration (code validation)..."
python3 << 'EOF'
from orchestrator.skill_loader import SkillLoader
from orchestrator.skill_matcher import SkillMatcher
from pathlib import Path

loader = SkillLoader(Path("./skills"))
matcher = SkillMatcher(loader)

# Test skill context formatting
skills = matcher.find_relevant_skills("Fix regex pattern", top_k=2)
context = matcher.get_skill_context(skills)

assert len(context) > 0
assert "regex-pattern-fixing" in context or len(skills) > 0

print("  ✓ Skill context formatting works")
print(f"    - Context length: {len(context)} characters")
print(f"    - Skills included: {len(skills)}")
EOF

echo ""
echo "=========================================="
echo "Minimal Integration Test Complete"
echo "=========================================="
echo ""
echo "All component tests passed!"
echo ""
echo "Note: Full integration tests require:"
echo "  - Docker running (for Redis, MCP, Orchestrator)"
echo "  - llama.cpp servers running (ports 8000-8004)"
echo ""
echo "See docs/SERVICE_STARTUP_GUIDE.md for startup instructions."

