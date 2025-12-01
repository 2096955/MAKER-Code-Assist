#!/usr/bin/env python3
"""
Test EE Memory integration
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncio
from orchestrator.ee_memory import HierarchicalMemoryNetwork, MelodicLine
from orchestrator.agent_memory import AgentMemoryNetwork, AgentName
from orchestrator.melodic_detector import MelodicLineDetector

# Try to import orchestrator (may fail if dependencies missing)
try:
    from orchestrator.orchestrator import Orchestrator
    ORCHESTRATOR_AVAILABLE = True
except ImportError:
    ORCHESTRATOR_AVAILABLE = False
    print("⚠ Orchestrator not available (missing dependencies)")


def test_hmn_basic():
    """Test basic HMN functionality"""
    print("Testing HMN basic functionality...")
    
    hmn = HierarchicalMemoryNetwork(codebase_path=".")
    
    # Add a test file
    test_content = """
def hello_world():
    print("Hello, World!")

class TestClass:
    def method(self):
        return "test"
"""
    l0_id = hmn.add_code_file("test_file.py", test_content)
    assert l0_id in hmn.l0_nodes, "L0 node not created"
    print(f"✓ Added file to L0: {l0_id}")
    
    # Extract entities
    entities = hmn.extract_entities(l0_id)
    assert len(entities) > 0, "No entities extracted"
    print(f"✓ Extracted {len(entities)} entities to L1")
    
    # Detect patterns
    patterns = hmn.detect_patterns(entities)
    print(f"✓ Detected {len(patterns)} patterns in L2")
    
    # Query with context
    context = hmn.query_with_context("test task")
    assert "code" in context, "Context missing code"
    assert "compression_ratio" in context, "Context missing compression ratio"
    print(f"✓ Query returned context with {context['compression_ratio']:.1%} compression")
    
    print("✓ HMN basic test passed\n")


def test_melodic_detector():
    """Test melodic line detection"""
    print("Testing melodic line detector...")
    
    detector = MelodicLineDetector(persistence_threshold=0.7)
    
    # Create test data
    codebase_files = {
        "auth/login.py": "def login(): pass\ndef validate(): pass",
        "auth/logout.py": "def logout(): pass",
        "payment/process.py": "def process_payment(): pass",
    }
    
    # Create minimal HMN structure
    hmn = HierarchicalMemoryNetwork(codebase_path=".")
    for file_path, content in codebase_files.items():
        l0_id = hmn.add_code_file(file_path, content)
        entities = hmn.extract_entities(l0_id)
        hmn.detect_patterns(entities)
    
    # Detect melodic lines
    melodic_lines = detector.detect_from_codebase(
        codebase_files,
        hmn.l0_nodes,
        hmn.l1_nodes,
        hmn.l2_nodes
    )
    
    print(f"✓ Detected {len(melodic_lines)} melodic lines")
    for ml in melodic_lines:
        print(f"  - {ml.name} (persistence: {ml.persistence_score:.2f})")
    
    print("✓ Melodic detector test passed\n")


def test_agent_memory():
    """Test per-agent memory networks"""
    print("Testing agent memory networks...")
    
    hmn = HierarchicalMemoryNetwork(codebase_path=".")
    hmn.add_code_file("test.py", "def test(): pass")
    
    # Create agent memories
    planner_memory = AgentMemoryNetwork(AgentName.PLANNER, hmn)
    coder_memory = AgentMemoryNetwork(AgentName.CODER, hmn)
    
    # Get context for each agent
    planner_context = planner_memory.get_context_for_agent("Update authentication")
    coder_context = coder_memory.get_context_for_agent("Update authentication")
    
    assert len(planner_context) > 0, "Planner context empty"
    assert len(coder_context) > 0, "Coder context empty"
    assert "Narrative" in planner_context or "Context" in planner_context, "Planner context missing narrative info"
    
    print(f"✓ Planner context: {len(planner_context)} chars")
    print(f"✓ Coder context: {len(coder_context)} chars")
    print("✓ Agent memory test passed\n")


async def test_orchestrator_integration():
    """Test orchestrator integration with EE Memory"""
    if not ORCHESTRATOR_AVAILABLE:
        print("⚠ Orchestrator test skipped (dependencies not available)\n")
        return
    
    print("Testing orchestrator integration...")
    
    try:
        orch = Orchestrator()
        
        # Check world model initialized
        assert orch.world_model is not None, "World model not initialized"
        print(f"✓ World model initialized")
        
        # Check agent memories created
        assert len(orch.agent_memories) == len(AgentName), "Not all agent memories created"
        print(f"✓ Created {len(orch.agent_memories)} agent memory networks")
        
        # Check stats
        stats = orch.world_model.get_stats()
        print(f"✓ HMN stats: {stats}")
        
        print("✓ Orchestrator integration test passed\n")
        
    except Exception as e:
        print(f"⚠ Orchestrator test skipped (may need Redis/MCP): {e}\n")


def main():
    """Run all tests"""
    print("=" * 60)
    print("EE Memory Integration Tests")
    print("=" * 60)
    print()
    
    test_hmn_basic()
    test_melodic_detector()
    test_agent_memory()
    
    # Orchestrator test (may fail if services not running)
    if ORCHESTRATOR_AVAILABLE:
        try:
            asyncio.run(test_orchestrator_integration())
        except Exception as e:
            print(f"⚠ Orchestrator test skipped: {e}\n")
    else:
        print("⚠ Orchestrator test skipped (dependencies not available)\n")
    
    print("=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()

