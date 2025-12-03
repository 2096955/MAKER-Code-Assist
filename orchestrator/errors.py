#!/usr/bin/env python3
"""
Error Handling System

Categorized errors with context-aware formatting, similar to Claude Code's error system.
Provides user-friendly error messages with actionable suggestions and recovery hints.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
import json
import logging

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Error categories for classification"""
    AUTHENTICATION = "authentication"
    FILE_SYSTEM = "file_system"
    GIT = "git"
    NETWORK = "network"
    VALIDATION = "validation"
    CONFIG = "config"
    MAKER_VOTING = "maker_voting"
    MODEL_TIMEOUT = "model_timeout"
    CONNECTION = "connection"
    INTERNAL = "internal"
    COMMAND_EXECUTION = "command_execution"
    AI_SERVICE = "ai_service"
    RESOURCE = "resource"
    UNKNOWN = "unknown"


class ErrorLevel(Enum):
    """Error severity levels"""
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFORMATIONAL = "informational"
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


class UserError(Exception):
    """
    User-friendly error with categorization, suggestions, and context.
    
    Similar to Claude Code's UserError class, provides structured error information
    that can be formatted for display to users.
    """
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        level: ErrorLevel = ErrorLevel.ERROR,
        suggestions: Optional[List[str]] = None,
        recoverable: bool = True,
        context: Optional[Dict[str, Any]] = None,
        code: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        """
        Initialize a UserError.
        
        Args:
            message: Error message
            category: Error category
            level: Error severity level
            suggestions: List of actionable suggestions to resolve the error
            recoverable: Whether the error is recoverable
            context: Additional context about the error
            code: Optional error code for programmatic handling
            cause: Original exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.category = category
        self.level = level
        self.suggestions = suggestions or []
        self.recoverable = recoverable
        self.context = context or {}
        self.code = code
        self.cause = cause
    
    def format_for_user(self) -> str:
        """
        Format error with suggestions for user display.
        
        Returns:
            Formatted error message string
        """
        lines = [f"Error: {self.message}"]
        
        if self.category != ErrorCategory.UNKNOWN:
            lines.append(f"Category: {self.category.value}")
        
        if self.suggestions:
            lines.append("\nSuggestions:")
            for suggestion in self.suggestions:
                lines.append(f"  • {suggestion}")
        
        if self.context:
            lines.append("\nContext:")
            for key, value in self.context.items():
                formatted_value = (
                    json.dumps(value, indent=2) if isinstance(value, (dict, list))
                    else str(value)
                )
                lines.append(f"  {key}: {formatted_value}")
        
        if self.cause:
            lines.append(f"\nOriginal error: {type(self.cause).__name__}: {self.cause}")
        
        return "\n".join(lines)
    
    def __str__(self) -> str:
        """String representation of the error"""
        return self.message
    
    def __repr__(self) -> str:
        """Detailed representation for debugging"""
        return (
            f"UserError(message={self.message!r}, category={self.category.value}, "
            f"level={self.level.value}, recoverable={self.recoverable})"
        )


def create_user_error(
    message: str,
    category: ErrorCategory = ErrorCategory.UNKNOWN,
    level: ErrorLevel = ErrorLevel.ERROR,
    suggestions: Optional[List[str]] = None,
    recoverable: bool = True,
    context: Optional[Dict[str, Any]] = None,
    code: Optional[str] = None,
    cause: Optional[Exception] = None
) -> UserError:
    """
    Create a user-friendly error from parameters.
    
    Args:
        message: Error message
        category: Error category
        level: Error severity level
        suggestions: List of actionable suggestions
        recoverable: Whether error is recoverable
        context: Additional context
        code: Optional error code
        cause: Original exception
        
    Returns:
        UserError instance
    """
    error = UserError(
        message=message,
        category=category,
        level=level,
        suggestions=suggestions,
        recoverable=recoverable,
        context=context,
        code=code,
        cause=cause
    )
    
    # Log the error with appropriate level
    log_level = 'error' if level in (ErrorLevel.FATAL, ErrorLevel.CRITICAL, ErrorLevel.ERROR) else 'warning'
    getattr(logger, log_level)(
        f"User error: {message}",
        extra={
            "category": category.value,
            "level": level.value,
            "context": context,
            "suggestions": suggestions
        }
    )
    
    return error


def format_error_for_display(error: Exception) -> str:
    """
    Format an error for display to the user.
    
    Args:
        error: Exception to format
        
    Returns:
        Formatted error message
    """
    if isinstance(error, UserError):
        return error.format_for_user()
    
    if isinstance(error, Exception):
        return f"System error: {error}"
    
    return f"Unknown error: {str(error)}"


def ensure_user_error(
    error: Exception,
    default_message: str = "An unexpected error occurred",
    category: ErrorCategory = ErrorCategory.UNKNOWN,
    suggestions: Optional[List[str]] = None
) -> UserError:
    """
    Convert an error to a UserError if it isn't already.
    
    Args:
        error: Exception to convert
        default_message: Default message if error has no message
        category: Error category
        suggestions: Optional suggestions
        
    Returns:
        UserError instance
    """
    if isinstance(error, UserError):
        return error
    
    message = str(error) if error else default_message
    
    return create_user_error(
        message=message,
        category=category,
        cause=error if isinstance(error, Exception) else None,
        suggestions=suggestions
    )


# Convenience functions for common error types

def file_not_found_error(path: str, suggestions: Optional[List[str]] = None) -> UserError:
    """Create a file not found error"""
    default_suggestions = [
        "Check the file path is correct",
        "Ensure the file exists in the codebase",
        "Try using a relative path from project root"
    ]
    return create_user_error(
        message=f"File not found: {path}",
        category=ErrorCategory.FILE_SYSTEM,
        suggestions=suggestions or default_suggestions,
        context={"path": path}
    )


def git_error(message: str, command: Optional[str] = None, suggestions: Optional[List[str]] = None) -> UserError:
    """Create a git operation error"""
    default_suggestions = [
        "Check that git is installed and in PATH",
        "Verify you have write permissions in the repository",
        "Check git repository status with 'git status'"
    ]
    context = {"command": command} if command else {}
    return create_user_error(
        message=f"Git error: {message}",
        category=ErrorCategory.GIT,
        suggestions=suggestions or default_suggestions,
        context=context
    )


def model_timeout_error(agent: str, port: Optional[int] = None, suggestions: Optional[List[str]] = None) -> UserError:
    """Create a model timeout error"""
    default_suggestions = [
        "Check llama.cpp server is running",
        "Verify model is loaded at the correct port",
        "Try restarting the llama.cpp server",
        "Check server logs for errors"
    ]
    context = {"agent": agent}
    if port:
        context["port"] = port
    return create_user_error(
        message=f"Model timeout for agent {agent}",
        category=ErrorCategory.MODEL_TIMEOUT,
        suggestions=suggestions or default_suggestions,
        context=context
    )


def config_error(message: str, config_path: Optional[str] = None, suggestions: Optional[List[str]] = None) -> UserError:
    """Create a configuration error"""
    default_suggestions = [
        "Check your .maker.json file for syntax errors",
        "Verify configuration values are valid",
        "See .maker.json.example for reference"
    ]
    context = {"config_path": config_path} if config_path else {}
    return create_user_error(
        message=f"Configuration error: {message}",
        category=ErrorCategory.CONFIG,
        suggestions=suggestions or default_suggestions,
        context=context
    )


def network_error(message: str, url: Optional[str] = None, suggestions: Optional[List[str]] = None) -> UserError:
    """Create a network error"""
    default_suggestions = [
        "Check your internet connection",
        "Verify the server URL is correct",
        "Check firewall settings",
        "Retry the operation"
    ]
    context = {"url": url} if url else {}
    return create_user_error(
        message=f"Network error: {message}",
        category=ErrorCategory.NETWORK,
        suggestions=suggestions or default_suggestions,
        context=context,
        recoverable=True
    )

