# Integration Test Plan - Phase 1 & 2 Validation

## Overview

This plan validates that Phase 1 (Long-Running Support) and Phase 2 (Skills Framework) work correctly with **actual running services** and **real LLM calls**, not just unit tests.

**Critical:** All tests require:
- 6 llama.cpp servers running (Preprocessor, Planner, Coder, Reviewer, Voter, GPT-OSS)
- Redis running
- MCP server running
- Docker services (orchestrator, phoenix) running

## Prerequisites

### 1. Verify All Services Are Running

```bash
# Check llama.cpp servers (ports 8000-8004)
for port in 8000 8001 8002 8003 8004; do
  echo "Checking port $port..."
  curl -s http://localhost:$port/health || echo "FAILED: Port $port not responding"
done

# Check Redis
redis-cli ping || echo "FAILED: Redis not running"

# Check MCP server
curl -s http://localhost:9001/health || echo "FAILED: MCP server not running"

# Check Orchestrator API
curl -s http://localhost:8080/health || echo "FAILED: Orchestrator not running"
```

**Expected:** All services respond with success.

### 2. Environment Setup

```bash
# Set required environment variables
export ENABLE_LONG_RUNNING=true
export ENABLE_SKILLS=true
export WORKSPACE_DIR=./workspace
export SKILLS_DIR=./skills
export REDIS_HOST=localhost
export REDIS_PORT=6379
export MCP_CODEBASE_URL=http://localhost:9001

# Verify skills exist
ls -la skills/*/SKILL.md
# Should show 5 skills
```

### 3. Clean Workspace

```bash
# Clean workspace for fresh test
rm -rf workspace/*
mkdir -p workspace

# Initialize git repo if needed (for checkpoint tests)
if [ ! -d .git ]; then
  git init
  git config user.name "Test User"
  git config user.email "test@example.com"
fi
```

---

## Test Suite 1: Phase 1 - Long-Running Support

### Test 1.1: Progress Tracking (Real Workflow)

**Purpose:** Verify progress tracking works with actual agent execution.

**Steps:**
```bash
# 1. Start a workflow
curl -X POST http://localhost:8080/api/workflow \
  -H "Content-Type: application/json" \
  -d '{
    "input": "Write a Python function to calculate fibonacci numbers",
    "task_id": "test_progress_001",
    "stream": false
  }'

# 2. Wait for completion (may take 30-60 seconds)

# 3. Check progress file
cat workspace/claude-progress.txt
# Expected: Contains log entries with timestamps

# 4. Check feature list
cat workspace/feature_list.json
# Expected: JSON structure with features
```

**Success Criteria:**
- ✅ Progress file contains entries with timestamps
- ✅ Feature list file exists and is valid JSON
- ✅ Progress entries match workflow execution

**Failure Modes to Test:**
- Workspace directory doesn't exist → Should auto-create
- File permissions issue → Should handle gracefully
- Concurrent writes → Should not corrupt files

---

### Test 1.2: Session Resumability (Real Interruption)

**Purpose:** Verify sessions can be resumed after interruption.

**Steps:**
```bash
# 1. Start a long-running workflow
curl -X POST http://localhost:8080/api/workflow \
  -H "Content-Type: application/json" \
  -d '{
    "input": "Refactor the orchestrator to use async/await throughout",
    "task_id": "test_resume_001",
    "stream": true
  }' > /tmp/workflow_output.txt &

WORKFLOW_PID=$!

# 2. Wait 10 seconds
sleep 10

# 3. Kill the workflow (simulate interruption)
kill $WORKFLOW_PID 2>/dev/null || true

# 4. Check session state in Redis
redis-cli GET "task:test_resume_001"

# 5. Resume the session
curl -X POST http://localhost:8080/api/session/test_resume_001/resume \
  -H "Content-Type: application/json" \
  > /tmp/resume_output.txt

# 6. Verify resume context
cat /tmp/resume_output.txt | grep -i "resuming\|continue\|progress"
```

**Success Criteria:**
- ✅ Session state saved to Redis
- ✅ Resume endpoint returns valid context
- ✅ Resume context includes recent progress
- ✅ Resume context includes git log
- ✅ Resume context includes next feature

