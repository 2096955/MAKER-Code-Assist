#!/usr/bin/env python3
"""
Per-agent specialized memory networks
Each agent has domain-specific HMN tuned to its role
"""

from typing import Dict, Any, List, TYPE_CHECKING
from orchestrator.ee_memory import HierarchicalMemoryNetwork

if TYPE_CHECKING:
    from orchestrator.orchestrator import AgentName
else:
    # Define AgentName locally to avoid circular import
    from enum import Enum
    class AgentName(str, Enum):
        PREPROCESSOR = "preprocessor"
        PLANNER = "planner"
        CODER = "coder"
        REVIEWER = "reviewer"
        VOTER = "voter"


class AgentMemoryNetwork:
    """Specialized HMN for a specific agent"""
    
    def __init__(self, agent_name: AgentName, base_hmn: HierarchicalMemoryNetwork):
        self.agent_name = agent_name
        self.base_hmn = base_hmn
        self.agent_specific_memory: Dict[str, Any] = {}
        self.preferences: Dict[str, Any] = {}  # Agent-specific preferences
    
    def get_context_for_agent(self, task_description: str) -> str:
        """Get agent-specific context with melodic line awareness"""
        base_context = self.base_hmn.query_with_context(task_description, top_k=5)
        
        # Agent-specific filtering/enhancement
        if self.agent_name == AgentName.PLANNER:
            return self._planner_context(base_context)
        elif self.agent_name == AgentName.CODER:
            return self._coder_context(base_context)
        elif self.agent_name == AgentName.REVIEWER:
            return self._reviewer_context(base_context)
        elif self.agent_name == AgentName.VOTER:
            return self._voter_context(base_context)
        elif self.agent_name == AgentName.PREPROCESSOR:
            return self._preprocessor_context(base_context)
        
        # Default: return code context
        return base_context.get("code", "")
    
    def _planner_context(self, context: Dict[str, Any]) -> str:
        """Planner needs narrative flows for task decomposition"""
        narratives = context.get("narratives", [])
        narrative_details = context.get("narrative_details", [])
        patterns = context.get("patterns", [])
        code = context.get("code", "")
        compression_ratio = context.get("compression_ratio", 0.0)
        
        narrative_text = []
        for ml_detail in narrative_details[:3]:  # Top 3 narratives
            narrative_text.append(
                f"- {ml_detail['name']} (persistence: {ml_detail['persistence_score']:.2f}): "
                f"{ml_detail['description']}"
            )
        
        return f"""Codebase Context with Narrative Awareness (Compression: {compression_ratio:.1%}):

Thematic Flows (Melodic Lines):
{chr(10).join(narrative_text) if narrative_text else "No specific narratives detected"}

Architectural Patterns:
{chr(10).join(f"- {p}" for p in patterns[:5]) if patterns else "No patterns detected"}

Relevant Code:
{code[:3000] if code else "No relevant code found"}

When decomposing tasks, preserve these narrative flows and maintain architectural integrity."""
    
    def _coder_context(self, context: Dict[str, Any]) -> str:
        """Coder needs patterns, idioms, and coding style"""
        narratives = context.get("narratives", [])
        patterns = context.get("patterns", [])
        code = context.get("code", "")
        entities = context.get("entities", [])
        
        # Extract coding patterns from narratives
        coding_patterns = []
        for narrative in narratives:
            # Look for coding-related keywords
            if any(keyword in narrative.lower() for keyword in ["error", "exception", "handler"]):
                coding_patterns.append("Error handling pattern")
            if any(keyword in narrative.lower() for keyword in ["auth", "security", "token"]):
                coding_patterns.append("Security pattern")
        
        return f"""Code Context for Implementation:

Relevant Patterns:
{chr(10).join(f"- {p}" for p in (coding_patterns + patterns[:3])) if (coding_patterns or patterns) else "No specific patterns"}

Related Entities:
{len(entities)} entities found

Reference Code:
{code[:4000] if code else "No reference code"}

Generate code that follows these patterns and maintains consistency with the codebase style."""
    
    def _reviewer_context(self, context: Dict[str, Any]) -> str:
        """Reviewer needs risk narratives and quality standards"""
        narratives = context.get("narratives", [])
        patterns = context.get("patterns", [])
        code = context.get("code", "")
        
        # Extract risk-related narratives
        risk_narratives = []
        quality_patterns = []
        
        for narrative in narratives:
            narrative_lower = narrative.lower()
            if any(keyword in narrative_lower for keyword in ["error", "exception", "fail", "risk"]):
                risk_narratives.append(narrative)
            if any(keyword in narrative_lower for keyword in ["test", "validate", "check", "verify"]):
                quality_patterns.append(narrative)
        
        return f"""Review Context with Risk Awareness:

Risk-Related Narratives:
{chr(10).join(f"- {n}" for n in risk_narratives[:3]) if risk_narratives else "No specific risk narratives"}

Quality Patterns:
{chr(10).join(f"- {p}" for p in (quality_patterns + patterns[:2])) if (quality_patterns or patterns) else "No specific quality patterns"}

Reference Code for Comparison:
{code[:2000] if code else "No reference code"}

Review code for:
1. Preservation of risk narratives
2. Adherence to quality patterns
3. Consistency with existing codebase"""
    
    def _voter_context(self, context: Dict[str, Any]) -> str:
        """Voter needs quality criteria and coherence metrics"""
        narratives = context.get("narratives", [])
        compression_ratio = context.get("compression_ratio", 0.0)
        
        return f"""Voting Context:

Relevant Narratives to Preserve:
{chr(10).join(f"- {n}" for n in narratives[:3]) if narratives else "No specific narratives"}

Context Compression: {compression_ratio:.1%}

Vote based on:
1. Narrative coherence (preserves thematic flows)
2. Code quality and correctness
3. Consistency with existing patterns"""
    
    def _preprocessor_context(self, context: Dict[str, Any]) -> str:
        """Preprocessor needs entity extraction context"""
        entities = context.get("entities", [])
        code = context.get("code", "")
        
        return f"""Preprocessing Context:

Entities to Extract:
{len(entities)} entities found

Reference Code:
{code[:1000] if code else "No reference code"}

Extract structured entities (functions, classes, variables) from input."""
    
    def update_preferences(self, key: str, value: Any):
        """Update agent-specific preferences"""
        self.preferences[key] = value
    
    def get_preferences(self) -> Dict[str, Any]:
        """Get agent-specific preferences"""
        return self.preferences.copy()

