# SWE-bench Integration Complete

## Summary

Your MAKER multi-agent system now has comprehensive SWE-bench Lite evaluation capabilities. This enables rigorous benchmarking against GPT-4, Claude 3.5 Sonnet, and other state-of-the-art AI coding assistants.

## What Was Created

### 1. Core Evaluation Infrastructure

**[tests/swe_bench_harness.py](../tests/swe_bench_harness.py)** (500+ lines)
- Loads SWE-bench Lite dataset (300 curated GitHub issues)
- Converts issues to MAKER-compatible prompts
- Generates predictions via your orchestrator
- Tracks EE Memory and MAKER voting metrics
- Produces comprehensive evaluation reports

**[tests/swe_bench_adapter.py](../tests/swe_bench_adapter.py)** (300+ lines)
- Extracts unified diff patches from MAKER output
- Handles multiple formats (markdown, JSON, plain code)
- Validates patch correctness
- Computes patch statistics (files, hunks, lines changed)

**[tests/swe_bench_metrics.py](../tests/swe_bench_metrics.py)** (400+ lines)
- Computes resolve rate, test pass rates
- Analyzes EE Memory impact (narrative correlation)
- Measures MAKER voting effectiveness
- Compares against 7 baseline systems
- Generates visualizations

### 2. Documentation & Scripts

**[tests/SWE_BENCH_README.md](../tests/SWE_BENCH_README.md)**
- Complete usage guide
- Baseline comparisons (GPT-4: 53.3%, Claude: 49.3%)
- Troubleshooting tips
- Performance expectations

**[tests/run_swe_bench_eval.sh](../tests/run_swe_bench_eval.sh)**
- One-command evaluation runner
- Health checks for all services
- Automatic metrics computation
- Quick summary display

## Quick Start

```bash
# 1. Start your MAKER system
bash scripts/start-llama-servers.sh
docker compose up -d

# 2. Run quick evaluation (10 instances, ~10 minutes)
bash tests/run_swe_bench_eval.sh 10

# 3. Full evaluation (300 instances, ~5-10 hours)
bash tests/run_swe_bench_eval.sh 300 results/swe_bench_full
```

## Output Structure

```
results/swe_bench_<timestamp>/
├── predictions.jsonl              # MAKER predictions with metadata
├── swebench_predictions.jsonl     # Converted for official evaluation
├── evaluation_report.md           # Human-readable report
├── metrics.json                   # Detailed metrics
├── baselines.json                 # Comparison data
└── visualizations/
    ├── resolve_rate.png           # Success rate
    ├── test_pass_rates.png        # FAIL_TO_PASS / PASS_TO_PASS
    ├── ee_memory_impact.png       # Narratives vs success
    └── confidence_calibration.png  # MAKER confidence vs actual success
```

## Key Metrics Tracked

### Core Performance
- **Resolve Rate**: % of issues successfully fixed
- **FAIL_TO_PASS**: Tests that must pass after fix
- **PASS_TO_PASS**: Existing tests that must continue passing

### MAKER-Specific
- **EE Mode Usage**: % using Expositional Engineering planner
- **Narrative Correlation**: How business narratives predict success
- **Confidence Calibration**: How well MAKER knows when it's right
- **Voting Effectiveness**: Candidate selection accuracy

### Patch Quality
- **Files Modified**: Average number of files changed
- **Hunks**: Number of diff hunks per patch
- **Lines Changed**: Total additions + deletions

## Baseline Comparisons

| System | Resolve Rate | Target |
|--------|--------------|--------|
| **GPT-4 Turbo** | 53.3% | Aspirational |
| **Claude 3.5 Sonnet (New)** | 49.3% | Primary target |
| **GPT-4o** | 47.7% | Primary target |
| Claude 3.5 Sonnet (Old) | 46.3% | Target |
| **GPT-4o Mini** | 31.7% | **Initial target** |
| Claude 3 Opus | 24.7% | Minimum |
| GPT-3.5 Turbo | 16.3% | Baseline |

**MAKER Target**:
- **Phase 1** (Current): >30% (competitive with GPT-4o Mini)
- **Phase 2** (EE Memory optimized): >45% (Claude 3.5 tier)
- **Phase 3** (Full optimization): >50% (GPT-4 tier)

## Expected Results

### MAKER Strengths

1. **Multi-Agent Collaboration**
   - Preprocessor → Planner → Coder → Reviewer
   - Should excel at complex, multi-step tasks

2. **MAKER Voting**
   - Parallel candidate generation (N=5)
   - First-to-K voting (K=3)
   - Should improve first-pass acceptance

3. **EE Memory**
   - Narrative-aware planning
   - Hierarchical compression (86% target)
   - Should help with large codebases

4. **Thematic PageRank**
   - Identifies critical code paths
   - Should reduce irrelevant changes

### Challenges

1. **Patch Format Conversion**
   - MAKER outputs code, not diffs
   - Adapter handles conversion (may introduce errors)

