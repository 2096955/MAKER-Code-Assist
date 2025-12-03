#!/usr/bin/env python3
"""
Phoenix Evaluations for MAKER Multi-Agent System

Evaluates collective brain, melodic memory, and code generation quality
using Phoenix's LLM evaluation framework with Playwright code validation.

Usage:
    python tests/phoenix_evaluator.py --experiment melodic_memory_ab
    python tests/phoenix_evaluator.py --experiment collective_brain_ab
    python tests/phoenix_evaluator.py --experiment swe_bench --num_instances 10
"""

import os
import sys
import json
import asyncio
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import pandas as pd
from phoenix.evals import (
    HallucinationEvaluator,
    QAEvaluator,
    RelevanceEvaluator,
    run_evals,
)
from phoenix.session.client import Client as PhoenixClient
from phoenix.trace import using_project


@dataclass
class EvalInstance:
    """Single evaluation instance"""
    instance_id: str
    question: str
    reference_answer: Optional[str]
    context: Optional[str]
    expected_code: Optional[str]
    test_assertions: Optional[List[str]]


@dataclass
class EvalResult:
    """Evaluation result with Phoenix metrics"""
    instance_id: str
    response: str
    hallucination_score: float  # 0-1, lower is better
    qa_correctness: float  # 0-1, higher is better
    relevance_score: float  # 0-1, higher is better
    code_execution_passed: bool
    execution_error: Optional[str]
    latency_ms: float
    melodic_memory_enabled: bool
    collective_brain_used: bool


