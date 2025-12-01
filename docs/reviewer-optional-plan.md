# Plan: Making Qwen3 Coder (Reviewer) Optional

## Overview

Make the Reviewer agent (Qwen3-Coder 32B) optional to reduce RAM requirements by ~18-20GB, making the system more accessible to users with less memory.

**Current RAM Usage:**
- Preprocessor (Gemma2-2B): ~4GB
- Planner (Nemotron Nano 8B): ~10GB
- Coder (Devstral 24B): ~18GB
- **Reviewer (Qwen3-Coder 32B): ~18-20GB** ← Target for optional
- Voter (Qwen2.5-1.5B): ~2GB
- **Total: ~52-54GB → ~34-36GB (with Reviewer disabled)**

## Current Reviewer Role

The Reviewer validates code quality in the workflow:
1. Receives generated code from Coder (after MAKER voting)
2. Validates correctness, security, readability
3. Returns JSON: `{"status": "approved"}` or `{"status": "failed", "feedback": "..."}`
4. If approved → workflow completes
5. If failed → loops back to Coder (max 3 iterations)

**Location in workflow:** `orchestrator/orchestrate_workflow()` lines 1066-1098

## Enhanced Approach: Planner Reflection (When Reviewer Disabled)

**Key Insight:** The Planner (Nemotron Nano 8B) already understands the task requirements (it created the plan), so it can validate if the generated code meets those requirements.

**Benefits:**
- ✅ No additional RAM (Planner already running)
- ✅ Better than auto-approval (actual validation)
- ✅ Uses existing agent's understanding of the task
- ✅ Can iterate up to 3 times (same as Reviewer flow)
- ✅ Validates against the plan it created

**How it works:**
1. Planner creates initial plan with task requirements
2. Coder generates code based on plan
3. **Planner reflects:** "Does this code meet the plan I created?"
4. If yes → approve
5. If no → provide feedback, iterate (max 3 times)

## Implementation Plan

### Phase 1: Environment Variable & Configuration

**Goal:** Add feature flag to enable/disable Reviewer

**Changes:**
1. **Environment Variable:**
   - `ENABLE_REVIEWER=true` (default: `true` for backward compatibility)
   - If `false`, skip Reviewer step entirely

2. **Orchestrator Initialization** (`orchestrator/orchestrator.py`):
   ```python
   # In __init__:
   self.enable_reviewer = os.getenv("ENABLE_REVIEWER", "true").lower() == "true"
   
   # Only add Reviewer endpoint if enabled
   if self.enable_reviewer:
       self.endpoints[AgentName.REVIEWER] = os.getenv(
           "REVIEWER_URL", 
           "http://localhost:8003/v1/chat/completions"
       )
   ```

3. **Health Check:**
   - Add health check method that verifies Reviewer endpoint only if enabled
   - Update `/health` endpoint to show Reviewer status

### Phase 2: Workflow Modification

**Goal:** Skip Reviewer step when disabled, use Planner Reflection for validation

**Changes in `orchestrator/orchestrate_workflow()`:**

**Current flow (lines 1066-1098):**
```python
# 4. REVIEW
reviewer_prompt = self._load_system_prompt("reviewer")
review_request = f"""Review this code: ..."""
review_output = ""
yield f"\n[REVIEWER] Validating code...\n"
async for chunk in self.call_agent(AgentName.REVIEWER, ...):
    review_output += chunk
    yield chunk

# Parse review_feedback
state.review_feedback = json.loads(review_output) or {"status": "approved"}

# Check if approved
if state.review_feedback.get("status") == "approved":
    state.status = "complete"
    break
```

