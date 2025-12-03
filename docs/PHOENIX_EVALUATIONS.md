# Phoenix Evaluations for MAKER Multi-Agent System

Complete guide to evaluating collective brain, melodic line memory, and code generation quality using Arize Phoenix.

## Overview

Phoenix Evaluations provides:
- **LLM-as-Judge evaluations** (hallucination, Q&A correctness, relevance)
- **Code execution validation** (via Playwright)
- **A/B testing framework** (compare configurations)
- **Visual analysis** in Phoenix UI at `http://localhost:6006`

## Setup

### 1. Install Dependencies

```bash
# Install Phoenix Evaluations SDK and Playwright
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 2. Verify Phoenix is Running

```bash
# Check Phoenix UI is accessible
curl http://localhost:6006/health

# Or visit in browser
open http://localhost:6006
```

## Running Evaluations

### Melodic Memory A/B Test

Compare agent performance with melodic line memory ON vs OFF:

```bash
python tests/phoenix_evaluator.py --experiment melodic_memory_ab
```

**What it tests:**
- Control group: Agents without shared reasoning chain (melodic_memory=False)
- Treatment group: Agents with Kùzu melodic line memory (melodic_memory=True)

**Metrics:**
- QA Correctness Lift: How much better are answers with melodic memory?
- Hallucination Reduction: Does melodic memory reduce hallucinations?
- Relevance: Are answers more on-topic with context awareness?

**Expected results:**
- ✅ Higher QA correctness (agents maintain intent across workflow)
- ✅ Lower hallucination (grounded in previous agent reasoning)
- ✅ Better relevance (coherent reasoning chain)

---

### Collective Brain A/B Test

Compare multi-agent consensus vs single-agent answers:

```bash
python tests/phoenix_evaluator.py --experiment collective_brain_ab
```

**What it tests:**
- Control group: Single agent (Preprocessor) answers complex questions
- Treatment group: Collective brain consults multiple agents (Preprocessor + Planner + Coder + Reviewer)

**Metrics:**
- QA Correctness Lift: Do multiple perspectives improve answers?
- Relevance Lift: Are answers more comprehensive?
- Consensus Confidence: How much do agents agree?

**Expected results:**
- ✅ Higher correctness for architectural/design questions
- ✅ Better coverage of trade-offs and considerations
- ✅ Dissenting opinions surface edge cases

---

### SWE-bench Evaluation

Evaluate on real GitHub issue fixes from SWE-bench Lite:

```bash
# Run on 10 instances (quick test)
python tests/phoenix_evaluator.py --experiment swe_bench --num_instances 10

# Run on 50 instances (thorough test)
python tests/phoenix_evaluator.py --experiment swe_bench --num_instances 50

# Full SWE-bench Lite (300 instances - takes hours)
python tests/phoenix_evaluator.py --experiment swe_bench --num_instances 300
```

**What it tests:**
- Real GitHub issues from popular Python repos
- Gold patches as reference answers
- Code execution validation (does generated code work?)

**Metrics:**
- QA Correctness: How close is generated patch to gold patch?
- Code Pass Rate: Does code execute without errors?
- Test Coverage: Do generated tests pass?
- Hallucination: Does code reference non-existent APIs?

---

## Analyzing Results in Phoenix UI

### 1. View Experiments

Navigate to `http://localhost:6006` and you'll see:

- **Projects**: Each experiment creates a Phoenix project
  - `melodic_memory_control`
  - `melodic_memory_treatment`
  - `collective_brain_control`
  - `collective_brain_treatment`
  - `swe_bench_10`, `swe_bench_50`, etc.

### 2. Compare Metrics

Click on a project to see:

- **Traces**: Full agent execution traces with timing
- **Evaluations**: LLM-as-judge scores for each instance
- **Distributions**: Score distributions across instances
- **Comparisons**: Side-by-side control vs treatment

### 3. Drill into Failures