**Failure Modes to Test:**
- Redis unavailable → Should handle gracefully
- Session not found → Should return 404
- Corrupted session state → Should handle gracefully

---

### Test 1.3: Checkpoint Creation (Real Git)

**Purpose:** Verify checkpoints create actual git commits.

**Steps:**
```bash
# 1. Create a test feature
mkdir -p test_feature
echo "def test_function(): pass" > test_feature/test.py

# 2. Add feature to progress tracker
python3 << 'EOF'
from orchestrator.progress_tracker import ProgressTracker
from pathlib import Path

tracker = ProgressTracker(Path("./workspace"))
tracker.add_feature("test_checkpoint", "Test checkpoint feature", priority=1)
EOF

# 3. Stage changes
git add test_feature/

# 4. Create checkpoint
curl -X POST http://localhost:8080/api/session/test_checkpoint_001/checkpoint \
  -H "Content-Type: application/json" \
  -d '{"feature_name": "test_checkpoint"}'

# 5. Verify git commit created
git log --oneline -1
# Expected: Commit with message "feat: Complete test_checkpoint"

# 6. Verify feature status updated
cat workspace/feature_list.json | grep -A 5 "test_checkpoint"
# Expected: "passes": true
```

**Success Criteria:**
- ✅ Git commit created with proper message
- ✅ Feature status updated to passes=true
- ✅ Progress logged
- ✅ Checkpoint saved to Redis

**Failure Modes to Test:**
- Tests fail → Should not create checkpoint
- Git not initialized → Should handle gracefully
- No changes to commit → Should return appropriate message
- Git commit fails → Should return error

---

## Test Suite 2: Phase 2 - Skills Framework

### Test 2.1: Skill Loading (Real Files)

**Purpose:** Verify skills load correctly from actual files.

**Steps:**
```bash
# 1. Verify skills exist
ls -la skills/*/SKILL.md
# Expected: 5 skills

# 2. Test skill loading via API (if endpoint exists) or Python
python3 << 'EOF'
from orchestrator.skill_loader import SkillLoader
from pathlib import Path

loader = SkillLoader(Path("./skills"))
skills = loader.load_all_skills()

print(f"Loaded {len(skills)} skills:")
for skill in skills:
    print(f"  - {skill.name}: {skill.description[:50]}...")
    print(f"    Applies to: {skill.applies_to}")
    print(f"    Category: {skill.category}")
    print()

assert len(skills) == 5, f"Expected 5 skills, got {len(skills)}"
EOF
```

**Success Criteria:**
- ✅ All 5 skills load successfully
- ✅ YAML frontmatter parsed correctly
- ✅ Instructions content loaded
- ✅ Metadata extracted

**Failure Modes to Test:**
- Missing SKILL.md file → Should handle gracefully
- Invalid YAML → Should log error and skip
- Missing required fields → Should log warning

---

### Test 2.2: Skill Matching (Real Task)

**Purpose:** Verify skill matcher finds relevant skills for actual tasks.

**Steps:**
```bash
# Test with regex task
python3 << 'EOF'
from orchestrator.skill_loader import SkillLoader
from orchestrator.skill_matcher import SkillMatcher
from pathlib import Path

loader = SkillLoader(Path("./skills"))
matcher = SkillMatcher(loader)

# Test regex task
task = "Fix regex pattern in email validator to handle edge cases"
skills = matcher.find_relevant_skills(task, top_k=3)

print(f"Task: {task}")
print(f"Found {len(skills)} relevant skills:")
for skill in skills:
    score = matcher.calculate_relevance(task, skill)
    print(f"  - {skill.name} (score: {score:.3f})")
    print(f"    Description: {skill.description[:60]}...")

# Should match regex-pattern-fixing
assert any(s.name == "regex-pattern-fixing" for s in skills), "Should match regex skill"
EOF

# Test with AST task
python3 << 'EOF'
from orchestrator.skill_loader import SkillLoader
from orchestrator.skill_matcher import SkillMatcher
from pathlib import Path

loader = SkillLoader(Path("./skills"))
matcher = SkillMatcher(loader)

task = "Refactor Python code using AST manipulation"
skills = matcher.find_relevant_skills(task, top_k=3)

print(f"Task: {task}")
print(f"Found {len(skills)} relevant skills:")
for skill in skills:
    score = matcher.calculate_relevance(task, skill)
    print(f"  - {skill.name} (score: {score:.3f})")

# Should match python-ast-refactoring
assert any(s.name == "python-ast-refactoring" for s in skills), "Should match AST skill"
EOF
```

