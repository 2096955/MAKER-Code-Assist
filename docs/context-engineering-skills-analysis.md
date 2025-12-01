# Context Engineering & Skills Analysis for MAKER

**Analyzing against:**
1. [Anthropic: Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
2. [Anthropic Skills Framework](https://github.com/anthropics/skills)
3. Incremental skill learning for long-term memory

---

## 1. Context Engineering for Long-Running Agents

### ❌ Current State: Limited Long-Running Support

**What MAKER has:**
- ✅ Session state management (lines 521-550 in orchestrator.py)
- ✅ Context compression (ContextCompressor class, lines 44-244)
- ✅ Redis persistence for task state (TaskState dataclass, lines 260-283)
- ✅ Conversation history with sliding window (recent + compressed older)
- ⚠️ Session save/load but NO automatic resumability

**What MAKER lacks:**

#### Missing: Initializer/Worker Agent Pattern
**Anthropic pattern:**
- Initializer agent scaffolds environment once
- Worker agents resume from structured state

**MAKER current behavior:**
- All agents are stateless between tasks
- No distinction between initialization and continuation
- Each task starts fresh (no memory of prior tasks in session)

#### Missing: Structured Progress Tracking
**Anthropic pattern:**
```
claude-progress.txt    # What was accomplished
feature_list.json      # { "features": [{"name": "auth", "passes": true}] }
init.sh                # Bootstrap environment
```

**MAKER current state:**
- TaskState tracks only CURRENT task (task_id, status, code, review_feedback)
- NO cross-task progress log
- NO structured feature checklist
- NO initialization script for environment setup

#### Missing: Resumability Protocol
**Anthropic pattern (each session starts with):**
1. `pwd` to orient
2. Read git logs + progress files
3. Select highest-priority incomplete feature
4. Run `init.sh`
5. Execute end-to-end test

**MAKER current state:**
- Agents receive task prompt only
- NO automatic orientation commands
- NO reading of previous session artifacts
- NO priority selection logic
- NO systematic verification

### ⚠️ Partial: Checkpointing

**What works:**
- TaskState saved to Redis with 24h TTL
- Context compression via Gemma2-2B Preprocessor
- Session serialization (to_dict/from_dict)

**What's missing:**
- NO git commits between iterations
- NO "clean state" verification before marking complete
- NO end-to-end testing requirement (only Reviewer approval)
- NO structured artifacts (all state in Redis, nothing on disk)

---

## 2. Agent Skills Framework

### ❌ Current State: No Skills System

**MAKER agents use static prompts:**
```
agents/planner-system.md       (45 lines, static instructions)
agents/coder-system.md         (56 lines, static instructions)
agents/reviewer-system.md      (46 lines, static instructions)
agents/preprocessor-system.md  (25 lines, static instructions)
agents/voter-system.md         (17 lines, static instructions)
```

**Issues:**
1. **No dynamic skill loading** - Agents can't learn new capabilities
2. **No skill discovery** - Agents don't know what tools they have
3. **No skill composition** - Can't combine skills for complex tasks
4. **No skill persistence** - Every task uses same static prompts

### Missing: Anthropic Skills Structure

**What a skill should look like:**
```markdown
---
name: xml-to-spss-converter
description: Convert XML survey data to SPSS format using specialized parsing
---

# XML to SPSS Conversion Skill

## When to Use
When user requests XML → SPSS conversion, especially for:
- Kantar survey data
- Complex nested structures
- Custom variable mappings

## Steps
1. Parse XML structure with lxml
2. Extract variable definitions
3. Map to SPSS variable types
4. Generate .sav file using pyreadstat

## Example
```python
import lxml.etree as ET
import pyreadstat

# Parse XML
tree = ET.parse('survey.xml')
# ... conversion logic
```

## Resources
- `scripts/xml_parser.py`
- `configs/spss_mapping.json`
```

**Current MAKER equivalents: NONE**

---

## 3. Incremental Skill Learning

### ❌ Current State: No Skill Memory

**Anthropic example:** User solves XML→SPSS conversion once, system learns it as a reusable skill for future XML tasks.

**MAKER current behavior:**
- Task completes, all context discarded
- Next XML task starts from scratch
- NO skill extraction or storage
- NO skill library accumulation

### What's Needed: Skill Learning Pipeline

```
Task Completion
    ↓
Extract Reusable Patterns
    ↓
Create Skill Card (SKILL.md)
    ↓
Store in Skills Registry
    ↓
Index for Future Discovery
    ↓
Load Dynamically When Relevant
```

**Current MAKER: NONE of these steps exist**

---

## Detailed Gap Analysis

### Gap 1: No Long-Running Agent Support

| Capability | Anthropic Pattern | MAKER Current | Gap |
|------------|------------------|---------------|-----|
| Session resumability | ✅ Initializer/Worker pattern | ⚠️ Save/load exists but not used | **HIGH** |
| Progress tracking | ✅ claude-progress.txt + feature_list.json | ❌ None | **CRITICAL** |
| Environment setup | ✅ init.sh | ❌ None | **HIGH** |
| Orientation protocol | ✅ pwd, git log, read progress | ❌ None | **HIGH** |
| Clean checkpoints | ✅ Git commits + verification | ⚠️ Redis state only | **MEDIUM** |
| End-to-end testing | ✅ Puppeteer/browser automation | ⚠️ Reviewer only, no E2E | **HIGH** |

### Gap 2: No Skills Framework

| Capability | Anthropic Skills | MAKER Current | Gap |
|------------|-----------------|---------------|-----|
| Skill definition | ✅ SKILL.md with YAML frontmatter | ❌ None | **CRITICAL** |
| Dynamic loading | ✅ Load based on task context | ❌ Static prompts | **CRITICAL** |
| Skill discovery | ✅ Description-based matching | ❌ None | **HIGH** |
| Skill composition | ✅ Combine multiple skills | ❌ None | **MEDIUM** |
| Skill marketplace | ✅ Install from registry | ❌ None | **LOW** |

### Gap 3: No Incremental Learning

| Capability | Desired State | MAKER Current | Gap |
|------------|--------------|---------------|-----|
| Pattern extraction | ✅ Extract reusable logic from tasks | ❌ None | **CRITICAL** |
| Skill creation | ✅ Auto-generate SKILL.md | ❌ None | **CRITICAL** |
| Skill indexing | ✅ Semantic search in skill library | ❌ None | **HIGH** |
| Skill application | ✅ "I've done this before" detection | ❌ None | **CRITICAL** |
| Skill evolution | ✅ Update skills with new learnings | ❌ None | **MEDIUM** |

---

## Impact Assessment

### Current System Limitations

**Without long-running support:**
- ❌ Can't work on features across multiple sessions
- ❌ No memory of what was accomplished yesterday
- ❌ User must manually track progress
- ❌ Can't resume interrupted work cleanly

**Without skills framework:**
- ❌ Can't specialize for domain-specific tasks (XML→SPSS)
- ❌ Rediscovers patterns every time
- ❌ No knowledge accumulation
- ❌ Limited to general-purpose coding

**Without incremental learning:**
- ❌ Every XML task is "new" even if solved before
- ❌ No learning from success patterns
- ❌ Can't build expertise over time
- ❌ User must re-teach same patterns

### Example: XML to SPSS Conversion

**Current MAKER behavior:**
```
Day 1: User requests XML→SPSS conversion
→ Planner: Break into steps
→ Coder: Generate conversion code
→ Reviewer: Approve
→ Result: Working code (one-time)
→ Memory: DISCARDED after task

Day 7: User requests another XML→SPSS task
→ Planner: Start from scratch
→ Coder: Re-solve same problem
→ No knowledge of previous solution
```

**With skills framework + learning:**
```
Day 1: User requests XML→SPSS conversion
→ Planner: Break into steps
→ Coder: Generate conversion code
→ Reviewer: Approve
→ Skill Extractor: Create "xml-to-spss-converter" skill
→ Skill Registry: Store for future use

Day 7: User requests another XML→SPSS task
→ Skill Matcher: Detect similarity to previous task
→ Load "xml-to-spss-converter" skill
→ Planner: Use specialized knowledge
→ Coder: Apply proven patterns
→ 10x faster, higher quality
```

---

## Recommendations

### Priority 1: Add Long-Running Agent Support (HIGH IMPACT)

**1.1 Implement Progress Tracking**
```python
# New file: orchestrator/progress_tracker.py
class ProgressTracker:
    def __init__(self, workspace_path: Path):
        self.progress_file = workspace_path / "claude-progress.txt"
        self.feature_list = workspace_path / "feature_list.json"

    def log_progress(self, message: str):
        """Append to progress log"""
        with open(self.progress_file, 'a') as f:
            f.write(f"[{datetime.now()}] {message}\n")

    def update_feature_status(self, feature_name: str, passes: bool):
        """Mark feature as complete/incomplete"""
        features = self._load_features()
        for feature in features:
            if feature['name'] == feature_name:
                feature['passes'] = passes
        self._save_features(features)

    def get_next_feature(self) -> Optional[Dict]:
        """Get highest-priority incomplete feature"""
        features = self._load_features()
        incomplete = [f for f in features if not f['passes']]
        return incomplete[0] if incomplete else None
```

**1.2 Add Resumability Protocol**
```python
# In orchestrator.py
async def resume_session(self, session_id: str):
    """Resume long-running agent session"""
    # 1. Orient
    cwd = os.getcwd()

    # 2. Read progress
    progress = self.progress_tracker.read_progress()

    # 3. Read git log
    git_log = subprocess.check_output(['git', 'log', '-5', '--oneline'])

    # 4. Select next feature
    next_feature = self.progress_tracker.get_next_feature()

    # 5. Construct context
    resume_prompt = f"""
You are resuming work on this project.

Current directory: {cwd}

Recent progress:
{progress}

Recent commits:
{git_log.decode()}

Next feature to implement:
{next_feature['name']}: {next_feature['description']}

Continue working on this feature.
"""

    return await self.orchestrate_workflow(session_id, resume_prompt)
```

**1.3 Add Clean Checkpoints**
```python
async def checkpoint_session(self, session_id: str, feature_name: str):
    """Create clean checkpoint with verification"""
    # 1. Run tests
    test_results = await self._run_end_to_end_tests()

    # 2. Verify clean state
    if not test_results['all_passed']:
        return {"error": "Tests failing, cannot checkpoint"}

    # 3. Git commit
    subprocess.run(['git', 'add', '.'])
    subprocess.run(['git', 'commit', '-m', f'Complete {feature_name}'])

    # 4. Update progress
    self.progress_tracker.update_feature_status(feature_name, True)
    self.progress_tracker.log_progress(f"Completed {feature_name}")

    # 5. Save session
    self.save_session(session_id)
```

### Priority 2: Implement Skills Framework (CRITICAL FOR LEARNING)

**2.1 Create Skills Directory Structure**
```bash
skills/
├── xml-to-spss-converter/
│   ├── SKILL.md
│   ├── converter.py
│   └── config.json
├── pdf-form-extractor/
│   ├── SKILL.md
│   └── extractor.py
└── skills_registry.json
```

**2.2 Add Skill Loader**
```python
# New file: orchestrator/skill_loader.py
class SkillLoader:
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.registry = self._load_registry()

    def load_skill(self, skill_name: str) -> Dict:
        """Load skill definition"""
        skill_path = self.skills_dir / skill_name / "SKILL.md"
        content = skill_path.read_text()

        # Parse YAML frontmatter
        yaml_match = re.match(r'---\n(.*?)\n---\n(.*)', content, re.DOTALL)
        metadata = yaml.safe_load(yaml_match.group(1))
        instructions = yaml_match.group(2)

        return {
            "name": metadata['name'],
            "description": metadata['description'],
            "instructions": instructions
        }

    def find_relevant_skills(self, task_description: str) -> List[Dict]:
        """Find skills relevant to task (using semantic search)"""
        # Use RAG to find similar skills
        from orchestrator.rag_service_faiss import RAGServiceFAISS
        rag = RAGServiceFAISS()

        # Search skill descriptions
        results = rag.search(task_description, collection="skills", top_k=3)
        return [self.load_skill(r['skill_name']) for r in results]
```

**2.3 Integrate Skills into Agents**
```python
# In orchestrator.py, modify call_agent()
async def call_agent(self, agent: AgentName, system_prompt: str, user_prompt: str, ...):
    # Load relevant skills
    skills = self.skill_loader.find_relevant_skills(user_prompt)

    # Augment system prompt with skills
    if skills:
        skills_section = "\n\n## Available Skills\n"
        for skill in skills:
            skills_section += f"\n### {skill['name']}\n{skill['instructions']}\n"

        system_prompt = system_prompt + skills_section

    # Continue with normal agent call...
```

### Priority 3: Add Incremental Skill Learning (LONG-TERM MEMORY)

**3.1 Skill Extraction After Task Completion**
```python
# New file: orchestrator/skill_extractor.py
class SkillExtractor:
    async def extract_skill_from_task(self, task_id: str) -> Optional[Dict]:
        """Extract reusable skill from completed task"""
        state = TaskState.from_redis(self.redis, task_id)

        # Check if task is suitable for skill extraction
        if not self._is_skill_worthy(state):
            return None

        # Use Planner to analyze task and extract pattern
        extraction_prompt = f"""
Analyze this completed task and extract a reusable skill.

Task: {state.user_input}
Code: {state.code}
Review: {state.review_feedback}

Create a skill definition in this format:
---
name: <skill-name>
description: <when to use this skill>
---

# Instructions
<step-by-step instructions for applying this pattern>

## Example
```python
<example code>
```
"""

        skill_definition = await self.orchestrator.call_agent_sync(
            AgentName.PLANNER,
            "You are a skill extraction specialist.",
            extraction_prompt
        )

        return self._save_skill(skill_definition)

    def _is_skill_worthy(self, state: TaskState) -> bool:
        """Determine if task is worth extracting as skill"""
        # Criteria:
        # 1. Approved by reviewer
        # 2. Non-trivial (>50 LOC or multi-file)
        # 3. Domain-specific pattern detected
        return (
            state.review_feedback.get('status') == 'approved' and
            len(state.code) > 200 and
            self._detect_domain_pattern(state.code)
        )
```

**3.2 Skill Registry with Semantic Search**
```python
# Update skills_registry.json after each extraction
{
  "skills": [
    {
      "name": "xml-to-spss-converter",
      "description": "Convert XML survey data to SPSS .sav format",
      "created": "2024-12-01T10:30:00",
      "usage_count": 5,
      "success_rate": 0.85,
      "tags": ["xml", "spss", "data-conversion", "kantar"]
    }
  ]
}

# Index in RAG for semantic search
rag.index_skill(skill_name, skill_description, skill_instructions)
```

**3.3 Auto-Apply Skills**
```python
# In orchestrate_workflow(), before planning
async def orchestrate_workflow(self, task_id: str, user_input: str):
    # Check if we've solved this before
    similar_skills = self.skill_loader.find_relevant_skills(user_input)

    if similar_skills and similar_skills[0]['similarity'] > 0.85:
        yield f"[SKILL] Found relevant skill: {similar_skills[0]['name']}\n"
        yield f"[SKILL] I've done this before! Applying proven pattern...\n"

        # Load skill into all agents
        for agent in [AgentName.PLANNER, AgentName.CODER]:
            self._inject_skill(agent, similar_skills[0])

    # Continue with normal workflow...
```

---

## Implementation Roadmap

### Phase 1: Long-Running Basics (Week 1-2)
- [ ] Add ProgressTracker class
- [ ] Implement feature_list.json structure
- [ ] Add resume_session() method
- [ ] Add checkpoint_session() with git commits
- [ ] Test multi-session workflows

### Phase 2: Skills Framework (Week 3-4)
- [ ] Create skills/ directory structure
- [ ] Implement SkillLoader class
- [ ] Add skill discovery via RAG
- [ ] Inject skills into agent prompts
- [ ] Test manual skill creation

### Phase 3: Incremental Learning (Week 5-6)
- [ ] Implement SkillExtractor
- [ ] Auto-extract skills from completed tasks
- [ ] Build skills registry with semantic search
- [ ] Add auto-apply logic
- [ ] Test skill learning loop

### Phase 4: Integration & Polish (Week 7-8)
- [ ] End-to-end testing harness
- [ ] Skill evolution (update existing skills)
- [ ] Performance monitoring
- [ ] Documentation
- [ ] User testing

---

## Expected Benefits

**With long-running support:**
- ✅ Multi-day projects feasible
- ✅ Clean resumability after interruptions
- ✅ Automated progress tracking
- ✅ Git-based rollback capability

**With skills framework:**
- ✅ Domain specialization (XML→SPSS, PDF forms, etc.)
- ✅ Consistent quality for repeated tasks
- ✅ Faster execution (apply proven patterns)
- ✅ Knowledge sharing across projects

**With incremental learning:**
- ✅ System gets smarter over time
- ✅ No re-solving known problems
- ✅ Builds expertise automatically
- ✅ 10x improvement on repeated task types

---

## Next Steps

1. **Review this analysis** with team/stakeholders
2. **Prioritize phases** based on immediate needs
3. **Start with Phase 1** (long-running basics) for quick wins
4. **Prototype skills framework** (Phase 2) for XML→SPSS use case
5. **Measure improvement** on SWE-bench after each phase

**Key Question:** Should we implement all phases, or focus on specific gaps first?
