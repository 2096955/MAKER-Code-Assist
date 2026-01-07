#!/usr/bin/env python3
"""
MCP Server: Exposes codebase as tools for agents
- read_file(path): Get file contents
- analyze_codebase(): Return structure summary
- search_docs(query): Search policy/design docs
- find_references(symbol): Find where a function/class is used
- git_diff(file): Get latest changes
- run_tests(test_file): Execute test suite
- rag_search(query, top_k): Semantic search in codebase (if RAG index exists)
- rag_query(question, top_k): RAG query with LLM generation (if RAG index exists)

RAG tools are agentic - agents call them when needed, not automatically injected.
If RAG index doesn't exist, tools simply won't appear in /api/mcp/tools list.
"""

import os
import json
import subprocess
import re
import logging

logger = logging.getLogger(__name__)
import ast
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Maximum file size before chunking (in characters)
MAX_FILE_SIZE_FOR_CHUNKING = 5000

app = FastAPI(title="MCP Codebase Server", version="1.0.0")

class CodebaseMCPServer:
    def __init__(self, codebase_root: str, redis_client=None):
        self.root = Path(codebase_root).resolve()
        self.redis_client = redis_client  # For loading code graph
        self.excluded = {
            '.git', 'node_modules', 'dist', 'build', '__pycache__', '.specify', '.claude',
            'models', '.venv', 'venv', 'env', '.env', 'vendor', 'target', 
            '.docker', 'docker-data', '.cache', '.npm', '.yarn', 'coverage',
            '.idea', '.vscode', '.DS_Store', 'tmp', 'temp', 'logs',
            'weaviate_data', 'redis_data', 'postgres_data'
        }
        
        # Language detection mapping
        self.EXTENSION_TO_LANGUAGE = {
            'ts': 'TypeScript',
            'tsx': 'TypeScript (React)',
            'js': 'JavaScript',
            'jsx': 'JavaScript (React)',
            'py': 'Python',
            'java': 'Java',
            'c': 'C',
            'cpp': 'C++',
            'cc': 'C++',
            'cxx': 'C++',
            'cs': 'C#',
            'go': 'Go',
            'rs': 'Rust',
            'php': 'PHP',
            'rb': 'Ruby',
            'swift': 'Swift',
            'kt': 'Kotlin',
            'scala': 'Scala',
            'html': 'HTML',
            'css': 'CSS',
            'scss': 'SCSS',
            'less': 'Less',
            'json': 'JSON',
            'md': 'Markdown',
            'yml': 'YAML',
            'yaml': 'YAML',
            'xml': 'XML',
            'sql': 'SQL',
            'sh': 'Shell',
            'bash': 'Bash',
            'zsh': 'Zsh',
            'bat': 'Batch',
            'ps1': 'PowerShell',
            'r': 'R',
            'm': 'Objective-C',
            'mm': 'Objective-C++',
            'vue': 'Vue',
            'svelte': 'Svelte'
        }
        
    def _chunk_python_file(self, file_path: Path, content: str) -> List[Dict[str, Any]]:
        """
        Chunk Python file respecting function/class boundaries (semantic-aware chunking).
        
        Returns:
            List of chunks with metadata: [{text, start_line, end_line, chunk_type, name}]
        """
        chunks = []
        lines = content.splitlines()
        
        try:
            tree = ast.parse(content, filename=str(file_path))
            
            class ChunkVisitor(ast.NodeVisitor):
                def __init__(self, lines_list):
                    self.lines = lines_list
                    self.chunks = []
                
                def visit_FunctionDef(self, node):
                    start_line = node.lineno - 1  # 0-indexed
                    end_line = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
                    chunk_text = '\n'.join(self.lines[start_line:end_line])
                    self.chunks.append({
                        'text': chunk_text,
                        'start_line': start_line + 1,  # 1-indexed for display
                        'end_line': end_line,
                        'chunk_type': 'function',
                        'name': node.name
                    })
                    self.generic_visit(node)
                
                def visit_ClassDef(self, node):
                    start_line = node.lineno - 1
                    end_line = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
                    chunk_text = '\n'.join(self.lines[start_line:end_line])
                    self.chunks.append({
                        'text': chunk_text,
                        'start_line': start_line + 1,
                        'end_line': end_line,
                        'chunk_type': 'class',
                        'name': node.name
                    })
                    self.generic_visit(node)
            
            visitor = ChunkVisitor(lines)
            visitor.visit(tree)
            
            # If no functions/classes found, create module-level chunk
            if not visitor.chunks:
                visitor.chunks.append({
                    'text': content[:MAX_FILE_SIZE_FOR_CHUNKING],
                    'start_line': 1,
                    'end_line': len(lines),
                    'chunk_type': 'module',
                    'name': 'module'
                })
            
            return visitor.chunks
            
        except SyntaxError:
            # If AST parsing fails, fall back to line-based chunking
            chunk_size = 100  # lines per chunk
            chunks = []
            for i in range(0, len(lines), chunk_size):
                chunk_lines = lines[i:i+chunk_size]
                chunks.append({
                    'text': '\n'.join(chunk_lines),
                    'start_line': i + 1,
                    'end_line': min(i + chunk_size, len(lines)),
                    'chunk_type': 'block',
                    'name': f'block_{i//chunk_size + 1}'
                })
            return chunks
    
    def read_file(self, path: str, chunked: Optional[bool] = None) -> str:
        """
        Safely read a file from codebase.
        
        Args:
            path: File path relative to codebase root
            chunked: If True and file is large, return semantic chunks instead of full file
        
        Returns:
            File content (or chunked representation if chunked=True and file is large)
        """
        file_path = (self.root / path).resolve()
        
        # Security: Ensure path is within codebase
        if not str(file_path).startswith(str(self.root)):
            raise ValueError(f"Path traversal attempt: {path}")
            
        if not file_path.exists():
            return f" File not found: {path}"
            
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Auto-enable chunking for large files (if chunked not explicitly False)
            # Default: chunked=None means auto-detect based on file size
            should_chunk = chunked if chunked is not None else (len(content) > MAX_FILE_SIZE_FOR_CHUNKING)
            
            # If chunking enabled and file is large, use intelligent chunking
            if should_chunk and len(content) > MAX_FILE_SIZE_FOR_CHUNKING:
                if file_path.suffix == '.py':
                    chunks = self._chunk_python_file(file_path, content)
                    # Format chunks for display
                    result = f"File {path} (chunked into {len(chunks)} semantic units):\n\n"
                    for chunk in chunks:
                        result += f"--- {chunk['chunk_type'].upper()}: {chunk['name']} (lines {chunk['start_line']}-{chunk['end_line']}) ---\n"
                        result += f"{chunk['text']}\n\n"
                    return result
                else:
                    # For non-Python files, truncate with note
                    return f"{content[:MAX_FILE_SIZE_FOR_CHUNKING]}\n\n... (truncated, file too large: {len(content)} chars)"
            
            return content
        except Exception as e:
            return f" Error reading file: {e}"
    
    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension"""
        ext = file_path.suffix.lstrip('.')
        return self.EXTENSION_TO_LANGUAGE.get(ext.lower(), 'Other')
    
    def _extract_dependencies(self, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """
        Extract dependencies (imports/requires) from a file.
        
        Returns:
            List of dependency info dicts: [{name, type, source, import_path, is_external}]
        """
        dependencies = []
        ext = file_path.suffix.lstrip('.').lower()
        
        try:
            # Python imports
            if ext == 'py':
                import_regex = re.compile(r'^\s*(?:import\s+(\S+)|from\s+(\S+)\s+import)', re.MULTILINE)
                for match in import_regex.finditer(content):
                    import_path = match.group(1) or match.group(2)
                    if import_path:
                        module_name = import_path.split('.')[0]
                        is_external = not import_path.startswith('.') and module_name not in [
                            'os', 'sys', 're', 'math', 'datetime', 'time', 'random', 'json', 'csv',
                            'collections', 'itertools', 'functools', 'pathlib', 'shutil', 'glob',
                            'pickle', 'urllib', 'http', 'logging', 'argparse', 'unittest', 'subprocess',
                            'threading', 'multiprocessing', 'typing', 'enum', 'io', 'tempfile', 'asyncio',
                            'httpx', 'fastapi', 'pydantic', 'redis'
                        ]
                        dependencies.append({
                            'name': module_name,
                            'type': 'import',
                            'source': str(file_path.relative_to(self.root)),
                            'import_path': import_path,
                            'is_external': is_external
                        })
            
            # JavaScript/TypeScript imports
            elif ext in ('js', 'jsx', 'ts', 'tsx'):
                # ES module imports
                es_import_regex = re.compile(r"import\s+(?:[\w\s{},*]*\s+from\s+)?['\"]([^'\"]+)['\"]", re.MULTILINE)
                for match in es_import_regex.finditer(content):
                    import_path = match.group(1)
                    package_name = import_path.split('/')[0].lstrip('@')
                    is_external = not (import_path.startswith('.') or import_path.startswith('/'))
                    dependencies.append({
                        'name': package_name,
                        'type': 'import',
                        'source': str(file_path.relative_to(self.root)),
                        'import_path': import_path,
                        'is_external': is_external
                    })
                
                # CommonJS requires
                require_regex = re.compile(r"(?:const|let|var)\s+(?:[\w\s{},*]*)\s*=\s*require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", re.MULTILINE)
                for match in require_regex.finditer(content):
                    import_path = match.group(1)
                    package_name = import_path.split('/')[0]
                    is_external = not (import_path.startswith('.') or import_path.startswith('/'))
                    dependencies.append({
                        'name': package_name,
                        'type': 'require',
                        'source': str(file_path.relative_to(self.root)),
                        'import_path': import_path,
                        'is_external': is_external
                    })
            
            # Java imports
            elif ext == 'java':
                import_regex = re.compile(r'^\s*import\s+([^;]+);', re.MULTILINE)
                for match in import_regex.finditer(content):
                    import_path = match.group(1)
                    package_name = import_path.split('.')[0]
                    dependencies.append({
                        'name': package_name,
                        'type': 'import',
                        'source': str(file_path.relative_to(self.root)),
                        'import_path': import_path,
                        'is_external': True
                    })
            
            # Ruby requires
            elif ext == 'rb':
                require_regex = re.compile(r"^\s*require\s+['\"]([^'\"]+)['\"]", re.MULTILINE)
                for match in require_regex.finditer(content):
                    import_path = match.group(1)
                    dependencies.append({
                        'name': import_path,
                        'type': 'require',
                        'source': str(file_path.relative_to(self.root)),
                        'import_path': import_path,
                        'is_external': True
                    })
        
        except Exception as e:
            # Silently fail dependency extraction
            pass
        
        return dependencies
    
    def analyze_file(self, path: str) -> Dict[str, Any]:
        """
        Analyze a single file for language, LOC, dependencies, and metrics.
        
        Args:
            path: File path relative to codebase root
            
        Returns:
            File info dict with: {path, extension, language, size, line_count, last_modified, dependencies}
        """
        file_path = (self.root / path).resolve()
        
        # Security: Ensure path is within codebase
        if not str(file_path).startswith(str(self.root)):
            raise ValueError(f"Path traversal attempt: {path}")
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        try:
            # Get file stats
            stat = file_path.stat()
            
            # Read content for analysis
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Detect language
            language = self._detect_language(file_path)
            
            # Count lines
            line_count = content.count('\n') + (1 if content else 0)
            
            # Extract dependencies
            dependencies = self._extract_dependencies(content, file_path)
            
            return {
                'path': path,
                'extension': file_path.suffix,
                'language': language,
                'size': stat.st_size,
                'line_count': line_count,
                'last_modified': stat.st_mtime,
                'dependencies': dependencies
            }
        
        except Exception as e:
            raise ValueError(f"Error analyzing file {path}: {e}")
    
    def analyze_codebase(self) -> Dict[str, Any]:
        """
        Analyze entire codebase structure with language detection and dependency tracking.
        
        Returns:
            Project structure dict with: {root, total_files, files_by_language, total_lines_of_code, directories, dependencies}
        """
        MAX_FILES = 500  # Limit to prevent timeout
        MAX_FILE_SIZE = 1_000_000  # 1MB max per file
        
        structure = {
            "root": str(self.root),
            "total_files": 0,
            "total_lines_of_code": 0,
            "files_by_language": {},
            "directories": {},
            "dependencies": [],
            "truncated": False
        }
        
        all_dependencies = []
        
        for root, dirs, files in os.walk(self.root):
            # Skip excluded dirs
            dirs[:] = [d for d in dirs if d not in self.excluded]
            
            # Record directory
            rel_dir = Path(root).relative_to(self.root)
            dir_key = str(rel_dir) if str(rel_dir) != '.' else '.'
            
            for file in files:
                if file.startswith('.'):
                    continue
                
                # Check file limit
                if structure["total_files"] >= MAX_FILES:
                    structure["truncated"] = True
                    break
                    
                file_path = Path(root) / file
                
                # Skip large files
                try:
                    if file_path.stat().st_size > MAX_FILE_SIZE:
                        continue
                except OSError:
                    continue
                
                # Detect language
                language = self._detect_language(file_path)
                structure["files_by_language"][language] = structure["files_by_language"].get(language, 0) + 1
                
                # Track directory structure
                if dir_key not in structure["directories"]:
                    structure["directories"][dir_key] = []
                structure["directories"][dir_key].append(str(file_path.relative_to(self.root)))
                
                # Count lines and extract dependencies (only for code files)
                if language != 'Other':
                    try:
                        if file_path.stat().st_size < 100_000:  # Only analyze files < 100KB
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                line_count = content.count('\n') + (1 if content else 0)
                                structure["total_lines_of_code"] += line_count
                                
                                # Extract dependencies
                                deps = self._extract_dependencies(content, file_path)
                                all_dependencies.extend(deps)
                    except (OSError, IOError, UnicodeDecodeError):
                        pass
                
                structure["total_files"] += 1
            
            if structure["truncated"]:
                break
        
        # Deduplicate dependencies
        seen = set()
        unique_deps = []
        for dep in all_dependencies:
            key = (dep['name'], dep['import_path'], dep['source'])
            if key not in seen:
                seen.add(key)
                unique_deps.append(dep)
        
        structure["dependencies"] = unique_deps
        
        return structure
    
    def search_docs(self, query: str) -> str:
        """Search in docs/ and README files for query term"""
        doc_dirs = [self.root / 'docs', self.root / 'README.md']
        results = []
        
        for path in doc_dirs:
            if path.is_file():
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if query.lower() in content.lower():
                            results.append(f" {path.name}: Found '{query}'")
                except (OSError, IOError, UnicodeDecodeError):
                    pass
            elif path.is_dir():
                for doc_file in path.rglob('*.md'):
                    try:
                        with open(doc_file, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            if query.lower() in content.lower():
                                results.append(f" {doc_file.name}: Found '{query}'")
                    except (OSError, IOError, UnicodeDecodeError):
                        pass
        
        return "\n".join(results) if results else f" No docs found for '{query}'"
    
    def _find_references_python(self, file_path: Path, symbol: str) -> List[Tuple[int, str]]:
        """Find references in Python files using AST parsing"""
        refs = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.splitlines()
            
            # Parse AST
            try:
                tree = ast.parse(content, filename=str(file_path))
            except SyntaxError:
                # If AST parsing fails, fall back to regex
                return self._find_references_regex(file_path, symbol, lines)
            
            # Visit AST nodes to find references
            class ReferenceVisitor(ast.NodeVisitor):
                def __init__(self, target_symbol):
                    self.target = target_symbol
                    self.refs = []
                
                def visit_Name(self, node):
                    if node.id == self.target:
                        self.refs.append((node.lineno, "name"))
                    self.generic_visit()
                
                def visit_Attribute(self, node):
                    if isinstance(node.attr, str) and node.attr == self.target:
                        self.refs.append((node.lineno, "attribute"))
                    self.generic_visit()
                
                def visit_FunctionDef(self, node):
                    if node.name == self.target:
                        self.refs.append((node.lineno, "definition"))
                    self.generic_visit()
                
                def visit_ClassDef(self, node):
                    if node.name == self.target:
                        self.refs.append((node.lineno, "definition"))
                    self.generic_visit()
            
            visitor = ReferenceVisitor(symbol)
            visitor.visit(tree)
            return visitor.refs
            
        except Exception:
            return []
    
    def _find_references_regex(self, file_path: Path, symbol: str, lines: List[str]) -> List[Tuple[int, str]]:
        """Find references using regex with word boundaries (for non-Python files)"""
        refs = []
        # Use word boundaries to avoid false positives
        # Match: symbol as whole word, not part of another word
        pattern = r'\b' + re.escape(symbol) + r'\b'
        
        for i, line in enumerate(lines, 1):
            if re.search(pattern, line):
                # Check if it's a definition (function/class/const/let/var)
                if re.search(rf'\b(function|class|const|let|var)\s+{re.escape(symbol)}\b', line):
                    refs.append((i, "definition"))
                else:
                    refs.append((i, "reference"))
        
        return refs
    
    def find_references(self, symbol: str) -> str:
        """Find all references to a function/class/variable using AST parsing for Python, regex for others"""
        refs = []
        
        for root, dirs, files in os.walk(self.root):
            dirs[:] = [d for d in dirs if d not in self.excluded]
            
            for file in files:
                if file.startswith('.'):
                    continue
                    
                file_path = Path(root) / file
                
                # Only search code files
                if file_path.suffix in {'.py', '.js', '.ts', '.tsx', '.jsx', '.md'}:
                    try:
                        if file_path.suffix == '.py':
                            # Use AST parsing for Python files
                            file_refs = self._find_references_python(file_path, symbol)
                        else:
                            # Use regex for other languages
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                lines = f.read().splitlines()
                            file_refs = self._find_references_regex(file_path, symbol, lines)
                        
                        # Format results
                        rel_path = file_path.relative_to(self.root)
                        for line_num, ref_type in file_refs:
                            marker = "📌" if ref_type == "definition" else "🔗"
                            refs.append(f"{marker} {rel_path}:{line_num} ({ref_type})")
                    except Exception:
                        pass
        
        return "\n".join(refs) if refs else f" No references found for '{symbol}'"
    
    def git_diff(self, file: Optional[str] = None) -> str:
        """Get git diff (what changed recently)"""
        try:
            original_cwd = os.getcwd()
            os.chdir(self.root)
            try:
                if file:
                    result = subprocess.run(['git', 'diff', file], 
                                          capture_output=True, text=True, timeout=10)
                else:
                    result = subprocess.run(['git', 'diff', '--stat'], 
                                          capture_output=True, text=True, timeout=10)
                return result.stdout if result.returncode == 0 else " Git not available"
            finally:
                os.chdir(original_cwd)
        except subprocess.TimeoutExpired:
            return " Git diff timed out"
        except Exception as e:
            return f" Git diff error: {e}"
    
    def run_tests(self, test_file: Optional[str] = None) -> str:
        """Run test suite (returns exit code + output)"""
        try:
            original_cwd = os.getcwd()
            os.chdir(self.root)
            try:
                if test_file:
                    # Run specific test file
                    if test_file.endswith('.py'):
                        cmd = ['python', '-m', 'pytest', test_file, '-v']
                    else:  # JavaScript/TypeScript
                        cmd = ['npm', 'test', '--', test_file]
                else:
                    # Run all tests
                    if (self.root / 'package.json').exists():
                        cmd = ['npm', 'test']
                    elif (self.root / 'pytest.ini').exists() or list(self.root.glob('**/test_*.py')):
                        cmd = ['python', '-m', 'pytest', '-v']
                    else:
                        return " No test framework detected"
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                return f"Exit: {result.returncode}\n\n{result.stdout}\n{result.stderr}"
            finally:
                os.chdir(original_cwd)
        except subprocess.TimeoutExpired:
            return " Tests timed out (>30s)"
        except Exception as e:
            return f" Test error: {e}"
    
    def find_callers(self, symbol: str, use_communities: bool = True) -> List[str]:
        """
        Find all callers of a function/class using code graph.
        
        Args:
            symbol: Function or class name to find callers for
            use_communities: If True, use community-aware fast search (default: True)
        
        Returns:
            List of formatted caller strings (file_path::name)
        """
        if not self.redis_client:
            return []
        
        try:
            from orchestrator.code_graph import CodeGraph
            graph = CodeGraph.load_from_redis(self.redis_client)
            if not graph:
                return []
            
            # Use fast community-aware search if available, otherwise fallback to regular
            if use_communities and graph.community_built:
                callers = graph.find_callers_fast(symbol)
            else:
                callers = graph.find_callers(symbol)
            
            # Format results with node info
            formatted = []
            for caller_id in callers:
                node_info = graph.get_node_info(caller_id)
                if node_info:
                    file_path = node_info.get('file', 'unknown')
                    name = node_info.get('name', caller_id)
                    formatted.append(f"{file_path}::{name}")
                else:
                    formatted.append(caller_id)
            return formatted
        except Exception as e:
            logger.warning(f"Error finding callers for {symbol}: {e}")
            return []
    
    def impact_analysis(self, symbol: str) -> List[str]:
        """Analyze impact of changing a function/class (all downstream dependencies)"""
        if not self.redis_client:
            return []
        
        try:
            from orchestrator.code_graph import CodeGraph
            graph = CodeGraph.load_from_redis(self.redis_client)
            if not graph:
                return []
            impacts = graph.impact_analysis(symbol)
            # Format results
            formatted = []
            for impact_id in impacts:
                node_info = graph.get_node_info(impact_id)
                if node_info:
                    file_path = node_info.get('file', 'unknown')
                    name = node_info.get('name', impact_id)
                    formatted.append(f"{file_path}::{name}")
                else:
                    formatted.append(impact_id)
            return formatted
        except Exception as e:
            logger.warning(f"Error analyzing impact for {symbol}: {e}")
            return []


# Initialize MCP server
codebase_root = os.getenv('CODEBASE_ROOT', os.getcwd())

# Get Redis client for code graph (optional)
_redis_client = None
try:
    import redis
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    _redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True, socket_connect_timeout=2)
    _redis_client.ping()  # Test connection
except (ImportError, redis.ConnectionError, redis.TimeoutError, Exception):
    # Redis not available - graph features will be disabled
    _redis_client = None

mcp_server = CodebaseMCPServer(codebase_root, redis_client=_redis_client)


# Request models
class ToolRequest(BaseModel):
    tool: str
    args: Dict[str, Any] = {}


class ReadFileRequest(BaseModel):
    path: str


class AnalyzeFileRequest(BaseModel):
    path: str


class SearchDocsRequest(BaseModel):
    query: str


class FindReferencesRequest(BaseModel):
    symbol: str


class GitDiffRequest(BaseModel):
    file: Optional[str] = None


class RunTestsRequest(BaseModel):
    test_file: Optional[str] = None


# API Endpoints
@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "codebase_root": str(mcp_server.root)}


@app.get("/api/mcp/tools")
async def list_tools():
    """List available MCP tools"""
    tools = [
        {
            "name": "read_file",
            "description": "Read a file from the codebase",
            "parameters": {
                "path": {"type": "string", "description": "File path relative to codebase"}
            }
        },
        {
            "name": "analyze_file",
            "description": "Analyze a single file for language, LOC, dependencies, and metrics",
            "parameters": {
                "path": {"type": "string", "description": "File path relative to codebase"}
            }
        },
        {
            "name": "analyze_codebase",
            "description": "Get codebase structure (files, languages, LOC, dependencies)",
            "parameters": {}
        },
        {
            "name": "search_docs",
            "description": "Search documentation for a topic",
            "parameters": {
                "query": {"type": "string"}
            }
        },
        {
            "name": "find_references",
            "description": "Find all references to a symbol (function/class/var)",
            "parameters": {
                "symbol": {"type": "string"}
            }
        },
        {
            "name": "find_callers",
            "description": "Find all functions/classes that call a given symbol (uses knowledge graph)",
            "parameters": {
                "symbol": {"type": "string", "description": "Function or class name to find callers for"}
            }
        },
        {
            "name": "impact_analysis",
            "description": "Analyze what would break if a function/class is changed (all downstream dependencies)",
            "parameters": {
                "symbol": {"type": "string", "description": "Function or class name to analyze"}
            }
        },
        {
            "name": "git_diff",
            "description": "Get recent git changes",
            "parameters": {
                "file": {"type": "string", "description": "Optional: specific file", "required": False}
            }
        },
        {
            "name": "run_tests",
            "description": "Run test suite",
            "parameters": {
                "test_file": {"type": "string", "description": "Optional: specific test file", "required": False}
            }
        }
    ]
    
    # Add RAG tools if RAG is available
    try:
        from orchestrator.rag_service_faiss import RAGServiceFAISS
        import os
        index_path = os.getenv("RAG_INDEX_PATH", "data/rag_indexes/codebase.index")
        if os.path.exists(index_path):
            tools.extend([
                {
                    "name": "rag_search",
                    "description": "Semantic search in codebase using RAG. Returns relevant code snippets with similarity scores.",
                    "parameters": {
                        "query": {"type": "string", "description": "Search query"},
                        "top_k": {"type": "integer", "description": "Number of results (default: 5)", "required": False}
                    }
                },
                {
                    "name": "rag_query",
                    "description": "RAG query: Retrieve relevant context and generate an answer using LLM. Use when you need a comprehensive answer based on codebase knowledge.",
                    "parameters": {
                        "question": {"type": "string", "description": "Question to answer"},
                        "top_k": {"type": "integer", "description": "Number of documents to retrieve (default: 5)", "required": False}
                    }
                }
            ])
    except (ImportError, Exception):
        # RAG not available - tools list stays as is
        pass
    
    return {"tools": tools}


@app.post("/api/mcp/tool")
async def call_tool(request: ToolRequest):
    """Execute an MCP tool with permission checking"""
    try:
        # Check tool permissions (Crush pattern) - Week 2 feature, optional
        try:
            from orchestrator.tool_permissions import ToolPermissions
            permissions = ToolPermissions(codebase_root=str(mcp_server.root))
            if not permissions.is_tool_allowed(request.tool):
                raise HTTPException(
                    status_code=403,
                    detail=f"Tool '{request.tool}' is blocked by .maker.json configuration"
                )
        except ImportError:
            # Tool permissions not available, skip check (backward compatible)
            pass
        if request.tool == "read_file":
            if "path" not in request.args:
                raise HTTPException(status_code=400, detail="Missing 'path' parameter")
            result = mcp_server.read_file(request.args["path"])
            return {"result": result}
        
        elif request.tool == "analyze_file":
            if "path" not in request.args:
                raise HTTPException(status_code=400, detail="Missing 'path' parameter")
            result = mcp_server.analyze_file(request.args["path"])
            return {"result": result}
        
        elif request.tool == "analyze_codebase":
            result = mcp_server.analyze_codebase()
            return {"result": result}
        
        elif request.tool == "search_docs":
            if "query" not in request.args:
                raise HTTPException(status_code=400, detail="Missing 'query' parameter")
            result = mcp_server.search_docs(request.args["query"])
            return {"result": result}
        
        elif request.tool == "find_references":
            if "symbol" not in request.args:
                raise HTTPException(status_code=400, detail="Missing 'symbol' parameter")
            result = mcp_server.find_references(request.args["symbol"])
            return {"result": result}
        
        elif request.tool == "find_callers":
            if "symbol" not in request.args:
                raise HTTPException(status_code=400, detail="Missing 'symbol' parameter")
            # Load graph from Redis
            callers = mcp_server.find_callers(request.args["symbol"])
            if not callers:
                return {"result": [], "error": "Code graph not available. Run codebase indexing first."}
            return {"result": callers}
        
        elif request.tool == "impact_analysis":
            if "symbol" not in request.args:
                raise HTTPException(status_code=400, detail="Missing 'symbol' parameter")
            impacts = mcp_server.impact_analysis(request.args["symbol"])
            if not impacts:
                return {"result": [], "error": "Code graph not available. Run codebase indexing first."}
            return {"result": impacts}
        
        elif request.tool == "git_diff":
            result = mcp_server.git_diff(request.args.get("file"))
            return {"result": result}
        
        elif request.tool == "run_tests":
            result = mcp_server.run_tests(request.args.get("test_file"))
            return {"result": result}
        
        # RAG tools (agentic - only called when agents need them)
        elif request.tool == "rag_search":
            if "query" not in request.args:
                raise HTTPException(status_code=400, detail="Missing 'query' parameter")
            top_k = request.args.get("top_k", 5)
            result = await _call_rag_search(request.args["query"], top_k)
            return {"result": result}
        
        elif request.tool == "rag_query":
            if "question" not in request.args:
                raise HTTPException(status_code=400, detail="Missing 'question' parameter")
            top_k = request.args.get("top_k", 5)
            result = await _call_rag_query(request.args["question"], top_k)
            return {"result": result}
        
        else:
            raise HTTPException(status_code=400, detail=f"Unknown tool: {request.tool}")
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tool execution error: {str(e)}")


# RAG tool implementations (lazy-loaded, optional)
_rag_service_cache = None

def _get_rag_service():
    """Lazy load RAG service if available"""
    global _rag_service_cache
    if _rag_service_cache is None:
        try:
            from orchestrator.rag_service_faiss import RAGServiceFAISS
            import os
            index_path = os.getenv("RAG_INDEX_PATH", "data/rag_indexes/codebase.index")
            if os.path.exists(index_path):
                _rag_service_cache = RAGServiceFAISS(
                    embedding_model=os.getenv("EMBEDDING_MODEL", "nomic-embed-text-v1.5"),
                    index_path=index_path
                )
        except (ImportError, Exception) as e:
            # RAG not available - return None
            _rag_service_cache = False  # Mark as checked
    return _rag_service_cache if _rag_service_cache else None

async def _call_rag_search(query: str, top_k: int = 5, hybrid: bool = True) -> str:
    """
    RAG search tool - called by agents when needed.
    Uses hybrid search (semantic + keyword) if available.
    """
    rag = _get_rag_service()
    if not rag:
        return " RAG not available. Index codebase first: python3 scripts/index_codebase.py"
    
    try:
        # Use hybrid search if enabled and MCP is available
        if hybrid:
            try:
                from orchestrator.hybrid_search import HybridSearch
                hybrid_search = HybridSearch(rag_service=rag, mcp_client=mcp_server)
                results = hybrid_search.search(query, top_k=top_k)
                
                if not results:
                    return f" No relevant documents found for: {query}"
                
                formatted = f"Found {len(results)} relevant documents (hybrid search):\n\n"
                for i, result in enumerate(results, 1):
                    file_path = result.get('file_path', 'unknown')
                    final_score = result.get('final_score', 0.0)
                    sources = result.get('sources', [])
                    formatted += f"[{i}] {file_path}\n"
                    formatted += f"   Score: {final_score:.3f} | Sources: {', '.join(sources)}"
                    if 'line_number' in result.get('metadata', {}):
                        formatted += f" | Line: {result['metadata']['line_number']}"
                    formatted += f"\n   {result.get('text', '')[:400]}...\n\n"
                return formatted
            except Exception as e:
                # Fall back to semantic-only if hybrid fails
                logger.warning(f"Hybrid search failed, using semantic-only: {e}")
        
        # Fallback: Semantic-only search
        results = rag.search(query, top_k=top_k)
        if not results:
            return f" No relevant documents found for: {query}"
        
        formatted = f"Found {len(results)} relevant documents:\n\n"
        for i, doc in enumerate(results, 1):
            file_path = doc['metadata'].get('file_path', 'unknown')
            similarity = doc.get('score', 0.0)
            confidence = doc.get('confidence', similarity)  # Use confidence if available, fallback to similarity
            formatted += f"[{i}] {file_path}\n"
            formatted += f"   Similarity: {similarity:.3f} | Confidence: {confidence:.3f}"
            if 'recency_score' in doc.get('metadata', {}):
                formatted += f" | Recency: {doc['metadata']['recency_score']:.2f} | Importance: {doc['metadata']['importance_score']:.2f}"
            formatted += f"\n   {doc['text'][:400]}...\n\n"
        return formatted
    except Exception as e:
        return f" RAG search error: {str(e)}"

async def _call_rag_query(question: str, top_k: int = 5) -> str:
    """RAG query tool - called by agents when they need comprehensive answers"""
    rag = _get_rag_service()
    if not rag:
        return " RAG not available. Index codebase first: python3 scripts/index_codebase.py"
    
    try:
        answer = await rag.query(question, top_k=top_k)
        return answer
    except Exception as e:
        return f" RAG query error: {str(e)}"


# Convenience endpoints
@app.post("/api/mcp/read_file")
async def read_file_endpoint(request: ReadFileRequest):
    """Read a file from the codebase"""
    try:
        result = mcp_server.read_file(request.path)
        return {"result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/mcp/analyze_file")
async def analyze_file_endpoint(request: AnalyzeFileRequest):
    """Analyze a single file"""
    try:
        result = mcp_server.analyze_file(request.path)
        return {"result": result}
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/mcp/analyze_codebase")
async def analyze_codebase_endpoint():
    """Get codebase structure"""
    result = mcp_server.analyze_codebase()
    return {"result": result}


@app.post("/api/mcp/search_docs")
async def search_docs_endpoint(request: SearchDocsRequest):
    """Search documentation"""
    result = mcp_server.search_docs(request.query)
    return {"result": result}


@app.post("/api/mcp/find_references")
async def find_references_endpoint(request: FindReferencesRequest):
    """Find references to a symbol"""
    result = mcp_server.find_references(request.symbol)
    return {"result": result}


@app.post("/api/mcp/git_diff")
async def git_diff_endpoint(request: GitDiffRequest):
    """Get git diff"""
    result = mcp_server.git_diff(request.file)
    return {"result": result}


@app.post("/api/mcp/run_tests")
async def run_tests_endpoint(request: RunTestsRequest):
    """Run test suite"""
    result = mcp_server.run_tests(request.test_file)
    return {"result": result}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("MCP_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)

