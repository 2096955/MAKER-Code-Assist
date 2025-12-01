# Cursor Implementation Guide - Quick Start

**Status:** ✅ Ready for implementation
**Estimated time:** 3 weeks (1 week per phase)
**Expected outcome:** SWE-bench resolve rate improvement from ~30% to >50%

---

## 📋 Document Index

### Start Here

1. **[CURSOR_QUESTIONS_ANSWERED.md](CURSOR_QUESTIONS_ANSWERED.md)** ← **READ THIS FIRST**
   - Answers all integration questions
   - Clarifies Skills vs EE Memory relationship
   - Explains testing strategy
   - Implementation decision tree

2. **[CURSOR_IMPLEMENTATION_PLAN.md](CURSOR_IMPLEMENTATION_PLAN.md)** ← **Implementation spec**
   - 3 phases, 12 tasks with detailed code examples
   - Test specifications for each component
   - Success criteria and metrics

3. **[.cursorrules](.cursorrules)** ← **Cursor configuration**
   - Code style, patterns, anti-patterns
   - Integration points with existing system
   - Environment variables and setup

### Supporting Documentation

4. **[docs/context-engineering-skills-analysis.md](docs/context-engineering-skills-analysis.md)**
   - Gap analysis vs Anthropic best practices
   - Current system limitations

5. **[docs/skills-framework-clarification.md](docs/skills-framework-clarification.md)**
   - **Critical:** Skills are for SWE-bench optimization, NOT user features
   - Example skills with actual SWE-bench patterns

6. **[docs/swe-bench-integration.md](docs/swe-bench-integration.md)**
   - SWE-bench evaluation harness overview
   - Baseline comparisons

7. **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)**
   - Executive summary of all components

---

## 🚀 Quick Start (30 seconds)

```bash
# 1. Create directories
mkdir -p workspace skills

# 2. Open in Cursor
cursor /Users/anthonylui/BreakingWind

# 3. In Cursor chat:
"Implement Task 1.1 from CURSOR_IMPLEMENTATION_PLAN.md:
Create ProgressTracker class in orchestrator/progress_tracker.py"

# 4. Follow the plan sequentially
# Phase 1: Tasks 1.1 → 1.2 → 1.3 → 1.4
# Phase 2: Tasks 2.1 → 2.2 → 2.3 → 2.4 → 2.5
# Phase 3: Tasks 3.1 → 3.2 → 3.3 → 3.4
```

---

## 🎯 What You're Building

### Phase 1: Long-Running Agent Support

**Purpose:** Enable MAKER to work across multiple sessions

**Key components:**
- `orchestrator/progress_tracker.py` - Track what was accomplished
- `orchestrator/session_manager.py` - Resume interrupted work
- `orchestrator/checkpoint_manager.py` - Clean git checkpoints

**Expected impact:** +2% SWE-bench resolve rate

### Phase 2: Skills Framework

**Purpose:** Teach MAKER proven coding patterns from SWE-bench

**Key components:**
- `skills/regex-pattern-fixing/SKILL.md` - Example skill
- `orchestrator/skill_loader.py` - Load skills
- `orchestrator/skill_matcher.py` - Find relevant skills

**Expected impact:** +10% SWE-bench resolve rate

### Phase 3: Incremental Learning

**Purpose:** Auto-extract skills from successful tasks

**Key components:**
- `orchestrator/skill_extractor.py` - Extract patterns
- `orchestrator/skill_registry.py` - Track usage stats
- Auto-apply learned skills on similar tasks

**Expected impact:** +8% SWE-bench resolve rate

---

## 📊 Success Metrics

| Milestone | Resolve Rate | vs GPT-4o Mini (31.7%) | vs Claude 3.5 (49.3%) |
|-----------|--------------|------------------------|----------------------|
| Current baseline | ~30% | -1.7% | -19.3% |
| + Phase 1 | ~32% | **+0.3%** ✅ | -17.3% |
| + Phase 2 | ~42% | **+10.3%** ✅✅ | -7.3% |
| + Phase 3 | ~50% | **+18.3%** ✅✅✅ | **+0.7%** 🎯 |

**Goal:** Beat GPT-4o Mini, approach Claude 3.5 Sonnet

---

## ⚡ Implementation Checklist

### Before Starting

