#!/usr/bin/env python3
"""
Tests for CheckpointManager class
"""

import pytest
import tempfile
import asyncio
from pathlib import Path
from orchestrator.progress_tracker import ProgressTracker
from orchestrator.checkpoint_manager import CheckpointManager


def test_checkpoint_manager_initialization(tmp_path):
    """Test CheckpointManager initializes correctly"""
    tracker = ProgressTracker(tmp_path)
    manager = CheckpointManager(tracker)
    
    assert manager.progress_tracker is tracker
    assert manager.redis is None


def test_generate_commit_message(tmp_path):
    """Test commit message generation"""
    tracker = ProgressTracker(tmp_path)
    manager = CheckpointManager(tracker)
    
    message = manager._generate_commit_message("auth", None)
    assert "feat: Complete auth" in message
    assert "MAKER Multi-Agent System" in message
    
    # With code
    code = "def login():\n    pass\n\nclass User:\n    pass"
    message = manager._generate_commit_message("auth", code)
    assert "Added 1 function" in message
    assert "Added 1 class" in message


def test_summarize_code_changes(tmp_path):
    """Test code change summarization"""
    tracker = ProgressTracker(tmp_path)
    manager = CheckpointManager(tracker)
    
    # Code with functions and classes
    code = """def function1():
    pass

def function2():
    pass

class MyClass:
    pass
"""
    summary = manager._summarize_code_changes(code)
    assert "2 functions" in summary
    assert "1 class" in summary
    
    # Code with just lines
    code = "\n".join([f"line {i}" for i in range(20)])
    summary = manager._summarize_code_changes(code)
    assert "20 lines" in summary


@pytest.mark.asyncio
async def test_verify_tests_pass_no_tests(tmp_path, monkeypatch):
    """Test verify_tests_pass when no test command works"""
    tracker = ProgressTracker(tmp_path)
    manager = CheckpointManager(tracker)
    
    # Mock all test commands to fail
    def mock_run_fail(*args, **kwargs):
        raise FileNotFoundError()
    
    monkeypatch.setattr("subprocess.run", mock_run_fail)
    
    # Should return False (safer: don't assume tests pass if we can't verify)
    result = await manager.verify_tests_pass()
    assert result is False


@pytest.mark.asyncio
async def test_verify_tests_pass_pytest_success(tmp_path, monkeypatch):
    """Test verify_tests_pass with successful pytest"""
    tracker = ProgressTracker(tmp_path)
    manager = CheckpointManager(tracker)
    
    # Mock pytest success
    def mock_pytest(*args, **kwargs):
        class MockResult:
            returncode = 0
            stdout = "3 passed"
        return MockResult()
    
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: mock_pytest())
    
    result = await manager.verify_tests_pass()
    assert result is True


def test_commit_changes_no_git(tmp_path, monkeypatch):
    """Test commit_changes when git is not available"""
    tracker = ProgressTracker(tmp_path)
    manager = CheckpointManager(tracker)
    
    # Mock git --version to fail
    def mock_git_version(*args, **kwargs):
        raise FileNotFoundError()
    
    monkeypatch.setattr("subprocess.run", mock_git_version)
    
    result = manager.commit_changes("Test commit")
    assert result is None


def test_commit_changes_no_changes(tmp_path, monkeypatch):
    """Test commit_changes when there are no changes"""
    tracker = ProgressTracker(tmp_path)
    manager = CheckpointManager(tracker)
    
    call_sequence = []
    
    def mock_git(*args, **kwargs):
        cmd = args[0] if args else []
        call_sequence.append(cmd)
        
        class MockResult:
            returncode = 0
            stdout = "" if "status" in str(cmd) else "abc123"
            stderr = ""
        
        return MockResult()
    
    monkeypatch.setattr("subprocess.run", mock_git)
    
    result = manager.commit_changes("Test commit")
    # Should return None when no changes
    assert result is None


@pytest.mark.asyncio
async def test_create_checkpoint_success(tmp_path, monkeypatch):
    """Test successful checkpoint creation"""
    tracker = ProgressTracker(tmp_path)
    manager = CheckpointManager(tracker)
    
    # Add feature
    tracker.add_feature("auth", "Authentication")
    
    # Mock successful test and git
    call_sequence = []
    
    def mock_subprocess(*args, **kwargs):
        cmd = args[0] if args else []
        call_sequence.append(str(cmd))
        
        if 'pytest' in str(cmd) or 'test' in str(cmd):
            class MockResult:
                returncode = 0
                stdout = "3 passed"
                stderr = ""
            return MockResult()
        
        if 'git' in str(cmd):
            class MockResult:
                returncode = 0
                stdout = "abc123def456" if 'rev-parse' in str(cmd) else ("M file.py" if 'status' in str(cmd) else "")
                stderr = ""
            return MockResult()
        
        # For git --version check
        class MockResult:
            returncode = 0
            stdout = "git version 2.0"
            stderr = ""
        return MockResult()
    
    monkeypatch.setattr("subprocess.run", mock_subprocess)
    
    result = await manager.create_checkpoint("auth", "def login(): pass")
    
    assert result["success"] is True
    assert result["commit_hash"] is not None
    assert result["error"] is None
    
    # Verify feature status updated
    features = tracker.load_feature_list()
    assert features[0].passes is True


@pytest.mark.asyncio
async def test_create_checkpoint_tests_fail(tmp_path, monkeypatch):
    """Test checkpoint fails when tests don't pass"""
    tracker = ProgressTracker(tmp_path)
    manager = CheckpointManager(tracker)
    
    tracker.add_feature("auth", "Authentication")
    
    # Mock verify_tests_pass to return False directly
    async def mock_verify_fail():
        return False
    
    manager.verify_tests_pass = mock_verify_fail
    
    result = await manager.create_checkpoint("auth", "code")
    
    assert result["success"] is False
    assert "Tests are failing" in result["error"]
    
    # Feature should not be marked as passing
    features = tracker.load_feature_list()
    assert features[0].passes is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