**New flow (with optional Reviewer + Planner Reflection):**
```python
# 4. REVIEW (optional - Reviewer or Planner Reflection)
if self.enable_reviewer:
    # Use Reviewer (original flow)
    reviewer_prompt = self._load_system_prompt("reviewer")
    review_request = f"""Review this code:

{code_output}

Original task: {task_desc}

Run tests and validate code quality.
"""
    review_output = ""
    yield f"\n[REVIEWER] Validating code...\n"
    
    try:
        async for chunk in self.call_agent(AgentName.REVIEWER, reviewer_prompt, review_request, temperature=0.1):
            review_output += chunk
            yield chunk
    except Exception as e:
        # If Reviewer unavailable, fall back to Planner reflection
        yield f"\n[REVIEWER] Unavailable ({e}), using Planner reflection...\n"
        review_output = await self._planner_reflection(state, code_output, task_desc)
    
    compressor.add_message("reviewer", review_output[:1000])
    
    try:
        state.review_feedback = json.loads(review_output)
    except json.JSONDecodeError:
        if "approved" in review_output.lower():
            state.review_feedback = {"status": "approved"}
        else:
            state.review_feedback = {"status": "failed", "feedback": review_output}
else:
    # Use Planner Reflection (new approach)
    yield f"\n[PLANNER] Reflecting on code quality (Reviewer disabled)...\n"
    review_output = await self._planner_reflection(state, code_output, task_desc)
    
    compressor.add_message("planner_reflection", review_output[:1000])
    
    try:
        state.review_feedback = json.loads(review_output)
    except json.JSONDecodeError:
        if "approved" in review_output.lower() or "meets requirements" in review_output.lower():
            state.review_feedback = {"status": "approved", "method": "planner_reflection"}
        else:
            state.review_feedback = {"status": "failed", "feedback": review_output, "method": "planner_reflection"}

# Check if approved (same logic for both paths)
if state.review_feedback.get("status") == "approved":
    state.status = "complete"
    # ... rest of completion logic
```

**New method: `_planner_reflection()`**
```python
async def _planner_reflection(self, state: TaskState, code_output: str, task_desc: str) -> str:
    """
    Use Planner to reflect on whether generated code meets the original plan.
    
    The Planner already understands the task (it created the plan), so it can
    validate if the code matches the requirements. This provides validation
    without requiring the Reviewer agent (saves ~18-20GB RAM).
    
    Args:
        state: Current task state (contains plan)
        code_output: Generated code to validate
        task_desc: Original task description
    
    Returns:
        JSON string with validation result: {"status": "approved"/"failed", ...}
    """
    planner_prompt = self._load_system_prompt("planner")
    
    # Get the original plan for context
    plan_summary = ""
    if state.plan and "plan" in state.plan:
        plan_items = state.plan["plan"]
        plan_summary = "\n".join([
            f"{i+1}. {item.get('description', '')}" 
            for i, item in enumerate(plan_items[:5])
        ])
    
    # Get narrative context if available (EE Memory)
    narrative_context = ""
    if hasattr(self, 'agent_memories'):
        planner_memory = self.agent_memories.get(AgentName.PLANNER)
        if planner_memory:
            narrative_context = planner_memory.get_context_for_agent(task_desc)
    
    reflection_request = f"""You are reflecting on code quality. You previously created a plan for this task.

ORIGINAL TASK:
{task_desc}

YOUR ORIGINAL PLAN:
{plan_summary if plan_summary else "Single-step task: " + task_desc}

NARRATIVE CONTEXT (if relevant):
{narrative_context[:1000] if narrative_context else "No specific narratives"}

GENERATED CODE TO VALIDATE:
```python
{code_output[:4000]}  # Truncate for context
```

REFLECTION TASK:
Does this code implementation meet the requirements from your plan?

Check these aspects:
1. **Completeness**: Does it address all requirements you identified in the plan?
2. **Correctness**: Are there obvious errors, missing imports, or logical issues?
3. **Architecture**: Does it follow the patterns and structure you considered?
4. **Narrative Coherence**: If relevant, does it preserve the business flows you identified?

RESPOND IN JSON FORMAT:
{{
  "status": "approved" or "failed",
  "reason": "Brief explanation of your assessment",
  "feedback": "Specific feedback for improvement (only if failed, otherwise empty string)"
}}

EXAMPLES:

If code is good:
{{"status": "approved", "reason": "Code implements all plan requirements correctly", "feedback": ""}}

If code has issues:
{{"status": "failed", "reason": "Missing error handling for edge case", "feedback": "Add try-except block around file I/O operations"}}

Begin your reflection:
"""
    
    reflection_output = await self.call_agent_sync(
        AgentName.PLANNER,
        planner_prompt,
        reflection_request,
        temperature=0.2  # Lower temperature for more consistent validation
    )
    
    return reflection_output
```

