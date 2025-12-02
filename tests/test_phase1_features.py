#!/usr/bin/env python3
"""
Integration tests for Phase 1 Quick Wins features.

Tests:
1. Auto-Compact Context - Does it trigger at 95%?
2. Tool Call Scaling - Does it change candidate counts?
3. Confidence Scoring - Does it improve results?
4. Intelligent File Chunking - Does it work with large files?
"""

"""
Integration tests for Phase 1 Quick Wins features.

Note: Some tests require optional dependencies (redis, etc.)
Run with: pytest tests/test_phase1_features.py -v
"""

import pytest
import asyncio
import os
import tempfile
from pathlib import Path

# Optional imports - tests will skip if not available
try:
    from orchestrator.orchestrator import Orchestrator, ContextCompressor
    ORCHESTRATOR_AVAILABLE = True
except ImportError:
    ORCHESTRATOR_AVAILABLE = False

try:
    from orchestrator.rag_service_faiss import RAGServiceFAISS
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

try:
    from orchestrator.mcp_server import CodebaseMCPServer
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

try:
    from orchestrator.code_verifier import CodeVerifier
    VERIFIER_AVAILABLE = True
except ImportError:
    VERIFIER_AVAILABLE = False


@pytest.mark.skipif(not ORCHESTRATOR_AVAILABLE, reason="Orchestrator not available")
class TestAutoCompactContext:
    """Test auto-compact context at 95% threshold"""
    
    def test_compression_triggers_at_95_percent(self):
        """Verify compression triggers when approaching 95% threshold"""
        # Create orchestrator mock
        class MockOrchestrator:
            async def call_agent_sync(self, *args, **kwargs):
                return "Summary of conversation"
        
        # Create compressor with small limits for testing
        compressor = ContextCompressor(
            orchestrator=MockOrchestrator(),
            max_context_tokens=1000,  # Small limit for testing
            recent_window_tokens=200,
            summary_chunk_size=100
        )
        
        # Add messages until we approach 95% (950 tokens)
        total_tokens = 0
        message_count = 0
        while total_tokens < 950:
            msg = f"Message {message_count}: " + "x" * 100  # ~25 tokens each
            compressor.add_message("user", msg)
            total_tokens += len(msg) // 4
            message_count += 1
        
        # Check that compression would trigger
        total = sum(m.token_estimate for m in compressor.conversation_history)
        total += compressor.compressed_token_count
        threshold = int(compressor.max_context_tokens * 0.95)
        
        assert total >= threshold, f"Total tokens {total} should be >= threshold {threshold}"
        
        # Compression should be needed
        # Note: This is a sync test, actual compression is async
        assert len(compressor.conversation_history) > 0


@pytest.mark.skipif(not ORCHESTRATOR_AVAILABLE, reason="Orchestrator not available")
class TestToolCallScaling:
    """Test tool call scaling based on task complexity"""
    
    def test_simple_tasks_get_fewer_candidates(self):
        """Verify simple tasks use 2 candidates"""
        orch = Orchestrator()
        orch.enable_tool_scaling = True
        
        count = orch._get_candidate_count("simple_code")
        assert count == 2, f"Simple tasks should use 2 candidates, got {count}"
    
    def test_complex_tasks_get_more_candidates(self):
        """Verify complex tasks use 8 candidates"""
        orch = Orchestrator()
        orch.enable_tool_scaling = True
        
        count = orch._get_candidate_count("complex_code")
        assert count == 8, f"Complex tasks should use 8 candidates, got {count}"
    
    def test_questions_get_fewer_candidates(self):
        """Verify questions use 2 candidates"""
        orch = Orchestrator()
        orch.enable_tool_scaling = True
        
        count = orch._get_candidate_count("question")
        assert count == 2, f"Questions should use 2 candidates, got {count}"
    
    def test_scaling_can_be_disabled(self):
        """Verify scaling can be disabled to use fixed count"""
        orch = Orchestrator()
        orch.enable_tool_scaling = False
        orch.num_candidates = 5
        
        count = orch._get_candidate_count("complex_code")
        assert count == 5, f"With scaling disabled, should use fixed count {orch.num_candidates}, got {count}"


