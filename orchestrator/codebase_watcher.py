#!/usr/bin/env python3
"""
Codebase Watcher: Real-time file system monitoring for world model updates

Uses watchdog library to monitor codebase changes and trigger world model updates.
Includes debouncing to prevent excessive updates from rapid file saves.
"""

from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler, FileSystemEvent
from pathlib import Path
from typing import Callable, Optional, Set, Dict
import logging
from threading import Timer
from collections import defaultdict
import time

logger = logging.getLogger(__name__)


class CodebaseWatcher(PatternMatchingEventHandler):
    """Watch for codebase changes and update world model with debouncing"""
    
    def __init__(
        self,
        codebase_root: str,
        update_callback: Callable[[str, bool], None],  # (file_path, deleted)
        debounce_ms: int = 500,
        ignore_patterns: Optional[list] = None
    ):
        """
        Initialize codebase watcher.
        
        Args:
            codebase_root: Root directory to watch
            update_callback: Function to call when file changes (takes relative file path)
            debounce_ms: Debounce window in milliseconds (default: 500ms)
            ignore_patterns: Additional patterns to ignore (beyond defaults)
        """
        self.codebase_root = Path(codebase_root).resolve()
        self.update_callback = update_callback
        self.debounce_delay = debounce_ms / 1000.0  # Convert to seconds
        
        # Default ignore patterns
        default_ignores = [
            "*.pyc",
            "__pycache__",
            ".git",
            ".DS_Store",
            "*.swp",
            "*.swo",
            "*~",
            ".venv",
            "venv",
            "env",
            ".env",
            "node_modules",
            ".idea",
            ".vscode",
            "*.log",
            "dist",
            "build",
            ".pytest_cache",
            ".mypy_cache",
            "*.egg-info"
        ]
        
        ignore_patterns = ignore_patterns or []
        all_ignores = default_ignores + ignore_patterns
        
        # Initialize PatternMatchingEventHandler
        super().__init__(
            patterns=["*.py", "*.js", "*.ts", "*.jsx", "*.tsx"],  # Watch these extensions
            ignore_patterns=all_ignores,
            ignore_directories=True,  # Only watch files, not directory changes
            case_sensitive=False
        )
        
        self.observer: Optional[Observer] = None
        self.debounce_timers: Dict[str, Timer] = {}
        self.pending_changes: Dict[str, bool] = {}  # path -> deleted
        
    def on_modified(self, event: FileSystemEvent):
        """Handle file modification"""
        if event.is_directory:
            return
        self._schedule_update(event.src_path, deleted=False)
    
    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion"""
        if event.is_directory:
            return
        self._schedule_update(event.src_path, deleted=True)
    
    def _schedule_update(self, file_path: str, deleted: bool):
        """Debounce file updates - wait 500ms after last change"""
        # Cancel existing timer for this file
        if file_path in self.debounce_timers:
            self.debounce_timers[file_path].cancel()
        
        # Store pending change
        self.pending_changes[file_path] = deleted
        
        # Schedule new timer
        timer = Timer(self.debounce_delay, self._process_update, args=[file_path])
        self.debounce_timers[file_path] = timer
        timer.start()
    
    def _process_update(self, file_path: str):
        """Process update after debounce delay"""
        if file_path not in self.pending_changes:
            return
        
        deleted = self.pending_changes.pop(file_path)
        self.debounce_timers.pop(file_path, None)
        
        # Get relative path
        try:
            rel_path = Path(file_path).relative_to(self.codebase_root)
            logger.info(f"Processing {'deleted' if deleted else 'modified'} file: {rel_path}")
            self.update_callback(str(rel_path), deleted=deleted)
        except ValueError:
            pass  # File not in codebase
        except Exception as e:
            logger.error(f"Error in update callback: {e}")
    
    def start(self):
        """Start watching codebase"""
        if self.observer and self.observer.is_alive():
            logger.warning("Watcher already running")
            return
        
        self.observer = Observer()
        self.observer.schedule(self, str(self.codebase_root), recursive=True)
        self.observer.start()
        logger.info(f"Started watching codebase: {self.codebase_root}")
    
    def stop(self):
        """Stop watching"""
        # Cancel all pending timers
        for timer in self.debounce_timers.values():
            timer.cancel()
        self.debounce_timers.clear()
        self.pending_changes.clear()
        
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)
            logger.info("Stopped watching codebase")
        
        self.observer = None