**Key Design Decisions:**
1. **Uses existing Planner prompt** - No new system prompt needed, Planner already understands task decomposition
2. **References original plan** - Planner validates against the plan it created (strong context)
3. **Includes narrative context** - If EE Memory is enabled, includes business narrative awareness
4. **Lower temperature (0.2)** - More consistent validation decisions
5. **JSON output format** - Same format as Reviewer for compatibility
6. **Truncates code to 4000 chars** - Fits within Planner's context window while keeping key parts

**Key Points:**
- When disabled: Use Planner Reflection (validates against original plan)
- When enabled but unavailable: Fall back to Planner Reflection (graceful degradation)
- Planner Reflection: Checks if code meets the plan it created (up to 3 iterations)
- Always set `review_feedback` so downstream code (skill_extractor, etc.) works
- Planner Reflection provides better quality than auto-approval while using no extra RAM

### Phase 3: Startup Scripts

**Goal:** Conditionally start Reviewer server

**Changes in `scripts/start-llama-servers.sh`:**

```bash
# Reviewer (port 8003) - Optional
if [ "${ENABLE_REVIEWER:-true}" = "true" ]; then
    if [ -f "models/qwen-coder-32b-instruct.Q6_K.gguf" ]; then
        llama-server \
          --model models/qwen-coder-32b-instruct.Q6_K.gguf \
          --port 8003 \
          --host 0.0.0.0 \
          --n-gpu-layers 999 \
          --ctx-size 262144 \
          --parallel 4 \
          > logs/llama-reviewer.log 2>&1 &
        echo $! > /tmp/llama-reviewer.pid
        echo " Reviewer started (PID: $(cat /tmp/llama-reviewer.pid), port 8003)"
    else
        echo "  Reviewer model not found: models/qwen-coder-32b-instruct.Q6_K.gguf"
        echo "  Set ENABLE_REVIEWER=false to skip"
    fi
else
    echo "  Reviewer disabled (ENABLE_REVIEWER=false)"
fi
```

**Changes in `scripts/stop-llama-servers.sh`:**

```bash
# Only stop Reviewer if PID file exists
if [ -f /tmp/llama-reviewer.pid ]; then
    kill $(cat /tmp/llama-reviewer.pid) 2>/dev/null || true
    rm /tmp/llama-reviewer.pid
    echo " Reviewer stopped"
fi
```

**Health check update:**
```bash
# In start-llama-servers.sh health check section:
for port in 8000 8001 8002; do  # Always required
    if curl -s http://localhost:$port/health > /dev/null 2>&1; then
        echo "   Port $port: Healthy"
    else
        echo "   Port $port: Starting..."
    fi
done

# Optional services
if [ "${ENABLE_REVIEWER:-true}" = "true" ]; then
    if curl -s http://localhost:8003/health > /dev/null 2>&1; then
        echo "   Port 8003 (Reviewer): Healthy"
    else
        echo "   Port 8003 (Reviewer): Starting..."
    fi
fi
```

### Phase 4: Docker Configuration

**Goal:** Make Reviewer URL optional in docker-compose

**Changes in `docker-compose.yml`:**

```yaml
orchestrator:
  environment:
    # ... existing vars ...
    - REVIEWER_URL=http://host.docker.internal:8003/v1/chat/completions
    - ENABLE_REVIEWER=${ENABLE_REVIEWER:-true}  # New: optional Reviewer
```

**Note:** Reviewer server still runs natively (not in Docker), so this just controls whether Orchestrator tries to use it.

### Phase 5: Agent Memory & Skills

**Goal:** Handle Reviewer context gracefully when disabled

**Changes in `orchestrator/agent_memory.py`:**

The `_reviewer_context()` method is only called if Reviewer is used, so no changes needed. However, we should ensure it doesn't break if Reviewer is disabled:

