#!/usr/bin/env python3
"""
Enhanced Agent-Specific Memory Contexts

Enhancements:
1. Role-specific context filtering and enhancement
2. Learning from agent interactions and feedback
3. Context relevance scoring and ranking
4. Multi-agent context sharing and collaboration
"""

from typing import Dict, Any, List, Optional, Tuple, TYPE_CHECKING
from collections import defaultdict
import time
from dataclasses import dataclass, field
from orchestrator.ee_memory import HierarchicalMemoryNetwork
from orchestrator.agent_memory import AgentMemoryNetwork

if TYPE_CHECKING:
    from orchestrator.orchestrator import AgentName
else:
    from enum import Enum
    class AgentName(str, Enum):
        PREPROCESSOR = "preprocessor"
        PLANNER = "planner"
        CODER = "coder"
        REVIEWER = "reviewer"
        VOTER = "voter"


@dataclass
class ContextFeedback:
    """Feedback from agent about context usefulness"""
    agent_name: str
    task_description: str
    context_used: str
    was_useful: bool
    relevance_score: float  # 0.0-1.0
    timestamp: float = field(default_factory=time.time)
    notes: Optional[str] = None


@dataclass
class ContextRelevanceScore:
    """Relevance score for context elements"""
    element: str
    score: float  # 0.0-1.0
    reason: str
    source: str  # Which agent/pattern provided this


