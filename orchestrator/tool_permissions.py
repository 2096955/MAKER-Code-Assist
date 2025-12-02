#!/usr/bin/env python3
"""
Tool Permissions: Declarative tool whitelisting/blacklisting per project (Crush pattern).

Supports .maker.json configuration:
{
  "allowed_tools": ["read_file", "search_docs"],
  "blocked_tools": ["run_tests"]
}
"""

import json
import os
from pathlib import Path
from typing import List, Set, Optional, Dict
from functools import lru_cache


class ToolPermissions:
    """Manages tool permissions from .maker.json config files"""
    
    def __init__(self, codebase_root: str = "."):
        self.codebase_root = Path(codebase_root).resolve()
        self._config_cache: Optional[Dict] = None
    
    @lru_cache(maxsize=1)
    def _load_config(self) -> Dict:
        """
        Load .maker.json config with hierarchy:
        1. Project .maker.json (codebase root)
        2. Global ~/.config/maker/.maker.json (if exists)
        
        Returns:
            Merged configuration dictionary
        """
        config = {
            "allowed_tools": None,  # None = allow all
            "blocked_tools": []    # Empty = block none
        }
        
        # 1. Load project config
        project_config_path = self.codebase_root / ".maker.json"
        if project_config_path.exists():
            try:
                with open(project_config_path, 'r') as f:
                    project_config = json.load(f)
                    if "allowed_tools" in project_config:
                        config["allowed_tools"] = project_config["allowed_tools"]
                    if "blocked_tools" in project_config:
                        config["blocked_tools"].extend(project_config["blocked_tools"])
            except Exception as e:
                print(f"Warning: Failed to load .maker.json: {e}")
        
        # 2. Load global config (if exists)
        global_config_path = Path.home() / ".config" / "maker" / ".maker.json"
        if global_config_path.exists():
            try:
                with open(global_config_path, 'r') as f:
                    global_config = json.load(f)
                    # Global config can only add to blocked_tools (safety)
                    if "blocked_tools" in global_config:
                        config["blocked_tools"].extend(global_config["blocked_tools"])
                    # Global allowed_tools is ignored (project takes precedence)
            except Exception as e:
                print(f"Warning: Failed to load global .maker.json: {e}")
        
        # Deduplicate blocked_tools
        config["blocked_tools"] = list(set(config["blocked_tools"]))
        
        return config
    
    def is_tool_allowed(self, tool_name: str) -> bool:
        """
        Check if a tool is allowed based on configuration.
        
        Args:
            tool_name: Name of the tool to check
            
        Returns:
            True if tool is allowed, False if blocked
        """
        config = self._load_config()
        
        # Check blocked list first (highest priority)
        if tool_name in config["blocked_tools"]:
            return False
        
        # Check allowed list (if specified)
        if config["allowed_tools"] is not None:
            return tool_name in config["allowed_tools"]
        
        # Default: allow all (if no allowed_tools specified)
        return True
    
    def get_allowed_tools(self, all_tools: List[str]) -> List[str]:
        """
        Filter list of tools to only include allowed ones.
        
        Args:
            all_tools: List of all available tools
            
        Returns:
            Filtered list of allowed tools
        """
        return [tool for tool in all_tools if self.is_tool_allowed(tool)]
    
    def get_blocked_tools(self) -> List[str]:
        """
        Get list of blocked tools.
        
        Returns:
            List of blocked tool names
        """
        config = self._load_config()
        return config["blocked_tools"]
    
    def get_config_summary(self) -> Dict:
        """
        Get summary of current tool permissions configuration.
        
        Returns:
            Dictionary with config summary
        """
        config = self._load_config()
        return {
            "allowed_tools": config["allowed_tools"],
            "blocked_tools": config["blocked_tools"],
            "mode": "whitelist" if config["allowed_tools"] is not None else "blacklist"
        }

