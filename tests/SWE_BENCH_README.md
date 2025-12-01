# SWE-bench Evaluation for MAKER Multi-Agent System

This directory contains the complete SWE-bench evaluation harness for the MAKER (Multi-Agent Knowledge-Enhanced Reasoning) system, enabling rigorous benchmarking against state-of-the-art AI coding assistants.

## Overview

**SWE-bench** is the industry-standard benchmark for evaluating AI systems on real-world software engineering tasks. It tests systems' ability to:
- Understand complex GitHub issues
- Navigate large codebases
- Generate correct patches
- Pass comprehensive test suites

**SWE-bench Lite** is a curated subset of 300 tasks from 11 popular Python repositories, designed for faster, cost-effective evaluation.

## Components

### 1. [swe_bench_harness.py](swe_bench_harness.py)
Main evaluation harness that:
- Loads SWE-bench Lite dataset from HuggingFace
- Converts GitHub issues to MAKER-compatible prompts
- Generates predictions using your MAKER orchestrator
- Runs official SWE-bench evaluation
- Produces comprehensive reports

### 2. [swe_bench_adapter.py](swe_bench_adapter.py)
Patch conversion utilities:
- Extracts unified diffs from MAKER output
- Handles multiple output formats (markdown, JSON, plain code)
- Validates patch format
- Computes patch statistics

### 3. [swe_bench_metrics.py](swe_bench_metrics.py)
Advanced metrics and analysis:
- Resolve rate, test pass rates
- EE Memory impact analysis
- MAKER voting effectiveness
- Baseline comparisons (GPT-4, Claude, etc.)
- Visualization generation

## Quick Start

### Prerequisites

```bash
# Install dependencies
pip install datasets httpx matplotlib numpy

# Optional: Install official SWE-bench harness for full evaluation
pip install swebench
```

### Basic Usage

```bash
# 1. Start your MAKER services
bash scripts/start-llama-servers.sh
docker compose up -d

# 2. Run evaluation on 10 instances (quick test)
python tests/swe_bench_harness.py --num_instances 10 --output_dir results/swe_bench_test

# 3. Run on full SWE-bench Lite (300 instances, ~5-10 hours)
python tests/swe_bench_harness.py --num_instances 300 --output_dir results/swe_bench_full

# 4. Evaluate existing predictions
python tests/swe_bench_harness.py --evaluate_only --predictions_path results/swe_bench_test/predictions.jsonl
```

### Advanced Options

```bash
# Use custom orchestrator URL
python tests/swe_bench_harness.py \
  --orchestrator_url http://custom-host:8080 \
  --num_instances 50 \
  --output_dir results/custom_run

# Disable EE mode (test baseline)
python tests/swe_bench_harness.py \
  --num_instances 50 \
  --output_dir results/baseline_no_ee \
  --ee_mode false

# Compute metrics only
python tests/swe_bench_metrics.py results/swe_bench_test/predictions.jsonl
```

## Output

Each run produces:

```
results/swe_bench_test/
├── predictions.jsonl              # MAKER predictions (incremental)
├── swebench_predictions.jsonl     # Converted to SWE-bench format
├── evaluation_report.md           # Comprehensive report
├── metrics.json                   # Detailed metrics
├── baselines.json                 # Baseline comparison data
└── visualizations/
    ├── resolve_rate.png
    ├── test_pass_rates.png
    ├── ee_memory_impact.png
    └── confidence_calibration.png
```

## Understanding Results

### Core Metrics

- **Resolve Rate**: Percentage of issues successfully fixed (higher is better)
- **FAIL_TO_PASS**: Tests that must pass after fix (regression tests)
- **PASS_TO_PASS**: Existing tests that must continue passing (no regressions)

### MAKER-Specific Metrics

- **EE Mode Usage**: % of instances using Expositional Engineering planner
- **Narrative Count**: Business narratives detected by EE Memory
- **Narrative Correlation**: How narratives correlate with success
- **Confidence Calibration**: How well MAKER's confidence predicts success
- **MAKER Candidates**: Number of parallel candidates generated
- **Voting Agreement**: How voter choices align with success

### Baselines (SWE-bench Lite Leaderboard)

| System | Resolve Rate | Date |
|--------|--------------|------|
| **GPT-4 Turbo** | 53.3% | Apr 2024 |
| **Claude 3.5 Sonnet (New)** | 49.3% | Oct 2024 |
| **GPT-4o (New)** | 47.7% | Nov 2024 |
| Claude 3.5 Sonnet | 46.3% | Jun 2024 |
| GPT-4o Mini | 31.7% | Jul 2024 |
| Claude 3 Opus | 24.7% | Feb 2024 |
| GPT-3.5 Turbo | 16.3% | Jan 2024 |

