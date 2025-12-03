#!/usr/bin/env python3
"""
Configuration Loader

Handles loading, validating, and providing access to application configuration.
Supports multiple sources like environment variables, config files, and CLI arguments.

Configuration hierarchy (highest priority first):
1. Environment variables
2. Project-level: .maker.json in project root
3. Global-level: ~/.maker/config.json
4. Defaults: Built-in defaults from schema
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

from orchestrator.config_schema import MakerAppConfig, CodeAnalysisConfig, TerminalConfig, GitConfig, EditorConfig, MakerConfig, PathsConfig

logger = logging.getLogger(__name__)


def get_config_paths(workspace: Optional[str] = None) -> List[Path]:
    """
    Get list of configuration file paths to check, in priority order.
    
    Returns:
        List of paths to check (highest priority first)
    """
    paths = []
    
    # 1. Project-level config (highest priority for project-specific settings)
    if workspace:
        project_config = Path(workspace) / '.maker.json'
        if project_config.exists():
            paths.append(project_config)
    else:
        # Try current working directory
        cwd_config = Path.cwd() / '.maker.json'
        if cwd_config.exists():
            paths.append(cwd_config)
    
    # 2. Global config in home directory
    home = Path.home()
    global_config = home / '.maker' / 'config.json'
    if global_config.exists():
        paths.append(global_config)
    
    # 3. XDG config directory (Linux/macOS)
    xdg_config_home = os.getenv('XDG_CONFIG_HOME')
    if xdg_config_home:
        xdg_config = Path(xdg_config_home) / 'maker' / 'config.json'
        if xdg_config.exists():
            paths.append(xdg_config)
    else:
        # Default XDG location
        xdg_config = home / '.config' / 'maker' / 'config.json'
        if xdg_config.exists():
            paths.append(xdg_config)
    
    # 4. Windows AppData directory
    appdata = os.getenv('APPDATA')
    if appdata:
        appdata_config = Path(appdata) / 'maker' / 'config.json'
        if appdata_config.exists():
            paths.append(appdata_config)
    
    return paths


def load_config_from_file(config_path: Path) -> Optional[Dict[str, Any]]:
    """
    Load configuration from a JSON file.
    
    Args:
        config_path: Path to config file
        
    Returns:
        Config dict or None if file doesn't exist or is invalid
    """
    try:
        if not config_path.exists():
            return None
        
        logger.debug(f"Loading configuration from {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        return config
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in config file {config_path}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error loading configuration from {config_path}: {e}")
        return None


def load_config_from_env() -> Dict[str, Any]:
    """
    Load configuration from environment variables.
    
    Returns:
        Config dict with environment variable values
    """
    env_config: Dict[str, Any] = {}
    
    # Log level
    if log_level := os.getenv('MAKER_LOG_LEVEL'):
        env_config['log_level'] = log_level.lower()
    
    # Workspace
    if workspace := os.getenv('MAKER_WORKSPACE'):
        env_config['workspace'] = workspace
    
    # MAKER mode
    if maker_mode := os.getenv('MAKER_MODE'):
        env_config['maker'] = env_config.get('maker', {})
        env_config['maker']['maker_mode'] = maker_mode.lower()
    
    # MAKER voting parameters
    if num_candidates := os.getenv('MAKER_NUM_CANDIDATES'):
        try:
            env_config['maker'] = env_config.get('maker', {})
            env_config['maker']['num_candidates'] = int(num_candidates)
        except ValueError:
            logger.warning(f"Invalid MAKER_NUM_CANDIDATES: {num_candidates}")
    
    if vote_k := os.getenv('MAKER_VOTE_K'):
        try:
            env_config['maker'] = env_config.get('maker', {})
            env_config['maker']['vote_k'] = int(vote_k)
        except ValueError:
            logger.warning(f"Invalid MAKER_VOTE_K: {vote_k}")
    
    # Context compression
    if max_context := os.getenv('MAX_CONTEXT_TOKENS'):
        try:
            env_config['maker'] = env_config.get('maker', {})
            env_config['maker']['max_context_tokens'] = int(max_context)
        except ValueError:
            logger.warning(f"Invalid MAX_CONTEXT_TOKENS: {max_context}")
    
    if recent_window := os.getenv('RECENT_WINDOW_TOKENS'):
        try:
            env_config['maker'] = env_config.get('maker', {})
            env_config['maker']['recent_window_tokens'] = int(recent_window)
        except ValueError:
            logger.warning(f"Invalid RECENT_WINDOW_TOKENS: {recent_window}")
    
    # Code analysis
    if index_depth := os.getenv('CODE_ANALYSIS_INDEX_DEPTH'):
        try:
            env_config['code_analysis'] = env_config.get('code_analysis', {})
            env_config['code_analysis']['index_depth'] = int(index_depth)
        except ValueError:
            logger.warning(f"Invalid CODE_ANALYSIS_INDEX_DEPTH: {index_depth}")
    
    # Git
    if git_remote := os.getenv('GIT_PREFERRED_REMOTE'):
        env_config['git'] = env_config.get('git', {})
        env_config['git']['preferred_remote'] = git_remote
    
    if sign_commits := os.getenv('GIT_SIGN_COMMITS'):
        env_config['git'] = env_config.get('git', {})
        env_config['git']['sign_commits'] = sign_commits.lower() in ('true', '1', 'yes')
    
    return env_config


def merge_configs(*configs: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Deep merge multiple configuration dictionaries.
    Later configs override earlier ones.
    
    Args:
        *configs: Configuration dicts to merge (in priority order)
        
    Returns:
        Merged configuration dict
    """
    result: Dict[str, Any] = {}
    
    for config in configs:
        if not config:
            continue
        
        for key, value in config.items():
            if value is None:
                continue
            
            # Recursively merge nested objects
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = merge_configs(result[key], value)
            else:
                # Overwrite primitives, arrays, etc.
                result[key] = value
    
    return result


