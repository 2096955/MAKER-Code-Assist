#!/usr/bin/env python3
"""
Test the full pipeline with a Fibonacci request
Tests EE Planner integration end-to-end
"""

import sys
import os
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from orchestrator.orchestrator import Orchestrator


async def test_fibonacci_pipeline():
    """Test full pipeline with Fibonacci request"""
    print("=" * 80)
    print("Testing Full Pipeline: Fibonacci Function")
    print("=" * 80)
    print()
    
    # Initialize orchestrator
    print("[1/5] Initializing Orchestrator...")
    try:
        orch = Orchestrator()
        print(f"  ✓ Orchestrator initialized")
        print(f"  ✓ EE Mode: {orch.ee_mode}")
    except Exception as e:
        print(f"  ✗ Failed to initialize: {e}")
        return
    
    # Check EE Planner
    print("\n[2/5] Checking EE Planner...")
    try:
        ee_planner = orch._get_ee_planner()
        if ee_planner:
            print(f"  ✓ EE Planner available")
        else:
            print(f"  ⚠ EE Planner not available (will use standard planner)")
    except Exception as e:
        print(f"  ⚠ EE Planner error: {e} (will fallback)")
    
    # Test request
    task_id = "test_fibonacci"
    user_input = "Write a Python function to calculate the nth Fibonacci number"
    
    print(f"\n[3/5] Processing request: {user_input}")
    print("-" * 80)
    
    # Collect output
    output_chunks = []
    
    try:
        async for chunk in orch.orchestrate_workflow(task_id, user_input):
            print(chunk, end="", flush=True)
            output_chunks.append(chunk)
        
        print("\n" + "-" * 80)
        print("\n[4/5] Checking results...")
        
        # Check if we got code output
        full_output = "".join(output_chunks)
        
        # Look for code blocks
        if "```" in full_output or "def fibonacci" in full_output.lower():
            print("  ✓ Code generation detected")
        else:
            print("  ⚠ No code block found in output")
        
        # Check for EE Planner usage
        if "[EE PLANNER]" in full_output or "[PLANNER] Using EE Planner" in full_output:
            print("  ✓ EE Planner was used")
        elif "[PLANNER]" in full_output:
            print("  ⚠ Standard planner was used (EE may have failed)")
        
        # Check for plan
        from orchestrator.orchestrator import TaskState
        state = TaskState.load_from_redis(task_id, orch.redis)
        if state:
            print(f"  ✓ Task state saved")
            print(f"  ✓ Status: {state.status}")
            if state.plan:
                print(f"  ✓ Plan generated: {len(state.plan.get('plan', []))} subtasks")
            if state.code:
                print(f"  ✓ Code generated: {len(state.code)} chars")
        
        print("\n[5/5] Pipeline test complete!")
        print("=" * 80)
        
        # Show final output
        print("\nFull Output Summary:")
        print("-" * 80)
        if len(full_output) > 1000:
            print(full_output[:500] + "\n...\n" + full_output[-500:])
        else:
            print(full_output)
        
    except Exception as e:
        print(f"\n✗ Pipeline error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_fibonacci_pipeline())
    sys.exit(0 if success else 1)