```python
# In AgentMemoryNetwork.get_context_for_agent():
if self.agent_name == AgentName.REVIEWER:
    # Only called if Reviewer is actually used
    return self._reviewer_context(base_context)
```

**No changes needed** - Reviewer context is only requested when Reviewer is called.

### Phase 6: Skill Extraction Compatibility

**Goal:** Ensure skill extraction works with auto-approved tasks

**Changes in `orchestrator/skill_extractor.py`:**

The `is_skill_worthy()` method checks `review_feedback.get('status') == 'approved'`. With auto-approval, this will still work, but we should distinguish:

```python
def is_skill_worthy(self, state: 'TaskState') -> bool:
    # ... existing code ...
    
    # For RESOLVED tasks: Extract proven patterns
    if state.review_feedback and state.review_feedback.get('status') == 'approved':
        # Check if auto-approved (less confidence)
        auto_approved = state.review_feedback.get('auto_approved', False)
        
        if auto_approved:
            # Require higher bar for auto-approved tasks
            return (
                state.code and
                len(state.code) > 500 and  # More code required
                state.iteration_count == 1 and  # First try success
                self._has_reusable_pattern(state) and
                # ... rest of checks
            )
        else:
            # Normal reviewer-approved path
            return (
                state.code and
                len(state.code) > 200 and
                # ... existing checks
            )
```

**Alternative (simpler):** Keep existing logic, just note in skill metadata that it was auto-approved.

### Phase 7: Testing & Validation

**Test Cases:**

1. **Reviewer Enabled (default):**
   - Start with `ENABLE_REVIEWER=true` (or unset)
   - Reviewer server starts
   - Workflow uses Reviewer
   - Code approved/rejected as normal

2. **Reviewer Disabled (Planner Reflection):**
   - Start with `ENABLE_REVIEWER=false`
   - Reviewer server doesn't start
   - Workflow uses Planner Reflection to validate code
   - Planner checks if code meets the plan it created
   - Can iterate up to 3 times if code doesn't meet requirements
   - Task completes successfully with validation

3. **Reviewer Enabled but Unavailable:**
   - Start with `ENABLE_REVIEWER=true`
   - Reviewer server not running (or crashes)
   - Workflow falls back to Planner Reflection
   - Task completes with validation (using Planner)

4. **Skill Extraction:**
   - Auto-approved task can still extract skills
   - Skills marked with `auto_approved: true` in metadata

5. **Backward Compatibility:**
   - Existing workflows continue to work
   - Default behavior unchanged (Reviewer enabled)

**Test Script:**
```bash
# tests/test_reviewer_optional.sh
#!/bin/bash

# Test 1: Reviewer enabled
export ENABLE_REVIEWER=true
bash scripts/start-llama-servers.sh
# ... run workflow test ...

# Test 2: Reviewer disabled
export ENABLE_REVIEWER=false
bash scripts/start-llama-servers.sh
# ... run workflow test ...

# Test 3: Reviewer unavailable (enabled but server down)
export ENABLE_REVIEWER=true
# Don't start Reviewer server
# ... run workflow test ...
```

## Migration Guide

### For Users Who Want to Disable Reviewer

1. **Set environment variable:**
   ```bash
   export ENABLE_REVIEWER=false
   ```

2. **Update docker-compose.yml** (if using Docker):
   ```yaml
   orchestrator:
     environment:
       - ENABLE_REVIEWER=false
   ```

3. **Restart services:**
   ```bash
   bash scripts/stop-llama-servers.sh
   bash scripts/start-llama-servers.sh
   docker compose restart orchestrator
   ```

4. **Verify:**
   ```bash
   curl http://localhost:8080/health
   # Should show reviewer: disabled
   ```

### For Users Who Keep Reviewer Enabled

**No changes needed** - default behavior unchanged.

## Risks & Mitigations

### Risk 1: Lower Code Quality Without Reviewer

**Mitigation:**
- **Planner Reflection** provides validation (not just auto-approval)
- Planner checks if code meets the plan it created
- Can iterate up to 3 times (same as Reviewer flow)
- Users can still manually review code
- Skill extraction still works
- **Documentation:** Note that Reviewer provides deeper validation, but Planner Reflection is a good alternative

