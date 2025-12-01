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
import ast
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="MCP Codebase Server", version="1.0.0")

class CodebaseMCPServer:
    def __init__(self, codebase_root: str):
        self.root = Path(codebase_root).resolve()
        self.excluded = {
            '.git', 'node_modules', 'dist', 'build', '__pycache__', '.specify', '.claude',
            'models', '.venv', 'venv', 'env', '.env', 'vendor', 'target', 
            '.docker', 'docker-data', '.cache', '.npm', '.yarn', 'coverage',
            '.idea', '.vscode', '.DS_Store', 'tmp', 'temp', 'logs',
            'weaviate_data', 'redis_data', 'postgres_data'
        }
        
    def read_file(self, path: str) -> str:
        """Safely read a file from codebase"""
        file_path = (self.root / path).resolve()
        
        # Security: Ensure path is within codebase
        if not str(file_path).startswith(str(self.root)):
            raise ValueError(f"Path traversal attempt: {path}")
            
        if not file_path.exists():
            return f" File not found: {path}"
            
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            return f" Error reading file: {e}"
    
    def analyze_codebase(self) -> Dict[str, Any]:
        """Return structure of codebase (files, folders, key exports)"""
        MAX_FILES = 500  # Limit to prevent timeout
        MAX_FILE_SIZE = 1_000_000  # 1MB max per file
        
        structure = {
            "total_files": 0,
            "total_lines": 0,
            "languages": {},
            "directories": [],
            "key_files": [],  # Important files found
            "truncated": False
        }
        
        for root, dirs, files in os.walk(self.root):
            # Skip excluded dirs
            dirs[:] = [d for d in dirs if d not in self.excluded]
            
            # Record directory
            rel_dir = Path(root).relative_to(self.root)
            if str(rel_dir) != '.':
                structure["directories"].append(str(rel_dir))
            
            for file in files:
                if file.startswith('.'):
                    continue
                
                # Check file limit
                if structure["total_files"] >= MAX_FILES:
                    structure["truncated"] = True
                    break
                    
                file_path = Path(root) / file
                ext = file_path.suffix
                
                # Skip large files
                try:
                    if file_path.stat().st_size > MAX_FILE_SIZE:
                        continue
                except:
                    continue
                
                # Count by language
                structure["languages"][ext] = structure["languages"].get(ext, 0) + 1
                
                # Track key files
                if file in {'README.md', 'package.json', 'requirements.txt', 'docker-compose.yml', 'Dockerfile', 'main.py', 'app.py', 'index.js', 'index.ts'}:
                    rel_path = file_path.relative_to(self.root)
                    structure["key_files"].append(str(rel_path))
                
                # Count lines (only for small files)
                try:
                    if file_path.stat().st_size < 100_000:  # Only count lines for files < 100KB
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = len(f.readlines())
                            structure["total_lines"] += lines
                except:
                    pass
                
                structure["total_files"] += 1
            
            if structure["truncated"]:
                break
        
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
                except:
                    pass
            elif path.is_dir():
                for doc_file in path.rglob('*.md'):
                    try:
                        with open(doc_file, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            if query.lower() in content.lower():
                                results.append(f" {doc_file.name}: Found '{query}'")
                    except:
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


# Initialize MCP server
codebase_root = os.getenv('CODEBASE_ROOT', os.getcwd())
mcp_server = CodebaseMCPServer(codebase_root)


# Request models
class ToolRequest(BaseModel):
    tool: str
    args: Dict[str, Any] = {}


class ReadFileRequest(BaseModel):
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
            "name": "analyze_codebase",
            "description": "Get codebase structure (files, languages, LOC)",
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
    """Execute an MCP tool"""
    try:
        if request.tool == "read_file":
            if "path" not in request.args:
                raise HTTPException(status_code=400, detail="Missing 'path' parameter")
            result = mcp_server.read_file(request.args["path"])
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

async def _call_rag_search(query: str, top_k: int = 5) -> str:
    """RAG search tool - called by agents when needed"""
    rag = _get_rag_service()
    if not rag:
        return " RAG not available. Index codebase first: python3 scripts/index_codebase.py"
    
    try:
        results = rag.search(query, top_k=top_k)
        if not results:
            return f" No relevant documents found for: {query}"
        
        formatted = f"Found {len(results)} relevant documents:\n\n"
        for i, doc in enumerate(results, 1):
            formatted += f"[{i}] {doc['metadata'].get('file_path', 'unknown')} (relevance: {doc['score']:.3f})\n"
            formatted += f"{doc['text'][:400]}...\n\n"
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

