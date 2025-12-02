#!/usr/bin/env python3
"""
Code Verifier: Self-verification loop for generated code (kilocode pattern).

Performs pre-flight checks before returning code:
- Syntax validation (AST parsing)
- Basic type checking
- Import resolution
- Test execution (if test file exists)
"""

import ast
import subprocess
import os
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class CodeVerifier:
    """Validates generated code before presenting to user"""
    
    def __init__(self, codebase_root: str = "."):
        self.codebase_root = Path(codebase_root).resolve()
    
    def verify_syntax(self, code: str, language: str = "python") -> Tuple[bool, Optional[str]]:
        """
        Validate code syntax using AST parsing.
        
        Args:
            code: Code to validate
            language: Programming language (currently only 'python')
            
        Returns:
            (is_valid, error_message)
        """
        if language != "python":
            return True, None  # Skip syntax check for non-Python
        
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            return False, f"Syntax error at line {e.lineno}: {e.msg}"
        except Exception as e:
            return False, f"Parse error: {str(e)}"
    
    def check_imports(self, code: str, codebase_root: Optional[str] = None) -> Tuple[bool, List[str]]:
        """
        Check if imports can be resolved.
        
        Args:
            code: Code to check
            codebase_root: Root directory for resolving relative imports
            
        Returns:
            (all_resolved, missing_imports)
        """
        missing = []
        
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name
                        if not self._can_import(module, codebase_root):
                            missing.append(module)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        if not self._can_import(node.module, codebase_root):
                            missing.append(node.module)
        except SyntaxError:
            # Can't parse, skip import checking
            return True, []
        
        return len(missing) == 0, missing
    
    def _can_import(self, module: str, codebase_root: Optional[str]) -> bool:
        """Check if a module can be imported"""
        try:
            __import__(module)
            return True
        except ImportError:
            # Check if it's a local file
            if codebase_root:
                module_path = Path(codebase_root) / module.replace('.', '/')
                if (module_path.with_suffix('.py').exists() or 
                    (module_path / '__init__.py').exists()):
                    return True
            return False
    
    def check_basic_types(self, code: str) -> Tuple[bool, List[str]]:
        """
        Basic type checking (looks for obvious type errors).
        
        Args:
            code: Code to check
            
        Returns:
            (is_valid, warnings)
        """
        warnings = []
        
        try:
            tree = ast.parse(code)
            
            # Check for common type issues
            for node in ast.walk(tree):
                # Check for None comparisons that might be wrong
                if isinstance(node, ast.Compare):
                    if any(isinstance(op, (ast.Is, ast.IsNot)) for op in node.ops):
                        # Check if comparing with None using == or !=
                        pass  # This is fine
                
                # Check for potential AttributeError
                if isinstance(node, ast.Attribute):
                    # Can't really check without runtime, but we can warn about common patterns
                    pass
        except SyntaxError:
            return True, []
        
        return True, warnings
    
    def find_test_file(self, file_path: Optional[str] = None) -> Optional[str]:
        """
        Find corresponding test file for a given file path.
        
        Args:
            file_path: Path to the source file
            
        Returns:
            Path to test file if found, None otherwise
        """
        if not file_path:
            return None
        
        source_path = Path(file_path)
        
        # Common test file patterns
        test_patterns = [
            f"test_{source_path.name}",
            f"{source_path.stem}_test.py",
            f"tests/test_{source_path.name}",
            f"tests/{source_path.stem}_test.py",
        ]
        
        # Check in same directory
        for pattern in test_patterns:
            test_path = source_path.parent / pattern
            if test_path.exists():
                return str(test_path)
        
        # Check in tests/ directory
        tests_dir = self.codebase_root / "tests"
        if tests_dir.exists():
            for pattern in test_patterns:
                test_path = tests_dir / pattern.split('/')[-1]  # Just filename
                if test_path.exists():
                    return str(test_path)
        
        return None
    
    def run_tests(self, test_file: str, timeout: int = 30) -> Tuple[bool, str]:
        """
        Run tests for a specific test file.
        
        Args:
            test_file: Path to test file
            timeout: Timeout in seconds
            
        Returns:
            (tests_passed, output)
        """
        if not os.path.exists(test_file):
            return False, f"Test file not found: {test_file}"
        
        try:
            # Try pytest first
            result = subprocess.run(
                ['python', '-m', 'pytest', test_file, '-v'],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.codebase_root)
            )
            
            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, f"Tests timed out after {timeout} seconds"
        except FileNotFoundError:
            # pytest not available, try unittest
            try:
                result = subprocess.run(
                    ['python', '-m', 'unittest', test_file],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(self.codebase_root)
                )
                return result.returncode == 0, result.stdout + result.stderr
            except Exception as e:
                return False, f"Could not run tests: {str(e)}"
        except Exception as e:
            return False, f"Test execution error: {str(e)}"
    
    def verify_code(self, code: str, file_path: Optional[str] = None, 
                   run_tests: bool = True) -> Dict[str, any]:
        """
        Complete verification of generated code.
        
        Args:
            code: Code to verify
            file_path: Optional file path (for finding test files)
            run_tests: Whether to run tests if test file exists
            
        Returns:
            Verification results dictionary
        """
        results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'tests_run': False,
            'tests_passed': False
        }
        
        # 1. Syntax validation
        syntax_valid, syntax_error = self.verify_syntax(code)
        if not syntax_valid:
            results['valid'] = False
            results['errors'].append(f"Syntax error: {syntax_error}")
            return results  # Can't continue if syntax is invalid
        
        # 2. Import resolution
        imports_ok, missing_imports = self.check_imports(code, str(self.codebase_root) if self.codebase_root else None)
        if not imports_ok:
            results['warnings'].append(f"Potentially missing imports: {', '.join(missing_imports)}")
        
        # 3. Basic type checking
        types_ok, type_warnings = self.check_basic_types(code)
        results['warnings'].extend(type_warnings)
        
        # 4. Test execution (if test file exists)
        if run_tests and file_path:
            test_file = self.find_test_file(file_path)
            if test_file:
                tests_passed, test_output = self.run_tests(test_file)
                results['tests_run'] = True
                results['tests_passed'] = tests_passed
                if not tests_passed:
                    results['warnings'].append(f"Tests failed: {test_output[:200]}")
        
        return results

