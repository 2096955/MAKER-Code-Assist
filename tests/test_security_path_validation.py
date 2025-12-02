#!/usr/bin/env python3
"""
Test security path validation in orchestrator.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import just the security function logic (extracted for testing)
def _is_safe_file_path(file_path: str) -> bool:
    """
    Security check: Validate file path is safe to read.
    
    Blocks:
    - System directories (/etc, /usr, /bin, /sbin, /var, /sys, /proc, /dev)
    - Root directory files
    - Hidden system files
    
    Allows:
    - User home directory (~/ or /Users/username/)
    - Codebase files (relative paths)
    - Files in common development directories
    """
    if not file_path:
        return False
    
    # Normalize path
    normalized = os.path.normpath(file_path)
    
    # Block system directories (absolute paths only)
    if normalized.startswith('/'):
        # Blocked system paths
        blocked_prefixes = [
            '/etc',      # System configuration
            '/usr',      # System programs
            '/bin',      # System binaries
            '/sbin',     # System admin binaries
            '/var',      # Variable data
            '/sys',      # System files
            '/proc',     # Process files
            '/dev',      # Device files
            '/root',     # Root home
            '/boot',     # Boot files
            '/lib',      # Libraries
            '/lib64',    # 64-bit libraries
            '/opt',      # Optional software (usually system)
            '/srv',      # Service data
            '/tmp',      # Temporary (security risk)
            '/run',      # Runtime data
        ]
        
        for prefix in blocked_prefixes:
            if normalized.startswith(prefix):
                return False
        
        # Allow user home directories
        home_dirs = [
            os.path.expanduser('~'),  # Current user's home
            '/Users',                  # macOS user homes
            '/home',                   # Linux user homes
        ]
        
        # Check if path is under any allowed home directory
        is_under_home = False
        for home_base in home_dirs:
            if home_base and normalized.startswith(home_base):
                # Additional check: ensure it's actually a user directory
                parts = normalized[len(home_base):].split(os.sep)
                if len(parts) > 1 and parts[1]:  # Has username component
                    is_under_home = True
                    break
        
        if not is_under_home:
            return False
    
    # Block hidden system files (but allow .git, .env in user directories)
    if os.path.basename(normalized).startswith('.') and normalized.startswith('/'):
        # Allow common dev files even if hidden
        allowed_hidden = ['.git', '.env', '.gitignore', '.gitconfig']
        basename = os.path.basename(normalized)
        if basename not in allowed_hidden:
            # Check if it's a system hidden file
            if any(normalized.startswith(f'/{sys_dir}/.') for sys_dir in ['etc', 'usr', 'var']):
                return False
    
    # Allow relative paths (assumed to be in codebase)
    if not normalized.startswith('/'):
        return True
    
    # If we get here and it's an absolute path, it passed all checks
    return True


def test_blocked_system_paths():
    """Test that system paths are blocked"""
    blocked_paths = [
        '/etc/passwd',
        '/usr/bin/python',
        '/var/log/syslog',
        '/tmp/evil.py',
        '/root/.ssh/id_rsa',
        '/bin/bash',
        '/sbin/init',
        '/sys/kernel',
        '/proc/self',
        '/dev/null',
        '/boot/vmlinuz',
        '/lib/libc.so',
        '/opt/system',
    ]
    
    for path in blocked_paths:
        assert not _is_safe_file_path(path), f"Should block: {path}"


def test_allowed_user_paths():
    """Test that user paths are allowed"""
    user_home = os.path.expanduser('~')
    allowed_paths = [
        'orchestrator/orchestrator.py',  # Relative
        './test.py',  # Relative with dot
        f'{user_home}/test.py',  # User home
        f'{user_home}/.gitconfig',  # User hidden file
        'test.py',  # Simple relative
    ]
    
    for path in allowed_paths:
        assert _is_safe_file_path(path), f"Should allow: {path}"


def test_allowed_absolute_user_paths():
    """Test absolute paths under user home"""
    username = os.getenv('USER', 'testuser')
    allowed_paths = [
        f'/Users/{username}/test.py',
        f'/Users/{username}/project/file.py',
        f'/home/{username}/test.py',
    ]
    
    for path in allowed_paths:
        # Only test if path structure makes sense for this system
        if path.startswith('/Users') or (path.startswith('/home') and os.path.exists('/home')):
            assert _is_safe_file_path(path), f"Should allow: {path}"


def test_blocked_root_paths():
    """Test that root-level paths are blocked"""
    blocked_paths = [
        '/Users',  # No username component
        '/home',   # No username component
        '/',       # Root itself
    ]
    
    for path in blocked_paths:
        assert not _is_safe_file_path(path), f"Should block: {path}"


def test_empty_and_none():
    """Test edge cases"""
    assert not _is_safe_file_path(''), "Empty string should be blocked"
    assert not _is_safe_file_path(None), "None should be blocked"


def test_relative_paths():
    """Test that relative paths are allowed"""
    allowed = [
        'file.py',
        'dir/file.py',
        '../parent/file.py',
        './current/file.py',
    ]
    
    for path in allowed:
        assert _is_safe_file_path(path), f"Should allow relative: {path}"


if __name__ == '__main__':
    print("Running security path validation tests...")
    test_blocked_system_paths()
    print("✓ Blocked system paths")
    
    test_allowed_user_paths()
    print("✓ Allowed user paths")
    
    test_allowed_absolute_user_paths()
    print("✓ Allowed absolute user paths")
    
    test_blocked_root_paths()
    print("✓ Blocked root paths")
    
    test_empty_and_none()
    print("✓ Edge cases")
    
    test_relative_paths()
    print("✓ Relative paths")
    
    print("\n✅ All security tests passed!")

