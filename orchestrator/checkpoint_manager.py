#!/usr/bin/env python3
"""
Checkpoint management for long-running agent sessions.

Creates clean checkpoints with git commits after successful feature completion.

Usage:
    manager = CheckpointManager(progress_tracker, redis_client)
    result = await manager.create_checkpoint("auth", code_string)
"""

import os
import subprocess
import json
from typing import Dict, Optional, Any, List
from orchestrator.progress_tracker import ProgressTracker


class CheckpointManager:
    """
    Manages checkpoints for long-running agent sessions.
    
    Creates clean git commits after verifying tests pass and
    updates feature status in progress tracker.
    """
    
    def __init__(self, progress_tracker: ProgressTracker, redis_client=None):
        """
        Initialize checkpoint manager.
        
        Args:
            progress_tracker: ProgressTracker instance
            redis_client: Optional Redis client for session state
        """
        self.progress_tracker = progress_tracker
        self.redis = redis_client
    
    async def create_checkpoint(
        self, 
        feature_name: str, 
        code: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a clean checkpoint for a completed feature.
        
        Checkpoint flow:
        1. Verify all tests pass
        2. Git commit with descriptive message
        3. Update feature status to passes=true
        4. Log progress
        5. Save session state to Redis (if available)
        
        Args:
            feature_name: Name of the feature being checkpointed
            code: Optional code content (for generating commit summary)
            session_id: Optional session ID for Redis storage
        
        Returns:
            Dictionary with checkpoint results
        """
        result = {
            "feature_name": feature_name,
            "success": False,
            "commit_hash": None,
            "error": None
        }
        
        try:
            # Step 1: Verify tests pass
            if not await self.verify_tests_pass():
                result["error"] = "Tests are failing, cannot create checkpoint"
                self.progress_tracker.log_progress(
                    f"Checkpoint failed for '{feature_name}': Tests failing"
                )
                return result
            
            # Step 2: Generate commit message
            commit_message = self._generate_commit_message(feature_name, code)
            
            # Step 3: Git commit
            commit_hash = self.commit_changes(commit_message)
            if not commit_hash:
                result["error"] = "Git commit failed"
                return result
            
            result["commit_hash"] = commit_hash
            
            # Step 4: Update feature status
            self.progress_tracker.update_feature_status(feature_name, passes=True)
            
            # Step 5: Log progress
            self.progress_tracker.log_progress(
                f"Checkpoint created for '{feature_name}' (commit: {commit_hash[:8]})"
            )
            
            # Step 6: Save session state to Redis (if available)
            if self.redis and session_id:
                try:
                    checkpoint_data = {
                        "feature_name": feature_name,
                        "commit_hash": commit_hash,
                        "timestamp": self._get_timestamp()
                    }
                    self.redis.set(
                        f"checkpoint:{session_id}:{feature_name}",
                        json.dumps(checkpoint_data)
                    )
                    self.redis.expire(f"checkpoint:{session_id}:{feature_name}", 86400 * 7)  # 7 days
                except Exception as e:
                    # Redis failure shouldn't block checkpoint
                    self.progress_tracker.log_progress(
                        f"Warning: Failed to save checkpoint to Redis: {e}"
                    )
            
            result["success"] = True
            return result
            
        except Exception as e:
            result["error"] = str(e)
            self.progress_tracker.log_progress(
                f"Checkpoint error for '{feature_name}': {e}"
            )
            return result
    
    async def verify_tests_pass(self) -> bool:
        """
        Verify that all tests pass before checkpointing.
        
        Returns:
            True if tests pass, False otherwise
        """
        # Try common test commands
        test_commands = [
            ['python', '-m', 'pytest'],
            ['pytest'],
            ['python', '-m', 'unittest', 'discover'],
            ['npm', 'test'],  # For Node.js projects
        ]
        
        test_found = False
        for cmd in test_commands:
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=os.getcwd()
                )
                
                # Command exists (didn't raise FileNotFoundError)
                test_found = True
                
                # Check if tests actually passed
                if result.returncode == 0:
                    # More strict: look for actual test results
                    output_lower = result.stdout.lower()
                    # Pytest format: "X passed" or "X failed"
                    # Unittest format: "OK" or "FAILED"
                    # npm test: "Tests: X passed"
                    
                    # Check for failure indicators first (more reliable)
                    if any(failure in output_lower for failure in [
                        "failed",
                        "error",
                        "errors",
                        "failures",
                        "test failed"
                    ]):
                        return False
                    
                    # Check for success indicators (more specific patterns)
                    success_patterns = [
                        " passed",  # pytest: "5 passed"
                        "test passed",  # explicit pass
                        "all tests passed",  # explicit all pass
                        "tests passed",  # npm style
                        "ok" if "test" in output_lower else None,  # unittest "OK" only if "test" also present
                    ]
                    success_patterns = [p for p in success_patterns if p]  # Remove None
                    
                    if any(pattern in output_lower for pattern in success_patterns):
                        return True
                    
                    # If returncode is 0 but no clear success pattern, be cautious
                    # (might be help text or other output)
                    return False
                else:
                    # Tests ran but failed (non-zero exit code)
                    return False
            except FileNotFoundError:
                # Command doesn't exist, try next
                continue
            except (subprocess.TimeoutExpired, Exception) as e:
                # Test command exists but failed to run
                self.progress_tracker.log_progress(
                    f"Warning: Test command {cmd} failed: {e}"
                )
                continue
        
        # If no test command found, we can't verify tests
        # This is a safety measure: don't assume tests pass if we can't run them
        if not test_found:
            self.progress_tracker.log_progress(
                "Warning: No test command found. Cannot verify tests pass."
            )
            # Return False to be safe (user can override if needed)
            return False
        
        # If we got here, tests were found but didn't pass
        return False
    
    def commit_changes(self, message: str) -> Optional[str]:
        """
        Commit changes to git with the given message.
        
        Args:
            message: Commit message
        
        Returns:
            Commit hash if successful, None otherwise
        """
        try:
            # Check if git is available
            subprocess.run(
                ['git', '--version'],
                capture_output=True,
                check=True,
                timeout=5
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
            # Git not available, skip commit
            self.progress_tracker.log_progress("Warning: Git not available, skipping commit")
            return None
        
        try:
            # Stage all changes
            subprocess.run(
                ['git', 'add', '.'],
                capture_output=True,
                check=True,
                timeout=10,
                cwd=os.getcwd()
            )
            
            # Check if there are changes to commit
            status_result = subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=os.getcwd()
            )
            
            if not status_result.stdout.strip():
                # No changes to commit
                self.progress_tracker.log_progress("No changes to commit")
                return None
            
            # Create commit
            commit_result = subprocess.run(
                ['git', 'commit', '-m', message],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
                cwd=os.getcwd()
            )
            
            # Get commit hash
            hash_result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
                cwd=os.getcwd()
            )
            
            commit_hash = hash_result.stdout.strip()
            return commit_hash
            
        except subprocess.CalledProcessError as e:
            self.progress_tracker.log_progress(f"Git commit failed: {e.stderr}")
            return None
        except subprocess.TimeoutExpired:
            self.progress_tracker.log_progress("Git commit timed out")
            return None
        except Exception as e:
            self.progress_tracker.log_progress(f"Git commit error: {e}")
            return None
    
    def _generate_commit_message(self, feature_name: str, code: Optional[str] = None) -> str:
        """
        Generate commit message following conventional commits format.
        
        Args:
            feature_name: Name of the feature
            code: Optional code content for summary generation
        
        Returns:
            Formatted commit message
        """
        # Base message
        message = f"feat: Complete {feature_name}\n\n"
        
        # Try to generate summary from code
        if code:
            summary = self._summarize_code_changes(code)
            if summary:
                message += f"{summary}\n\n"
        
        # Add MAKER signature
        message += " Generated by MAKER Multi-Agent System"
        
        return message
    
    def _summarize_code_changes(self, code: str) -> str:
        """
        Generate a brief summary of code changes.
        
        Args:
            code: Code content
        
        Returns:
            Brief summary string
        """
        # Simple heuristic: count functions/classes added
        lines = code.split('\n')
        functions = sum(1 for line in lines if line.strip().startswith('def '))
        classes = sum(1 for line in lines if line.strip().startswith('class '))
        
        summary_parts = []
        if functions > 0:
            summary_parts.append(f"Added {functions} function{'s' if functions > 1 else ''}")
        if classes > 0:
            summary_parts.append(f"Added {classes} class{'es' if classes > 1 else ''}")
        
        if summary_parts:
            return ", ".join(summary_parts) + "."
        
        # Fallback: count lines
        if len(lines) > 10:
            return f"Added {len(lines)} lines of code."
        
        return ""
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def get_checkpoint_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get checkpoint history for a session.
        
        Args:
            session_id: Session identifier
        
        Returns:
            List of checkpoint dictionaries
        """
        if not self.redis:
            return []
        
        try:
            checkpoints = []
            pattern = f"checkpoint:{session_id}:*"
            
            for key in self.redis.scan_iter(match=pattern):
                data = self.redis.get(key)
                if data:
                    checkpoints.append(json.loads(data))
            
            # Sort by timestamp
            checkpoints.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return checkpoints
        except Exception:
            return []

