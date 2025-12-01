#!/usr/bin/env python3
"""
Tests for SkillExtractor class
"""

import pytest
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from orchestrator.skill_extractor import SkillExtractor
from orchestrator.skill_loader import SkillLoader

# Define TaskState locally to avoid circular import
@dataclass
class TaskState:
    """TaskState for testing"""
    task_id: str
    user_input: str
    preprocessed_input: str = ""
    plan: Optional[dict] = None
    code: Optional[str] = None
    test_results: Optional[dict] = None
    review_feedback: Optional[Dict[str, Any]] = None
    status: str = "pending"
    iteration_count: int = 0
    context_stats: Optional[dict] = None


def create_test_task_state(
    task_id: str,
    code: str,
    user_input: str,
    status: str = "approved",
    feedback: str = ""
) -> TaskState:
    """Helper to create test TaskState"""
    return TaskState(
        task_id=task_id,
        user_input=user_input,
        preprocessed_input=user_input,
        code=code,
        review_feedback={"status": status, "feedback": feedback},
        status="complete" if status == "approved" else "failed",
        iteration_count=1 if status == "approved" else 3
    )


def test_skill_extractor_initialization(tmp_path):
    """Test SkillExtractor initializes correctly"""
    loader = SkillLoader(tmp_path)
    extractor = SkillExtractor(tmp_path, loader)
    
    assert extractor.skills_dir == Path(tmp_path)
    assert extractor.skill_loader is loader


def test_detect_pattern_type_regex(tmp_path):
    """Test pattern detection for regex"""
    loader = SkillLoader(tmp_path)
    extractor = SkillExtractor(tmp_path, loader)
    
    code = """
import re

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None
"""
    
    pattern_type = extractor._detect_pattern_type(code)
    assert pattern_type == "regex-pattern-fixing"


def test_detect_pattern_type_ast(tmp_path):
    """Test pattern detection for AST"""
    loader = SkillLoader(tmp_path)
    extractor = SkillExtractor(tmp_path, loader)
    
    code = """
import ast

class RefactorVisitor(ast.NodeVisitor):
    def visit_FunctionDef(self, node):
        return node
"""
    
    pattern_type = extractor._detect_pattern_type(code)
    assert pattern_type == "python-ast-refactoring"


def test_is_skill_worthy_approved(tmp_path):
    """Test skill worthiness for approved task"""
    loader = SkillLoader(tmp_path)
    extractor = SkillExtractor(tmp_path, loader)
    
    code = """
import re

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    pattern = r'^\\+?[1-9]\\d{1,14}$'
    return re.match(pattern, phone) is not None
"""
    
    state = create_test_task_state(
        "test_001",
        code,
        "Fix email validation regex",
        status="approved"
    )
    
    assert extractor.is_skill_worthy(state) is True


def test_is_skill_worthy_too_short(tmp_path):
    """Test skill worthiness rejects too short code"""
    loader = SkillLoader(tmp_path)
    extractor = SkillExtractor(tmp_path, loader)
    
    code = "x = 1"  # Too short
    
    state = create_test_task_state(
        "test_002",
        code,
        "Simple assignment",
        status="approved"
    )
    
    assert extractor.is_skill_worthy(state) is False


def test_is_skill_worthy_failed_task(tmp_path):
    """Test skill worthiness for failed task with clear reason"""
    loader = SkillLoader(tmp_path)
    extractor = SkillExtractor(tmp_path, loader)
    
    code = """
def validate_email(email):
    pattern = r'[\\w.]+@[\\w.]+'  # Missing anchors
    return re.match(pattern, email)
"""
    
    state = create_test_task_state(
        "test_003",
        code,
        "Fix email validation",
        status="failed",
        feedback="Error: Pattern matches invalid emails"
    )
    state.iteration_count = 3  # Multiple attempts
    
    assert extractor.is_skill_worthy(state) is True


def test_generate_skill_name(tmp_path):
    """Test skill name generation"""
    loader = SkillLoader(tmp_path)
    extractor = SkillExtractor(tmp_path, loader)
    
    state = create_test_task_state(
        "test_004",
        "import re\ndef validate(): pass",
        "Fix email validation regex pattern"
    )
    
    name = extractor._generate_skill_name("regex-pattern-fixing", state)
    assert "regex" in name.lower()
    assert "-" in name  # Should have dashes


def test_extract_keywords(tmp_path):
    """Test keyword extraction"""
    loader = SkillLoader(tmp_path)
    extractor = SkillExtractor(tmp_path, loader)
    
    user_input = "Fix email validation regex pattern"
    code = "import re\ndef validate_email(email): pass"
    
    keywords = extractor._extract_keywords(user_input, code)
    
    assert len(keywords) > 0
    assert "email" in keywords or "validation" in keywords


def test_extract_patterns(tmp_path):
    """Test pattern extraction from code"""
    loader = SkillLoader(tmp_path)
    extractor = SkillExtractor(tmp_path, loader)
    
    code = """
def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    return True
"""
    
    patterns = extractor._extract_patterns(code)
    
    assert len(patterns) > 0
    assert "validate_email" in patterns[0]


def test_extract_anti_patterns(tmp_path):
    """Test anti-pattern extraction"""
    loader = SkillLoader(tmp_path)
    extractor = SkillExtractor(tmp_path, loader)
    
    code = "pattern = r'.*@.*'  # Greedy matching"
    feedback = "Error: Pattern matches too much"
    
    anti_patterns = extractor._extract_anti_patterns(code, feedback)
    
    assert len(anti_patterns) > 0


@pytest.mark.asyncio
async def test_generate_skill_definition(tmp_path):
    """Test skill definition generation"""
    loader = SkillLoader(tmp_path)
    extractor = SkillExtractor(tmp_path, loader)
    
    code = """
import re

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None
"""
    
    state = create_test_task_state(
        "test_005",
        code,
        "Fix email validation regex",
        status="approved"
    )
    
    skill_def = await extractor.generate_skill_definition(
        state,
        "regex-pattern-fixing",
        "test-skill"
    )
    
    assert skill_def is not None
    assert "test-skill" in skill_def  # Name appears in frontmatter
    assert "## Recognition" in skill_def
    assert "validate_email" in skill_def or "pattern" in skill_def


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