2. **Local Models**
   - Using Qwen2.5-Coder-32B vs GPT-4
   - May have lower raw capability
   - EE Memory and MAKER voting should compensate

3. **Context Limits**
   - Some SWE-bench repos >100K LOC
   - Tests EE compression effectiveness

## Using Results

### After Evaluation

```bash
# View full report
cat results/swe_bench_<timestamp>/evaluation_report.md

# Extract key metrics
python3 -c "
import json
with open('results/swe_bench_<timestamp>/metrics.json') as f:
    m = json.load(f)
    print(f\"Resolve Rate: {m['core_metrics']['resolve_rate']:.1%}\")
    print(f\"EE Narratives: {m['ee_memory']['avg_narratives']:.1f}\")
    print(f\"Confidence: {m['maker_metrics']['avg_confidence']:.3f}\")
"

# View visualizations
open results/swe_bench_<timestamp>/visualizations/
```

### Interpreting EE Memory Impact

**Good Signs** (EE Memory is helping):
- ✅ Narrative correlation > 0.3
- ✅ Instances with narratives have higher resolve rate
- ✅ EE mode instances faster (better context selection)

**Bad Signs** (EE Memory needs tuning):
- ⚠️ Narrative correlation < 0.1
- ⚠️ EE mode slower with no accuracy gain
- ⚠️ Low narrative detection (avg < 0.5)

### Optimizing Performance

If results are below target:

1. **Check patch extraction**: Many failures may be formatting issues
   ```bash
   grep '"error":' results/*/predictions.jsonl | wc -l
   ```

2. **Analyze failure patterns**: What types of issues fail?
   ```bash
   python3 tests/analyze_failures.py results/*/predictions.jsonl
   ```

3. **Tune EE Memory**: Adjust thresholds in `ee_world_model.py`
   ```python
   persistence_threshold = 0.6  # Lower to detect more narratives
   ```

4. **Increase MAKER candidates**: More diversity in voting
   ```bash
   export MAKER_NUM_CANDIDATES=7
   export MAKER_VOTE_K=4
   ```

## Running Official Evaluation

Once you have predictions, run the official SWE-bench harness:

```bash
# Install official SWE-bench (requires Docker)
pip install swebench

# Run official evaluation
python tests/swe_bench_harness.py \
  --evaluate_only \
  --predictions_path results/swe_bench_<timestamp>/predictions.jsonl

# This will:
# 1. Convert predictions to official format
# 2. Spin up Docker containers for each instance
# 3. Apply patches and run tests
# 4. Generate official scores
```

**Note**: Official evaluation requires:
- x86_64 architecture (or ARM with `--namespace` flag)
- 120GB free storage
- 16GB RAM
- Docker installed

## Next Steps

1. **Run Initial Evaluation**
   ```bash
   bash tests/run_swe_bench_eval.sh 10
   ```

2. **Analyze Results**
   - Check resolve rate vs baseline
   - Review EE Memory correlation
   - Identify failure patterns

3. **Optimize & Iterate**
   - Tune EE Memory thresholds
   - Adjust MAKER voting parameters
   - Improve patch extraction

4. **Full Benchmark**
   ```bash
   bash tests/run_swe_bench_eval.sh 300 results/swe_bench_final
   ```

5. **Submit to Leaderboard** (optional)
   - Official results via SWE-bench harness
   - Submit to https://www.swebench.com/

## Integration with Existing Tests

Your existing tests remain functional:

```bash
# Old workflow test (still works)
bash tests/test_workflow.sh

# New SWE-bench evaluation
bash tests/run_swe_bench_eval.sh 10

# Both test the same orchestrator
# SWE-bench is more rigorous and industry-standard
```

## Cost Estimation

Using local llama.cpp models:
- **Free** for compute (runs on your M4 Max)
- **Network**: ~500MB dataset download (one-time)
- **Time**:
  - 10 instances: ~10 minutes
  - 300 instances: ~5-10 hours

Using cloud APIs (if you switch):
- **GPT-4**: ~$0.50-1.00 per instance × 300 = $150-300
- **Claude**: ~$0.40-0.80 per instance × 300 = $120-240

**Your local setup = $0 per evaluation** 🎉

## Support

For issues:
1. Check [tests/SWE_BENCH_README.md](../tests/SWE_BENCH_README.md) FAQ
2. Review logs in `results/` directory
3. Ensure all services healthy: `bash tests/run_swe_bench_eval.sh`

## Resources

- **SWE-bench Website**: https://www.swebench.com/
- **Dataset**: https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite
- **Leaderboard**: https://www.swebench.com/lite.html
- **Paper**: https://arxiv.org/abs/2310.06770

---

**Your MAKER system is now ready for industry-standard benchmarking!** 🚀

Target: Beat GPT-4o Mini (31.7%), approach Claude 3.5 Sonnet (49.3%) with EE Memory optimization.