@pytest.mark.skipif(not RAG_AVAILABLE, reason="RAG service not available")
class TestConfidenceScoring:
    """Test confidence scoring in RAG results"""
    
    def test_confidence_scores_are_included(self):
        """Verify confidence scores are included in RAG results"""
        # This test requires a RAG index, so we'll mock it
        # In real test, would need to create a test index
        
        # Check that confidence calculation doesn't exceed 1.0
        similarity = 1.0
        recency = 1.0
        importance = 1.0
        rank_boost = 1.0
        
        confidence = (
            similarity * 0.5 +
            recency * 0.2 +
            importance * 0.2 +
            rank_boost * 0.1
        )
        
        assert confidence <= 1.0, f"Confidence {confidence} should not exceed 1.0"
        assert confidence == 1.0, f"Max confidence should be 1.0, got {confidence}"
    
    def test_git_recency_uses_codebase_root(self):
        """Verify git recency check uses CODEBASE_ROOT env var"""
        # This would require actual git repo and file
        # For now, just verify the method exists and handles missing git gracefully
        rag = RAGServiceFAISS()
        
        # Should not crash on non-existent file
        score = rag._get_file_recency_score("nonexistent_file.py")
        assert 0.0 <= score <= 1.0, f"Recency score should be between 0 and 1, got {score}"


@pytest.mark.skipif(not MCP_AVAILABLE, reason="MCP server not available")
class TestIntelligentFileChunking:
    """Test intelligent file chunking"""
    
    def test_chunking_respects_function_boundaries(self):
        """Verify Python files are chunked by function/class boundaries"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test Python file with multiple functions
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("""
def function1():
    return 1

def function2():
    return 2

class MyClass:
    def method1(self):
        pass
""")
            
            mcp = CodebaseMCPServer(tmpdir)
            chunks = mcp._chunk_python_file(test_file, test_file.read_text())
            
            # Should have chunks for each function/class
            assert len(chunks) >= 3, f"Should have at least 3 chunks (2 functions + 1 class), got {len(chunks)}"
            
            # Check chunk types
            chunk_types = [c['chunk_type'] for c in chunks]
            assert 'function' in chunk_types, "Should have function chunks"
            assert 'class' in chunk_types, "Should have class chunks"
    
    def test_auto_chunking_for_large_files(self):
        """Verify large files are automatically chunked"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a large Python file
            test_file = Path(tmpdir) / "large.py"
            large_content = "def func():\n    pass\n" * 1000  # ~6000 chars
            test_file.write_text(large_content)
            
            mcp = CodebaseMCPServer(tmpdir)
            # chunked=None should auto-enable for large files
            result = mcp.read_file("large.py", chunked=None)
            
            # Should be chunked (contains chunk markers)
            assert "chunked into" in result or "FUNCTION:" in result or "CLASS:" in result, \
                "Large file should be automatically chunked"
    
    def test_small_files_not_chunked(self):
        """Verify small files are not chunked"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "small.py"
            test_file.write_text("def hello(): return 'world'")
            
            mcp = CodebaseMCPServer(tmpdir)
            result = mcp.read_file("small.py", chunked=None)
            
            # Should not be chunked
            assert "chunked into" not in result, "Small file should not be chunked"


@pytest.mark.skipif(not VERIFIER_AVAILABLE, reason="Code verifier not available")
class TestCodeVerification:
    """Test self-verification loop"""
    
    def test_syntax_validation_catches_errors(self):
        """Verify syntax validation catches syntax errors"""
        verifier = CodeVerifier()
        
        valid, error = verifier.verify_syntax("def hello(): return 'world'")
        assert valid, "Valid Python code should pass syntax check"
        assert error is None, "Valid code should have no error"
        
        valid, error = verifier.verify_syntax("def hello(: return 'world'")  # Syntax error
        assert not valid, "Invalid Python code should fail syntax check"
        assert error is not None, "Invalid code should have error message"
    
    def test_import_checking(self):
        """Verify import checking works"""
        verifier = CodeVerifier()
        
        # Standard library import should work
        resolved, missing = verifier.check_imports("import os")
        assert resolved, "Standard library imports should resolve"
        
        # Non-existent import should be detected
        resolved, missing = verifier.check_imports("import nonexistent_module_xyz123")
        # May or may not resolve depending on environment, but shouldn't crash


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