Filter by low scores to see:
- Which questions failed?
- What did the agent respond?
- Why did Phoenix evaluator mark it wrong?
- What was the execution error?

### 4. Export Data

Download CSV results from:
- `results/phoenix_evals/melodic_memory_control_*.csv`
- `results/phoenix_evals/melodic_memory_treatment_*.csv`
- etc.

---

## Understanding Phoenix Evaluators

### HallucinationEvaluator

**What it checks:** Does the output contain information NOT present in the context?

Example:
```python
Context: "User wants JWT auth"
Output: "Implement JWT auth with OAuth2 and SAML"
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ (HALLUCINATION - SAML not mentioned)
Score: 0.7 (high hallucination)
```

**Why it matters:** Melodic memory should ground agents in actual context, reducing hallucinations.

---

### QAEvaluator

**What it checks:** Is the output a correct answer to the question given the reference?

Example:
```python
Question: "How to fix this bug?"
Reference: "Change line 42: x = 5 to x = 10"
Output: "Change x to 10 on line 42"
Score: 0.95 (very correct)
```

**Why it matters:** Collective brain should synthesize better answers than single agents.

---

### RelevanceEvaluator

**What it checks:** Is the output relevant to the input question?

Example:
```python
Question: "Should I use GraphQL or REST?"
Output: "GraphQL provides flexible queries, REST is simpler. Consider team expertise."
Score: 0.9 (highly relevant)

Output: "I recommend TypeScript for type safety"
Score: 0.2 (not relevant - wrong topic)
```

**Why it matters:** Agents should stay on topic, not drift to tangential advice.

---

## Code Execution Validation

Uses Playwright to safely execute generated code:

```python
# Phoenix evaluator extracts code blocks
code = """
def fibonacci(n):
    if n <= 1: return n
    return fibonacci(n-1) + fibonacci(n-2)
"""

# Runs test assertions
assertions = [
    "assert fibonacci(0) == 0",
    "assert fibonacci(5) == 5",
    "assert fibonacci(10) == 55"
]

# Executes in isolated Python subprocess
result = subprocess.run(['python3', temp_file], timeout=10)
# ✅ PASS or ❌ FAIL
```

**Why it matters:** Code that looks correct but doesn't run is useless. This catches:
- Syntax errors
- Runtime errors
- Logic bugs
- API misuse

---

## Interpreting A/B Test Results

### Melodic Memory Example

```
📈 A/B Test Results:
  QA Correctness Lift: +12.5%
  Hallucination Reduction: +8.3%
```

**Interpretation:**
- With melodic memory, agents give 12.5% more correct answers
- Hallucinations reduced by 8.3% (fewer made-up facts)
- **Conclusion**: Melodic line helps agents maintain coherent reasoning

### Collective Brain Example

```
📈 A/B Test Results:
  QA Correctness Lift: +18.2%
  Relevance Lift: +7.4%
```

**Interpretation:**
- Collective brain answers are 18.2% more correct
- 7.4% more relevant (better coverage of the question)
- **Conclusion**: Multi-agent consensus beats single-agent for complex questions

---

## Customizing Evaluations

### Add Your Own Test Cases

Edit `create_melodic_memory_ab_test()` in `tests/phoenix_evaluator.py`:

```python
EvalInstance(
    instance_id="custom_1",
    question="Your question here",
    reference_answer="Expected answer",
    context="Relevant context",
    expected_code="# Expected code snippet",
    test_assertions=["assert result == expected"]
)
```

### Change Evaluation Criteria

Modify `_run_phoenix_evals()` to add custom evaluators:

```python
from phoenix.evals import CodeQualityEvaluator  # Custom evaluator

code_eval = CodeQualityEvaluator()
results = run_evals(
    dataframe=eval_df,
    evaluators=[code_eval],
    provide_explanation=True
)
```

---

## Troubleshooting

### "Phoenix connection refused"

