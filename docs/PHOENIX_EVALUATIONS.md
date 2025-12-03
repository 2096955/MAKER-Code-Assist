# Phoenix Evaluations: A/B Testing & Validation

## Overview

The Phoenix Evaluations framework provides quantitative, data-driven validation of MAKER system improvements through A/B testing and automated evaluation.

## Features

### 1. Melodic Memory A/B Testing

**Purpose**: Validate that melodic line memory improves coherent reasoning across agents.

**Experiment**: `melodic_memory_ab`

**What It Tests**:
- **Control**: Agents WITHOUT melodic line memory (standard workflow)
- **Treatment**: Agents WITH melodic line memory (Kùzu graph database)

**Metrics Measured**:
- **QA Correctness**: Answer accuracy vs reference answers
- **Hallucination Reduction**: Unsupported claims detected
- **Relevance Improvement**: Response on-topic percentage

**Usage**:
```bash
python tests/phoenix_evaluator.py --experiment melodic_memory_ab
```

**Expected Results**:
- Treatment group should show higher QA correctness
- Lower hallucination rate
- Better relevance scores

### 2. Collective Brain A/B Testing

**Purpose**: Validate that multi-agent consensus provides better answers than single-agent responses.

**Experiment**: `collective_brain_ab`

**What It Tests**:
- **Control**: Single-agent answers (Preprocessor only)
- **Treatment**: Multi-agent consensus (Planner + Coder + Reviewer)

**Metrics Measured**:
- **Answer Quality**: Comprehensive vs surface-level answers
- **Coverage of Trade-offs**: Multiple perspectives considered
- **Consensus Confidence**: Agreement between agents

**Usage**:
```bash
python tests/phoenix_evaluator.py --experiment collective_brain_ab
```

**Expected Results**:
- Treatment group should show higher answer quality
- Better coverage of trade-offs and edge cases
- Higher consensus confidence scores

### 3. SWE-bench Evaluation

**Purpose**: Test code generation on real GitHub issues with execution validation.

**Experiment**: `swe_bench`

**What It Tests**:
- Code generation for real GitHub issues
- Generated code execution with Playwright
- Test assertion validation

**Metrics Measured**:
- **Patch Correctness**: Generated code matches expected solution
- **Test Pass Rate**: Generated code passes test suite
- **Execution Errors**: Syntax errors, runtime errors, logic bugs

**Usage**:
```bash
# Run on 10 instances
python tests/phoenix_evaluator.py --experiment swe_bench --num_instances 10

# Run on all instances
python tests/phoenix_evaluator.py --experiment swe_bench
```

**Expected Results**:
- High patch correctness rate
- Test pass rate > 50% (baseline for SWE-bench)
- Low execution error rate

## LLM-as-Judge Evaluators

### HallucinationEvaluator

**Purpose**: Detects unsupported claims in agent responses.

**How It Works**:
- Uses LLM to check if claims are supported by context
- Flags assertions without evidence
- Measures hallucination rate

**Example**:
```python
evaluator = HallucinationEvaluator()
result = evaluator.evaluate(
    response="The system uses Redis for caching",
    context="Codebase uses Redis for session storage"
)
# Result: Hallucination detected (context says session, not caching)
```

### QAEvaluator

**Purpose**: Measures answer correctness vs reference answers.

**How It Works**:
- Compares agent response to ground truth
- Uses LLM to assess correctness
- Measures QA accuracy percentage

**Example**:
```python
evaluator = QAEvaluator()
result = evaluator.evaluate(
    response="The system uses Redis",
    reference="The system uses Redis for session storage"
)
# Result: Partially correct (missing detail about session storage)
```

### RelevanceEvaluator

**Purpose**: Checks if response is on-topic and relevant.

**How It Works**:
- Uses LLM to assess relevance to question
- Measures on-topic percentage
- Flags off-topic responses

**Example**:
```python
evaluator = RelevanceEvaluator()
result = evaluator.evaluate(
    question="How does authentication work?",
    response="The system uses JWT tokens for authentication"
)
# Result: Highly relevant
```

## Code Execution Validation

### Playwright-Based Execution

**Purpose**: Safely execute generated code and validate test assertions.

**How It Works**:
1. Generate code from agent response
2. Run test assertions in isolated subprocess
3. Catch syntax errors, runtime errors, logic bugs
4. Report execution results

**Safety Features**:
- Isolated subprocess execution
- Timeout protection
- Error capture and reporting

**Example**:
```python
# Generated code
code = """
def test_authentication():
    assert authenticate("user", "pass") == True
"""

# Execute with Playwright
result = execute_code(code)
# Result: Test passed / Test failed / Syntax error / Runtime error
```

## Visual Analysis

### Phoenix UI Dashboard

**Access**: http://localhost:6006

**Features**:
- Side-by-side control vs treatment comparison
- Drill into failures to identify patterns
- Filter by experiment, metric, date
- Export results to CSV

**Navigation**:
1. Open http://localhost:6006 in browser
2. Click on experiment projects (e.g., "melodic_memory_ab")
3. Compare metrics between control and treatment
4. Click on individual traces to see details

### Metrics Visualization

**Available Metrics**:
- QA Correctness: Percentage of correct answers
- Hallucination Rate: Percentage of unsupported claims
- Relevance Score: On-topic percentage
- Consensus Confidence: Agent agreement level
- Test Pass Rate: SWE-bench test success rate

**Charts**:
- Bar charts: Control vs Treatment comparison
- Line charts: Metrics over time
- Scatter plots: Correlation analysis

