#!/usr/bin/env python3
"""
SWE-bench Evaluation Harness for MAKER Multi-Agent System

Evaluates the MAKER system on SWE-bench Lite (300 curated GitHub issues).
Measures patch correctness, test pass rates, and compares against baselines.

Usage:
    python tests/swe_bench_harness.py --num_instances 10 --output_dir results/swe_bench
    python tests/swe_bench_harness.py --evaluate_only --predictions_path results/swe_bench/predictions.jsonl
"""

import os
import sys
import json
import asyncio
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from datasets import load_dataset
import httpx


@dataclass
class SWEBenchInstance:
    """SWE-bench task instance"""
    instance_id: str
    repo: str
    base_commit: str
    problem_statement: str
    hints_text: str
    test_patch: str
    patch: str  # Gold patch
    FAIL_TO_PASS: List[str]
    PASS_TO_PASS: List[str]
    created_at: str = ""
    version: str = ""

    @classmethod
    def from_dict(cls, data: Dict) -> 'SWEBenchInstance':
        """Load from HuggingFace dataset dict"""
        return cls(
            instance_id=data['instance_id'],
            repo=data['repo'],
            base_commit=data['base_commit'],
            problem_statement=data['problem_statement'],
            hints_text=data.get('hints_text', ''),
            test_patch=data.get('test_patch', ''),
            patch=data['patch'],
            FAIL_TO_PASS=json.loads(data.get('FAIL_TO_PASS', '[]')),
            PASS_TO_PASS=json.loads(data.get('PASS_TO_PASS', '[]')),
            created_at=data.get('created_at', ''),
            version=data.get('version', '')
        )


@dataclass
class MAKERPrediction:
    """MAKER system prediction for SWE-bench"""
    instance_id: str
    model_name_or_path: str
    model_patch: str  # Generated patch in unified diff format
    ee_mode: bool
    narrative_count: int
    average_confidence: float
    maker_candidates: int
    maker_votes: Dict[int, int]  # candidate_id -> vote_count
    execution_time_seconds: float
    error: Optional[str] = None


@dataclass
class EvaluationResult:
    """Evaluation result for one instance"""
    instance_id: str
    resolved: bool  # Did patch fix the issue?
    fail_to_pass: Dict[str, bool]  # Test outcomes
    pass_to_pass: Dict[str, bool]
    patch_applied: bool
    error_message: Optional[str] = None


