#!/usr/bin/env python3
"""
Tests for ProgressTracker class
"""

import pytest
import json
import tempfile
from pathlib import Path
from orchestrator.progress_tracker import ProgressTracker, Feature


def test_progress_tracker_initialization(tmp_path):
    """Test ProgressTracker creates files on init"""
    tracker = ProgressTracker(tmp_path)
    
    assert tracker.progress_file.exists()
    assert tracker.feature_list_file.exists()
    
    # Verify feature_list.json has correct structure
    with open(tracker.feature_list_file) as f:
        data = json.load(f)
        assert "features" in data
        assert isinstance(data["features"], list)


def test_log_progress(tmp_path):
    """Test logging progress messages"""
    tracker = ProgressTracker(tmp_path)
    
    tracker.log_progress("Test message 1")
    tracker.log_progress("Test message 2")
    
    # Read back
    with open(tracker.progress_file) as f:
        content = f.read()
        assert "Test message 1" in content
        assert "Test message 2" in content
        assert "[" in content  # Timestamp present


def test_add_and_load_features(tmp_path):
    """Test adding and loading features"""
    tracker = ProgressTracker(tmp_path)
    
    # Add features
    tracker.add_feature("auth", "User authentication", priority=1)
    tracker.add_feature("api", "REST API endpoints", priority=2)
    
    # Load back
    features = tracker.load_feature_list()
    assert len(features) == 2
    assert features[0].name == "auth"
    assert features[1].name == "api"
    assert features[0].priority == 1
    assert features[1].priority == 2


def test_update_feature_status(tmp_path):
    """Test updating feature pass/fail status"""
    tracker = ProgressTracker(tmp_path)
    
    # Add feature
    tracker.add_feature("auth", "User authentication")
    
    # Update status
    updated = tracker.update_feature_status("auth", passes=True)
    assert updated is True
    
    # Verify
    features = tracker.load_feature_list()
    assert features[0].passes is True
    
    # Update to False
    tracker.update_feature_status("auth", passes=False)
    features = tracker.load_feature_list()
    assert features[0].passes is False


def test_get_next_feature(tmp_path):
    """Test getting highest-priority incomplete feature"""
    tracker = ProgressTracker(tmp_path)
    
    # Add features with different priorities
    tracker.add_feature("low_priority", "Low priority task", priority=5)
    tracker.add_feature("high_priority", "High priority task", priority=1)
    tracker.add_feature("medium_priority", "Medium priority task", priority=3)
    
    # Mark high_priority as complete
    tracker.update_feature_status("high_priority", passes=True)
    
    # Get next feature (should be medium_priority, not low_priority)
    next_feature = tracker.get_next_feature()
    assert next_feature is not None
    assert next_feature.name == "medium_priority"
    assert next_feature.priority == 3


def test_get_next_feature_all_complete(tmp_path):
    """Test get_next_feature returns None when all complete"""
    tracker = ProgressTracker(tmp_path)
    
    tracker.add_feature("task1", "Task 1")
    tracker.add_feature("task2", "Task 2")
    
    # Mark all as complete
    tracker.update_feature_status("task1", passes=True)
    tracker.update_feature_status("task2", passes=True)
    
    # Should return None
    next_feature = tracker.get_next_feature()
    assert next_feature is None


def test_get_progress_summary(tmp_path):
    """Test progress summary statistics"""
    tracker = ProgressTracker(tmp_path)
    
    tracker.add_feature("task1", "Task 1", priority=1)
    tracker.add_feature("task2", "Task 2", priority=2)
    tracker.add_feature("task3", "Task 3", priority=3)
    
    tracker.update_feature_status("task1", passes=True)
    tracker.log_progress("Some progress")
    
    summary = tracker.get_progress_summary()
    
    assert summary["total_features"] == 3
    assert summary["passed_features"] == 1
    assert summary["incomplete_features"] == 2
    assert summary["completion_rate"] == pytest.approx(1.0 / 3.0, rel=0.01)
    assert summary["next_feature"] == "task2"  # Next incomplete by priority


def test_read_recent_progress(tmp_path):
    """Test reading recent progress entries"""
    tracker = ProgressTracker(tmp_path)
    
    # Log multiple messages
    for i in range(15):
        tracker.log_progress(f"Message {i}")
    
    # Read last 10
    recent = tracker.read_recent_progress(lines=10)
    assert len(recent) == 10
    assert "Message 5" in recent[0]  # First of last 10
    assert "Message 14" in recent[-1]  # Last message


def test_duplicate_feature_prevention(tmp_path):
    """Test that adding duplicate feature is ignored"""
    tracker = ProgressTracker(tmp_path)
    
    tracker.add_feature("auth", "Authentication")
    tracker.add_feature("auth", "Authentication")  # Duplicate
    
    features = tracker.load_feature_list()
    assert len(features) == 1  # Only one feature


def test_feature_priority_sorting(tmp_path):
    """Test that get_next_feature sorts by priority correctly"""
    tracker = ProgressTracker(tmp_path)
    
    # Add features in non-priority order
    tracker.add_feature("z_last", "Last", priority=10)
    tracker.add_feature("a_first", "First", priority=1)
    tracker.add_feature("m_middle", "Middle", priority=5)
    
    # All incomplete, should get highest priority (lowest number)
    next_feature = tracker.get_next_feature()
    assert next_feature.name == "a_first"
    assert next_feature.priority == 1


def test_corrupted_feature_list_recovery(tmp_path):
    """Test recovery from corrupted feature_list.json"""
    tracker = ProgressTracker(tmp_path)
    
    # Corrupt the file
    with open(tracker.feature_list_file, 'w') as f:
        f.write("invalid json{")
    
    # Should return empty list, not crash
    features = tracker.load_feature_list()
    assert isinstance(features, list)
    assert len(features) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

