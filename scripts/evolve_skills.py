#!/usr/bin/env python3
"""
Skill evolution script - Refine skills based on usage data.

Analyzes skill performance and updates skill instructions based on what works.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.skill_registry import SkillRegistry
from orchestrator.skill_loader import SkillLoader
import redis


def analyze_skill_performance(registry: SkillRegistry, threshold: float = 0.3) -> Dict[str, Any]:
    """
    Analyze skill performance and identify issues.
    
    Args:
        registry: SkillRegistry instance
        threshold: Minimum success rate threshold
    
    Returns:
        Dictionary with analysis results
    """
    all_stats = registry.get_all_skill_stats()
    
    analysis = {
        "total_skills": len(all_stats),
        "high_performers": [],
        "low_performers": [],
        "needs_improvement": [],
        "deprecated": []
    }
    
    for skill_name, stats in all_stats.items():
        success_rate = stats.get("success_rate", 0.5)
        usage_count = stats.get("usage_count", 0)
        
        if usage_count < 2:
            # Not enough data
            continue
        
        if success_rate >= 0.7:
            analysis["high_performers"].append({
                "name": skill_name,
                "success_rate": success_rate,
                "usage_count": usage_count
            })
        elif success_rate < threshold:
            analysis["low_performers"].append({
                "name": skill_name,
                "success_rate": success_rate,
                "usage_count": usage_count
            })
        elif success_rate < 0.5:
            analysis["needs_improvement"].append({
                "name": skill_name,
                "success_rate": success_rate,
                "usage_count": usage_count
            })
    
    # Get deprecated skills
    analysis["deprecated"] = registry.deprecate_low_performing_skills(threshold)
    
    return analysis


def suggest_skill_improvements(loader: SkillLoader, registry: SkillRegistry) -> List[Dict[str, Any]]:
    """
    Suggest improvements for underperforming skills.
    
    Args:
        loader: SkillLoader instance
        registry: SkillRegistry instance
    
    Returns:
        List of improvement suggestions
    """
    suggestions = []
    
    all_stats = registry.get_all_skill_stats()
    
    for skill_name, stats in all_stats.items():
        success_rate = stats.get("success_rate", 0.5)
        usage_count = stats.get("usage_count", 0)
        
        # Only suggest for skills with enough usage and low success rate
        if usage_count >= 3 and success_rate < 0.5:
            skill = loader.load_skill(skill_name)
            if skill:
                suggestions.append({
                    "skill_name": skill_name,
                    "current_rate": success_rate,
                    "usage_count": usage_count,
                    "suggestion": f"Review and update skill instructions based on {usage_count} usage instances",
                    "action": "update_instructions"
                })
    
    return suggestions


def merge_duplicate_skills(loader: SkillLoader, registry: SkillRegistry, similarity_threshold: float = 0.9) -> List[Dict[str, Any]]:
    """
    Identify and merge duplicate skills.
    
    Args:
        loader: SkillLoader instance
        registry: SkillRegistry instance
        similarity_threshold: Minimum similarity to merge (0.0-1.0)
    
    Returns:
        List of merge operations performed
    """
    # This is a simplified version - full implementation would use semantic similarity
    # For now, check for skills with very similar names
    all_skills = loader.load_all_skills()
    merged = []
    
    # Group by pattern type (from category or name prefix)
    skill_groups = {}
    for skill in all_skills:
        # Extract base pattern type (e.g., "regex-pattern-fixing" from "regex-pattern-fixing-v2")
        base_name = skill.name.split("-v")[0]
        if base_name not in skill_groups:
            skill_groups[base_name] = []
        skill_groups[base_name].append(skill.name)
    
    # Merge versions of same skill
    for base_name, versions in skill_groups.items():
        if len(versions) > 1:
            # Keep the most used version, merge others
            versions_with_stats = []
            for version in versions:
                stats = registry.get_skill_stats(version)
                if stats:
                    versions_with_stats.append((version, stats.get("usage_count", 0)))
            
            if versions_with_stats:
                # Sort by usage count
                versions_with_stats.sort(key=lambda x: x[1], reverse=True)
                keep_version = versions_with_stats[0][0]
                
                # Merge others into keep_version
                for version, _ in versions_with_stats[1:]:
                    if registry.merge_similar_skills(keep_version, version):
                        merged.append({
                            "merged_from": version,
                            "merged_into": keep_version,
                            "reason": "Duplicate version"
                        })
    
    return merged


def main():
    """Main evolution script"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Evolve skills based on usage data")
    parser.add_argument("--skills-dir", default="./skills", help="Skills directory")
    parser.add_argument("--redis-host", default="localhost", help="Redis host")
    parser.add_argument("--redis-port", type=int, default=6379, help="Redis port")
    parser.add_argument("--threshold", type=float, default=0.3, help="Deprecation threshold")
    parser.add_argument("--analyze", action="store_true", help="Analyze skill performance")
    parser.add_argument("--suggest", action="store_true", help="Suggest improvements")
    parser.add_argument("--merge", action="store_true", help="Merge duplicate skills")
    parser.add_argument("--all", action="store_true", help="Run all operations")
    
    args = parser.parse_args()
    
    # Initialize
    skills_dir = Path(args.skills_dir)
    loader = SkillLoader(skills_dir)
    
    try:
        redis_client = redis.Redis(host=args.redis_host, port=args.redis_port, decode_responses=True)
        redis_client.ping()
    except Exception as e:
        print(f"Error connecting to Redis: {e}")
        print("Using mock registry (no persistence)")
        redis_client = None
    
    registry = SkillRegistry(redis_client) if redis_client else None
    
    if not registry:
        print("⚠ Redis not available - cannot analyze skill performance")
        return
    
    print("=" * 60)
    print("Skill Evolution")
    print("=" * 60)
    print()
    
    if args.analyze or args.all:
        print("1. Analyzing skill performance...")
        analysis = analyze_skill_performance(registry, args.threshold)
        
        print(f"   Total skills: {analysis['total_skills']}")
        print(f"   High performers (≥70%): {len(analysis['high_performers'])}")
        print(f"   Low performers (<{args.threshold*100:.0f}%): {len(analysis['low_performers'])}")
        print(f"   Needs improvement: {len(analysis['needs_improvement'])}")
        print(f"   Deprecated: {len(analysis['deprecated'])}")
        print()
        
        if analysis['high_performers']:
            print("   Top performers:")
            for skill in analysis['high_performers'][:5]:
                print(f"     - {skill['name']}: {skill['success_rate']:.0%} ({skill['usage_count']} uses)")
            print()
        
        if analysis['low_performers']:
            print("   Low performers:")
            for skill in analysis['low_performers']:
                print(f"     - {skill['name']}: {skill['success_rate']:.0%} ({skill['usage_count']} uses)")
            print()
    
    if args.suggest or args.all:
        print("2. Suggesting improvements...")
        suggestions = suggest_skill_improvements(loader, registry)
        
        if suggestions:
            print(f"   Found {len(suggestions)} skills needing improvement:")
            for suggestion in suggestions:
                print(f"     - {suggestion['skill_name']}: {suggestion['current_rate']:.0%} success rate")
                print(f"       → {suggestion['suggestion']}")
            print()
        else:
            print("   No skills need improvement")
            print()
    
    if args.merge or args.all:
        print("3. Merging duplicate skills...")
        merged = merge_duplicate_skills(loader, registry)
        
        if merged:
            print(f"   Merged {len(merged)} duplicate skills:")
            for merge_op in merged:
                print(f"     - Merged {merge_op['merged_from']} into {merge_op['merged_into']}")
            print()
        else:
            print("   No duplicate skills found")
            print()
    
    print("=" * 60)
    print("Evolution Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()