class SWEBenchHarness:
    """Harness for evaluating MAKER on SWE-bench Lite"""

    def __init__(
        self,
        orchestrator_url: str = "http://localhost:8080",
        output_dir: Path = Path("results/swe_bench"),
        ee_mode: bool = True
    ):
        self.orchestrator_url = orchestrator_url
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.ee_mode = ee_mode

        # SWE-bench dataset
        self.dataset = None

    def load_dataset(self, split: str = "test", num_instances: Optional[int] = None):
        """Load SWE-bench Lite dataset"""
        print(f"📦 Loading SWE-bench Lite dataset ({split} split)...")
        self.dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split=split)

        if num_instances:
            self.dataset = self.dataset.select(range(min(num_instances, len(self.dataset))))

        print(f"✅ Loaded {len(self.dataset)} instances")
        return self.dataset

    async def generate_prediction(self, instance: SWEBenchInstance) -> MAKERPrediction:
        """
        Generate patch prediction using MAKER orchestrator
        Converts GitHub issue -> MAKER workflow -> unified diff patch
        """
        start_time = datetime.now()

        # Construct MAKER-compatible prompt
        task_prompt = self._convert_to_maker_prompt(instance)

        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                response = await client.post(
                    f"{self.orchestrator_url}/api/workflow",
                    json={
                        "input": task_prompt,
                        "stream": False
                    }
                )

                if response.status_code != 200:
                    raise Exception(f"HTTP {response.status_code}: {response.text}")

                result = response.json()

                # Extract patch from MAKER output
                model_patch = self._extract_patch_from_maker_output(result)

                execution_time = (datetime.now() - start_time).total_seconds()

                return MAKERPrediction(
                    instance_id=instance.instance_id,
                    model_name_or_path="maker-multi-agent",
                    model_patch=model_patch,
                    ee_mode=result.get('ee_mode', self.ee_mode),
                    narrative_count=result.get('narrative_count', 0),
                    average_confidence=result.get('average_confidence', 0.0),
                    maker_candidates=result.get('maker_candidates', 5),
                    maker_votes=result.get('maker_votes', {}),
                    execution_time_seconds=execution_time
                )

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            return MAKERPrediction(
                instance_id=instance.instance_id,
                model_name_or_path="maker-multi-agent",
                model_patch="",
                ee_mode=self.ee_mode,
                narrative_count=0,
                average_confidence=0.0,
                maker_candidates=0,
                maker_votes={},
                execution_time_seconds=execution_time,
                error=str(e)
            )

    def _convert_to_maker_prompt(self, instance: SWEBenchInstance) -> str:
        """Convert SWE-bench instance to MAKER-compatible prompt"""
        prompt = f"""Repository: {instance.repo}
Base Commit: {instance.base_commit}

Issue Description:
{instance.problem_statement}
"""

        if instance.hints_text:
            prompt += f"""

Hints from Discussion:
{instance.hints_text}
"""

        prompt += """

Task: Generate a unified diff patch that fixes this issue. The patch must:
1. Resolve the reported bug/issue
2. Pass all existing tests (PASS_TO_PASS)
3. Pass new tests that previously failed (FAIL_TO_PASS)

Output the patch in unified diff format (diff --git a/... b/...).
"""

        return prompt

    def _extract_patch_from_maker_output(self, maker_result: Dict) -> str:
        """
        Extract unified diff patch from MAKER output
        MAKER may return code blocks, file changes, or direct diff output
        """
        # Try to find unified diff in output
        output_text = maker_result.get('output', '')

        # Look for diff blocks
        if 'diff --git' in output_text:
            # Extract diff content
            lines = output_text.split('\n')
            diff_lines = []
            in_diff = False

            for line in lines:
                if line.startswith('diff --git'):
                    in_diff = True
                if in_diff:
                    diff_lines.append(line)

            return '\n'.join(diff_lines)

        # Fallback: convert file changes to diff format
        # This would require parsing MAKER's file modification output
        # For now, return empty if no diff found
        return ""

    async def run_predictions(self, instances: List[SWEBenchInstance]) -> List[MAKERPrediction]:
        """Generate predictions for all instances"""
        predictions = []

        for i, instance in enumerate(instances, 1):
            print(f"\n{'='*80}")
            print(f"[{i}/{len(instances)}] Processing: {instance.instance_id}")
            print(f"Repo: {instance.repo}")
            print(f"{'='*80}")

            prediction = await self.generate_prediction(instance)
            predictions.append(prediction)

            # Save incrementally
            self._save_predictions(predictions)

            if prediction.error:
                print(f"❌ Error: {prediction.error}")
            else:
                print(f"✅ Generated patch ({len(prediction.model_patch)} chars)")
                print(f"   EE Mode: {prediction.ee_mode}, Narratives: {prediction.narrative_count}")
                print(f"   Confidence: {prediction.average_confidence:.2f}, Time: {prediction.execution_time_seconds:.1f}s")

        return predictions

    def _save_predictions(self, predictions: List[MAKERPrediction]):
        """Save predictions in SWE-bench format"""
        predictions_file = self.output_dir / "predictions.jsonl"

        with open(predictions_file, 'w') as f:
            for pred in predictions:
                f.write(json.dumps(asdict(pred)) + '\n')

        print(f"💾 Saved {len(predictions)} predictions to {predictions_file}")

    def evaluate_predictions(self, predictions_path: Path) -> Dict:
        """
        Evaluate predictions using official SWE-bench harness
        Requires: pip install swebench
        """
        print(f"\n{'='*80}")
        print("🔍 Running SWE-bench Official Evaluation")
        print(f"{'='*80}\n")

        # Convert MAKER predictions to SWE-bench format
        swebench_predictions = self._convert_to_swebench_format(predictions_path)
        swebench_file = self.output_dir / "swebench_predictions.jsonl"

        with open(swebench_file, 'w') as f:
            for pred in swebench_predictions:
                f.write(json.dumps(pred) + '\n')

        print(f"📝 Converted predictions to SWE-bench format: {swebench_file}")

        # Run official evaluation
        try:
            cmd = [
                "python", "-m", "swebench.harness.run_evaluation",
                "--dataset_name", "princeton-nlp/SWE-bench_Lite",
                "--predictions_path", str(swebench_file),
                "--max_workers", "4",
                "--run_id", f"maker_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            ]

            print(f"Running: {' '.join(cmd)}\n")
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                print("✅ Evaluation completed successfully")
                print(result.stdout)
                return {"success": True, "output": result.stdout}
            else:
                print(f"❌ Evaluation failed with code {result.returncode}")
                print(result.stderr)
                return {"success": False, "error": result.stderr}

        except FileNotFoundError:
            print("⚠️  SWE-bench package not installed")
            print("Install with: pip install swebench")
            return {"success": False, "error": "swebench not installed"}

    def _convert_to_swebench_format(self, predictions_path: Path) -> List[Dict]:
        """Convert MAKER predictions to SWE-bench evaluation format"""
        swebench_preds = []

        with open(predictions_path, 'r') as f:
            for line in f:
                pred = json.loads(line)
                swebench_preds.append({
                    "instance_id": pred['instance_id'],
                    "model_name_or_path": pred['model_name_or_path'],
                    "model_patch": pred['model_patch']
                })

        return swebench_preds

    def generate_report(self, predictions: List[MAKERPrediction], eval_results: Optional[Dict] = None):
        """Generate evaluation report"""
        report_path = self.output_dir / "evaluation_report.md"

        total = len(predictions)
        successful = sum(1 for p in predictions if not p.error)
        failed = sum(1 for p in predictions if p.error)

        avg_confidence = sum(p.average_confidence for p in predictions) / total if total > 0 else 0
        avg_time = sum(p.execution_time_seconds for p in predictions) / total if total > 0 else 0
        avg_narratives = sum(p.narrative_count for p in predictions) / total if total > 0 else 0

        report = f"""# SWE-bench Lite Evaluation Report - MAKER Multi-Agent System

**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**System**: MAKER (EE Mode: {self.ee_mode})
**Dataset**: SWE-bench Lite

## Summary

| Metric | Value |
|--------|-------|
| Total Instances | {total} |
| Successful Predictions | {successful} ({successful/total*100:.1f}%) |
| Failed Predictions | {failed} ({failed/total*100:.1f}%) |
| Average Confidence | {avg_confidence:.3f} |
| Average Execution Time | {avg_time:.1f}s |
| Average Narratives Detected | {avg_narratives:.1f} |

## EE Memory Statistics

| Metric | Value |
|--------|-------|
| EE Mode Enabled | {sum(1 for p in predictions if p.ee_mode)} instances |
| Instances with Narratives | {sum(1 for p in predictions if p.narrative_count > 0)} |
| Max Narratives | {max((p.narrative_count for p in predictions), default=0)} |

## MAKER Voting Statistics

| Metric | Value |
|--------|-------|
| Average Candidates | {sum(p.maker_candidates for p in predictions) / total if total > 0 else 0:.1f} |
| Total Votes Cast | {sum(sum(v.values()) for p in predictions for v in [p.maker_votes] if v)} |

## Performance Distribution

### Execution Time
- Min: {min((p.execution_time_seconds for p in predictions), default=0):.1f}s
- Max: {max((p.execution_time_seconds for p in predictions), default=0):.1f}s
- Median: {sorted([p.execution_time_seconds for p in predictions])[len(predictions)//2] if predictions else 0:.1f}s

### Confidence Score
- Min: {min((p.average_confidence for p in predictions), default=0):.3f}
- Max: {max((p.average_confidence for p in predictions), default=0):.3f}
- Median: {sorted([p.average_confidence for p in predictions])[len(predictions)//2] if predictions else 0:.3f}

## Official SWE-bench Results

"""

        if eval_results and eval_results.get('success'):
            report += eval_results['output']
        else:
            report += "⚠️ Official evaluation not run. Use --evaluate flag to run SWE-bench harness.\n"

        report += f"""

## Configuration

- Orchestrator URL: {self.orchestrator_url}
- Output Directory: {self.output_dir}
- EE Mode: {self.ee_mode}

## Predictions

Detailed predictions saved to: `{self.output_dir}/predictions.jsonl`

---
Generated by MAKER SWE-bench Harness
"""

        with open(report_path, 'w') as f:
            f.write(report)

        print(f"\n📊 Report saved to: {report_path}")
        return report


async def main():
    parser = argparse.ArgumentParser(description="SWE-bench Evaluation Harness for MAKER")
    parser.add_argument("--num_instances", type=int, default=10, help="Number of instances to evaluate")
    parser.add_argument("--orchestrator_url", default="http://localhost:8080", help="MAKER orchestrator URL")
    parser.add_argument("--output_dir", default="results/swe_bench", help="Output directory")
    parser.add_argument("--ee_mode", action="store_true", default=True, help="Enable EE mode")
    parser.add_argument("--evaluate_only", action="store_true", help="Only run evaluation on existing predictions")
    parser.add_argument("--predictions_path", help="Path to predictions file for evaluation")

    args = parser.parse_args()

    harness = SWEBenchHarness(
        orchestrator_url=args.orchestrator_url,
        output_dir=Path(args.output_dir),
        ee_mode=args.ee_mode
    )

    if args.evaluate_only:
        if not args.predictions_path:
            print("❌ --predictions_path required for --evaluate_only")
            return

        eval_results = harness.evaluate_predictions(Path(args.predictions_path))
        harness.generate_report([], eval_results)
        return

    # Load dataset
    dataset = harness.load_dataset(num_instances=args.num_instances)
    instances = [SWEBenchInstance.from_dict(item) for item in dataset]

    # Generate predictions
    print(f"\n🚀 Starting MAKER prediction generation for {len(instances)} instances...")
    predictions = await harness.run_predictions(instances)

    # Optionally run evaluation
    eval_results = None
    if input("\nRun official SWE-bench evaluation? (requires swebench package) [y/N]: ").lower() == 'y':
        eval_results = harness.evaluate_predictions(harness.output_dir / "predictions.jsonl")

    # Generate report
    harness.generate_report(predictions, eval_results)

    print(f"\n✅ Evaluation complete! Results in: {args.output_dir}")


if __name__ == "__main__":
    asyncio.run(main())