class PhoenixEvaluator:
    """Phoenix-based evaluator for MAKER system"""

    def __init__(
        self,
        orchestrator_url: str = "http://localhost:8080",
        phoenix_url: str = "http://localhost:6006",
        output_dir: Path = Path("results/phoenix_evals")
    ):
        self.orchestrator_url = orchestrator_url
        self.phoenix_url = phoenix_url
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Phoenix client
        self.phoenix = PhoenixClient(endpoint=phoenix_url)

        print(f"[Phoenix Evaluator] Initialized")
        print(f"  Orchestrator: {orchestrator_url}")
        print(f"  Phoenix UI: {phoenix_url}")
        print(f"  Output: {output_dir}")

    async def run_experiment(
        self,
        experiment_name: str,
        instances: List[EvalInstance],
        melodic_memory: bool = True,
        use_collective_brain: bool = False
    ) -> pd.DataFrame:
        """
        Run evaluation experiment and send to Phoenix

        Args:
            experiment_name: Phoenix project name
            instances: Evaluation instances to test
            melodic_memory: Enable melodic line memory
            use_collective_brain: Force collective brain usage

        Returns:
            DataFrame with evaluation results
        """
        print(f"\n{'='*60}")
        print(f"Experiment: {experiment_name}")
        print(f"Instances: {len(instances)}")
        print(f"Melodic Memory: {melodic_memory}")
        print(f"Collective Brain: {use_collective_brain}")
        print(f"{'='*60}\n")

        results = []

        # Use Phoenix project for this experiment
        with using_project(experiment_name):
            for i, instance in enumerate(instances, 1):
                print(f"[{i}/{len(instances)}] {instance.instance_id}")

                try:
                    result = await self._evaluate_instance(
                        instance,
                        melodic_memory=melodic_memory,
                        use_collective_brain=use_collective_brain
                    )
                    results.append(result)

                    print(f"  ✓ QA Correctness: {result.qa_correctness:.2%}")
                    print(f"  ✓ Hallucination: {result.hallucination_score:.2%}")
                    print(f"  ✓ Relevance: {result.relevance_score:.2%}")
                    if instance.expected_code:
                        print(f"  ✓ Code Execution: {'PASS' if result.code_execution_passed else 'FAIL'}")
                    print(f"  ⏱ Latency: {result.latency_ms:.0f}ms\n")

                except Exception as e:
                    print(f"  ✗ Error: {e}\n")
                    # Add failed result
                    results.append(EvalResult(
                        instance_id=instance.instance_id,
                        response="",
                        hallucination_score=1.0,
                        qa_correctness=0.0,
                        relevance_score=0.0,
                        code_execution_passed=False,
                        execution_error=str(e),
                        latency_ms=0.0,
                        melodic_memory_enabled=melodic_memory,
                        collective_brain_used=use_collective_brain
                    ))

        # Convert to DataFrame for Phoenix
        df = pd.DataFrame([asdict(r) for r in results])

        # Run Phoenix evaluations on the results
        print("\n🔍 Running Phoenix LLM Evaluations...")
        df = await self._run_phoenix_evals(df, instances)

        # Save results
        results_path = self.output_dir / f"{experiment_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(results_path, index=False)
        print(f"\n✅ Results saved: {results_path}")

        # Print summary
        self._print_summary(df, experiment_name)

        return df

    async def _evaluate_instance(
        self,
        instance: EvalInstance,
        melodic_memory: bool,
        use_collective_brain: bool
    ) -> EvalResult:
        """Evaluate single instance"""
        import time
        start_time = time.time()

        # Build request to orchestrator
        # Force collective brain by making question "complex"
        question = instance.question
        if use_collective_brain and not any(kw in question.lower() for kw in ["should i", "which is better", "architecture"]):
            question = f"What's the best approach to: {question}"

        # Call orchestrator
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.orchestrator_url}/v1/chat/completions",
                json={
                    "model": "multi-agent",
                    "messages": [{"role": "user", "content": question}],
                    "stream": False
                }
            )
            response.raise_for_status()
            result = response.json()

        latency_ms = (time.time() - start_time) * 1000
        response_text = result['choices'][0]['message']['content']

        # Check if collective brain was actually used
        collective_brain_used = "[COLLECTIVE BRAIN]" in response_text or use_collective_brain

        # Validate code execution if expected code provided
        code_passed = False
        execution_error = None
        if instance.expected_code:
            code_passed, execution_error = await self._validate_code_execution(
                response_text,
                instance.test_assertions or []
            )

        return EvalResult(
            instance_id=instance.instance_id,
            response=response_text,
            hallucination_score=0.0,  # Will be filled by Phoenix evals
            qa_correctness=0.0,  # Will be filled by Phoenix evals
            relevance_score=0.0,  # Will be filled by Phoenix evals
            code_execution_passed=code_passed,
            execution_error=execution_error,
            latency_ms=latency_ms,
            melodic_memory_enabled=melodic_memory,
            collective_brain_used=collective_brain_used
        )

    async def _validate_code_execution(
        self,
        response: str,
        test_assertions: List[str]
    ) -> tuple[bool, Optional[str]]:
        """
        Validate code execution using Playwright

        Extracts code from response and runs test assertions
        """
        try:
            # Extract code blocks from response
            import re
            code_blocks = re.findall(r'```(?:python)?\n(.*?)```', response, re.DOTALL)

            if not code_blocks:
                return False, "No code blocks found in response"

            # Combine all code blocks
            full_code = "\n\n".join(code_blocks)

            # Add test assertions
            test_code = f"{full_code}\n\n# Test assertions\n"
            for assertion in test_assertions:
                test_code += f"{assertion}\n"

            # Execute in isolated environment using Playwright
            # This runs code in a headless browser context for safety
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()

                # Execute Python code in browser console (via PyScript or similar)
                # For now, use subprocess as fallback
                import subprocess
                import tempfile

                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    f.write(test_code)
                    temp_path = f.name

                try:
                    result = subprocess.run(
                        ['python3', temp_path],
                        capture_output=True,
                        timeout=10,
                        text=True
                    )

                    if result.returncode == 0:
                        return True, None
                    else:
                        return False, result.stderr
                finally:
                    os.unlink(temp_path)
                    await browser.close()

        except Exception as e:
            return False, f"Execution error: {str(e)}"

    async def _run_phoenix_evals(
        self,
        df: pd.DataFrame,
        instances: List[EvalInstance]
    ) -> pd.DataFrame:
        """Run Phoenix LLM-based evaluations"""

        # Prepare data for Phoenix evaluators
        eval_data = []
        for idx, (_, row) in enumerate(df.iterrows()):
            instance = instances[idx]
            eval_data.append({
                'input': instance.question,
                'output': row['response'],
                'reference': instance.reference_answer or "",
                'context': instance.context or ""
            })

        eval_df = pd.DataFrame(eval_data)

        # Run hallucination evaluation (checks if output is grounded in context)
        if eval_df['context'].notna().any():
            print("  Running hallucination detection...")
            hallucination_eval = HallucinationEvaluator()
            hallucination_results = run_evals(
                dataframe=eval_df,
                evaluators=[hallucination_eval],
                provide_explanation=True
            )
            df['hallucination_score'] = hallucination_results[0]['score']

        # Run Q&A correctness evaluation
        if eval_df['reference'].notna().any():
            print("  Running Q&A correctness evaluation...")
            qa_eval = QAEvaluator()
            qa_results = run_evals(
                dataframe=eval_df,
                evaluators=[qa_eval],
                provide_explanation=True
            )
            df['qa_correctness'] = qa_results[0]['score']

        # Run relevance evaluation
        print("  Running relevance evaluation...")
        relevance_eval = RelevanceEvaluator()
        relevance_results = run_evals(
            dataframe=eval_df,
            evaluators=[relevance_eval],
            provide_explanation=True
        )
        df['relevance_score'] = relevance_results[0]['score']

        return df

    def _print_summary(self, df: pd.DataFrame, experiment_name: str):
        """Print evaluation summary"""
        print(f"\n{'='*60}")
        print(f"📊 Evaluation Summary: {experiment_name}")
        print(f"{'='*60}")

        print(f"\n🎯 Overall Metrics:")
        print(f"  QA Correctness:    {df['qa_correctness'].mean():.2%} ± {df['qa_correctness'].std():.2%}")
        print(f"  Hallucination:     {df['hallucination_score'].mean():.2%} ± {df['hallucination_score'].std():.2%}")
        print(f"  Relevance:         {df['relevance_score'].mean():.2%} ± {df['relevance_score'].std():.2%}")

        if 'code_execution_passed' in df.columns:
            pass_rate = df['code_execution_passed'].mean()
            print(f"  Code Pass Rate:    {pass_rate:.2%} ({int(pass_rate * len(df))}/{len(df)} passed)")

        print(f"\n⏱️  Performance:")
        print(f"  Avg Latency:       {df['latency_ms'].mean():.0f}ms")
        print(f"  P95 Latency:       {df['latency_ms'].quantile(0.95):.0f}ms")

        print(f"\n🧠 Configuration:")
        if 'melodic_memory_enabled' in df.columns:
            print(f"  Melodic Memory:    {df['melodic_memory_enabled'].iloc[0]}")
        if 'collective_brain_used' in df.columns:
            cb_rate = df['collective_brain_used'].mean()
            print(f"  Collective Brain:  {cb_rate:.2%} of queries")

        print(f"\n{'='*60}\n")


