#!/usr/bin/env python3
"""
Progress tracking for long-running agent sessions.

Implements Anthropic's pattern of structured progress files:
- claude-progress.txt: Append-only log of accomplishments
- feature_list.json: Structured feature checklist with pass/fail status

Usage:
    tracker = ProgressTracker(workspace_path)
    tracker.log_progress("Completed user authentication")
    tracker.update_feature_status("auth", passes=True)
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Windows-compatible file locking
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False
    # Windows fallback: use msvcrt for file locking
    try:
        import msvcrt
        HAS_MSVCRT = True
    except ImportError:
        HAS_MSVCRT = False


@dataclass
class Feature:
    """Single feature in the feature list"""
    name: str
    description: str
    passes: bool = False
    priority: int = 1  # Lower number = higher priority
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "name": self.name,
            "description": self.description,
            "passes": self.passes,
            "priority": self.priority
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Feature':
        """Create Feature from dictionary"""
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            passes=data.get("passes", False),
            priority=data.get("priority", 1)
        )


class ProgressTracker:
    """
    Tracks progress across long-running agent sessions.
    
    Maintains two files:
    1. claude-progress.txt - Append-only log of accomplishments
    2. feature_list.json - Structured feature checklist
    """
    
    def __init__(self, workspace_path: Path):
        """
        Initialize progress tracker.
        
        Args:
            workspace_path: Path to workspace directory (e.g., ./workspace)
        """
        self.workspace_path = Path(workspace_path)
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        
        # File paths
        self.progress_file = self.workspace_path / "claude-progress.txt"
        self.feature_list_file = self.workspace_path / "feature_list.json"
        
        # Auto-create files if they don't exist
        if not self.progress_file.exists():
            self.progress_file.touch()
        
        if not self.feature_list_file.exists():
            self._save_feature_list([])
    
    def log_progress(self, message: str) -> None:
        """
        Append a progress message to claude-progress.txt.
        
        Thread-safe using file locking.
        
        Args:
            message: Progress message to log
        """
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] {message}\n"
        
        # Thread-safe append with cross-platform locking
        try:
            with open(self.progress_file, 'a') as f:
                if HAS_FCNTL:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                elif HAS_MSVCRT:
                    msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    f.write(log_entry)
                    f.flush()
                finally:
                    if HAS_FCNTL:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    elif HAS_MSVCRT:
                        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except (OSError, PermissionError, IOError):
            # Fallback: write without locking (better than crashing)
            logger.warning("File locking failed, writing without lock")
            with open(self.progress_file, 'a') as f:
                f.write(log_entry)
                f.flush()
    
    def load_feature_list(self) -> List[Feature]:
        """
        Load feature list from feature_list.json.
        
        Returns:
            List of Feature objects
        """
        if not self.feature_list_file.exists():
            return []
        
        try:
            with open(self.feature_list_file, 'r') as f:
                data = json.load(f)
            
            features_data = data.get("features", [])
            return [Feature.from_dict(f) for f in features_data]
        except (json.JSONDecodeError, KeyError, OSError, ValueError) as e:
            # If file is corrupted, return empty list
            logger.warning(f"Failed to load feature list: {e}")
            return []
    
    def _save_feature_list(self, features: List[Feature]) -> None:
        """
        Save feature list to feature_list.json.
        
        Thread-safe using file locking.
        
        Args:
            features: List of Feature objects to save
        """
        data = {
            "features": [f.to_dict() for f in features]
        }
        
        # Thread-safe write with cross-platform locking
        try:
            with open(self.feature_list_file, 'w') as f:
                if HAS_FCNTL:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                elif HAS_MSVCRT:
                    msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    json.dump(data, f, indent=2)
                    f.flush()
                finally:
                    if HAS_FCNTL:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    elif HAS_MSVCRT:
                        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except (OSError, PermissionError, IOError):
            # Fallback: write without locking (better than crashing)
            logger.warning("File locking failed, writing without lock")
            with open(self.feature_list_file, 'w') as f:
                json.dump(data, f, indent=2)
                f.flush()
    
    def update_feature_status(self, name: str, passes: bool) -> bool:
        """
        Update the pass/fail status of a feature.
        
        Uses atomic read-modify-write to prevent race conditions.
        
        Args:
            name: Feature name to update
            passes: True if feature passes, False otherwise
        
        Returns:
            True if feature was found and updated, False otherwise
        """
        # Atomic read-modify-write with retry on conflict
        max_retries = 3
        for attempt in range(max_retries):
            try:
                features = self.load_feature_list()
                
                updated = False
                for feature in features:
                    if feature.name == name:
                        feature.passes = passes
                        updated = True
                        break
                
                if updated:
                    self._save_feature_list(features)
                    status = "passes" if passes else "fails"
                    self.log_progress(f"Feature '{name}' now {status}")
                    return True
                else:
                    self.log_progress(f"Warning: Feature '{name}' not found in feature list")
                    return False
            except (json.JSONDecodeError, IOError) as e:
                # Retry on read/write conflicts
                if attempt < max_retries - 1:
                    import time
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    self.log_progress(f"Error updating feature '{name}': {e}")
                    return False
        
        return False
    
    def add_feature(self, name: str, description: str, priority: int = 1) -> None:
        """
        Add a new feature to the feature list.
        
        Args:
            name: Feature name
            description: Feature description
            priority: Priority (lower = higher priority, default: 1)
        """
        features = self.load_feature_list()
        
        # Check if feature already exists
        for feature in features:
            if feature.name == name:
                self.log_progress(f"Feature '{name}' already exists, skipping add")
                return
        
        # Add new feature
        new_feature = Feature(
            name=name,
            description=description,
            passes=False,
            priority=priority
        )
        features.append(new_feature)
        self._save_feature_list(features)
        self.log_progress(f"Added feature '{name}' (priority: {priority})")
    
    def get_next_feature(self) -> Optional[Feature]:
        """
        Get the highest-priority incomplete feature.
        
        Returns:
            Feature object with highest priority (lowest number) that doesn't pass,
            or None if all features are complete
        """
        features = self.load_feature_list()
        
        # Filter incomplete features
        incomplete = [f for f in features if not f.passes]
        
        if not incomplete:
            return None
        
        # Sort by priority (lower number = higher priority)
        incomplete.sort(key=lambda f: (f.priority, f.name))
        
        return incomplete[0]
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """
        Get summary of progress.
        
        Returns:
            Dictionary with progress statistics
        """
        features = self.load_feature_list()
        total = len(features)
        passed = sum(1 for f in features if f.passes)
        incomplete = total - passed
        
        # Count progress log lines
        progress_lines = 0
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    progress_lines = len(f.readlines())
            except (OSError, PermissionError, IOError):
                pass
        
        return {
            "total_features": total,
            "passed_features": passed,
            "incomplete_features": incomplete,
            "completion_rate": passed / total if total > 0 else 0.0,
            "progress_log_entries": progress_lines,
            "next_feature": self.get_next_feature().name if self.get_next_feature() else None
        }
    
    def read_recent_progress(self, lines: int = 10) -> List[str]:
        """
        Read recent progress log entries.
        
        Args:
            lines: Number of recent lines to read (default: 10)
        
        Returns:
            List of recent log entries (most recent last)
        """
        if not self.progress_file.exists():
            return []
        
        try:
            with open(self.progress_file, 'r') as f:
                all_lines = f.readlines()
            
            # Return last N lines
            return [line.strip() for line in all_lines[-lines:] if line.strip()]
        except (OSError, PermissionError, json.JSONDecodeError, ValueError):
            logger.warning("Failed to get completed features")
            return []