**Target**: MAKER should aim for >30% (competitive with GPT-4o Mini) initially, >45% (Claude 3.5 tier) with EE Memory optimization.

## Expected Performance

### MAKER Strengths

1. **Multi-Agent Collaboration**: Preprocessor → Planner → Coder → Reviewer pipeline
2. **MAKER Voting**: Parallel candidate generation with first-to-K voting
3. **EE Memory**: Narrative-aware context compression
4. **Hierarchical Understanding**: L₀→L₁→L₂→L₃ memory network
5. **Thematic PageRank**: Identifies critical code paths

### Challenges

1. **Patch Format**: MAKER must output unified diffs (adapter handles conversion)
2. **Large Codebases**: Some repos have >100K LOC (tests EE Memory compression)
3. **Test Understanding**: Must infer correct fixes from test failures
4. **No Internet Access**: Can't look up docs/external resources

## Debugging

### Common Issues

**"No patch found in output"**
- MAKER may output code blocks instead of diffs
- Adapter tries multiple extraction strategies
- Check `predictions.jsonl` for raw output

**"Orchestrator timeout"**
- Increase timeout: `--orchestrator_timeout 1200`
- Some tasks are complex and slow

**"swebench not installed"**
- Optional for full evaluation
- Predictions still generated without it

**"EE Planner initialization failed"**
- Check MCP server is running: `curl http://localhost:9001/health`
- Verify world model indexing completed

### Viewing Logs

```bash
# MAKER orchestrator logs
docker logs orchestrator

# llama.cpp model logs
tail -f logs/llama-*.log

# Evaluation progress
tail -f results/swe_bench_test/evaluation_report.md
```

## Interpreting EE Memory Impact

The harness tracks how EE Memory affects performance:

### Positive Indicators
- ✅ Narrative correlation > 0.3: Narratives help identify correct modules
- ✅ Confidence calibration > 0.5: MAKER knows when it's right
- ✅ EE mode resolve rate > baseline: EE Memory adds value

### Negative Indicators
- ⚠️ Narrative correlation < 0.1: Narratives not predictive
- ⚠️ Confidence correlation < 0.2: Overconfident or underconfident
- ⚠️ EE mode slower with no accuracy gain: Overhead not justified

## Extending the Harness

### Add Custom Metrics

Edit `swe_bench_metrics.py`:

```python
# Add to SWEBenchMetrics dataclass
@dataclass
class SWEBenchMetrics:
    # ... existing fields ...
    custom_metric: float

# Add to compute_metrics()
def compute_metrics(self) -> SWEBenchMetrics:
    custom_value = ...  # Compute from predictions
    return SWEBenchMetrics(
        # ... existing values ...
        custom_metric=custom_value
    )
```

### Test on Custom Datasets

```python
from datasets import load_dataset

# Load your custom dataset
dataset = load_dataset("your-org/your-dataset", split="test")

# Pass to harness
harness.dataset = dataset
```

### Add New Baseline

Edit `swe_bench_metrics.py`:

```python
SWEBENCH_LITE_BASELINES["your-system"] = {"resolve_rate": 0.XXX}
```

## Citation

If you use this harness in research, please cite:

```bibtex
@inproceedings{jimenez2024swebench,
  title={SWE-bench: Can Language Models Resolve Real-World GitHub Issues?},
  author={Jimenez, Carlos E and Yang, John and Wettig, Alexander and Yao, Shunyu and Pei, Kexin and Press, Ofir and Narasimhan, Karthik},
  booktitle={ICLR},
  year={2024}
}

@article{cognizant2024maker,
  title={MAKER: Multi-Agent Knowledge-Enhanced Reasoning for Code Generation},
  author={Cognizant AI Research},
  journal={arXiv preprint arXiv:2511.09030},
  year={2024}
}
```

## Resources

- **SWE-bench Website**: https://www.swebench.com/
- **SWE-bench GitHub**: https://github.com/SWE-bench/SWE-bench
- **Dataset (HuggingFace)**: https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite
- **Leaderboard**: https://www.swebench.com/lite.html
- **MAKER Paper**: https://arxiv.org/abs/2511.09030

## Support

For issues or questions:
1. Check the FAQ in this README
2. Review logs in `results/` directory
3. Open an issue on GitHub with `predictions.jsonl` sample

---

**Good luck with your evaluation!** 🚀

Target: Beat GPT-4o Mini (31.7%) baseline, approach Claude 3.5 Sonnet (49.3%) with EE Memory.
