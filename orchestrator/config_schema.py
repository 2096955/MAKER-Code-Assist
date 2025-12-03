#!/usr/bin/env python3
"""
Configuration Schema

Defines the structure and validation rules for the MAKER application configuration.
Uses Pydantic for runtime type validation, similar to Claude Code's Zod schemas.

Supports hierarchical configuration:
- Project-level: .maker.json in project root
- Global-level: ~/.maker/config.json
- Defaults: Built-in defaults
"""

from pydantic import BaseModel, Field
from typing import Literal, List, Optional, Dict, Any


class CodeAnalysisConfig(BaseModel):
    """Code analysis configuration"""
    index_depth: int = Field(default=3, ge=1, le=10, description="Maximum directory depth to index")
    exclude_patterns: List[str] = Field(
        default_factory=lambda: [
            'node_modules/**',
            '.git/**',
            '__pycache__/**',
            'dist/**',
            'build/**',
            '**/*.min.js',
            '**/*.bundle.js',
            '**/vendor/**',
            '.DS_Store',
            '**/*.log',
            '**/*.lock',
            '**/package-lock.json',
            '**/yarn.lock',
            '**/pnpm-lock.yaml',
            '.env*',
            '**/*.map',
            'models/**',
            '.venv/**',
            'venv/**',
            'env/**',
            'target/**',
            '.docker/**',
            'docker-data/**',
            '.cache/**',
            'coverage/**',
            'weaviate_data/**',
            'redis_data/**',
            'postgres_data/**'
        ],
        description="Glob patterns to exclude from analysis"
    )
    include_patterns: List[str] = Field(
        default_factory=lambda: ['**/*'],
        description="Glob patterns to include in analysis"
    )
    max_file_size: int = Field(
        default=1024 * 1024,  # 1MB
        ge=1024,
        description="Maximum file size in bytes to analyze"
    )
    scan_timeout: int = Field(
        default=30000,  # 30 seconds
        ge=1000,
        description="Timeout for codebase scan in milliseconds"
    )


class TerminalConfig(BaseModel):
    """Terminal/UI configuration"""
    theme: Literal['dark', 'light', 'system'] = Field(
        default='system',
        description="Terminal theme preference"
    )
    show_progress_indicators: bool = Field(
        default=True,
        description="Show progress indicators during operations"
    )
    use_colors: bool = Field(
        default=True,
        description="Enable colored output"
    )
    code_highlighting: bool = Field(
        default=True,
        description="Enable syntax highlighting in code blocks"
    )
    max_height: Optional[int] = Field(
        default=None,
        ge=10,
        description="Maximum terminal height in lines"
    )
    max_width: Optional[int] = Field(
        default=None,
        ge=40,
        description="Maximum terminal width in characters"
    )


class GitConfig(BaseModel):
    """Git configuration"""
    preferred_remote: str = Field(
        default='origin',
        description="Preferred git remote name"
    )
    preferred_branch: Optional[str] = Field(
        default=None,
        description="Preferred git branch name"
    )
    use_ssh: bool = Field(
        default=False,
        description="Use SSH for git operations"
    )
    use_gpg: bool = Field(
        default=False,
        description="Use GPG for commit signing"
    )
    sign_commits: bool = Field(
        default=False,
        description="Sign git commits"
    )


class EditorConfig(BaseModel):
    """Editor configuration"""
    preferred_launcher: Optional[str] = Field(
        default=None,
        description="Preferred editor launcher command"
    )
    tab_width: int = Field(
        default=2,
        ge=1,
        le=8,
        description="Tab width in spaces"
    )
    insert_spaces: bool = Field(
        default=True,
        description="Use spaces instead of tabs"
    )
    format_on_save: bool = Field(
        default=True,
        description="Format code on save"
    )


class MakerConfig(BaseModel):
    """MAKER-specific configuration"""
    maker_mode: Literal['high', 'low'] = Field(
        default='high',
        description="MAKER mode: 'high' uses all 6 models, 'low' uses 5 models (no Reviewer)"
    )
    num_candidates: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of parallel candidates for MAKER voting"
    )
    vote_k: int = Field(
        default=3,
        ge=1,
        description="Number of votes needed to win in first-to-K voting"
    )
    max_context_tokens: int = Field(
        default=32000,
        ge=1000,
        description="Maximum context tokens for agents"
    )
    recent_window_tokens: int = Field(
        default=8000,
        ge=1000,
        description="Recent window size in tokens (kept in full)"
    )


class PathsConfig(BaseModel):
    """Path configuration (populated at runtime)"""
    home: Optional[str] = None
    app: Optional[str] = None
    cache: Optional[str] = None
    logs: Optional[str] = None
    workspace: Optional[str] = None


class MakerAppConfig(BaseModel):
    """Main application configuration schema"""
    # Basic configuration
    workspace: Optional[str] = Field(
        default=None,
        description="Workspace directory path"
    )
    log_level: Literal['error', 'warn', 'info', 'debug'] = Field(
        default='info',
        description="Logging level"
    )
    
    # Subsystem configurations
    code_analysis: CodeAnalysisConfig = Field(
        default_factory=CodeAnalysisConfig,
        description="Code analysis settings"
    )
    terminal: TerminalConfig = Field(
        default_factory=TerminalConfig,
        description="Terminal/UI settings"
    )
    git: GitConfig = Field(
        default_factory=GitConfig,
        description="Git settings"
    )
    editor: EditorConfig = Field(
        default_factory=EditorConfig,
        description="Editor settings"
    )
    maker: MakerConfig = Field(
        default_factory=MakerConfig,
        description="MAKER-specific settings"
    )
    
    # Runtime configuration (populated at runtime)
    paths: Optional[PathsConfig] = None
    
    # Tool permissions (optional)
    allowed_tools: Optional[List[str]] = Field(
        default=None,
        description="List of allowed MCP tools (if None, all tools allowed)"
    )
    blocked_tools: Optional[List[str]] = Field(
        default=None,
        description="List of blocked MCP tools"
    )
    
    class Config:
        """Pydantic config"""
        extra = "allow"  # Allow extra fields for extensibility
        json_schema_extra = {
            "example": {
                "workspace": "/path/to/project",
                "log_level": "info",
                "maker": {
                    "maker_mode": "high",
                    "num_candidates": 5,
                    "vote_k": 3
                },
                "code_analysis": {
                    "index_depth": 3,
                    "exclude_patterns": ["node_modules/**", "dist/**"]
                },
                "git": {
                    "sign_commits": True,
                    "preferred_remote": "origin"
                }
            }
        }

