#!/usr/bin/env python3
"""
Tests for SessionManager class
"""

import pytest
import tempfile
from pathlib import Path
from orchestrator.progress_tracker import ProgressTracker
from orchestrator.session_manager import SessionManager


def test_session_manager_initialization(tmp_path):
    """Test SessionManager initializes correctly"""
    tracker = ProgressTracker(tmp_path)
    manager = SessionManager(tracker)
    
    assert manager.progress_tracker is tracker


def test_create_resume_context(tmp_path):
    """Test resume context creation"""
    tracker = ProgressTracker(tmp_path)
    manager = SessionManager(tracker)
    
    # Add some progress
    tracker.add_feature("auth", "Authentication", priority=1)
    tracker.log_progress("Started authentication")
    tracker.log_progress("Completed login")
    
    context = manager.create_resume_context()
    
    assert "resuming work" in context.lower()
    assert "Working directory" in context
    assert "Recent progress" in context
    assert "auth" in context
    assert "Authentication" in context


def test_resume_context_includes_git_log(tmp_path, monkeypatch):
    """Test that resume context includes git log"""
    tracker = ProgressTracker(tmp_path)
    manager = SessionManager(tracker)
    
    # Mock git log
    def mock_git_log(*args, **kwargs):
        class MockResult:
            returncode = 0
            stdout = "abc123 Fix bug\n def456 Add feature"
        return MockResult()
    
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: mock_git_log())
    
    context = manager.create_resume_context()
    assert "Recent git commits" in context


def test_resume_context_with_no_features(tmp_path):
    """Test resume context when no features exist"""
    tracker = ProgressTracker(tmp_path)
    manager = SessionManager(tracker)
    
    context = manager.create_resume_context()
    
    assert "No incomplete features remaining" in context
    assert "Total features: 0" in context


def test_resume_session(tmp_path):
    """Test resume_session returns correct structure"""
    tracker = ProgressTracker(tmp_path)
    manager = SessionManager(tracker)
    
    tracker.add_feature("test_feature", "Test feature")
    tracker.log_progress("Some progress")
    
    result = manager.resume_session("test_session_123")
    
    assert result["session_id"] == "test_session_123"
    assert "resume_context" in result
    assert "is_clean" in result
    assert "working_directory" in result
    assert result["next_feature"] == "test_feature"


def test_verify_clean_state_clean(tmp_path, monkeypatch):
    """Test verify_clean_state returns True for clean state"""
    tracker = ProgressTracker(tmp_path)
    manager = SessionManager(tracker)
    
    # Mock clean git status
    def mock_git_status(*args, **kwargs):
        class MockResult:
            returncode = 0
            stdout = ""  # No changes
        return MockResult()
    
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: mock_git_status())
    
    is_clean = manager.verify_clean_state()
    assert is_clean is True


def test_verify_clean_state_uncommitted_changes(tmp_path, monkeypatch):
    """Test verify_clean_state returns False with uncommitted changes"""
    tracker = ProgressTracker(tmp_path)
    manager = SessionManager(tracker)
    
    # Mock git status with changes
    def mock_git_status(*args, **kwargs):
        class MockResult:
            returncode = 0
            stdout = "M  file.py"  # Modified file
        return MockResult()
    
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: mock_git_status())
    
    is_clean = manager.verify_clean_state()
    assert is_clean is False


def test_verify_clean_state_with_errors(tmp_path):
    """Test verify_clean_state detects errors in progress"""
    tracker = ProgressTracker(tmp_path)
    manager = SessionManager(tracker)
    
    # Log error messages
    tracker.log_progress("Error: Something went wrong")
    tracker.log_progress("Exception occurred")
    
    is_clean = manager.verify_clean_state()
    assert is_clean is False


def test_get_orientation_info(tmp_path):
    """Test get_orientation_info returns correct structure"""
    tracker = ProgressTracker(tmp_path)
    manager = SessionManager(tracker)
    
    tracker.add_feature("test", "Test feature")
    
    info = manager.get_orientation_info()
    
    assert "working_directory" in info
    assert "git_branch" in info
    assert "git_status" in info
    assert "next_feature" in info
    assert "is_clean" in info


def test_resume_context_template_structure(tmp_path):
    """Test resume context follows Anthropic template structure"""
    tracker = ProgressTracker(tmp_path)
    manager = SessionManager(tracker)
    
    tracker.add_feature("feature1", "First feature", priority=1)
    tracker.log_progress("Progress entry 1")
    tracker.log_progress("Progress entry 2")
    
    context = manager.create_resume_context()
    
    # Check template elements
    assert "You are resuming work" in context
    assert "Working directory:" in context
    assert "Recent progress" in context
    assert "Recent git commits" in context
    assert "Next feature to implement:" in context
    assert "Continue working on this feature" in context


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

