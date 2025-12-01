# Cursor Implementation Questions - ANSWERED

## 1. Integration with existing EE Memory

**Question:** How should skills relate to melodic lines?

**Answer:** Keep them SEPARATE but complementary:

- **Melodic Lines (L₃)**: Business narratives (e.g., "Payment Processing Flow" across modules)
- **Skills**: Coding patterns (e.g., "How to fix regex bugs based on 100 examples")

**Implementation:**

```python
# Skills are NOT stored in EE World Model
# They are stored separately in skills/ directory + Redis

# SkillMatcher uses RAG service directly (NOT EE World Model)
class SkillMatcher:
    def __init__(self, skill_loader: SkillLoader, rag_service):
        self.rag = rag_service  # Use existing RAG, create "skills" collection

# In call_agent(), inject BOTH:
context = agent_memory.get_context_for_agent(task)  # EE Memory narratives
skills = skill_matcher.find_relevant_skills(task)   # Coding patterns

# Combined prompt:
system_prompt = base_prompt + "\n\n# Narrative Context\n" + context + "\n\n# Proven Patterns\n" + skills
```

**Why separate:**
- Melodic lines: "What business flows exist" (architectural understanding)
- Skills: "How to code specific patterns" (tactical execution)

---

## 2. SWE-bench integration

**Question:** Should I create SWE-bench harness files?

**Answer:** They ALREADY EXIST! Created earlier in this conversation.

**Files:**
- ✅ `tests/swe_bench_harness.py` (exists, 500+ lines)
- ✅ `tests/swe_bench_adapter.py` (exists, 300+ lines)
- ✅ `tests/swe_bench_metrics.py` (exists, 400+ lines)
- ✅ `tests/run_swe_bench_eval.sh` (exists, executable)

**What you need to do:**
- Use them as-is for testing
- After Phase 2, run: `bash tests/run_swe_bench_eval.sh 50 results/phase2_test`

**Don't recreate them.** Focus on implementing Phases 1-3.

---

## 3. Skills vs. EE Memory overlap

**Question:** How should they interact?

**Answer:** Use BOTH together, different purposes:

```python
# In orchestrator.py call_agent()

# 1. Get narrative context from EE Memory
if self.ee_mode:
    narrative_context = self.agent_memories[agent].get_context_for_agent(user_prompt)
else:
    narrative_context = ""

# 2. Get coding patterns from Skills
if self.enable_skills:
    skills = self.skill_matcher.find_relevant_skills(user_prompt, top_k=2)
    skill_context = "\n\n".join([s.instructions for s in skills])
else:
    skill_context = ""

# 3. Combine both
augmented_prompt = system_prompt
if narrative_context:
    augmented_prompt += f"\n\n## Codebase Narratives\n{narrative_context}"
if skill_context:
    augmented_prompt += f"\n\n## Proven Coding Patterns\n{skill_context}"

# Call agent with combined context
response = await self._call_llm(agent, augmented_prompt, user_prompt)
```

**Result:**
- EE Memory: "This task affects the Payment Processing narrative"
- Skills: "Use these proven regex patterns for validation"
- Agent: Gets both architectural context AND tactical patterns

---

## 4. Priority clarification

**Question:** Which phase first if time limited?

**Answer:** Implement **in order** (Phase 1 → 2 → 3):

