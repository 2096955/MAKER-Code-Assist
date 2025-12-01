#!/usr/bin/env python3
"""
Test output quality with/without skills.

Compares LLM output quality when skills are enabled vs disabled.
"""

import os
import sys
import json
import httpx
import asyncio
from typing import Dict, List
from pathlib import Path


class OutputQualityTester:
    """Test output quality with and without skills"""
    
    def __init__(self, orchestrator_url: str = "http://localhost:8080"):
        self.orchestrator_url = orchestrator_url
        self.results = []
    
    async def test_regex_task(self, with_skills: bool) -> Dict:
        """Test regex pattern fixing task"""
        task = "Fix this regex pattern: r'[\\w.]+@[\\w.]+' to properly validate email addresses"
        
        # Set skills mode via environment or API
        # Note: This assumes orchestrator reads ENABLE_SKILLS env var
        env_skills = os.getenv("ENABLE_SKILLS", "false")
        if with_skills:
            os.environ["ENABLE_SKILLS"] = "true"
        else:
            os.environ["ENABLE_SKILLS"] = "false"
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.orchestrator_url}/v1/chat/completions",
                    json={
                        "model": "multi-agent",
                        "messages": [
                            {"role": "user", "content": task}
                        ]
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    return {
                        "success": True,
                        "content": content,
                        "has_anchors": "^" in content and "$" in content,
                        "has_escaping": "\\." in content or r"\." in content,
                        "mentions_edge_cases": any(word in content.lower() for word in ["edge", "empty", "special", "case"]),
                        "length": len(content)
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}",
                        "content": response.text
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            os.environ["ENABLE_SKILLS"] = env_skills
    
    async def test_ast_task(self, with_skills: bool) -> Dict:
        """Test AST refactoring task"""
        task = "Refactor Python code using AST manipulation to add type hints"
        
        env_skills = os.getenv("ENABLE_SKILLS", "false")
        if with_skills:
            os.environ["ENABLE_SKILLS"] = "true"
        else:
            os.environ["ENABLE_SKILLS"] = "false"
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.orchestrator_url}/v1/chat/completions",
                    json={
                        "model": "multi-agent",
                        "messages": [
                            {"role": "user", "content": task}
                        ]
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    return {
                        "success": True,
                        "content": content,
                        "mentions_ast": "ast" in content.lower(),
                        "mentions_lineno": "lineno" in content.lower() or "line" in content.lower(),
                        "mentions_visitor": "visitor" in content.lower() or "transformer" in content.lower(),
                        "length": len(content)
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            os.environ["ENABLE_SKILLS"] = env_skills
    
    def analyze_improvement(self, baseline: Dict, enhanced: Dict) -> Dict:
        """Analyze improvement from baseline to enhanced"""
        if not baseline.get("success") or not enhanced.get("success"):
            return {"error": "One or both tests failed"}
        
        improvements = {}
        
        # Regex-specific improvements
        if "has_anchors" in baseline:
            improvements["anchors_added"] = not baseline["has_anchors"] and enhanced["has_anchors"]
            improvements["escaping_added"] = not baseline["has_escaping"] and enhanced["has_escaping"]
            improvements["edge_cases_mentioned"] = not baseline["mentions_edge_cases"] and enhanced["mentions_edge_cases"]
        
        # AST-specific improvements
        if "mentions_ast" in baseline:
            improvements["ast_mentioned"] = not baseline["mentions_ast"] and enhanced["mentions_ast"]
            improvements["lineno_mentioned"] = not baseline["mentions_lineno"] and enhanced["mentions_lineno"]
            improvements["visitor_mentioned"] = not baseline["mentions_visitor"] and enhanced["mentions_visitor"]
        
        # General improvements
        improvements["length_increase"] = enhanced["length"] - baseline["length"]
        improvements["length_percent"] = ((enhanced["length"] - baseline["length"]) / baseline["length"] * 100) if baseline["length"] > 0 else 0
        
        return improvements


async def main():
    """Run output quality tests"""
    print("=" * 60)
    print("Output Quality Test: Skills Impact")
    print("=" * 60)
    print()
    
    tester = OutputQualityTester()
    
    # Test 1: Regex task
    print("Test 1: Regex Pattern Fixing")
    print("-" * 60)
    
    print("  Running baseline (no skills)...")
    baseline_regex = await tester.test_regex_task(with_skills=False)
    
    print("  Running enhanced (with skills)...")
    enhanced_regex = await tester.test_regex_task(with_skills=True)
    
    if baseline_regex.get("success") and enhanced_regex.get("success"):
        improvements = tester.analyze_improvement(baseline_regex, enhanced_regex)
        print()
        print("  Results:")
        print(f"    Baseline: {baseline_regex['length']} chars, anchors={baseline_regex['has_anchors']}, escaping={baseline_regex['has_escaping']}")
        print(f"    Enhanced:  {enhanced_regex['length']} chars, anchors={enhanced_regex['has_anchors']}, escaping={enhanced_regex['has_escaping']}")
        print()
        print("  Improvements:")
        for key, value in improvements.items():
            if isinstance(value, bool):
                status = "✓" if value else "✗"
                print(f"    {status} {key}: {value}")
            else:
                print(f"    {key}: {value}")
    else:
        print("  ⚠ Tests failed - check service status")
        if not baseline_regex.get("success"):
            print(f"    Baseline error: {baseline_regex.get('error')}")
        if not enhanced_regex.get("success"):
            print(f"    Enhanced error: {enhanced_regex.get('error')}")
    
    print()
    
    # Test 2: AST task
    print("Test 2: AST Refactoring")
    print("-" * 60)
    
    print("  Running baseline (no skills)...")
    baseline_ast = await tester.test_ast_task(with_skills=False)
    
    print("  Running enhanced (with skills)...")
    enhanced_ast = await tester.test_ast_task(with_skills=True)
    
    if baseline_ast.get("success") and enhanced_ast.get("success"):
        improvements = tester.analyze_improvement(baseline_ast, enhanced_ast)
        print()
        print("  Results:")
        print(f"    Baseline: {baseline_ast['length']} chars, AST={baseline_ast['mentions_ast']}, lineno={baseline_ast['mentions_lineno']}")
        print(f"    Enhanced:  {enhanced_ast['length']} chars, AST={enhanced_ast['mentions_ast']}, lineno={enhanced_ast['mentions_lineno']}")
        print()
        print("  Improvements:")
        for key, value in improvements.items():
            if isinstance(value, bool):
                status = "✓" if value else "✗"
                print(f"    {status} {key}: {value}")
            else:
                print(f"    {key}: {value}")
    else:
        print("  ⚠ Tests failed - check service status")
    
    print()
    print("=" * 60)
    print("Test Complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

