#!/usr/bin/env python3
"""
Tests for SkillRegistry class
"""

import pytest
import json
from datetime import datetime
from orchestrator.skill_registry import SkillRegistry
from orchestrator.skill_loader import Skill


class MockRedis:
    """Mock Redis client for testing"""
    def __init__(self):
        self.data = {}
    
    def hset(self, key, field, value):
        if key not in self.data:
            self.data[key] = {}
        self.data[key][field] = value
    
    def hget(self, key, field):
        if key in self.data and field in self.data[key]:
            return self.data[key][field]
        return None
    
    def hgetall(self, key):
        return self.data.get(key, {})
    
    def hdel(self, key, field):
        if key in self.data and field in self.data[key]:
            del self.data[key][field]


def test_skill_registry_initialization():
    """Test SkillRegistry initializes correctly"""
    redis = MockRedis()
    registry = SkillRegistry(redis)
    
    assert registry.redis is redis
    assert registry.registry_key == "skills:registry"


def test_register_skill():
    """Test registering a new skill"""
    redis = MockRedis()
    registry = SkillRegistry(redis)
    
    skill = Skill(
        name="test-skill",
        description="Test skill",
        category="test",
        applies_to=["test"],
        instructions="# Test skill",
        metadata={"learned": True}
    )
    
    result = registry.register_skill(skill)
    assert result is True
    
    stats = registry.get_skill_stats("test-skill")
    assert stats is not None
    assert stats["name"] == "test-skill"
    assert stats["usage_count"] == 0
    assert stats["success_rate"] == 0.5


def test_update_skill_stats_success():
    """Test updating skill stats with success"""
    redis = MockRedis()
    registry = SkillRegistry(redis)
    
    # Register skill first
    skill = Skill(
        name="test-skill",
        description="Test",
        category="test",
        applies_to=[],
        instructions=""
    )
    registry.register_skill(skill)
    
    # Update with success
    result = registry.update_skill_stats("test-skill", success=True)
    assert result is True
    
    stats = registry.get_skill_stats("test-skill")
    assert stats["usage_count"] == 1
    assert stats["success_count"] == 1
    assert stats["success_rate"] == 1.0


def test_update_skill_stats_failure():
    """Test updating skill stats with failure"""
    redis = MockRedis()
    registry = SkillRegistry(redis)
    
    skill = Skill(
        name="test-skill",
        description="Test",
        category="test",
        applies_to=[],
        instructions=""
    )
    registry.register_skill(skill)
    
    # Update with failure
    registry.update_skill_stats("test-skill", success=False)
    registry.update_skill_stats("test-skill", success=False)
    registry.update_skill_stats("test-skill", success=True)
    
    stats = registry.get_skill_stats("test-skill")
    assert stats["usage_count"] == 3
    assert stats["success_count"] == 1
    assert stats["success_rate"] == pytest.approx(1.0 / 3.0, rel=0.01)


def test_get_skill_stats_not_found():
    """Test getting stats for non-existent skill"""
    redis = MockRedis()
    registry = SkillRegistry(redis)
    
    stats = registry.get_skill_stats("nonexistent")
    assert stats is None


def test_get_all_skill_stats():
    """Test getting all skill statistics"""
    redis = MockRedis()
    registry = SkillRegistry(redis)
    
    # Register multiple skills
    for i in range(3):
        skill = Skill(
            name=f"skill-{i}",
            description=f"Skill {i}",
            category="test",
            applies_to=[],
            instructions=""
        )
        registry.register_skill(skill)
    
    all_stats = registry.get_all_skill_stats()
    assert len(all_stats) == 3
    assert "skill-0" in all_stats
    assert "skill-1" in all_stats
    assert "skill-2" in all_stats


def test_merge_similar_skills():
    """Test merging two similar skills"""
    redis = MockRedis()
    registry = SkillRegistry(redis)
    
    # Register two skills
    skill1 = Skill(name="skill-1", description="", category="", applies_to=[], instructions="")
    skill2 = Skill(name="skill-2", description="", category="", applies_to=[], instructions="")
    
    registry.register_skill(skill1)
    registry.register_skill(skill2)
    
    # Update stats for both
    registry.update_skill_stats("skill-1", success=True)
    registry.update_skill_stats("skill-1", success=True)
    registry.update_skill_stats("skill-2", success=True)
    registry.update_skill_stats("skill-2", success=False)
    
    # Merge
    result = registry.merge_similar_skills("skill-1", "skill-2")
    assert result is True
    
    # Check merged stats
    merged = registry.get_skill_stats("skill-1")
    assert merged["usage_count"] == 4  # 2 + 2
    assert merged["success_count"] == 3  # 2 + 1
    assert merged["success_rate"] == pytest.approx(3.0 / 4.0, rel=0.01)
    
    # Check skill-2 is removed
    assert registry.get_skill_stats("skill-2") is None


def test_deprecate_low_performing_skills():
    """Test finding low-performing skills"""
    redis = MockRedis()
    registry = SkillRegistry(redis)
    
    # Create skills with different success rates
    for i, success_rate in enumerate([0.2, 0.5, 0.8]):
        skill = Skill(
            name=f"skill-{i}",
            description="",
            category="",
            applies_to=[],
            instructions=""
        )
        registry.register_skill(skill)
        
        # Update to achieve target success rate
        for _ in range(5):
            success = (i * 2 + _) % 5 < (success_rate * 5)
            registry.update_skill_stats(f"skill-{i}", success=success)
    
    # Find deprecated skills
    deprecated = registry.deprecate_low_performing_skills(threshold=0.3)
    
    # skill-0 should be deprecated (low success rate)
    assert "skill-0" in deprecated
    # skill-1 and skill-2 should not be deprecated
    assert "skill-1" not in deprecated or "skill-2" not in deprecated


def test_get_top_skills():
    """Test getting top performing skills"""
    redis = MockRedis()
    registry = SkillRegistry(redis)
    
    # Create skills with different success rates
    for i, target_rate in enumerate([0.3, 0.6, 0.9]):
        skill = Skill(
            name=f"top-skill-{i}",
            description="",
            category="",
            applies_to=[],
            instructions=""
        )
        registry.register_skill(skill)
        
        # Update to achieve target rate
        for _ in range(10):
            success = _ < (target_rate * 10)
            registry.update_skill_stats(f"top-skill-{i}", success=success)
    
    # Get top skills
    top_skills = registry.get_top_skills(top_k=2)
    
    assert len(top_skills) == 2
    # Should be sorted by success rate (descending)
    assert top_skills[0]["success_rate"] >= top_skills[1]["success_rate"]
    # Top skill should be the one with 0.9 rate
    assert top_skills[0]["name"] == "top-skill-2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

