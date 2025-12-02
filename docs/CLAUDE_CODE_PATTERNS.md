# Claude Code Patterns Analysis

Analysis of Claude Code's architecture and patterns from the deobfuscated source code at `/Users/anthonylui/claude-code-source-code-deobfuscation` to identify features we should replicate for our localized MAKER code assistant.

## 1. Configuration System

### What Claude Code Has

**File**: `src/config/schema.ts`

**Pattern**: **Hierarchical Zod Schema** with runtime validation

```typescript
configSchema = {
  workspace: string,
  logLevel: 'error' | 'warn' | 'info' | 'verbose' | 'debug' | 'trace',

  api: {
    key, baseUrl, version, timeout
  },

  telemetry: {
    enabled, anonymizeData, errorReporting
  },

  terminal: {
    theme: 'dark' | 'light' | 'system',
    showProgressIndicators, useColors, codeHighlighting,
    maxHeight, maxWidth
  },

  codeAnalysis: {
    indexDepth: 3,
    excludePatterns: ['node_modules/**', '.git/**', ...],
    includePatterns: ['**/*'],
    maxFileSize: 1MB,
    scanTimeout: 30s
  },

  git: {
    preferredRemote: 'origin',
    preferredBranch, useSsh, useGpg, signCommits
  },

  editor: {
    preferredLauncher, tabWidth: 2, insertSpaces, formatOnSave
  },

  paths: {
    home, app, cache, logs, workspace
  }
}
```

### What We Should Replicate

**Priority**: 🔴 High

**Create**: `orchestrator/config_schema.py` using Pydantic

**Features to add**:
1. **Hierarchical config structure** - Subsystem-specific configs
2. **Runtime validation** - Pydantic models instead of environment variables
3. **Per-project overrides** - `.maker.json` in project root
4. **Config hierarchy**: Project `.maker.json` → Global `~/.maker/config.json` → Defaults

**Example implementation**:
```python
from pydantic import BaseModel, Field
from typing import Literal, List, Optional

class CodeAnalysisConfig(BaseModel):
    index_depth: int = Field(default=3, ge=1)
    exclude_patterns: List[str] = Field(default=[
        'node_modules/**', '.git/**', '__pycache__/**'
    ])
    max_file_size: int = Field(default=1024*1024)  # 1MB
    scan_timeout: int = Field(default=30000)  # 30s

class TerminalConfig(BaseModel):
    theme: Literal['dark', 'light', 'system'] = 'system'
    show_progress: bool = True
    use_colors: bool = True
    code_highlighting: bool = True

class GitConfig(BaseModel):
    preferred_remote: str = 'origin'
    sign_commits: bool = False
    use_gpg: bool = False

class MakerConfig(BaseModel):
    workspace: Optional[str] = None
    log_level: Literal['error', 'warn', 'info', 'debug'] = 'info'

    code_analysis: CodeAnalysisConfig = Field(default_factory=CodeAnalysisConfig)
    terminal: TerminalConfig = Field(default_factory=TerminalConfig)
    git: GitConfig = Field(default_factory=GitConfig)

    # MAKER-specific
    maker_mode: Literal['high', 'low'] = 'high'
    num_candidates: int = Field(default=5, ge=1, le=10)
    vote_k: int = Field(default=3, ge=1)
```

**Files to create**:
- `orchestrator/config_schema.py` - Pydantic schema
- `orchestrator/config_loader.py` - Load from files/env
- `.maker.json.example` - Example project config

---

## 2. Codebase Analyzer

### What Claude Code Has

**File**: `src/codebase/analyzer.ts`

**Capabilities**:
- **File info** with language detection, stats, line count
- **Dependency tracking** - Import/require analysis
- **Project structure** - Files by language, total LOC
- **Language detection** by extension
- **Metrics** - Complexity, maintainability scores

**Key interfaces**:
```typescript
interface FileInfo {
  path, extension, language, size, lineCount, lastModified
}

interface DependencyInfo {
  name, type, source, importPath, isExternal
}

interface ProjectStructure {
  root, totalFiles, filesByLanguage, totalLOC, dependencies
}
```

