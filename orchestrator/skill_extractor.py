#!/usr/bin/env python3
"""
Skill extractor for learning patterns from completed tasks.

Extracts reusable coding patterns from successful tasks and creates new skills.
Also extracts anti-patterns from failed tasks.
"""

import re
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from orchestrator.orchestrator import TaskState
else:
    # Import at runtime to avoid circular dependency
    try:
        from orchestrator.orchestrator import TaskState
    except ImportError:
        # Fallback for testing
        TaskState = None

from orchestrator.skill_loader import Skill, SkillLoader


class SkillExtractor:
    """
    Extracts skills from completed tasks.
    
    Analyzes successful code to identify reusable patterns,
    and failed code to identify anti-patterns.
    """
    
    def __init__(self, skills_dir: Path, skill_loader: SkillLoader):
        """
        Initialize skill extractor.
        
        Args:
            skills_dir: Path to skills directory
            skill_loader: SkillLoader instance for checking existing skills
        """
        self.skills_dir = Path(skills_dir)
        self.skill_loader = skill_loader
    
    def is_skill_worthy(self, state: 'TaskState') -> bool:
        """
        Determine if a task is worth extracting as a skill.
        
        Args:
            state: TaskState from completed task
        
        Returns:
            True if task should be extracted as skill
        """
        # For RESOLVED tasks: Extract proven patterns
        if state.review_feedback and state.review_feedback.get('status') == 'approved':
            return (
                state.code and
                len(state.code) > 200 and  # Non-trivial
                self._has_reusable_pattern(state) and
                self._detect_pattern_type(state.code) is not None and
                not self._is_one_off_solution(state)
            )
        
        # For FAILED tasks: Extract anti-patterns (what NOT to do)
        if state.review_feedback and state.review_feedback.get('status') == 'failed':
            return (
                state.iteration_count > 2 and  # Multiple attempts
                self._has_clear_failure_reason(state) and
                state.code and
                len(state.code) > 100  # Enough code to analyze
            )
        
        return False
    
    async def extract_skill_from_task(self, task_id: str, state: 'TaskState', redis_client) -> Optional[Skill]:
        """
        Extract a skill from a completed task.
        
        Args:
            task_id: Task identifier
            state: TaskState from completed task
            redis_client: Redis client for accessing task data
        
        Returns:
            Skill object if extraction successful, None otherwise
        """
        if not self.is_skill_worthy(state):
            return None
        
        # Detect pattern type
        pattern_type = self._detect_pattern_type(state.code)
        if not pattern_type:
            return None
        
        # Generate skill name
        skill_name = self._generate_skill_name(pattern_type, state)
        
        # Check if skill already exists
        existing_skill = self.skill_loader.load_skill(skill_name)
        if existing_skill:
            # Skill exists - might want to merge/update instead
            # For now, create versioned name
            skill_name = f"{skill_name}-v{self._get_next_version(skill_name)}"
        
        # Generate skill definition
        skill_content = await self.generate_skill_definition(state, pattern_type, skill_name)
        
        if not skill_content:
            return None
        
        # Save skill to file
        skill_path = self.skills_dir / skill_name / "SKILL.md"
        skill_path.parent.mkdir(parents=True, exist_ok=True)
        skill_path.write_text(skill_content, encoding='utf-8')
        
        # Load the created skill
        skill = self.skill_loader.reload_skill(skill_name)
        
        return skill
    
    def _detect_pattern_type(self, code: str) -> Optional[str]:
        """
        Detect what type of pattern this code represents.
        
        Args:
            code: Code string to analyze
        
        Returns:
            Pattern type name or None
        """
        code_lower = code.lower()
        
        # Regex patterns
        if re.search(r'\bimport\s+re\b', code) or re.search(r're\.(compile|match|search|findall)', code):
            return "regex-pattern-fixing"
        
        # AST manipulation
        if re.search(r'\bimport\s+ast\b', code) or 'NodeVisitor' in code or 'NodeTransformer' in code:
            return "python-ast-refactoring"
        
        # Django migrations
        if 'migrations.Migration' in code or 'makemigrations' in code_lower or 'models.Model' in code:
            return "django-migration-patterns"
        
        # Test-driven (has test assertions)
        if 'assert' in code or 'pytest' in code_lower or 'unittest' in code_lower:
            return "test-driven-bug-fixing"
        
        # Error message reading (has error handling)
        if 'except' in code or 'try:' in code or 'Error' in code:
            return "error-message-reading"
        
        return None
    
    def _has_reusable_pattern(self, state: 'TaskState') -> bool:
        """
        Check if task contains a reusable pattern.
        
        Args:
            state: TaskState to analyze
        
        Returns:
            True if pattern is reusable
        """
        if not state.code:
            return False
        
        # Check for common patterns
        code = state.code
        
        # Has functions/classes (reusable structure)
        has_structure = bool(re.search(r'\b(def|class)\s+\w+', code))
        
        # Has patterns we can extract
        has_pattern = self._detect_pattern_type(code) is not None
        
        # Not just a single line change
        lines_of_code = len([l for l in code.split('\n') if l.strip() and not l.strip().startswith('#')])
        has_complexity = lines_of_code >= 3
        
        return has_structure and has_pattern and has_complexity
    
    def _is_one_off_solution(self, state: 'TaskState') -> bool:
        """
        Check if this is a one-off solution not worth extracting.
        
        Args:
            state: TaskState to analyze
        
        Returns:
            True if solution is too specific
        """
        if not state.code:
            return True
        
        code = state.code
        
        # Too many hardcoded values
        hardcoded_count = len(re.findall(r'["\']\w+["\']', code))
        if hardcoded_count > 10:
            return True
        
        # Very specific file paths
        if re.search(r'/[a-z]+/[a-z]+/[a-z]+', code):
            return True
        
        # Very short code (might be trivial)
        if len(code) < 200:
            return True
        
        return False
    
    def _has_clear_failure_reason(self, state: 'TaskState') -> bool:
        """
        Check if failed task has a clear failure reason to learn from.
        
        Args:
            state: TaskState from failed task
        
        Returns:
            True if failure reason is clear
        """
        if not state.review_feedback:
            return False
        
        feedback = state.review_feedback.get('feedback', '')
        
        # Has specific error messages
        has_error = any(word in feedback.lower() for word in ['error', 'failed', 'exception', 'bug'])
        
        # Has multiple iterations (tried different approaches)
        has_iterations = state.iteration_count > 2
        
        return has_error and has_iterations
    
    def _generate_skill_name(self, pattern_type: str, state: 'TaskState') -> str:
        """
        Generate a skill name from pattern type and task.
        
        Args:
            pattern_type: Detected pattern type
            state: TaskState
        
        Returns:
            Skill name
        """
        # Use pattern type as base
        base_name = pattern_type
        
        # If task has a specific domain, add it
        if state.user_input:
            # Extract key terms from user input
            words = re.findall(r'\b\w+\b', state.user_input.lower())
            if len(words) > 0:
                # Use first significant word as modifier
                modifier = words[0] if words[0] not in ['fix', 'add', 'update', 'create'] else words[1] if len(words) > 1 else None
                if modifier and len(modifier) > 3:
                    base_name = f"{pattern_type}-{modifier}"
        
        # Sanitize name
        base_name = re.sub(r'[^a-z0-9-]', '-', base_name.lower())
        base_name = re.sub(r'-+', '-', base_name)
        base_name = base_name.strip('-')
        
        return base_name
    
    def _get_next_version(self, skill_name: str) -> int:
        """
        Get next version number for a skill.
        
        Args:
            skill_name: Base skill name
        
        Returns:
            Next version number
        """
        # Check existing versions
        existing = []
        for path in self.skills_dir.glob(f"{skill_name}-v*"):
            match = re.search(r'-v(\d+)$', path.name)
            if match:
                existing.append(int(match.group(1)))
        
        if existing:
            return max(existing) + 1
        return 1
    
    async def generate_skill_definition(
        self, 
        state: 'TaskState', 
        pattern_type: str,
        skill_name: str
    ) -> Optional[str]:
        """
        Generate SKILL.md content from task state.
        
        Args:
            state: TaskState
            pattern_type: Detected pattern type
            skill_name: Generated skill name
        
        Returns:
            SKILL.md content string
        """
        is_success = state.review_feedback and state.review_feedback.get('status') == 'approved'
        
        # Extract key information
        code = state.code or ""
        user_input = state.user_input or ""
        feedback = state.review_feedback.get('feedback', '') if state.review_feedback else ''
        
        # Generate frontmatter
        frontmatter = {
            "name": skill_name,
            "description": self._generate_description(user_input, pattern_type, is_success),
            "category": self._get_category(pattern_type),
            "applies_to": self._extract_keywords(user_input, code),
            "success_rate": 0.5,  # Initial rate, will be updated by registry
            "usage_count": 0,
            "created": datetime.now().isoformat(),
            "source_task": state.task_id,
            "learned": True
        }
        
        # Generate content
        content_parts = []
        
        # Title
        content_parts.append(f"# {skill_name.replace('-', ' ').title()}")
        content_parts.append("")
        
        # Recognition
        content_parts.append("## Recognition")
        content_parts.append("")
        content_parts.append("This skill applies when:")
        keywords = self._extract_keywords(user_input, code)
        for keyword in keywords[:5]:  # Top 5 keywords
            content_parts.append(f"- Task mentions \"{keyword}\"")
        content_parts.append("")
        
        if is_success:
            # Proven patterns (from successful task)
            content_parts.append("## Proven Patterns (from successful task)")
            content_parts.append("")
            patterns = self._extract_patterns(code)
            for pattern in patterns:
                content_parts.append(f"```python")
                content_parts.append(pattern)
                content_parts.append("```")
                content_parts.append("")
        else:
            # Anti-patterns (from failed task)
            content_parts.append("## Anti-Patterns (from failed task)")
            content_parts.append("")
            content_parts.append("**What NOT to do:**")
            content_parts.append("")
            anti_patterns = self._extract_anti_patterns(code, feedback)
            for anti_pattern in anti_patterns:
                content_parts.append(f"❌ {anti_pattern}")
            content_parts.append("")
        
        # Code example
        if code:
            content_parts.append("## Code Example")
            content_parts.append("")
            content_parts.append("```python")
            # Include relevant code snippet (first 50 lines)
            code_lines = code.split('\n')[:50]
            content_parts.append('\n'.join(code_lines))
            if len(code.split('\n')) > 50:
                content_parts.append("# ... (truncated)")
            content_parts.append("```")
            content_parts.append("")
        
        # Source
        content_parts.append("## Source")
        content_parts.append("")
        content_parts.append(f"Learned from task: {state.task_id}")
        if user_input:
            content_parts.append(f"Original task: {user_input[:100]}...")
        content_parts.append("")
        
        # Combine frontmatter and content
        yaml_frontmatter = "---\n"
        for key, value in frontmatter.items():
            if isinstance(value, list):
                yaml_frontmatter += f"{key}: {json.dumps(value)}\n"
            elif isinstance(value, str):
                yaml_frontmatter += f"{key}: {json.dumps(value)}\n"
            else:
                yaml_frontmatter += f"{key}: {value}\n"
        yaml_frontmatter += "---\n"
        
        return yaml_frontmatter + "\n" + "\n".join(content_parts)
    
    def _generate_description(self, user_input: str, pattern_type: str, is_success: bool) -> str:
        """Generate skill description"""
        if is_success:
            return f"Pattern learned from successful task: {user_input[:80]}..."
        else:
            return f"Anti-pattern learned from failed task: {user_input[:80]}..."
    
    def _get_category(self, pattern_type: str) -> str:
        """Get category for pattern type"""
        categories = {
            "regex-pattern-fixing": "core-coding",
            "python-ast-refactoring": "core-coding",
            "django-migration-patterns": "framework-specific",
            "test-driven-bug-fixing": "core-coding",
            "error-message-reading": "core-coding"
        }
        return categories.get(pattern_type, "uncategorized")
    
    def _extract_keywords(self, user_input: str, code: str) -> List[str]:
        """Extract keywords from user input and code"""
        keywords = []
        
        # From user input
        if user_input:
            words = re.findall(r'\b\w{4,}\b', user_input.lower())
            keywords.extend(words[:5])
        
        # From code (imports, function names)
        if code:
            imports = re.findall(r'import\s+(\w+)', code)
            keywords.extend(imports[:3])
            
            functions = re.findall(r'\bdef\s+(\w+)', code)
            keywords.extend(functions[:3])
        
        # Remove duplicates and common words
        common_words = {'this', 'that', 'with', 'from', 'import', 'def', 'class'}
        keywords = [k for k in set(keywords) if k not in common_words and len(k) > 3]
        
        return keywords[:10]  # Top 10
    
    def _extract_patterns(self, code: str) -> List[str]:
        """Extract key patterns from successful code"""
        patterns = []
        
        # Extract function definitions
        functions = re.findall(r'def\s+\w+\([^)]*\):.*?(?=\n\ndef|\nclass|\Z)', code, re.DOTALL)
        for func in functions[:3]:  # Top 3 functions
            # Clean up function
            func_lines = func.split('\n')
            if len(func_lines) > 20:
                func = '\n'.join(func_lines[:20]) + "\n    # ..."
            patterns.append(func.strip())
        
        return patterns
    
    def _extract_anti_patterns(self, code: str, feedback: str) -> List[str]:
        """Extract anti-patterns from failed code"""
        anti_patterns = []
        
        # From feedback
        if feedback:
            # Look for negative indicators
            if 'error' in feedback.lower():
                anti_patterns.append("Causes errors: " + feedback[:100])
            if 'failed' in feedback.lower():
                anti_patterns.append("Failed approach: " + feedback[:100])
        
        # From code (common mistakes)
        if 'try:' in code and 'except:' in code:
            if 'except Exception' in code or 'except:' in code:
                anti_patterns.append("Using bare except clauses")
        
        if re.search(r'\.\*[^?]', code):  # Greedy matching without lazy
            anti_patterns.append("Using greedy matching instead of lazy")
        
        if re.search(r'[^\\]\.', code):  # Unescaped dots
            anti_patterns.append("Not escaping special characters in regex")
        
        return anti_patterns[:5]  # Top 5