**Success Criteria:**
- ✅ Regex task matches `regex-pattern-fixing`
- ✅ AST task matches `python-ast-refactoring`
- ✅ Relevance scores are reasonable (0.0-1.0)
- ✅ Skills sorted by relevance

**Failure Modes to Test:**
- No matching skills → Should return empty list gracefully
- All skills have same score → Should still return top_k

---

### Test 2.3: Skills in Agent Prompts (Real LLM Call)

**Purpose:** Verify skills are actually injected into agent system prompts and improve output.

**Steps:**
```bash
# 1. Test WITHOUT skills (baseline)
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "multi-agent",
    "messages": [
      {
        "role": "user",
        "content": "Fix this regex pattern: r\"[\\w.]+@[\\w.]+\" to properly validate email addresses"
      }
    ]
  }' > /tmp/baseline_output.json

# 2. Test WITH skills enabled
# (Set ENABLE_SKILLS=true in orchestrator environment)
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "multi-agent",
    "messages": [
      {
        "role": "user",
        "content": "Fix this regex pattern: r\"[\\w.]+@[\\w.]+\" to properly validate email addresses"
      }
    ]
  }' > /tmp/skills_output.json

# 3. Compare outputs
echo "=== BASELINE OUTPUT ==="
cat /tmp/baseline_output.json | jq -r '.choices[0].message.content' | head -20

echo ""
echo "=== SKILLS OUTPUT ==="
cat /tmp/skills_output.json | jq -r '.choices[0].message.content' | head -20

# 4. Check if skills output mentions skill patterns
cat /tmp/skills_output.json | jq -r '.choices[0].message.content' | grep -i "anchor\|escape\|^.*\$" || echo "WARNING: Skills output may not show skill influence"
```

**Success Criteria:**
- ✅ Skills output includes references to skill patterns (anchors, escaping)
- ✅ Skills output is more accurate than baseline
- ✅ Skills output follows proven patterns from skill
- ✅ Skill usage logged in Redis

**Validation:**
```bash
# Check skill usage in Redis
redis-cli GET "skills:usage:regex-pattern-fixing"
# Expected: Counter incremented
```

**Failure Modes to Test:**
- Skills not found → Should continue without skills
- Skill matching fails → Should not crash
- Skills too long → Should truncate gracefully

---

## Test Suite 3: End-to-End Integration

### Test 3.1: Full Workflow with Skills

**Purpose:** Complete workflow from task to code with skills enabled.

**Steps:**
```bash
# 1. Start workflow with regex task
TASK_ID="integration_test_$(date +%s)"
curl -X POST http://localhost:8080/api/workflow \
  -H "Content-Type: application/json" \
  -d "{
    \"input\": \"Fix regex pattern r'[\\\\w.]+@[\\\\w.]+' to properly validate email addresses with edge cases\",
    \"task_id\": \"$TASK_ID\",
    \"stream\": true
  }" > /tmp/full_workflow.txt

# 2. Monitor progress
tail -f workspace/claude-progress.txt

# 3. Wait for completion (may take 1-2 minutes)

# 4. Verify final state
redis-cli GET "task:$TASK_ID" | jq '.status'
# Expected: "complete"

# 5. Check if skills were used
redis-cli KEYS "skills:usage:*"
# Expected: At least one skill usage counter

# 6. Verify code quality
redis-cli GET "task:$TASK_ID" | jq -r '.code' | grep -E "\\^|\\$|\\\\." || echo "WARNING: Code may not show skill influence"
```

