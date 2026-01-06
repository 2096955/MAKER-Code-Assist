#!/usr/bin/env python3
"""
Skill matcher for finding relevant skills for tasks using RAG.

Uses keyword matching, semantic search, and success rate weighting.
"""

import logging
from typing import List, Optional
from orchestrator.skill_loader import SkillLoader, Skill

logger = logging.getLogger(__name__)


class SkillMatcher:
    """
    Finds relevant skills for a given task using multiple matching strategies.
    
    Matching combines:
    1. Keyword matching (applies_to list)
    2. Semantic search (RAG query on descriptions)
    3. Category filtering (prefer core-coding)
    4. Success rate weighting (boost high-performing skills)
    """
    
    def __init__(self, skill_loader: SkillLoader, rag_service=None):
        """
        Initialize skill matcher.
        
        Args:
            skill_loader: SkillLoader instance
            rag_service: Optional RAG service for semantic search
        """
        self.skill_loader = skill_loader
        self.rag = rag_service
        self._skills_indexed = False
    
    def index_all_skills(self):
        """
        Index all skills in RAG service for semantic search.
        
        Creates a separate collection for skills if RAG supports it.
        """
        if not self.rag:
            return
        
        # Load all skills
        skills = self.skill_loader.load_all_skills()
        
        # Prepare documents for batch indexing
        documents = []
        for skill in skills:
            # Format: "name: description\n\ninstructions"
            skill_text = f"{skill.name}: {skill.description}\n\n{skill.instructions[:500]}"
            
            documents.append({
                'text': skill_text,
                'metadata': {
                    "skill_name": skill.name,
                    "category": skill.category,
                    "applies_to": skill.applies_to
                }
            })
        
        # Batch add to RAG index
        if documents:
            try:
                if hasattr(self.rag, 'add_documents'):
                    self.rag.add_documents(documents)
                elif hasattr(self.rag, 'add_document'):
                    # Fallback: add one by one
                    for doc in documents:
                        self.rag.add_document(
                            text=doc['text'],
                            metadata=doc.get('metadata', {})
                        )
            except (AttributeError, ValueError, TypeError) as e:
                logger.warning(f"Failed to index skills in RAG: {e}")
        
        self._skills_indexed = True
    
    def find_relevant_skills(self, task_description: str, top_k: int = 3) -> List[Skill]:
        """
        Find relevant skills for a task description.
        
        Args:
            task_description: Task description or user prompt
            top_k: Number of top skills to return
        
        Returns:
            List of relevant skills, sorted by relevance score
        """
        # Load all skills
        all_skills = self.skill_loader.load_all_skills()
        
        if not all_skills:
            return []
        
        # Calculate relevance scores
        scored_skills = []
        for skill in all_skills:
            score = self.calculate_relevance(task_description, skill)
            scored_skills.append((score, skill))
        
        # Sort by score (descending)
        scored_skills.sort(key=lambda x: x[0], reverse=True)
        
        # Return top_k
        return [skill for _, skill in scored_skills[:top_k]]
    
    def calculate_relevance(self, task: str, skill: Skill) -> float:
        """
        Calculate relevance score for a skill given a task.
        
        Score components:
        - Keyword match: 0.3 weight
        - Semantic similarity: 0.4 weight
        - Success rate: 0.2 weight
        - Usage count boost: 0.1 weight
        
        Args:
            task: Task description
            skill: Skill to score
        
        Returns:
            Relevance score (0.0 to 1.0)
        """
        task_lower = task.lower()
        
        # 1. Keyword matching (0.3 weight)
        keyword_score = 0.0
        for keyword in skill.applies_to:
            if keyword.lower() in task_lower:
                keyword_score += 1.0 / len(skill.applies_to) if skill.applies_to else 0.0
        
        # Normalize to 0-1
        keyword_score = min(1.0, keyword_score)
        
        # 2. Semantic similarity (0.4 weight)
        semantic_score = 0.0
        if self.rag and self._skills_indexed:
            try:
                # Search for similar skills
                results = self.rag.search(task, top_k=5)
                for result in results:
                    # RAGServiceFAISS returns metadata in result['metadata']
                    metadata = result.get('metadata', {})
                    if isinstance(metadata, dict) and metadata.get('skill_name') == skill.name:
                        # Use similarity score from RAG (normalized to 0-1)
                        semantic_score = result.get('score', 0.0)
                        break
            except (AttributeError, ValueError, TypeError) as e:
                logger.warning(f"RAG search failed: {e}")
        
        # Fallback: Simple text similarity if RAG not available
        if semantic_score == 0.0:
            semantic_score = self._simple_text_similarity(task, skill.description)
        
        # 3. Success rate (0.2 weight)
        success_rate = skill.metadata.get('success_rate', 0.5)  # Default 0.5 if not set
        success_score = float(success_rate)
        
        # 4. Usage count boost (0.1 weight)
        # Boost skills that have been used successfully
        usage_count = skill.metadata.get('usage_count', 0)
        usage_boost = min(1.0, usage_count / 10.0)  # Normalize: 10 uses = max boost
        
        # Combine scores
        final_score = (
            keyword_score * 0.3 +
            semantic_score * 0.4 +
            success_score * 0.2 +
            usage_boost * 0.1
        )
        
        return final_score
    
    def _simple_text_similarity(self, text1: str, text2: str) -> float:
        """
        Simple text similarity as fallback when RAG not available.
        
        Uses word overlap ratio.
        
        Args:
            text1: First text
            text2: Second text
        
        Returns:
            Similarity score (0.0 to 1.0)
        """
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        if not union:
            return 0.0
        
        return len(intersection) / len(union)
    
    def get_skill_context(self, skills: List[Skill]) -> str:
        """
        Format skills as context string for agent prompts.
        
        Args:
            skills: List of skills to format
        
        Returns:
            Formatted context string
        """
        if not skills:
            return ""
        
        context_parts = []
        for skill in skills:
            context_parts.append(f"## {skill.name}\n{skill.description}\n\n{skill.instructions[:1000]}")
        
        return "\n\n---\n\n".join(context_parts)

