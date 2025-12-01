#!/usr/bin/env python3
"""
Skill loader for loading and parsing skills from SKILL.md files.

Skills are stored in skills/ directory with YAML frontmatter.
"""

import re
import yaml
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field


@dataclass
class Skill:
    """Represents a loaded skill"""
    name: str
    description: str
    category: str
    applies_to: List[str]
    instructions: str  # Full markdown content after frontmatter
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert skill to dictionary"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "applies_to": self.applies_to,
            "instructions": self.instructions,
            "metadata": self.metadata
        }


class SkillLoader:
    """
    Loads and parses skills from SKILL.md files.
    
    Skills are stored in skills/{skill-name}/SKILL.md with YAML frontmatter.
    """
    
    def __init__(self, skills_dir: Path):
        """
        Initialize skill loader.
        
        Args:
            skills_dir: Path to skills directory (e.g., ./skills)
        """
        self.skills_dir = Path(skills_dir)
        self.skills_cache: Dict[str, Skill] = {}
    
    def load_skill(self, skill_name: str) -> Optional[Skill]:
        """
        Load a single skill by name.
        
        Args:
            skill_name: Name of the skill (directory name)
        
        Returns:
            Skill object if found, None otherwise
        """
        # Check cache first
        if skill_name in self.skills_cache:
            return self.skills_cache[skill_name]
        
        # Load from file
        skill_path = self.skills_dir / skill_name / "SKILL.md"
        if not skill_path.exists():
            return None
        
        skill = self.parse_skill_file(skill_path)
        if skill:
            self.skills_cache[skill_name] = skill
        
        return skill
    
    def load_all_skills(self) -> List[Skill]:
        """
        Load all skills from skills directory.
        
        Returns:
            List of all loaded skills
        """
        skills = []
        
        if not self.skills_dir.exists():
            return skills
        
        # Find all SKILL.md files
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                skill = self.parse_skill_file(skill_file)
                if skill:
                    skills.append(skill)
                    self.skills_cache[skill.name] = skill
        
        return skills
    
    def parse_skill_file(self, path: Path) -> Optional[Skill]:
        """
        Parse a SKILL.md file with YAML frontmatter.
        
        Args:
            path: Path to SKILL.md file
        
        Returns:
            Skill object if parsing succeeds, None otherwise
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split frontmatter from markdown
            frontmatter_match = re.match(
                r'^---\s*\n(.*?)\n---\s*\n(.*)$',
                content,
                re.DOTALL
            )
            
            if not frontmatter_match:
                # No frontmatter, try to parse anyway
                return None
            
            frontmatter_text = frontmatter_match.group(1)
            markdown_content = frontmatter_match.group(2)
            
            # Parse YAML frontmatter
            try:
                metadata = yaml.safe_load(frontmatter_text)
                if not metadata:
                    return None
            except yaml.YAMLError as e:
                print(f"Warning: Failed to parse YAML frontmatter in {path}: {e}")
                return None
            
            # Validate required fields
            if 'name' not in metadata or 'description' not in metadata:
                print(f"Warning: Skill {path} missing required fields (name, description)")
                return None
            
            # Extract fields
            name = metadata['name']
            description = metadata['description']
            category = metadata.get('category', 'uncategorized')
            applies_to = metadata.get('applies_to', [])
            if isinstance(applies_to, str):
                applies_to = [applies_to]  # Handle single string
            
            # Store remaining metadata
            skill_metadata = {
                k: v for k, v in metadata.items()
                if k not in ['name', 'description', 'category', 'applies_to']
            }
            
            # Create skill
            skill = Skill(
                name=name,
                description=description,
                category=category,
                applies_to=applies_to,
                instructions=markdown_content.strip(),
                metadata=skill_metadata
            )
            
            return skill
            
        except Exception as e:
            print(f"Error loading skill from {path}: {e}")
            return None
    
    def reload_skill(self, skill_name: str) -> Optional[Skill]:
        """
        Reload a skill from disk (bypass cache).
        
        Args:
            skill_name: Name of the skill to reload
        
        Returns:
            Skill object if found, None otherwise
        """
        # Remove from cache
        if skill_name in self.skills_cache:
            del self.skills_cache[skill_name]
        
        # Reload
        return self.load_skill(skill_name)
    
    def clear_cache(self):
        """Clear the skills cache"""
        self.skills_cache.clear()
    
    def get_skill_names(self) -> List[str]:
        """
        Get list of all available skill names.
        
        Returns:
            List of skill names
        """
        if not self.skills_dir.exists():
            return []
        
        skill_names = []
        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                skill_names.append(skill_dir.name)
        
        return skill_names