**Rationale:**
- **Phase 1 first**: Foundation for Phases 2 & 3 (progress tracking needed for skill learning)
- **Phase 2 second**: Immediate SWE-bench impact (+10% resolve rate)
- **Phase 3 third**: Builds on Phase 2 (can't extract skills without skill framework)

**If extremely time-limited:**
- Minimum: Phase 1 (Tasks 1.1, 1.2 only) + Phase 2 (Tasks 2.1-2.4)
- Skip: Task 1.3 (checkpointing), Task 1.4 (full integration), Phase 3 (learning)

**But recommended:** Do all phases in order for full benefit.

---

## 5. Workspace directory structure

**Question:** Where should workspace be?

**Answer:**

```yaml
# In docker-compose.yml (already partially there):
volumes:
  - ./workspace:/app/workspace  # Host ./workspace → Container /app/workspace
  - ./skills:/app/skills

# On host:
BreakingWind/
├── workspace/           # NEW: Create this
│   ├── claude-progress.txt
│   ├── feature_list.json
│   └── (per-session subdirs)
├── skills/             # NEW: Create this
│   ├── regex-pattern-fixing/
│   │   └── SKILL.md
│   └── test-driven-bug-fixing/
│       └── SKILL.md
├── orchestrator/
├── tests/
└── docker-compose.yml

# Environment variable:
WORKSPACE_DIR=/app/workspace  # Inside container
```

**Create directories:**
```bash
mkdir -p workspace skills
```

**Git:**
```gitignore
# Add to .gitignore:
workspace/*
!workspace/.gitkeep

# Keep skills in git:
skills/
```

---

## 6. Skill extraction criteria

**Question:** Extract from resolved only, or failed too?

**Answer:** Extract from BOTH, differently:

```python
def is_skill_worthy(self, state: TaskState) -> bool:
    # For RESOLVED tasks: Extract proven patterns
    if state.review_feedback.get('status') == 'approved':
        return (
            len(state.code) > 200 and  # Non-trivial
            self._has_reusable_pattern(state) and
            self._detect_pattern_type(state.code) is not None
        )

    # For FAILED tasks: Extract anti-patterns (what NOT to do)
    if state.review_feedback.get('status') == 'failed':
        return (
            state.iteration_count > 2 and  # Multiple attempts
            self._has_clear_failure_reason(state)
        )

    return False

# Skill structure includes both:
"""
## Proven Patterns (from successful tasks)
✅ Use lazy matching: `.*?`

## Anti-Patterns (from failed tasks)
❌ Don't use greedy matching: `.*`
"""
```

**SWE-bench specific:**
- Extract from **resolved** tasks (patch worked)
- Analyze **unresolved** tasks for anti-patterns
- Minimum complexity: 3+ lines of code change

---

## 7. Testing strategy

**Question:** Integration tests with real agents, or mocked?

**Answer:** Use BOTH:

**Unit tests (mocked LLMs):**
```python
# tests/test_skill_loader.py
def test_load_skill(tmp_path):
    skill = skill_loader.load_skill("regex-pattern-fixing")
    assert skill.name == "regex-pattern-fixing"
    # No LLM calls, just file parsing
```

**Integration tests (real agents, short tasks):**
```python
# tests/test_skill_integration.py
@pytest.mark.integration
async def test_skill_injection():
    # Use actual Coder agent, but simple task
    result = await orchestrator.orchestrate_workflow(
        "test_id",
        "Fix regex pattern"  # Quick task
    )
    # Verify skill was loaded
    assert "regex-pattern-fixing" in captured_logs
```

**Manual validation (SWE-bench subset):**
```bash
# After Phase 2, test on 10 real SWE-bench tasks
bash tests/run_swe_bench_eval.sh 10 results/phase2_manual
```

**Strategy:**
1. Unit tests (fast, no LLM): Run on every commit
2. Integration tests (slow, real LLM): Run before phase completion
3. SWE-bench validation (very slow): Run after each phase

**Use pytest marks:**
```python
@pytest.mark.unit  # Fast, mocked
@pytest.mark.integration  # Slow, real agents
@pytest.mark.swebench  # Very slow, full evaluation
```

---

## 8. Backward compatibility

**Question:** Should long-running work with EE Planner?

**Answer:** YES, must work with BOTH planners:

```python
# In orchestrator.py

async def resume_session(self, session_id: str) -> AsyncGenerator:
    """Resume works with both EE and standard planners"""

    # Load session context
    context = self.session_manager.create_resume_context()

    # EE mode uses enhanced planning (if enabled)
    if self.ee_mode:
        # EE Planner gets progress context + narrative context
        ee_plan = await self._plan_with_ee(context)
        if ee_plan:
            state.plan = ee_plan

    # Standard planner also gets progress context
    if not self.ee_mode or not state.plan:
        # Standard planner gets progress context
        narrative_context = self.agent_memories[AgentName.PLANNER].get_context_for_agent(context)
        # Continue with standard planning...

    # Both modes benefit from progress tracking
    self.progress_tracker.log_progress(f"Resumed session {session_id}")
```

**Feature flags allow mixing:**
```bash
# All features enabled
EE_MODE=true ENABLE_LONG_RUNNING=true ENABLE_SKILLS=true

# Only long-running + skills (no EE)
EE_MODE=false ENABLE_LONG_RUNNING=true ENABLE_SKILLS=true

# Only EE + skills (no long-running)
EE_MODE=true ENABLE_LONG_RUNNING=false ENABLE_SKILLS=true
```

**Backward compatibility guarantee:**
- Default flags: All existing behavior preserved
- New features: Opt-in via environment variables
- No breaking changes to existing API endpoints

---

## Implementation Decision Tree

```
START
  ↓
Create workspace/ and skills/ directories
  ↓
Implement Phase 1 (Task 1.1)
  ↓
├─ ProgressTracker works standalone
├─ Uses workspace/ directory
└─ No dependencies on EE Memory or Skills
  ↓
Continue Phase 1 (Tasks 1.2-1.4)
  ↓
├─ Works with EE_MODE=true or false
├─ Works with ENABLE_SKILLS=true or false
└─ Fully backward compatible
  ↓
Test Phase 1: pytest + manual validation
  ↓
Implement Phase 2 (Task 2.1)
  ↓
├─ Skills stored in skills/ directory
├─ Skills indexed in RAG (new "skills" collection)
└─ Skills separate from EE Memory melodic lines
  ↓
Continue Phase 2 (Tasks 2.2-2.4)
  ↓
├─ SkillMatcher uses RAG, NOT EE World Model
├─ Skills injected alongside EE Memory context
└─ Both provide different context types
  ↓
Test Phase 2: SWE-bench subset (50 tasks)
  ↓
Implement Phase 3
  ↓
├─ Extract from resolved (patterns) + failed (anti-patterns)
├─ Skill registry in Redis
└─ Auto-apply on similar tasks
  ↓
Test Phase 3: SWE-bench full (300 tasks)
  ↓
DONE: Target >50% resolve rate
```

---

## Ready to Implement

### Start with Task 1.1

**No blockers. Proceed immediately:**

```python
# Task 1.1: Create orchestrator/progress_tracker.py
# - Standalone component
# - No EE Memory integration needed yet
# - No skills integration needed yet
# - Simple file I/O + JSON parsing

# You can implement right now without waiting
```

**Next steps after Task 1.1:**
1. Write tests: `tests/test_progress_tracker.py`
2. Run tests: `pytest tests/test_progress_tracker.py -v`
3. Commit: `git commit -m "feat(long-running): Add ProgressTracker for session continuity"`
4. Move to Task 1.2

---

## Quick Reference

| Question | Answer |
|----------|--------|
| Skills vs Melodic Lines | Separate: Skills=coding patterns, Melodic=business narratives |
| SWE-bench files | Already exist, use them |
| Skills + EE Memory | Use both together, different purposes |
| Phase priority | In order: 1 → 2 → 3 |
| Workspace location | `./workspace` (host) → `/app/workspace` (container) |
| Skill extraction | From resolved (patterns) + failed (anti-patterns) |
| Testing strategy | Unit (mocked) + Integration (real) + SWE-bench (validation) |
| Backward compat | Must work with EE_MODE true/false |

---

**You are UNBLOCKED. Start Task 1.1 immediately.**