def populate_paths_config(workspace: Optional[str] = None) -> PathsConfig:
    """
    Populate paths configuration at runtime.
    
    Args:
        workspace: Workspace directory path
        
    Returns:
        PathsConfig with populated paths
    """
    home = Path.home()
    
    return PathsConfig(
        home=str(home),
        app=str(home / '.maker'),
        cache=str(home / '.maker' / 'cache'),
        logs=str(home / '.maker' / 'logs'),
        workspace=workspace
    )


def load_config(
    workspace: Optional[str] = None,
    config_file: Optional[str] = None,
    **overrides: Any
) -> MakerAppConfig:
    """
    Load configuration from all sources and merge them.
    
    Configuration priority (highest to lowest):
    1. Function overrides (kwargs)
    2. Environment variables
    3. Project-level .maker.json
    4. Global ~/.maker/config.json
    5. Defaults from schema
    
    Args:
        workspace: Workspace directory path
        config_file: Optional path to specific config file
        **overrides: Additional config overrides
        
    Returns:
        Validated MakerAppConfig instance
    """
    logger.debug("Loading configuration", extra={"workspace": workspace})
    
    # Start with empty dict (defaults come from Pydantic models)
    config_dict: Dict[str, Any] = {}
    
    # 1. Load from files (project → global)
    if config_file:
        # Load from specified file
        file_config = load_config_from_file(Path(config_file))
        if file_config:
            config_dict = merge_configs(config_dict, file_config)
        else:
            logger.warning(f"Could not load configuration from {config_file}")
    else:
        # Load from standard locations
        config_paths = get_config_paths(workspace)
        for config_path in config_paths:
            file_config = load_config_from_file(config_path)
            if file_config:
                config_dict = merge_configs(config_dict, file_config)
                logger.debug(f"Loaded configuration from {config_path}")
                # Don't break - merge all configs (project overrides global)
    
    # 2. Load from environment variables
    env_config = load_config_from_env()
    config_dict = merge_configs(config_dict, env_config)
    
    # 3. Apply function overrides (highest priority)
    if overrides:
        config_dict = merge_configs(config_dict, overrides)
    
    # 4. Populate paths at runtime
    if not config_dict.get('paths'):
        config_dict['paths'] = populate_paths_config(workspace or config_dict.get('workspace'))
    
    # 5. Validate and create config object
    try:
        config = MakerAppConfig(**config_dict)
        logger.info("Configuration loaded successfully")
        return config
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        # Return defaults on validation error
        logger.warning("Using default configuration due to validation error")
        return MakerAppConfig(workspace=workspace, paths=populate_paths_config(workspace))


def save_config(config: MakerAppConfig, path: Path) -> None:
    """
    Save configuration to a file.
    
    Args:
        config: Configuration to save
        path: Path to save config file
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict, excluding None values and paths (runtime-only)
        config_dict = config.model_dump(exclude_none=True, exclude={'paths'})
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Configuration saved to {path}")
    except Exception as e:
        logger.error(f"Failed to save configuration to {path}: {e}")
        raise