**Success Criteria:**
- ✅ Workflow completes successfully
- ✅ Skills matched and used
- ✅ Generated code follows skill patterns
- ✅ Progress tracked throughout
- ✅ Task state saved to Redis

---

### Test 3.2: Resume + Skills Integration

**Purpose:** Verify resume works with skills enabled.

**Steps:**
```bash
# 1. Start workflow
TASK_ID="resume_skills_$(date +%s)"
curl -X POST http://localhost:8080/api/workflow \
  -H "Content-Type: application/json" \
  -d "{
    \"input\": \"Refactor code using AST manipulation to add type hints\",
    \"task_id\": \"$TASK_ID\",
    \"stream\": true
  }" > /tmp/resume_workflow.txt &

# 2. Wait 15 seconds
sleep 15

# 3. Kill workflow
pkill -f "curl.*workflow" || true

# 4. Resume with skills
curl -X POST http://localhost:8080/api/session/$TASK_ID/resume \
  -H "Content-Type: application/json" \
  > /tmp/resume_output.txt

# 5. Verify resume context includes skills
cat /tmp/resume_output.txt | grep -i "python-ast\|AST\|refactor" || echo "WARNING: Resume may not include skill context"
```

**Success Criteria:**
- ✅ Resume succeeds
- ✅ Resume context includes progress
- ✅ Skills still available after resume
- ✅ Workflow continues with skill context

---

### Test 3.3: Checkpoint + Skills

**Purpose:** Verify checkpoint works after skill-enhanced workflow.

**Steps:**
```bash
# 1. Complete a workflow with skills
TASK_ID="checkpoint_skills_$(date +%s)"
# ... (run workflow as in Test 3.1)

# 2. Add feature to tracker
python3 << EOF
from orchestrator.progress_tracker import ProgressTracker
from pathlib import Path

tracker = ProgressTracker(Path("./workspace"))
tracker.add_feature("regex_email_fix", "Fix email regex with skills", priority=1)
EOF

# 3. Create checkpoint
curl -X POST http://localhost:8080/api/session/$TASK_ID/checkpoint \
  -H "Content-Type: application/json" \
  -d '{"feature_name": "regex_email_fix"}'

# 4. Verify checkpoint
git log --oneline -1
# Expected: Commit with feature name

cat workspace/feature_list.json | jq '.features[] | select(.name=="regex_email_fix")'
# Expected: "passes": true
```

**Success Criteria:**
- ✅ Checkpoint created successfully
- ✅ Git commit includes feature name
- ✅ Feature marked as passing
- ✅ Skills usage tracked

---

## Test Suite 4: Error Handling & Edge Cases

### Test 4.1: Services Unavailable

**Purpose:** Verify graceful degradation when services are down.

**Steps:**
```bash
# 1. Stop Redis
docker stop redis || redis-cli shutdown

# 2. Try to use long-running features
curl -X POST http://localhost:8080/api/session/test_error/checkpoint \
  -H "Content-Type: application/json" \
  -d '{"feature_name": "test"}'
# Expected: Error message, not crash

# 3. Restart Redis
docker start redis || redis-server --daemonize yes

# 4. Verify system recovers
curl http://localhost:8080/health
```

**Success Criteria:**
- ✅ System handles Redis unavailability gracefully
- ✅ Error messages are clear
- ✅ System recovers when Redis returns

---

### Test 4.2: Invalid Skills

**Purpose:** Verify system handles corrupted or invalid skill files.

**Steps:**
```bash
# 1. Create invalid skill
mkdir -p skills/invalid-skill
echo "---\ninvalid yaml: [\n---\n# Invalid" > skills/invalid-skill/SKILL.md

# 2. Try to load skills
python3 << 'EOF'
from orchestrator.skill_loader import SkillLoader
from pathlib import Path

loader = SkillLoader(Path("./skills"))
skills = loader.load_all_skills()

# Should load valid skills, skip invalid
print(f"Loaded {len(skills)} valid skills")
assert len(skills) >= 5, "Should load at least 5 valid skills"
EOF

# 3. Clean up
rm -rf skills/invalid-skill
```

**Success Criteria:**
- ✅ Invalid skills skipped
- ✅ Valid skills still load
- ✅ Error logged but doesn't crash