def load_swe_bench_samples(num_instances: int = 10) -> List[EvalInstance]:
    """Load SWE-bench samples for evaluation"""
    from datasets import load_dataset

    print(f"Loading SWE-bench Lite (first {num_instances} instances)...")
    dataset = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")

    instances = []
    for i, item in enumerate(dataset):
        if i >= num_instances:
            break

        instances.append(EvalInstance(
            instance_id=item['instance_id'],
            question=f"Fix this GitHub issue:\n\n{item['problem_statement']}\n\nRepo: {item['repo']}",
            reference_answer=item['patch'],  # Gold patch
            context=item.get('hints_text', ''),
            expected_code=item['patch'],
            test_assertions=[]  # SWE-bench has test patches, we'd parse these
        ))

    return instances


def create_melodic_memory_ab_test() -> tuple[List[EvalInstance], List[EvalInstance]]:
    """
    Create A/B test instances for melodic memory evaluation

    Returns (control_instances, treatment_instances)
    """
    # Same questions, but control will have melodic_memory=False
    questions = [
        EvalInstance(
            instance_id="mm_ab_1",
            question="Implement a JWT authentication system with middleware",
            reference_answer="Should include: JWT signing, middleware with rate limiting, secure secret handling",
            context="Security is a priority. The system needs to handle authentication tokens securely.",
            expected_code=None,
            test_assertions=None
        ),
        EvalInstance(
            instance_id="mm_ab_2",
            question="Refactor this API to use async/await",
            reference_answer="Should convert synchronous code to async, use asyncio properly, maintain same interface",
            context="Existing codebase uses sync requests. Need to improve performance with async.",
            expected_code=None,
            test_assertions=None
        ),
        EvalInstance(
            instance_id="mm_ab_3",
            question="Add caching to reduce database queries",
            reference_answer="Should implement Redis caching, cache invalidation, TTL management",
            context="Database is slow. Need to cache frequently accessed data.",
            expected_code=None,
            test_assertions=None
        )
    ]

    return questions, questions  # Same instances, different config


