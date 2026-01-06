#!/usr/bin/env python3
"""
Skill registry for managing skill lifecycle and statistics.

Tracks skill usage, success rates, and handles skill evolution.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Optional, Any, List
from orchestrator.skill_loader import Skill

logger = logging.getLogger(__name__)


class SkillRegistry:
    """
    Manages skill lifecycle and statistics in Redis.
    
    Tracks:
    - Usage count per skill
    - Success rate per skill
    - Last used timestamp
    - Skill versions
    """
    
    def __init__(self, redis_client):
        """
        Initialize skill registry.
        
        Args:
            redis_client: Redis client for persistence
        """
        self.redis = redis_client
        self.registry_key = "skills:registry"
    
    def register_skill(self, skill: Skill) -> bool:
        """
        Register a new skill in the registry.
        
        Args:
            skill: Skill to register
        
        Returns:
            True if registered successfully
        """
        try:
            skill_data = {
                "name": skill.name,
                "created": datetime.now().isoformat(),
                "usage_count": 0,
                "success_count": 0,
                "success_rate": 0.5,  # Initial rate
                "last_used": None,
                "version": 1,
                "category": skill.category,
                "learned": skill.metadata.get("learned", False)
            }
            
            # Store in Redis hash
            self.redis.hset(
                self.registry_key,
                skill.name,
                json.dumps(skill_data)
            )
            
            return True
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Error registering skill {skill.name}: {e}")
            return False
    
    def update_skill_stats(self, skill_name: str, success: bool) -> bool:
        """
        Update skill statistics after use.
        
        Args:
            skill_name: Name of the skill
            success: True if task succeeded, False otherwise
        
        Returns:
            True if updated successfully
        """
        try:
            # Get current stats
            skill_data = self.get_skill_stats(skill_name)
            if not skill_data:
                # Skill not in registry, create entry
                skill_data = {
                    "name": skill_name,
                    "created": datetime.now().isoformat(),
                    "usage_count": 0,
                    "success_count": 0,
                    "success_rate": 0.5,
                    "last_used": None,
                    "version": 1
                }
            
            # Update stats
            skill_data["usage_count"] = skill_data.get("usage_count", 0) + 1
            if success:
                skill_data["success_count"] = skill_data.get("success_count", 0) + 1
            
            # Calculate success rate
            if skill_data["usage_count"] > 0:
                skill_data["success_rate"] = skill_data["success_count"] / skill_data["usage_count"]
            
            skill_data["last_used"] = datetime.now().isoformat()
            
            # Save back to Redis
            self.redis.hset(
                self.registry_key,
                skill_name,
                json.dumps(skill_data)
            )
            
            return True
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Error updating skill stats for {skill_name}: {e}")
            return False
    
    def get_skill_stats(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics for a skill.
        
        Args:
            skill_name: Name of the skill
        
        Returns:
            Dictionary with skill statistics, or None if not found
        """
        try:
            data = self.redis.hget(self.registry_key, skill_name)
            if data:
                return json.loads(data)
            return None
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            logger.error(f"Error getting skill stats for {skill_name}: {e}")
            return None
    
    def get_all_skill_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all skills.
        
        Returns:
            Dictionary mapping skill names to their statistics
        """
        try:
            all_data = self.redis.hgetall(self.registry_key)
            result = {}
            for skill_name, data_str in all_data.items():
                try:
                    result[skill_name] = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
            return result
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            logger.error(f"Error getting all skill stats: {e}")
            return {}
    
    def merge_similar_skills(self, skill1_name: str, skill2_name: str) -> bool:
        """
        Merge two similar skills.
        
        Args:
            skill1_name: First skill name (kept)
            skill2_name: Second skill name (merged into first)
        
        Returns:
            True if merged successfully
        """
        try:
            stats1 = self.get_skill_stats(skill1_name)
            stats2 = self.get_skill_stats(skill2_name)
            
            if not stats1 or not stats2:
                return False
            
            # Merge statistics
            merged_stats = {
                "name": skill1_name,
                "created": min(stats1.get("created", ""), stats2.get("created", "")),
                "usage_count": stats1.get("usage_count", 0) + stats2.get("usage_count", 0),
                "success_count": stats1.get("success_count", 0) + stats2.get("success_count", 0),
                "last_used": max(stats1.get("last_used", ""), stats2.get("last_used", "")),
                "version": max(stats1.get("version", 1), stats2.get("version", 1)) + 1
            }
            
            # Calculate merged success rate
            if merged_stats["usage_count"] > 0:
                merged_stats["success_rate"] = merged_stats["success_count"] / merged_stats["usage_count"]
            else:
                merged_stats["success_rate"] = 0.5
            
            # Update skill1 with merged stats
            self.redis.hset(
                self.registry_key,
                skill1_name,
                json.dumps(merged_stats)
            )
            
            # Remove skill2
            self.redis.hdel(self.registry_key, skill2_name)
            
            return True
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Error merging skills {skill1_name} and {skill2_name}: {e}")
            return False
    
    def deprecate_low_performing_skills(self, threshold: float = 0.3) -> List[str]:
        """
        Find skills with success rate below threshold.
        
        Args:
            threshold: Minimum success rate (default: 0.3)
        
        Returns:
            List of skill names to deprecate
        """
        all_stats = self.get_all_skill_stats()
        deprecated = []
        
        for skill_name, stats in all_stats.items():
            success_rate = stats.get("success_rate", 0.5)
            usage_count = stats.get("usage_count", 0)
            
            # Only deprecate if used multiple times and low success rate
            if usage_count >= 3 and success_rate < threshold:
                deprecated.append(skill_name)
        
        return deprecated
    
    def get_top_skills(self, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Get top performing skills by success rate.
        
        Args:
            top_k: Number of top skills to return
        
        Returns:
            List of skill statistics, sorted by success rate
        """
        all_stats = self.get_all_skill_stats()
        
        # Filter skills with minimum usage
        qualified = [
            stats for stats in all_stats.values()
            if stats.get("usage_count", 0) >= 2
        ]
        
        # Sort by success rate (descending)
        qualified.sort(key=lambda x: x.get("success_rate", 0), reverse=True)
        
        return qualified[:top_k]