```bash
# Make sure Phoenix container is running
docker compose ps phoenix

# Check logs
docker compose logs phoenix --tail=50

# Restart if needed
docker compose restart phoenix
```

### "No module named 'phoenix'"

```bash
# Install Phoenix SDK
pip install arize-phoenix arize-phoenix-evals

# Verify installation
python -c "import phoenix; print(phoenix.__version__)"
```

### "Playwright browsers not installed"

```bash
# Install Chromium for code execution
playwright install chromium

# Or install all browsers
playwright install
```

### "HuggingFace dataset download timeout"

```bash
# SWE-bench Lite is ~500MB, might take time
# Use fewer instances for quick tests
python tests/phoenix_evaluator.py --experiment swe_bench --num_instances 5
```

---

## Best Practices

### 1. Start Small

Run 5-10 instances first to verify everything works:

```bash
python tests/phoenix_evaluator.py --experiment swe_bench --num_instances 5
```

### 2. Use Control Groups

Always run A/B tests with control and treatment:
- Control: Baseline configuration
- Treatment: New feature (melodic memory, collective brain)

### 3. Check Phoenix UI During Runs

Watch traces in real-time at `http://localhost:6006` to debug issues.

### 4. Save Results

All results auto-saved to `results/phoenix_evals/*.csv` with timestamps.

### 5. Iterate on Failures

Filter Phoenix UI by low scores → identify patterns → improve prompts/logic.

---

## Example Workflow

```bash
# 1. Verify Phoenix is running
curl http://localhost:6006/health

# 2. Run melodic memory A/B test
python tests/phoenix_evaluator.py --experiment melodic_memory_ab

# 3. View results in Phoenix UI
open http://localhost:6006

# 4. Click on "melodic_memory_treatment" project
# 5. Compare QA Correctness scores
# 6. Drill into low-scoring instances
# 7. Identify improvement opportunities

# 8. Run collective brain test
python tests/phoenix_evaluator.py --experiment collective_brain_ab

# 9. Compare collective_brain_treatment vs control

# 10. Run SWE-bench on 10 instances
python tests/phoenix_evaluator.py --experiment swe_bench --num_instances 10

# 11. Check code execution pass rate
# 12. Export CSV for further analysis
```

---

## What to Look For

### ✅ Good Signs

- **High QA Correctness** (>80%): Agents answering correctly
- **Low Hallucination** (<20%): Grounded in actual context
- **High Relevance** (>85%): Staying on topic
- **Code Pass Rate** (>70%): Generated code actually works

### ⚠️ Warning Signs

- **Low QA Correctness** (<60%): Agents not understanding questions
- **High Hallucination** (>40%): Making up information
- **Low Relevance** (<70%): Going off-topic
- **Code Failures** (>40%): Generated code doesn't execute

---

## Next Steps

After running evaluations:

1. **Identify Patterns**: What types of questions fail most?
2. **Improve Prompts**: Update agent system prompts based on failures
3. **Tune Hyperparameters**: Adjust temperature, candidate count, etc.
4. **Add Training Data**: Feed successful examples back to improve
5. **Compare Configurations**: Test different MAKER modes (High vs Low)

---

## Resources

- **Phoenix Docs**: https://docs.arize.com/phoenix
- **Phoenix Evals**: https://docs.arize.com/phoenix/evaluation/llm-as-a-judge
- **SWE-bench**: https://www.swebench.com/
- **Playwright**: https://playwright.dev/python/

---

## Summary

Phoenix Evaluations gives you **data-driven insights** into:
- Does melodic line memory improve coherence? → Run A/B test
- Does collective brain give better answers? → Run A/B test
- Can MAKER fix real GitHub issues? → Run SWE-bench eval
- Where are agents failing? → Drill into Phoenix UI

**Key insight**: You now have quantitative metrics (not just vibes) to validate that your multi-agent architecture actually works better than single-agent baselines.