- [ ] Read `CURSOR_QUESTIONS_ANSWERED.md`
- [ ] Create `workspace/` and `skills/` directories
- [ ] Understand Skills ≠ User Features (Skills = SWE-bench patterns)

### Phase 1 (Week 1)

- [ ] Task 1.1: ProgressTracker
- [ ] Task 1.2: SessionManager
- [ ] Task 1.3: CheckpointManager
- [ ] Task 1.4: Orchestrator integration
- [ ] Tests pass: `pytest tests/test_progress*.py`

### Phase 2 (Week 2)

- [ ] Task 2.1: Create 5 core skills
- [ ] Task 2.2: SkillLoader
- [ ] Task 2.3: SkillMatcher
- [ ] Task 2.4: Agent integration
- [ ] Task 2.5: SWE-bench subset test (50 tasks)
- [ ] Verify: +8-12% improvement

### Phase 3 (Week 3)

- [ ] Task 3.1: SkillExtractor
- [ ] Task 3.2: SkillRegistry
- [ ] Task 3.3: Auto-apply skills
- [ ] Task 3.4: Skill evolution
- [ ] Full SWE-bench test (300 tasks)
- [ ] Verify: >50% resolve rate

---

## 🔑 Key Clarifications

### Skills vs EE Memory

| Feature | EE Memory | Skills |
|---------|-----------|--------|
| Purpose | Business narratives | Coding patterns |
| Example | "Payment Processing Flow" | "How to fix regex bugs" |
| Source | Codebase structure | SWE-bench experience |
| Storage | EE World Model L₃ | `skills/` directory + RAG |
| Usage | Architectural context | Tactical execution |

**Both used together in agent prompts** (different context types)

### Testing Strategy

- **Unit tests** (fast, mocked): Run on every commit
- **Integration tests** (slow, real agents): Run before phase completion
- **SWE-bench validation** (very slow): Run after each phase

```bash
# Unit tests (fast)
pytest tests/test_progress_tracker.py -v

# Integration tests (slower)
pytest tests/test_skill_integration.py -v -m integration

# SWE-bench validation (slowest)
bash tests/run_swe_bench_eval.sh 50 results/phase2_test
```

---

## 🛠️ Environment Setup

### Directories

```bash
BreakingWind/
├── workspace/           # NEW (progress files)
├── skills/             # NEW (skill library)
├── orchestrator/       # Modified
├── tests/              # New tests added
└── docker-compose.yml  # Updated
```

### Environment Variables

```yaml
# Add to docker-compose.yml:
environment:
  - ENABLE_LONG_RUNNING=true
  - ENABLE_SKILLS=true
  - ENABLE_SKILL_LEARNING=true
  - WORKSPACE_DIR=/app/workspace
  - SKILLS_DIR=/app/skills

volumes:
  - ./workspace:/app/workspace
  - ./skills:/app/skills
```

---

## 💡 Example Cursor Prompts

### Starting Task 1.1

```
Implement Task 1.1 from CURSOR_IMPLEMENTATION_PLAN.md:
Create ProgressTracker class in orchestrator/progress_tracker.py
following the spec exactly
```

### After Implementation

```
Add unit tests for ProgressTracker in tests/test_progress_tracker.py
covering log_progress(), update_feature_status(), and get_next_feature()
```

### Integration

```
Integrate ProgressTracker into Orchestrator class per Task 1.4
in CURSOR_IMPLEMENTATION_PLAN.md
```

---

## 📞 Support

### If Stuck

1. Check **CURSOR_QUESTIONS_ANSWERED.md** for clarifications
2. Review existing patterns in `orchestrator/orchestrator.py`
3. Look at similar components (e.g., `ContextCompressor`)

### Common Issues

**"Skills vs EE Memory confusion"**
→ Read section 1 in CURSOR_QUESTIONS_ANSWERED.md

**"SWE-bench files missing"**
→ They exist! Check `tests/swe_bench_*.py`

**"Directory structure unclear"**
→ See section 5 in CURSOR_QUESTIONS_ANSWERED.md

---

## 🎯 Ready to Start

**Next action:**

```bash
mkdir -p workspace skills
cursor /Users/anthonylui/BreakingWind
```

Then in Cursor:

```
"Read CURSOR_QUESTIONS_ANSWERED.md then implement Task 1.1"
```

**Good luck! Target: >50% SWE-bench resolve rate** 🚀