### What We Should Replicate

**Priority**: 🟡 Medium

**Enhance**: `orchestrator/mcp_server.py`

**Add methods**:
1. `analyze_file()` - Return FileInfo with language, LOC, dependencies
2. `analyze_project()` - Return ProjectStructure with all files
3. `find_dependencies()` - Extract imports/requires from file
4. `get_file_metrics()` - Complexity, maintainability scores

**Implementation**:
```python
# Add to mcp_server.py
def analyze_file(self, path: str) -> Dict[str, Any]:
    """Analyze a single file for language, LOC, dependencies."""
    content = self.read_file(path)

    return {
        "path": path,
        "extension": Path(path).suffix,
        "language": self._detect_language(path),
        "size": len(content),
        "line_count": content.count('\n'),
        "last_modified": Path(path).stat().st_mtime,
        "dependencies": self._extract_imports(content, path)
    }

def analyze_codebase(self) -> Dict[str, Any]:
    """Analyze entire codebase structure."""
    files = self._find_all_files(self.codebase_path)

    files_by_language = {}
    total_loc = 0

    for file_path in files:
        info = self.analyze_file(file_path)
        lang = info["language"]
        files_by_language[lang] = files_by_language.get(lang, 0) + 1
        total_loc += info["line_count"]

    return {
        "root": str(self.codebase_path),
        "total_files": len(files),
        "files_by_language": files_by_language,
        "total_loc": total_loc
    }
```

---

## 3. Command System

### What Claude Code Has

**File**: `src/commands/index.ts`

**Pattern**: **Typed command registry** with argument validation

```typescript
interface CommandDef {
  name: string,
  description: string,
  args: CommandArgDef[],
  handler: (args, context) => Promise<void>,
  aliases?: string[],
  hidden?: boolean
}

interface CommandArgDef {
  name, description, type: 'string' | 'number' | 'boolean' | 'array',
  required?, default?, choices?,
  position?,  // For positional args
  shortFlag?, // -v for --verbose
  hidden?
}
```

**Features**:
- Strongly typed arguments
- Auto-generated help text
- Positional and flag arguments
- Argument validation
- Command aliases
- Hidden commands for internal use

### What We Should Replicate

**Priority**: 🟢 Low (we have slash commands, but could enhance)

**Current**: Slash commands in `.claude/commands/*.md`

**Enhancement**: Add type validation and auto-help

**Create**: `orchestrator/command_registry.py`

```python
from pydantic import BaseModel
from typing import Callable, List, Optional, Literal, Union

class CommandArg(BaseModel):
    name: str
    description: str
    type: Literal['string', 'number', 'boolean', 'array']
    required: bool = False
    default: Optional[Union[str, int, bool]] = None
    choices: Optional[List[str]] = None
    short_flag: Optional[str] = None

class CommandDef(BaseModel):
    name: str
    description: str
    args: List[CommandArg] = []
    handler: Callable
    aliases: List[str] = []
    hidden: bool = False

# Example usage
COMMANDS = {
    "commit": CommandDef(
        name="commit",
        description="Create a git commit with AI-generated message",
        args=[
            CommandArg(name="message", type="string", required=False),
            CommandArg(name="all", type="boolean", default=False, short_flag="-a")
        ],
        handler=lambda args: create_commit(args["message"], args["all"])
    )
}
```

---

## 4. Error Handling System

### What Claude Code Has

**Files**: `src/errors/formatter.ts`, `src/errors/types.ts`

**Pattern**: **Categorized errors** with context-aware formatting

```typescript
enum ErrorCategory {
  Authentication,
  FileSystem,
  Git,
  Network,
  Validation,
  Config,
  Internal
}

interface UserError {
  category: ErrorCategory,
  message: string,
  originalError?: Error,
  suggestions?: string[],
  recoverable?: boolean,
  context?: Record<string, any>
}
```

**Features**:
- Error categorization
- User-friendly error messages
- Actionable suggestions
- Recovery hints
- Context preservation

### What We Should Replicate

**Priority**: 🟡 Medium

**Create**: `orchestrator/errors.py`