---

### Test 4.3: Concurrent Operations

**Purpose:** Verify thread-safety of progress tracking.

**Steps:**
```bash
# 1. Run multiple workflows concurrently
for i in {1..5}; do
  curl -X POST http://localhost:8080/api/workflow \
    -H "Content-Type: application/json" \
    -d "{
      \"input\": \"Test concurrent workflow $i\",
      \"task_id\": \"concurrent_$i\",
      \"stream\": false
    }" &
done

wait

# 2. Check progress file integrity
python3 << 'EOF'
import json
from pathlib import Path

# Progress file should be readable
progress_file = Path("./workspace/claude-progress.txt")
assert progress_file.exists(), "Progress file should exist"
lines = progress_file.read_text().splitlines()
print(f"Progress file has {len(lines)} entries")

# Feature list should be valid JSON
feature_file = Path("./workspace/feature_list.json")
if feature_file.exists():
    data = json.loads(feature_file.read_text())
    print(f"Feature list has {len(data.get('features', []))} features")
EOF
```

**Success Criteria:**
- ✅ No file corruption
- ✅ All progress entries valid
- ✅ Feature list is valid JSON
- ✅ No race conditions

---

## Manual Verification Checklist

After automated tests, manually verify:

### Code Quality
- [ ] Generated code follows skill patterns (e.g., regex has anchors)
- [ ] Code is syntactically correct
- [ ] Code handles edge cases mentioned in skills

### Progress Tracking
- [ ] Progress entries are meaningful and accurate
- [ ] Feature list reflects actual work done
- [ ] Resume context is helpful and accurate

### Skills Impact
- [ ] Skills are matched correctly for tasks
- [ ] Skill instructions are clear and actionable
- [ ] Skills improve code quality vs baseline

### System Stability
- [ ] No memory leaks during long runs
- [ ] Redis doesn't grow unbounded
- [ ] File handles are closed properly
- [ ] No zombie processes

---

## Expected Test Duration

| Test Suite | Duration | Notes |
|------------|----------|-------|
| Prerequisites | 5 min | Service health checks |
| Test Suite 1 | 30 min | Phase 1 validation |
| Test Suite 2 | 45 min | Phase 2 validation |
| Test Suite 3 | 30 min | End-to-end integration |
| Test Suite 4 | 20 min | Error handling |
| **Total** | **~2 hours** | With real LLM calls |

---

## Success Criteria Summary

### Phase 1 (Long-Running)
- ✅ Progress tracking works with real workflows
- ✅ Sessions can be resumed after interruption
- ✅ Checkpoints create actual git commits
- ✅ All features backward compatible

### Phase 2 (Skills)
- ✅ Skills load from actual files
- ✅ Skills match relevant tasks correctly
- ✅ Skills improve LLM output quality
- ✅ Skills usage tracked in Redis

### Integration
- ✅ Full workflows complete successfully
- ✅ Resume works with skills enabled
- ✅ Checkpoints work after skill-enhanced workflows
- ✅ System handles errors gracefully

---

## Running the Tests

### Quick Validation (30 min)
```bash
# Run critical tests only
bash tests/integration_test_suite_1.sh  # Phase 1
bash tests/integration_test_suite_2.sh  # Phase 2
```

### Full Validation (2 hours)
```bash
# Run all tests
bash tests/run_all_integration_tests.sh
```

### Continuous Validation
```bash
# Run tests in CI/CD
ENABLE_LONG_RUNNING=true ENABLE_SKILLS=true \
  pytest tests/integration/ -v --tb=short
```

---

## Next Steps After Validation

1. **If all tests pass:** Proceed to Phase 3 (Skill Learning)
2. **If tests fail:** Document failures and fix before Phase 3
3. **If partial failures:** Prioritize fixes based on impact

---

## Notes

- All tests require **actual running services** - no mocks
- Tests may take hours if running full SWE-bench evaluation
- Some tests require manual inspection of outputs
- Performance may vary based on hardware (M4 Max vs other systems)

**This is the real validation - unit tests only verify components work in isolation.**