class EnhancedAgentMemoryNetwork(AgentMemoryNetwork):
    """
    Enhanced agent memory with learning and relevance scoring
    """
    
    def __init__(self, agent_name: AgentName, base_hmn: HierarchicalMemoryNetwork):
        super().__init__(agent_name, base_hmn)
        
        # Learning from feedback
        self.feedback_history: List[ContextFeedback] = []
        self.useful_patterns: Dict[str, float] = defaultdict(float)  # pattern -> usefulness score
        self.useless_patterns: Dict[str, float] = defaultdict(float)  # pattern -> uselessness score
        
        # Relevance scoring
        self.relevance_cache: Dict[str, List[ContextRelevanceScore]] = {}
        
        # Multi-agent sharing
        self.shared_contexts: Dict[str, Dict[str, Any]] = {}  # task_id -> shared context
        self.collaboration_history: List[Dict[str, Any]] = []
    
    def get_context_for_agent(
        self, 
        task_description: str,
        include_relevance_scores: bool = True,
        top_k: int = 5
    ) -> str:
        """
        Enhanced context with relevance scoring and learning
        """
        # Get base context
        base_context = self.base_hmn.query_with_context(task_description, top_k=top_k)
        
        # Score relevance of each element
        if include_relevance_scores:
            relevance_scores = self._score_context_relevance(task_description, base_context)
            base_context["relevance_scores"] = [rs.__dict__ for rs in relevance_scores]
        
        # Apply agent-specific filtering and enhancement
        enhanced_context = self._enhance_context_for_role(base_context, task_description)
        
        # Learn from previous feedback
        enhanced_context = self._apply_learned_preferences(enhanced_context, task_description)
        
        return enhanced_context
    
    def _score_context_relevance(
        self, 
        task_description: str, 
        context: Dict[str, Any]
    ) -> List[ContextRelevanceScore]:
        """
        Score relevance of context elements to task
        
        Returns: List of relevance scores sorted by score (highest first)
        """
        task_lower = task_description.lower()
        task_words = set(task_lower.split())
        
        scores = []
        
        # Score narratives
        narratives = context.get("narratives", [])
        narrative_details = context.get("narrative_details", [])
        for i, narrative in enumerate(narratives):
            score = 0.0
            narrative_lower = narrative.lower()
            
            # Keyword matching
            matching_words = task_words.intersection(set(narrative_lower.split()))
            score += len(matching_words) / max(1, len(task_words)) * 0.4
            
            # Persistence score boost
            if i < len(narrative_details):
                persistence = narrative_details[i].get("persistence_score", 0.0)
                score += persistence * 0.3
            
            # Learned usefulness
            if narrative in self.useful_patterns:
                score += min(0.3, self.useful_patterns[narrative] / 10.0)
            
            scores.append(ContextRelevanceScore(
                element=f"narrative:{narrative}",
                score=min(1.0, score),
                reason=f"Keyword match: {len(matching_words)} words, persistence: {persistence:.2f}",
                source="melodic_line"
            ))
        
        # Score patterns
        patterns = context.get("patterns", [])
        for pattern in patterns:
            score = 0.0
            pattern_lower = pattern.lower()
            
            # Keyword matching
            matching_words = task_words.intersection(set(pattern_lower.split()))
            score += len(matching_words) / max(1, len(task_words)) * 0.5
            
            # Learned usefulness
            if pattern in self.useful_patterns:
                score += min(0.5, self.useful_patterns[pattern] / 10.0)
            
            scores.append(ContextRelevanceScore(
                element=f"pattern:{pattern}",
                score=min(1.0, score),
                reason=f"Keyword match: {len(matching_words)} words",
                source="pattern_detection"
            ))
        
        # Score code snippets (simplified - could be enhanced with semantic similarity)
        code = context.get("code", "")
        if code:
            code_lower = code.lower()
            matching_words = task_words.intersection(set(code_lower.split()))
            code_score = min(1.0, len(matching_words) / max(1, len(task_words)) * 0.6)
            
            scores.append(ContextRelevanceScore(
                element="code",
                score=code_score,
                reason=f"Keyword match: {len(matching_words)} words in code",
                source="code_retrieval"
            ))
        
        # Sort by score (highest first)
        scores.sort(key=lambda x: x.score, reverse=True)
        return scores
    
    def _enhance_context_for_role(
        self, 
        context: Dict[str, Any], 
        task_description: str
    ) -> str:
        """
        Enhanced role-specific context with relevance filtering
        """
        # Get relevance scores
        relevance_scores = context.get("relevance_scores", [])
        
        # Filter to top relevant elements
        top_relevant = [rs for rs in relevance_scores if rs["score"] > 0.3][:5]
        
        # Agent-specific enhancement
        if self.agent_name == AgentName.PLANNER:
            return self._enhanced_planner_context(context, top_relevant, task_description)
        elif self.agent_name == AgentName.CODER:
            return self._enhanced_coder_context(context, top_relevant, task_description)
        elif self.agent_name == AgentName.REVIEWER:
            return self._enhanced_reviewer_context(context, top_relevant, task_description)
        elif self.agent_name == AgentName.VOTER:
            return self._enhanced_voter_context(context, top_relevant, task_description)
        elif self.agent_name == AgentName.PREPROCESSOR:
            return self._enhanced_preprocessor_context(context, top_relevant, task_description)
        
        # Default
        return self._default_enhanced_context(context, top_relevant)
    
    def _enhanced_planner_context(
        self, 
        context: Dict[str, Any], 
        top_relevant: List[Dict], 
        task_description: str
    ) -> str:
        """Enhanced planner context with narrative prioritization"""
        narratives = context.get("narratives", [])
        narrative_details = context.get("narrative_details", [])
        patterns = context.get("patterns", [])
        code = context.get("code", "")
        compression_ratio = context.get("compression_ratio", 0.0)
        
        # Prioritize high-relevance narratives
        relevant_narratives = []
        for rs in top_relevant:
            if rs["element"].startswith("narrative:"):
                narrative_name = rs["element"].replace("narrative:", "")
                if narrative_name in narratives:
                    idx = narratives.index(narrative_name)
                    if idx < len(narrative_details):
                        relevant_narratives.append((narrative_details[idx], rs["score"]))
        
        # Sort by relevance
        relevant_narratives.sort(key=lambda x: x[1], reverse=True)
        
        narrative_text = []
        for ml_detail, relevance in relevant_narratives[:3]:
            narrative_text.append(
                f"- {ml_detail['name']} (relevance: {relevance:.2f}, persistence: {ml_detail['persistence_score']:.2f}): "
                f"{ml_detail['description']}"
            )
        
        return f"""Enhanced Planner Context (Compression: {compression_ratio:.1%}):

🎯 High-Relevance Thematic Flows:
{chr(10).join(narrative_text) if narrative_text else "No highly relevant narratives detected"}

📐 Architectural Patterns:
{chr(10).join(f"- {p}" for p in patterns[:5]) if patterns else "No patterns detected"}

💡 Task Decomposition Guidance:
- Preserve these narrative flows: {', '.join([n[0]['name'] for n in relevant_narratives[:3]])}
- Maintain architectural integrity with patterns: {', '.join(patterns[:3]) if patterns else 'N/A'}
- Consider codebase structure when breaking down tasks

📝 Relevant Code Context:
{code[:3000] if code else "No relevant code found"}"""
    
    def _enhanced_coder_context(
        self, 
        context: Dict[str, Any], 
        top_relevant: List[Dict], 
        task_description: str
    ) -> str:
        """Enhanced coder context with pattern prioritization"""
        patterns = context.get("patterns", [])
        code = context.get("code", "")
        entities = context.get("entities", [])
        
        # Prioritize high-relevance patterns
        relevant_patterns = []
        for rs in top_relevant:
            if rs["element"].startswith("pattern:"):
                pattern_name = rs["element"].replace("pattern:", "")
                if pattern_name in patterns:
                    relevant_patterns.append((pattern_name, rs["score"]))
        
        relevant_patterns.sort(key=lambda x: x[1], reverse=True)
        
        return f"""Enhanced Coder Context:

🎨 High-Relevance Patterns (follow these):
{chr(10).join(f"- {p[0]} (relevance: {p[1]:.2f})" for p in relevant_patterns[:5]) if relevant_patterns else "No specific patterns"}

📚 Related Entities:
{len(entities)} entities found in codebase

💻 Reference Implementation:
{code[:4000] if code else "No reference code"}

[OK] Code Generation Guidelines:
- Follow patterns: {', '.join([p[0] for p in relevant_patterns[:3]]) if relevant_patterns else 'general patterns'}
- Maintain consistency with {len(entities)} related entities
- Preserve codebase style and conventions"""
    
    def _enhanced_reviewer_context(
        self, 
        context: Dict[str, Any], 
        top_relevant: List[Dict], 
        task_description: str
    ) -> str:
        """Enhanced reviewer context with risk awareness"""
        narratives = context.get("narratives", [])
        patterns = context.get("patterns", [])
        code = context.get("code", "")
        
        # Extract risk-related narratives
        risk_narratives = []
        for narrative in narratives:
            narrative_lower = narrative.lower()
            if any(keyword in narrative_lower for keyword in ["error", "exception", "fail", "risk", "security"]):
                risk_narratives.append(narrative)
        
        return f"""Enhanced Reviewer Context:

[WARNING] Risk-Related Narratives to Preserve:
{chr(10).join(f"- {n}" for n in risk_narratives[:3]) if risk_narratives else "No specific risk narratives"}

[OK] Quality Patterns:
{chr(10).join(f"- {p}" for p in patterns[:3]) if patterns else "No specific quality patterns"}

📋 Reference Code for Comparison:
{code[:2000] if code else "No reference code"}

🔍 Review Checklist:
1. [OK] Preserves risk narratives: {', '.join(risk_narratives[:2]) if risk_narratives else 'N/A'}
2. [OK] Adheres to quality patterns: {', '.join(patterns[:2]) if patterns else 'N/A'}
3. [OK] Consistent with codebase style
4. [OK] No breaking changes to existing flows"""
    
    def _enhanced_voter_context(
        self, 
        context: Dict[str, Any], 
        top_relevant: List[Dict], 
        task_description: str
    ) -> str:
        """Enhanced voter context with coherence metrics"""
        narratives = context.get("narratives", [])
        compression_ratio = context.get("compression_ratio", 0.0)
        
        # Get top relevant narratives
        relevant_narratives = []
        for rs in top_relevant:
            if rs["element"].startswith("narrative:"):
                narrative_name = rs["element"].replace("narrative:", "")
                if narrative_name in narratives:
                    relevant_narratives.append((narrative_name, rs["score"]))
        
        relevant_narratives.sort(key=lambda x: x[1], reverse=True)
        
        return f"""Enhanced Voting Context:

🎯 Narratives to Preserve (priority order):
{chr(10).join(f"- {n[0]} (relevance: {n[1]:.2f})" for n in relevant_narratives[:3]) if relevant_narratives else "No specific narratives"}

📊 Context Compression: {compression_ratio:.1%}

⚖️ Voting Criteria (weighted):
1. Narrative coherence (40%): Preserves thematic flows
2. Code quality (35%): Correctness and style
3. Pattern consistency (25%): Matches existing patterns

🎯 Focus on preserving: {', '.join([n[0] for n in relevant_narratives[:2]]) if relevant_narratives else 'general coherence'}"""
    
    def _enhanced_preprocessor_context(
        self, 
        context: Dict[str, Any], 
        top_relevant: List[Dict], 
        task_description: str
    ) -> str:
        """Enhanced preprocessor context"""
        entities = context.get("entities", [])
        code = context.get("code", "")
        
        return f"""Enhanced Preprocessing Context:

📦 Entities to Extract:
{len(entities)} entities found in codebase

📄 Reference Code Structure:
{code[:1000] if code else "No reference code"}

🔧 Extraction Guidelines:
- Extract structured entities (functions, classes, variables)
- Preserve relationships between entities
- Maintain semantic meaning"""
    
    def _default_enhanced_context(
        self, 
        context: Dict[str, Any], 
        top_relevant: List[Dict]
    ) -> str:
        """Default enhanced context"""
        code = context.get("code", "")
        return f"""Context (Relevance-filtered):

Top Relevant Elements:
{chr(10).join(f"- {rs['element']} (score: {rs['score']:.2f}): {rs['reason']}" for rs in top_relevant[:5]) if top_relevant else "No relevance scores"}

Code:
{code[:2000] if code else "No code"}"""
    
    def _apply_learned_preferences(
        self, 
        context: Dict[str, Any], 
        task_description: str
    ) -> str:
        """
        Apply learned preferences from feedback history
        """
        # Boost patterns that were useful in similar tasks
        task_lower = task_description.lower()
        task_words = set(task_lower.split())
        
        # Find similar past tasks
        similar_tasks = []
        for feedback in self.feedback_history:
            past_task_words = set(feedback.task_description.lower().split())
            similarity = len(task_words.intersection(past_task_words)) / max(1, len(task_words.union(past_task_words)))
            if similarity > 0.3 and feedback.was_useful:
                similar_tasks.append(feedback)
        
        # Boost context elements that were useful in similar tasks
        if similar_tasks:
            # This would enhance the context string, but for now we return as-is
            # In a full implementation, we'd re-rank narratives/patterns based on learned usefulness
            pass
        
        # Return context (enhanced in future)
        return context if isinstance(context, str) else str(context)
    
    def record_feedback(
        self, 
        task_description: str, 
        context_used: str, 
        was_useful: bool, 
        relevance_score: float,
        notes: Optional[str] = None
    ):
        """
        Record feedback from agent about context usefulness
        """
        feedback = ContextFeedback(
            agent_name=self.agent_name.value,
            task_description=task_description,
            context_used=context_used,
            was_useful=was_useful,
            relevance_score=relevance_score,
            notes=notes
        )
        
        self.feedback_history.append(feedback)
        
        # Update usefulness scores
        # Extract patterns/narratives from context
        if was_useful:
            # Boost patterns that were useful
            for word in task_description.lower().split():
                if len(word) > 3:  # Skip short words
                    self.useful_patterns[word] += relevance_score
        else:
            # Track useless patterns
            for word in task_description.lower().split():
                if len(word) > 3:
                    self.useless_patterns[word] += 1.0
        
        # Keep only recent feedback (last 100)
        if len(self.feedback_history) > 100:
            self.feedback_history = self.feedback_history[-100:]
    
    def share_context(self, task_id: str, context: Dict[str, Any], with_agents: List[AgentName]):
        """
        Share context with other agents for collaboration
        """
        self.shared_contexts[task_id] = {
            "context": context,
            "shared_with": [agent.value for agent in with_agents],
            "shared_at": time.time(),
            "shared_by": self.agent_name.value
        }
        
        self.collaboration_history.append({
            "task_id": task_id,
            "shared_at": time.time(),
            "shared_by": self.agent_name.value,
            "shared_with": [agent.value for agent in with_agents]
        })
    
    def get_shared_context(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get context shared by another agent"""
        return self.shared_contexts.get(task_id)
    
    def get_learning_stats(self) -> Dict[str, Any]:
        """Get statistics about learning from feedback"""
        if not self.feedback_history:
            return {"total_feedback": 0, "useful_rate": 0.0}
        
        useful_count = sum(1 for f in self.feedback_history if f.was_useful)
        avg_relevance = sum(f.relevance_score for f in self.feedback_history) / len(self.feedback_history)
        
        return {
            "total_feedback": len(self.feedback_history),
            "useful_count": useful_count,
            "useful_rate": useful_count / len(self.feedback_history),
            "average_relevance": avg_relevance,
            "useful_patterns_count": len([p for p, score in self.useful_patterns.items() if score > 1.0]),
            "collaboration_count": len(self.collaboration_history)
        }