## Data Export

### CSV Export

**Location**: `results/phoenix_evals/*.csv`

**Format**: Timestamped files for tracking experiments over time

**Columns**:
- `experiment`: Experiment name
- `run_id`: Unique run identifier
- `timestamp`: When experiment ran
- `metric`: Metric name (qa_correctness, hallucination_rate, etc.)
- `control_value`: Control group value
- `treatment_value`: Treatment group value
- `improvement`: Percentage improvement

**Example**:
```csv
experiment,run_id,timestamp,metric,control_value,treatment_value,improvement
melodic_memory_ab,run_001,2025-01-15T10:00:00,qa_correctness,0.65,0.78,20.0
melodic_memory_ab,run_001,2025-01-15T10:00:00,hallucination_rate,0.15,0.08,-46.7
```

## Setup

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium
```

### Verify Phoenix is Running

```bash
# Check Phoenix health
curl http://localhost:6006/health

# Or start Phoenix if not running
docker compose up -d phoenix
```

## Running Evaluations

### Basic Usage

```bash
# Run melodic memory A/B test
python tests/phoenix_evaluator.py --experiment melodic_memory_ab

# Run collective brain A/B test
python tests/phoenix_evaluator.py --experiment collective_brain_ab

# Run SWE-bench evaluation (10 instances)
python tests/phoenix_evaluator.py --experiment swe_bench --num_instances 10
```

### Advanced Options

```bash
# Custom number of instances
python tests/phoenix_evaluator.py --experiment swe_bench --num_instances 50

# Custom output directory
python tests/phoenix_evaluator.py --experiment melodic_memory_ab --output results/custom/

# Verbose logging
python tests/phoenix_evaluator.py --experiment collective_brain_ab --verbose
```

## Interpreting Results

### Melodic Memory A/B Test

**Key Metrics**:
- **QA Correctness Lift**: Should be positive (treatment > control)
- **Hallucination Reduction**: Should be negative (treatment < control)
- **Relevance Improvement**: Should be positive (treatment > control)

**Good Results**:
- QA correctness: +10-20% improvement
- Hallucination rate: -30-50% reduction
- Relevance: +5-15% improvement

### Collective Brain A/B Test

**Key Metrics**:
- **Answer Quality**: Treatment should be higher
- **Coverage of Trade-offs**: Treatment should consider more perspectives
- **Consensus Confidence**: Should be > 0.7 for good consensus

**Good Results**:
- Answer quality: +15-25% improvement
- Trade-off coverage: +20-30% improvement
- Consensus confidence: > 0.7

### SWE-bench Evaluation

**Key Metrics**:
- **Patch Correctness**: Should be > 0.5 (50% baseline)
- **Test Pass Rate**: Should be > 0.4 (40% baseline)
- **Execution Errors**: Should be < 0.1 (10% error rate)

**Good Results**:
- Patch correctness: > 0.6 (60%)
- Test pass rate: > 0.5 (50%)
- Execution errors: < 0.05 (5%)

## Troubleshooting

### Issue: Phoenix not accessible

**Solution**: Ensure Phoenix is running:
```bash
docker compose ps phoenix
docker compose up -d phoenix
```

### Issue: Playwright browser not found

**Solution**: Install Playwright browser:
```bash
playwright install chromium
```

### Issue: No results in Phoenix UI

**Solution**: Check that evaluations are sending data:
```bash
# Check Phoenix logs
docker compose logs phoenix --tail=50

# Verify traces are being sent
curl http://localhost:6006/api/traces
```

### Issue: Code execution fails

**Solution**: Check Playwright subprocess execution:
```bash
# Test Playwright directly
python -c "from playwright.sync_api import sync_playwright; sync_playwright().start()"
```

## Best Practices

1. **Run Baseline First**: Establish control group baseline before testing treatment
2. **Multiple Runs**: Run experiments multiple times for statistical significance
3. **Track Over Time**: Use timestamped CSV exports to track improvements
4. **Compare Metrics**: Look at multiple metrics, not just one
5. **Drill Into Failures**: Use Phoenix UI to identify failure patterns

## Related Documentation

- [Phoenix Observability](PHOENIX_OBSERVABILITY.md) - General observability and tracing
- [SWE-bench Integration](swe-bench-integration.md) - SWE-bench setup and usage
- [Melodic Line Memory](KUZU_MELODIC_LINE_PROPOSAL.md) - Melodic memory implementation
- [Collective Brain](COLLECTIVE_BRAIN.md) - Multi-agent consensus system

## Example Workflow

```bash
# 1. Start Phoenix
docker compose up -d phoenix

# 2. Run baseline (control)
python tests/phoenix_evaluator.py --experiment melodic_memory_ab --group control

# 3. Run treatment
python tests/phoenix_evaluator.py --experiment melodic_memory_ab --group treatment

# 4. View results in Phoenix UI
open http://localhost:6006

# 5. Export results
python tests/phoenix_evaluator.py --export results/phoenix_evals/melodic_memory_ab.csv
```

## Summary

The Phoenix Evaluations framework provides:

✅ **Quantitative Validation**: Data-driven metrics, not just intuition  
✅ **A/B Testing**: Control vs treatment comparison  
✅ **Code Execution**: Real test validation with Playwright  
✅ **Visual Analysis**: Phoenix UI for interactive exploration  
✅ **Data Export**: CSV files for tracking over time  

This gives you confidence that melodic line memory and collective brain actually improve agent performance!