### Risk 2: Breaking Existing Workflows

**Mitigation:**
- Default `ENABLE_REVIEWER=true` (backward compatible)
- Graceful fallback if Reviewer unavailable
- All existing code paths still work

### Risk 3: Skill Extraction Less Reliable

**Mitigation:**
- Higher bar for auto-approved tasks (more code, first-try success)
- Mark skills with `auto_approved: true` for transparency
- Users can re-enable Reviewer for critical tasks

## Reviewer vs Planner Reflection Comparison

| Aspect | Reviewer (Qwen3-Coder 32B) | Planner Reflection (Nemotron Nano 8B) |
|--------|----------------------------|--------------------------------------|
| **RAM Usage** | ~18-20GB | 0GB (already running) |
| **Validation Depth** | Deep: correctness, security, readability | Medium: plan compliance, obvious errors |
| **Context Window** | 256K tokens | 128K tokens |
| **Model Size** | 32B parameters | 8B parameters |
| **Specialization** | Code review expert | Task planning & validation |
| **Iteration Capability** | Yes (up to 3) | Yes (up to 3) |
| **Speed** | Slower (larger model) | Faster (smaller model) |
| **Best For** | Production code, security-critical | Development, prototyping, RAM-constrained |

**When to Use Each:**

- **Use Reviewer (default):**
  - Production code generation
  - Security-sensitive tasks
  - Complex refactoring
  - When you have 50GB+ RAM available

- **Use Planner Reflection:**
  - Development/prototyping
  - RAM-constrained systems (<40GB)
  - Simple to medium complexity tasks
  - When Reviewer model unavailable

**Quality Comparison:**
- Reviewer: Catches subtle bugs, security issues, style problems
- Planner Reflection: Validates plan compliance, catches obvious errors, ensures completeness
- **Gap:** Planner Reflection may miss subtle bugs that Reviewer would catch

## Success Criteria

✅ Reviewer can be disabled via `ENABLE_REVIEWER=false`  
✅ Workflow completes successfully without Reviewer  
✅ Planner Reflection validates code against original plan  
✅ Can iterate up to 3 times with Planner Reflection feedback  
✅ Graceful fallback if Reviewer enabled but unavailable  
✅ Startup scripts conditionally start Reviewer  
✅ Health checks show Reviewer status  
✅ Skill extraction works with Planner Reflection-validated tasks  
✅ Backward compatible (default: enabled)  
✅ RAM usage reduced by ~18-20GB when disabled  
✅ Documentation updated  

## Implementation Order

1. **Phase 1:** Environment variable & Orchestrator initialization
2. **Phase 2:** Workflow modification (Planner Reflection when Reviewer disabled)
   - Add `_planner_reflection()` method
   - Update review step to use Planner Reflection when Reviewer disabled
3. **Phase 3:** Startup scripts (conditional Reviewer start)
4. **Phase 4:** Docker configuration
5. **Phase 5:** Agent memory (verify no changes needed)
6. **Phase 6:** Skill extraction compatibility
7. **Phase 7:** Testing & validation

## Documentation Updates

1. **README.md:** Add section on optional Reviewer
2. **CLAUDE.md:** Update architecture diagram
3. **QUICK_START_SERVICES.md:** Note Reviewer is optional
4. **docs/SERVICE_STARTUP_GUIDE.md:** Add ENABLE_REVIEWER flag

## Estimated Impact

**RAM Reduction:** ~18-20GB (from ~52-54GB to ~34-36GB)  
**Code Quality:** Good (Planner Reflection validates against plan) - Better than auto-approval, slightly less thorough than Reviewer  
**Workflow Speed:** Similar (Planner Reflection takes similar time to Reviewer)  
**Backward Compatibility:** 100% (default enabled)  
**Iteration Capability:** Same (up to 3 iterations with feedback)  

---

**Status:** Ready for implementation  
**Priority:** Medium (accessibility improvement)  
**Breaking Changes:** None (opt-in via env var)

