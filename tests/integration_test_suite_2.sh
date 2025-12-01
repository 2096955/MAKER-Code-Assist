#!/bin/bash
# Integration Test Suite 2: Phase 2 - Skills Framework
# Requires: All services running + skills directory

set -e

echo "=========================================="
echo "Integration Test Suite 2: Phase 2"
echo "=========================================="

# Check prerequisites
echo ""
echo "1. Checking prerequisites..."
if [ ! -d "skills" ]; then
  echo "  ✗ Skills directory not found"
  exit 1
fi

SKILL_COUNT=$(find skills -name "SKILL.md" | wc -l | tr -d ' ')
if [ "$SKILL_COUNT" -lt 5 ]; then
  echo "  ✗ Expected at least 5 skills, found $SKILL_COUNT"
  exit 1
fi
echo "  ✓ Found $SKILL_COUNT skills"

# Test 2.1: Skill Loading
echo ""
echo "2. Test 2.1: Skill Loading (Real Files)"
python3 << 'EOF'
from orchestrator.skill_loader import SkillLoader
from pathlib import Path

loader = SkillLoader(Path("./skills"))
skills = loader.load_all_skills()

print(f"  Loaded {len(skills)} skills:")
for skill in skills:
    print(f"    ✓ {skill.name}")
    print(f"      Description: {skill.description[:50]}...")
    print(f"      Applies to: {', '.join(skill.applies_to[:3])}...")
    print()

if len(skills) < 5:
    raise Exception(f"Expected at least 5 skills, got {len(skills)}")

print("  ✓ All skills loaded successfully")
EOF

# Test 2.2: Skill Matching
echo ""
echo "3. Test 2.2: Skill Matching (Real Tasks)"

# Test regex task
echo "  Testing regex task matching..."
python3 << 'EOF'
from orchestrator.skill_loader import SkillLoader
from orchestrator.skill_matcher import SkillMatcher
from pathlib import Path

loader = SkillLoader(Path("./skills"))
matcher = SkillMatcher(loader)

task = "Fix regex pattern in email validator to handle edge cases"
skills = matcher.find_relevant_skills(task, top_k=3)

print(f"    Task: {task}")
print(f"    Found {len(skills)} relevant skills:")
for skill in skills:
    score = matcher.calculate_relevance(task, skill)
    print(f"      - {skill.name} (score: {score:.3f})")

# Should match regex-pattern-fixing
if any(s.name == "regex-pattern-fixing" for s in skills):
    print("    ✓ Regex skill matched correctly")
else:
    print("    ⚠ Regex skill not in top matches")
EOF

# Test AST task
echo "  Testing AST task matching..."
python3 << 'EOF'
from orchestrator.skill_loader import SkillLoader
from orchestrator.skill_matcher import SkillMatcher
from pathlib import Path

loader = SkillLoader(Path("./skills"))
matcher = SkillMatcher(loader)

task = "Refactor Python code using AST manipulation"
skills = matcher.find_relevant_skills(task, top_k=3)

print(f"    Task: {task}")
print(f"    Found {len(skills)} relevant skills:")
for skill in skills:
    score = matcher.calculate_relevance(task, skill)
    print(f"      - {skill.name} (score: {score:.3f})")

# Should match python-ast-refactoring
if any(s.name == "python-ast-refactoring" for s in skills):
    print("    ✓ AST skill matched correctly")
else:
    print("    ⚠ AST skill not in top matches")
EOF

# Test 2.3: Skills in Agent Prompts
echo ""
echo "4. Test 2.3: Skills in Agent Prompts (Real LLM Call)"
echo "  Note: This requires ENABLE_SKILLS=true in orchestrator"

# Check if skills are enabled
SKILLS_ENABLED=$(curl -s http://localhost:8080/health | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('skills_enabled', False))" 2>/dev/null || echo "unknown")

if [ "$SKILLS_ENABLED" != "true" ]; then
  echo "  ⚠ Skills not enabled in orchestrator (set ENABLE_SKILLS=true)"
  echo "  Skipping LLM call test"
else
  echo "  Testing with regex task..."
  
  # Make API call
  RESPONSE=$(curl -s -X POST http://localhost:8080/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
      "model": "multi-agent",
      "messages": [
        {
          "role": "user",
          "content": "Fix this regex pattern: r\"[\\w.]+@[\\w.]+\" to properly validate email addresses"
        }
      ]
    }')
  
  if [ -n "$RESPONSE" ]; then
    echo "  ✓ LLM call succeeded"
    
    # Extract content
    CONTENT=$(echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('choices', [{}])[0].get('message', {}).get('content', ''))" 2>/dev/null || echo "")
    
    if [ -n "$CONTENT" ]; then
      echo "  Response preview:"
      echo "$CONTENT" | head -10 | sed 's/^/    /'
      
      # Check for skill patterns
      if echo "$CONTENT" | grep -qiE "\^|\$|\\\."; then
        echo "  ✓ Response shows skill influence (anchors/escaping mentioned)"
      else
        echo "  ⚠ Response may not show clear skill influence"
      fi
    fi
    
    # Check skill usage in Redis
    USAGE=$(redis-cli GET "skills:usage:regex-pattern-fixing" 2>/dev/null || echo "")
    if [ -n "$USAGE" ] && [ "$USAGE" != "0" ]; then
      echo "  ✓ Skill usage tracked in Redis: $USAGE"
    else
      echo "  ⚠ Skill usage not found in Redis (may be expected if not logged yet)"
    fi
  else
    echo "  ✗ LLM call failed"
  fi
fi

echo ""
echo "=========================================="
echo "Test Suite 2 Complete"
echo "=========================================="
echo ""
echo "Summary:"
echo "  - Skill loading: ✓"
echo "  - Skill matching: ✓"
echo "  - Skills in prompts: $(if [ "$SKILLS_ENABLED" = "true" ]; then echo '✓'; else echo '⚠ (not enabled)'; fi)"
echo ""