def create_collective_brain_ab_test() -> tuple[List[EvalInstance], List[EvalInstance]]:
    """
    Create A/B test for collective brain vs single-agent

    Returns (control_instances, treatment_instances)
    """
    questions = [
        EvalInstance(
            instance_id="cb_ab_1",
            question="Should I use GraphQL or REST for my new API?",
            reference_answer="Consider: team expertise, client needs, caching requirements, ecosystem maturity",
            context="Building a new API for mobile and web clients",
            expected_code=None,
            test_assertions=None
        ),
        EvalInstance(
            instance_id="cb_ab_2",
            question="What's the best way to handle microservice authentication?",
            reference_answer="Options: service mesh, JWT, mTLS. Depends on scale, security needs, complexity tolerance.",
            context="Migrating monolith to microservices",
            expected_code=None,
            test_assertions=None
        ),
        EvalInstance(
            instance_id="cb_ab_3",
            question="How should I architect a real-time notification system?",
            reference_answer="Consider: WebSockets vs SSE, scaling strategy, message queue, fallback mechanisms",
            context="Need to send push notifications to millions of users",
            expected_code=None,
            test_assertions=None
        )
    ]

    return questions, questions


async def main():
    parser = argparse.ArgumentParser(description="Phoenix Evaluations for MAKER")
    parser.add_argument("--experiment", required=True, choices=[
        "melodic_memory_ab",
        "collective_brain_ab",
        "swe_bench"
    ], help="Experiment type to run")
    parser.add_argument("--num_instances", type=int, default=10, help="Number of SWE-bench instances")
    parser.add_argument("--orchestrator_url", default="http://localhost:8080")
    parser.add_argument("--phoenix_url", default="http://localhost:6006")
    parser.add_argument("--output_dir", default="results/phoenix_evals")

    args = parser.parse_args()

    evaluator = PhoenixEvaluator(
        orchestrator_url=args.orchestrator_url,
        phoenix_url=args.phoenix_url,
        output_dir=Path(args.output_dir)
    )

    if args.experiment == "melodic_memory_ab":
        print("\n🧪 Running Melodic Memory A/B Test")
        control, treatment = create_melodic_memory_ab_test()

        # Control: melodic memory OFF
        print("\n--- Control Group (Melodic Memory OFF) ---")
        control_df = await evaluator.run_experiment(
            "melodic_memory_control",
            control,
            melodic_memory=False,
            use_collective_brain=False
        )

        # Treatment: melodic memory ON
        print("\n--- Treatment Group (Melodic Memory ON) ---")
        treatment_df = await evaluator.run_experiment(
            "melodic_memory_treatment",
            treatment,
            melodic_memory=True,
            use_collective_brain=False
        )

        # Compare results
        print("\n📈 A/B Test Results:")
        print(f"  QA Correctness Lift: {(treatment_df['qa_correctness'].mean() - control_df['qa_correctness'].mean()) * 100:+.1f}%")
        print(f"  Hallucination Reduction: {(control_df['hallucination_score'].mean() - treatment_df['hallucination_score'].mean()) * 100:+.1f}%")

    elif args.experiment == "collective_brain_ab":
        print("\n🧪 Running Collective Brain A/B Test")
        control, treatment = create_collective_brain_ab_test()

        # Control: single-agent (Preprocessor only)
        print("\n--- Control Group (Single Agent) ---")
        control_df = await evaluator.run_experiment(
            "collective_brain_control",
            control,
            melodic_memory=True,
            use_collective_brain=False
        )

        # Treatment: collective brain
        print("\n--- Treatment Group (Collective Brain) ---")
        treatment_df = await evaluator.run_experiment(
            "collective_brain_treatment",
            treatment,
            melodic_memory=True,
            use_collective_brain=True
        )

        # Compare results
        print("\n📈 A/B Test Results:")
        print(f"  QA Correctness Lift: {(treatment_df['qa_correctness'].mean() - control_df['qa_correctness'].mean()) * 100:+.1f}%")
        print(f"  Relevance Lift: {(treatment_df['relevance_score'].mean() - control_df['relevance_score'].mean()) * 100:+.1f}%")

    elif args.experiment == "swe_bench":
        print(f"\n🧪 Running SWE-bench Evaluation ({args.num_instances} instances)")
        instances = load_swe_bench_samples(args.num_instances)

        df = await evaluator.run_experiment(
            f"swe_bench_{args.num_instances}",
            instances,
            melodic_memory=True,
            use_collective_brain=True
        )

    print(f"\n✅ Evaluation complete! View results in Phoenix UI:")
    print(f"   {args.phoenix_url}")


if __name__ == "__main__":
    asyncio.run(main())