```python
from enum import Enum
from typing import Optional, List, Dict, Any

class ErrorCategory(Enum):
    AUTHENTICATION = "authentication"
    FILE_SYSTEM = "file_system"
    GIT = "git"
    NETWORK = "network"
    VALIDATION = "validation"
    CONFIG = "config"
    MAKER_VOTING = "maker_voting"
    MODEL_TIMEOUT = "model_timeout"
    INTERNAL = "internal"

class UserError(Exception):
    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        suggestions: Optional[List[str]] = None,
        recoverable: bool = True,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.category = category
        self.suggestions = suggestions or []
        self.recoverable = recoverable
        self.context = context or {}

    def format_for_user(self) -> str:
        """Format error with suggestions for user display."""
        lines = [f"Error: {self.args[0]}"]

        if self.suggestions:
            lines.append("\nSuggestions:")
            for suggestion in self.suggestions:
                lines.append(f"  • {suggestion}")

        if self.context:
            lines.append(f"\nContext: {self.context}")

        return "\n".join(lines)

# Usage example
def read_file_safe(path: str) -> str:
    try:
        return Path(path).read_text()
    except FileNotFoundError:
        raise UserError(
            f"File not found: {path}",
            category=ErrorCategory.FILE_SYSTEM,
            suggestions=[
                "Check the file path is correct",
                "Ensure the file exists in the codebase",
                "Try using a relative path from project root"
            ],
            recoverable=True,
            context={"attempted_path": path}
        )
```

---

## 5. Terminal/UI Formatting

### What Claude Code Has

**File**: `src/terminal/formatting.ts`

**Functions we saw earlier** (the file you wanted to convert to Rust):
- `clearScreen()` - Clear terminal
- `getTerminalSize()` - Get dimensions
- `formatOutput()` - Markdown rendering
- `wordWrap()` - Text wrapping
- `formatCodeBlocks()` - Code block rendering with borders
- `highlightSyntax()` - Keyword highlighting

**Features**:
- ANSI color support
- Markdown parsing
- Code block borders (┏━━┓ style)
- Syntax highlighting
- Progress indicators
- Spinners

### What We Should Replicate

**Priority**: 🟢 Low (API-focused, not TUI)

**Current**: Basic output via FastAPI streaming

**Consideration**: Could enhance file output formatting for `output_file` parameter

**Potential enhancement**:
```python
# Add to orchestrator/output_formatter.py
def format_markdown_output(text: str) -> str:
    """Format streamed output as pretty markdown for file output."""
    # Add code block borders
    # Add syntax highlighting (ANSI codes)
    # Format headers, lists, etc.
    pass
```

---

## 6. Key Patterns Summary

### 1. ✅ **We Already Have** (Better Than Claude Code)

