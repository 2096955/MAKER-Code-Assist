#!/usr/bin/env python3
"""
Session management for long-running agent sessions.

Implements Anthropic's resumability protocol:
1. Orient (pwd, git log)
2. Read progress files
3. Select next feature
4. Create resume context

Usage:
    manager = SessionManager(progress_tracker)
    context = manager.create_resume_context()
    is_clean = manager.verify_clean_state()
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, Optional
from orchestrator.progress_tracker import ProgressTracker


class SessionManager:
    """
    Manages session resumability for long-running agent work.
    
    Creates orientation context that helps agents resume work
    after interruptions.
    """
    
    def __init__(self, progress_tracker: ProgressTracker):
        """
        Initialize session manager.
        
        Args:
            progress_tracker: ProgressTracker instance for reading progress
        """
        self.progress_tracker = progress_tracker
    
    def create_resume_context(self) -> str:
        """
        Create resume context following Anthropic's protocol.
        
        Returns:
            Formatted string with orientation information
        """
        # 1. Get working directory
        cwd = os.getcwd()
        
        # 2. Read recent progress
        recent_progress = self.progress_tracker.read_recent_progress(lines=10)
        progress_text = "\n".join(recent_progress) if recent_progress else "No recent progress"
        
        # 3. Read git log
        git_log = self._get_git_log(lines=5)
        
        # 4. Get next feature
        next_feature = self.progress_tracker.get_next_feature()
        if next_feature:
            feature_text = f"{next_feature.name}: {next_feature.description} (priority: {next_feature.priority})"
        else:
            feature_text = "No incomplete features remaining"
        
        # 5. Get progress summary
        summary = self.progress_tracker.get_progress_summary()
        
        # Construct resume context
        context = f"""You are resuming work on this project.

Working directory: {cwd}

Recent progress (last 10 entries):
{progress_text}

Recent git commits (last 5):
{git_log}

Progress summary:
- Total features: {summary['total_features']}
- Completed: {summary['passed_features']}
- Remaining: {summary['incomplete_features']}
- Completion rate: {summary['completion_rate']:.0%}

Next feature to implement:
{feature_text}

Continue working on this feature. Do not start new features unless explicitly requested."""
        
        return context
    
    def resume_session(self, session_id: str) -> Dict[str, str]:
        """
        Resume a session and return context information.
        
        Args:
            session_id: Session identifier
        
        Returns:
            Dictionary with resume context and metadata
        """
        context = self.create_resume_context()
        is_clean = self.verify_clean_state()
        
        return {
            "session_id": session_id,
            "resume_context": context,
            "is_clean": is_clean,
            "working_directory": os.getcwd(),
            "next_feature": self.progress_tracker.get_next_feature().name if self.progress_tracker.get_next_feature() else None
        }
    
    def verify_clean_state(self) -> bool:
        """
        Verify if workspace is in a clean state (safe to continue).
        
        Checks:
        - Git working tree is clean (no uncommitted changes)
        - No obvious errors in recent progress
        
        Returns:
            True if state is clean, False if there are issues
        """
        # Check git status
        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # If there are uncommitted changes, state is not clean
            if result.returncode == 0 and result.stdout.strip():
                return False
            
            # Check for recent errors in progress
            recent_progress = self.progress_tracker.read_recent_progress(lines=5)
            error_indicators = ['error', 'failed', 'exception', 'traceback']
            for entry in recent_progress:
                if any(indicator in entry.lower() for indicator in error_indicators):
                    return False
            
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            # If git is not available or times out, assume clean
            # (not all projects use git)
            return True
    
    def _get_git_log(self, lines: int = 5) -> str:
        """
        Get recent git commit log.
        
        Args:
            lines: Number of commits to retrieve
        
        Returns:
            Formatted git log string, or empty string if git unavailable
        """
        try:
            result = subprocess.run(
                ['git', 'log', f'-{lines}', '--oneline', '--no-decorate'],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=os.getcwd()
            )
            
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            else:
                return "No git history available"
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return "Git not available"
    
    def get_orientation_info(self) -> Dict[str, str]:
        """
        Get basic orientation information.
        
        Returns:
            Dictionary with current state information
        """
        return {
            "working_directory": os.getcwd(),
            "git_branch": self._get_git_branch(),
            "git_status": self._get_git_status(),
            "next_feature": self.progress_tracker.get_next_feature().name if self.progress_tracker.get_next_feature() else None,
            "is_clean": self.verify_clean_state()
        }
    
    def _get_git_branch(self) -> str:
        """Get current git branch name"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.SubprocessError, OSError, FileNotFoundError):
            pass
        return "unknown"
    
    def _get_git_status(self) -> str:
        """Get git status summary"""
        try:
            result = subprocess.run(
                ['git', 'status', '--short'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                status = result.stdout.strip()
                return status if status else "clean"
        except (subprocess.SubprocessError, OSError, FileNotFoundError):
            pass
        return "unknown"

