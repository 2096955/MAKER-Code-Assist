#!/usr/bin/env python3
"""
Tests for SkillLoader class
"""

import pytest
import tempfile
from pathlib import Path
from orchestrator.skill_loader import SkillLoader, Skill


def create_test_skill(tmp_path: Path, skill_name: str, content: str):
    """Helper to create a test skill file"""
    skill_dir = tmp_path / skill_name
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(content, encoding='utf-8')
    return skill_file


def test_skill_loader_initialization(tmp_path):
    """Test SkillLoader initializes correctly"""
    loader = SkillLoader(tmp_path)
    assert loader.skills_dir == Path(tmp_path)
    assert len(loader.skills_cache) == 0


def test_load_skill_success(tmp_path):
    """Test loading a valid skill"""
    skill_content = """---
name: test-skill
description: A test skill
category: test
applies_to: ["test", "example"]
success_rate: 0.5
---

# Test Skill

This is a test skill.
"""
    create_test_skill(tmp_path, "test-skill", skill_content)
    
    loader = SkillLoader(tmp_path)
    skill = loader.load_skill("test-skill")
    
    assert skill is not None
    assert skill.name == "test-skill"
    assert skill.description == "A test skill"
    assert skill.category == "test"
    assert skill.applies_to == ["test", "example"]
    assert "Test Skill" in skill.instructions
    assert skill.metadata["success_rate"] == 0.5


def test_load_skill_not_found(tmp_path):
    """Test loading non-existent skill"""
    loader = SkillLoader(tmp_path)
    skill = loader.load_skill("nonexistent")
    assert skill is None


def test_load_skill_missing_required_fields(tmp_path):
    """Test loading skill with missing required fields"""
    skill_content = """---
category: test
---

# Test Skill
"""
    create_test_skill(tmp_path, "bad-skill", skill_content)
    
    loader = SkillLoader(tmp_path)
    skill = loader.load_skill("bad-skill")
    assert skill is None


def test_load_skill_caching(tmp_path):
    """Test that skills are cached"""
    skill_content = """---
name: cached-skill
description: A cached skill
category: test
---

# Cached Skill
"""
    create_test_skill(tmp_path, "cached-skill", skill_content)
    
    loader = SkillLoader(tmp_path)
    skill1 = loader.load_skill("cached-skill")
    skill2 = loader.load_skill("cached-skill")
    
    # Should be same object (cached)
    assert skill1 is skill2


def test_load_all_skills(tmp_path):
    """Test loading all skills"""
    skill1_content = """---
name: skill-1
description: First skill
category: test
---

# Skill 1
"""
    skill2_content = """---
name: skill-2
description: Second skill
category: test
---

# Skill 2
"""
    create_test_skill(tmp_path, "skill-1", skill1_content)
    create_test_skill(tmp_path, "skill-2", skill2_content)
    
    loader = SkillLoader(tmp_path)
    skills = loader.load_all_skills()
    
    assert len(skills) == 2
    skill_names = {s.name for s in skills}
    assert skill_names == {"skill-1", "skill-2"}


def test_parse_skill_file_applies_to_string(tmp_path):
    """Test that applies_to can be a single string"""
    skill_content = """---
name: string-skill
description: Skill with string applies_to
category: test
applies_to: "single-value"
---

# Skill
"""
    create_test_skill(tmp_path, "string-skill", skill_content)
    
    loader = SkillLoader(tmp_path)
    skill = loader.load_skill("string-skill")
    
    assert skill is not None
    assert skill.applies_to == ["single-value"]


def test_parse_skill_file_defaults(tmp_path):
    """Test skill parsing with defaults"""
    skill_content = """---
name: default-skill
description: Skill with defaults
---

# Skill
"""
    create_test_skill(tmp_path, "default-skill", skill_content)
    
    loader = SkillLoader(tmp_path)
    skill = loader.load_skill("default-skill")
    
    assert skill is not None
    assert skill.category == "uncategorized"
    assert skill.applies_to == []


def test_reload_skill(tmp_path):
    """Test reloading a skill bypasses cache"""
    skill_content = """---
name: reload-skill
description: Original description
category: test
---

# Original
"""
    create_test_skill(tmp_path, "reload-skill", skill_content)
    
    loader = SkillLoader(tmp_path)
    skill1 = loader.load_skill("reload-skill")
    
    # Modify file
    new_content = """---
name: reload-skill
description: Updated description
category: test
---

# Updated
"""
    (tmp_path / "reload-skill" / "SKILL.md").write_text(new_content, encoding='utf-8')
    
    # Reload
    skill2 = loader.reload_skill("reload-skill")
    
    assert skill2 is not None
    assert skill2.description == "Updated description"
    assert "Updated" in skill2.instructions


def test_get_skill_names(tmp_path):
    """Test getting list of skill names"""
    create_test_skill(tmp_path, "skill-1", """---
name: skill-1
description: First
---

# Skill 1
""")
    create_test_skill(tmp_path, "skill-2", """---
name: skill-2
description: Second
---

# Skill 2
""")
    
    loader = SkillLoader(tmp_path)
    names = loader.get_skill_names()
    
    assert len(names) == 2
    assert "skill-1" in names
    assert "skill-2" in names


def test_clear_cache(tmp_path):
    """Test clearing the cache"""
    skill_content = """---
name: cache-test
description: Cache test
category: test
---

# Test
"""
    create_test_skill(tmp_path, "cache-test", skill_content)
    
    loader = SkillLoader(tmp_path)
    loader.load_skill("cache-test")
    assert len(loader.skills_cache) == 1
    
    loader.clear_cache()
    assert len(loader.skills_cache) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

