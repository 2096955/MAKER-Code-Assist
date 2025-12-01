#!/usr/bin/env python3
"""
Tests for SkillMatcher class
"""

import pytest
import tempfile
from pathlib import Path
from orchestrator.skill_loader import SkillLoader, Skill
from orchestrator.skill_matcher import SkillMatcher


def create_test_skill(tmp_path: Path, skill_name: str, content: str):
    """Helper to create a test skill file"""
    skill_dir = tmp_path / skill_name
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(content, encoding='utf-8')
    return skill_file


class MockRAGService:
    """Mock RAG service for testing"""
    def __init__(self):
        self.documents = []
        self.indexed = {}
    
    def add_document(self, text: str, metadata: dict):
        """Mock add_document"""
        self.indexed[metadata.get('skill_name')] = {
            'text': text,
            'metadata': metadata
        }
    
    def search(self, query: str, top_k: int = 5):
        """Mock search - returns simple results"""
        results = []
        query_lower = query.lower()
        
        for skill_name, doc in self.indexed.items():
            if query_lower in doc['text'].lower():
                results.append({
                    'score': 0.8,  # Mock similarity score
                    'metadata': doc['metadata']
                })
        
        return results[:top_k]


def test_skill_matcher_initialization(tmp_path):
    """Test SkillMatcher initializes correctly"""
    loader = SkillLoader(tmp_path)
    matcher = SkillMatcher(loader)
    
    assert matcher.skill_loader is loader
    assert matcher.rag is None
    assert matcher._skills_indexed is False


def test_find_relevant_skills_keyword_match(tmp_path):
    """Test finding skills by keyword matching"""
    skill_content = """---
name: regex-skill
description: Fix regex patterns
category: core-coding
applies_to: ["regex", "pattern", "validation"]
success_rate: 0.65
---

# Regex Skill
"""
    create_test_skill(tmp_path, "regex-skill", skill_content)
    
    loader = SkillLoader(tmp_path)
    matcher = SkillMatcher(loader)
    
    # Task mentions "regex"
    skills = matcher.find_relevant_skills("Fix regex pattern in email validator", top_k=1)
    
    assert len(skills) == 1
    assert skills[0].name == "regex-skill"


def test_find_relevant_skills_no_match(tmp_path):
    """Test when no skills match"""
    skill_content = """---
name: regex-skill
description: Fix regex patterns
category: core-coding
applies_to: ["regex"]
---

# Regex Skill
"""
    create_test_skill(tmp_path, "regex-skill", skill_content)
    
    loader = SkillLoader(tmp_path)
    matcher = SkillMatcher(loader)
    
    # Task doesn't mention regex
    skills = matcher.find_relevant_skills("Fix database migration", top_k=1)
    
    # Should still return skills (sorted by score, even if low)
    assert isinstance(skills, list)


def test_calculate_relevance_keyword_match(tmp_path):
    """Test relevance calculation with keyword match"""
    skill_content = """---
name: test-skill
description: Test skill
category: test
applies_to: ["test", "example"]
success_rate: 0.8
---

# Test Skill
"""
    create_test_skill(tmp_path, "test-skill", skill_content)
    
    loader = SkillLoader(tmp_path)
    matcher = SkillMatcher(loader)
    skill = loader.load_skill("test-skill")
    
    # Task contains keyword
    score = matcher.calculate_relevance("This is a test example", skill)
    
    assert score > 0.0
    assert score <= 1.0


def test_calculate_relevance_no_keyword(tmp_path):
    """Test relevance calculation without keyword match"""
    skill_content = """---
name: test-skill
description: Test skill
category: test
applies_to: ["regex"]
success_rate: 0.5
---

# Test Skill
"""
    create_test_skill(tmp_path, "test-skill", skill_content)
    
    loader = SkillLoader(tmp_path)
    matcher = SkillMatcher(loader)
    skill = loader.load_skill("test-skill")
    
    # Task doesn't contain keyword
    score = matcher.calculate_relevance("Fix database migration", skill)
    
    # Should still have some score (from semantic similarity and success rate)
    assert score >= 0.0
    assert score <= 1.0


def test_calculate_relevance_with_rag(tmp_path):
    """Test relevance calculation with RAG service"""
    skill_content = """---
name: regex-skill
description: Fix regex patterns
category: core-coding
applies_to: ["regex"]
success_rate: 0.65
---

# Regex Skill
"""
    create_test_skill(tmp_path, "regex-skill", skill_content)
    
    loader = SkillLoader(tmp_path)
    rag = MockRAGService()
    matcher = SkillMatcher(loader, rag)
    
    # Index skills
    matcher.index_all_skills()
    
    skill = loader.load_skill("regex-skill")
    score = matcher.calculate_relevance("Fix regex pattern", skill)
    
    assert score > 0.0
    assert score <= 1.0


def test_index_all_skills(tmp_path):
    """Test indexing all skills in RAG"""
    skill1_content = """---
name: skill-1
description: First skill
category: test
applies_to: ["test"]
---

# Skill 1
"""
    skill2_content = """---
name: skill-2
description: Second skill
category: test
applies_to: ["example"]
---

# Skill 2
"""
    create_test_skill(tmp_path, "skill-1", skill1_content)
    create_test_skill(tmp_path, "skill-2", skill2_content)
    
    loader = SkillLoader(tmp_path)
    rag = MockRAGService()
    matcher = SkillMatcher(loader, rag)
    
    matcher.index_all_skills()
    
    assert matcher._skills_indexed is True
    assert len(rag.indexed) == 2
    assert "skill-1" in rag.indexed
    assert "skill-2" in rag.indexed


def test_get_skill_context(tmp_path):
    """Test formatting skills as context"""
    skill_content = """---
name: test-skill
description: Test skill description
category: test
applies_to: ["test"]
---

# Test Skill

Instructions here.
"""
    create_test_skill(tmp_path, "test-skill", skill_content)
    
    loader = SkillLoader(tmp_path)
    matcher = SkillMatcher(loader)
    skill = loader.load_skill("test-skill")
    
    context = matcher.get_skill_context([skill])
    
    assert "test-skill" in context
    assert "Test skill description" in context
    assert "Instructions here" in context


def test_simple_text_similarity(tmp_path):
    """Test simple text similarity fallback"""
    loader = SkillLoader(tmp_path)
    matcher = SkillMatcher(loader)
    
    score = matcher._simple_text_similarity("regex pattern", "regex pattern fixing")
    assert score > 0.0
    assert score <= 1.0
    
    score2 = matcher._simple_text_similarity("database", "regex pattern")
    assert score2 < score  # Less similar


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