- **MAKER Voting** - Parallel candidate generation (Claude doesn't have this)
- **Dual Orchestrator** - High/Low RAM modes
- **EE Memory** - Narrative-aware code understanding
- **Context Compression** - Hierarchical with sliding window
- **MCP Server** - Codebase tools
- **Request Queue** - Mutex prevention

### 2. 🔴 **Critical to Add** (Quick Wins)

**From MISSING_CAPABILITIES.md + Claude Code**:

1. **Hierarchical Config System** (2-3 hours)
   - `.maker.json` at project/root/global levels
   - Pydantic schema validation
   - Subsystem-specific configs
   - Files: `orchestrator/config_schema.py`, `orchestrator/config_loader.py`

2. **Enhanced Error Handling** (2-3 hours)
   - Categorized errors with suggestions
   - Recovery hints
   - Context preservation
   - Files: `orchestrator/errors.py`

3. **File/Project Analyzer** (3-4 hours)
   - Language detection
   - Dependency extraction
   - Project metrics
   - Add to: `orchestrator/mcp_server.py`

### 3. 🟡 **Medium Priority**

4. **Command Registry** (3-4 hours)
   - Type validation for slash commands
   - Auto-generated help
   - Argument validation
   - Files: `orchestrator/command_registry.py`

5. **Declarative Tool Permissions** (2-3 hours)
   - Per-project allowed/blocked tools
   - `.maker.json` config
   - Safety controls

### 4. 🟢 **Nice-to-Have**

6. **Output Formatting** (2-3 hours)
   - Markdown rendering for file output
   - Code block borders
   - Syntax highlighting

---

## 7. Recommended Implementation Order

### Phase 1: Configuration System (Week 2)

**Total**: ~5-6 hours

1. Create `orchestrator/config_schema.py` with Pydantic models
2. Create `orchestrator/config_loader.py` with hierarchy loading
3. Add `.maker.json` support to orchestrator initialization
4. Update documentation

**Files**:
- `orchestrator/config_schema.py` (new)
- `orchestrator/config_loader.py` (new)
- `orchestrator/orchestrator.py` (modify to use config)
- `.maker.json.example` (new)
- `docs/CONFIGURATION.md` (new)

### Phase 2: Error Handling (Week 2)

**Total**: ~3 hours

1. Create `orchestrator/errors.py` with categorized exceptions
2. Add UserError with suggestions
3. Update existing code to use UserError
4. Add error recovery hints

**Files**:
- `orchestrator/errors.py` (new)
- Update all `orchestrator/*.py` files to use UserError

### Phase 3: Enhanced Analyzer (Week 3)

**Total**: ~4 hours

1. Add `analyze_file()` to MCP server
2. Add `analyze_codebase()` for project structure
3. Add dependency extraction
4. Add language detection

**Files**:
- `orchestrator/mcp_server.py` (enhance existing)
- `orchestrator/language_detector.py` (new)

---

## 8. What NOT to Replicate

**From Claude Code**:
- ❌ OAuth authentication (we're local-first)
- ❌ Terminal UI/TUI (we're API-focused)
- ❌ Telemetry (privacy-focused)
- ❌ Cloud sync (local-only)

**Our Advantages Over Claude Code**:
- ✅ 100% local (no API costs, works offline)
- ✅ MAKER voting (better quality than single-shot)
- ✅ Dual orchestrator modes (resource flexibility)
- ✅ EE Memory (narrative awareness)
- ✅ Context compression (handle longer sessions)
- ✅ File output streaming (crash recovery)

---

## 9. Integration Points

### How to Use Claude Code Patterns in MAKER

**1. Config System → `.maker.json`**
```json
{
  "maker_mode": "high",
  "num_candidates": 5,
  "code_analysis": {
    "exclude_patterns": ["node_modules/**", "dist/**"],
    "max_file_size": 1048576
  },
  "git": {
    "sign_commits": true,
    "preferred_remote": "origin"
  },
  "allowed_tools": ["read_file", "search_docs"],
  "blocked_tools": ["run_tests"]
}
```

**2. Error Handling → User-Friendly Messages**
```python
try:
    orchestrator.call_agent(agent, prompt)
except Exception as e:
    raise UserError(
        f"Agent {agent} failed to respond",
        category=ErrorCategory.MODEL_TIMEOUT,
        suggestions=[
            "Check llama.cpp server is running",
            "Verify model is loaded at the correct port",
            "Try restarting the llama.cpp server"
        ],
        context={"agent": agent, "port": get_agent_port(agent)}
    )
```

**3. Analyzer → Better MCP Tools**
```python
# MCP tool response
{
  "tool": "analyze_file",
  "result": {
    "path": "orchestrator/orchestrator.py",
    "language": "python",
    "loc": 1800,
    "dependencies": ["fastapi", "redis", "httpx"],
    "complexity": "high",
    "maintainability_score": 72
  }
}
```

---

## Conclusion

**Key Takeaways**:
1. Claude Code has excellent **configuration hierarchy** we should replicate
2. Their **error handling** with suggestions is user-friendly
3. The **codebase analyzer** provides useful project insights
4. We already have advantages with **MAKER voting** and **local-first**

**Next Steps**:
1. Implement hierarchical config system (`.maker.json`)
2. Add categorized error handling with suggestions
3. Enhance MCP server with file/project analysis
4. Document new features in user guide

**Total Effort**: ~12-15 hours for Phase 1-3 (Week 2-3 implementation)
