#!/usr/bin/env python3
"""
Agent Coordinator: Self-aware agents that know their strengths and delegate intelligently
"""

from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass

class AgentCapability(Enum):
    """What each agent is good at"""
    # Preprocessor (Gemma2-2B)
    MULTIMODAL = "multimodal"  # Images, audio, video → text
    UNDERSTANDING = "understanding"  # Extract meaning from messy content
    SUMMARIZATION = "summarization"  # Condense long text
    INTENT_DETECTION = "intent_detection"  # What does user really want?
    
    # Planner (Nemotron Nano 8B)
    TASK_BREAKDOWN = "task_breakdown"  # Break complex tasks into steps
    DEPENDENCY_ANALYSIS = "dependency_analysis"  # What needs to happen first?
    NARRATIVE_PRESERVATION = "narrative_preservation"  # Maintain business logic flows
    STRATEGIC_THINKING = "strategic_thinking"  # High-level architecture decisions
    
    # Coder (Devstral 24B)
    CODE_GENERATION = "code_generation"  # Write actual code
    CODE_UNDERSTANDING = "code_understanding"  # Read and explain existing code
    REFACTORING = "refactoring"  # Improve code structure
    DEBUG_ASSISTANCE = "debug_assistance"  # Help find bugs
    
    # Reviewer (Qwen 32B)
    CODE_REVIEW = "code_review"  # Validate code quality
    SECURITY_AUDIT = "security_audit"  # Find vulnerabilities
    TEST_VALIDATION = "test_validation"  # Verify tests work
    STANDARDS_COMPLIANCE = "standards_compliance"  # Check best practices
    
    # Voter (Qwen 1.5B)
    CONSENSUS_BUILDING = "consensus_building"  # MAKER voting
    QUALITY_COMPARISON = "quality_comparison"  # Which code is better?


@dataclass
class AgentProfile:
    """What an agent knows about itself"""
    name: str
    model: str
    strengths: list[AgentCapability]
    weaknesses: list[str]  # What this agent is NOT good at
    when_to_use: str  # Simple description
    delegate_to: Dict[str, str]  # When I'm not suited, who to call


class AgentCoordinator:
    """
    Smart routing: Agents understand their roles and delegate intelligently
    
    Instead of rigid workflow (Preprocessor → Planner → Coder → Reviewer),
    agents self-coordinate based on task requirements.
    """
    
    def __init__(self):
        self.agents = {
            "preprocessor": AgentProfile(
                name="Preprocessor",
                model="Gemma2-2B (multimodal)",
                strengths=[
                    AgentCapability.MULTIMODAL,
                    AgentCapability.UNDERSTANDING,
                    AgentCapability.SUMMARIZATION,
                    AgentCapability.INTENT_DETECTION,
                ],
                weaknesses=[
                    "Code generation",
                    "Complex reasoning",
                    "Long-form planning",
                ],
                when_to_use="Converting messy input to clean understanding. Images/audio → text. Extracting meaning from READMEs/docs.",
                delegate_to={
                    "code_question": "coder",  # If user asks about code, send to Coder
                    "planning_needed": "planner",  # If task needs breakdown, send to Planner
                    "code_review": "reviewer",  # If reviewing code, send to Reviewer
                }
            ),
            
            "planner": AgentProfile(
                name="Planner",
                model="Nemotron Nano 8B (strategic)",
                strengths=[
                    AgentCapability.TASK_BREAKDOWN,
                    AgentCapability.DEPENDENCY_ANALYSIS,
                    AgentCapability.NARRATIVE_PRESERVATION,
                    AgentCapability.STRATEGIC_THINKING,
                ],
                weaknesses=[
                    "Writing actual code",
                    "Multimodal processing",
                    "Deep code analysis",
                ],
                when_to_use="Breaking complex tasks into steps. Understanding dependencies. Preserving business logic narratives.",
                delegate_to={
                    "needs_code": "coder",  # Plan is done, need implementation
                    "unclear_input": "preprocessor",  # Input needs clarification
                    "validation_needed": "reviewer",  # Need to verify plan is sound
                }
            ),
            
            "coder": AgentProfile(
                name="Coder",
                model="Devstral 24B (coding specialist)",
                strengths=[
                    AgentCapability.CODE_GENERATION,
                    AgentCapability.CODE_UNDERSTANDING,
                    AgentCapability.REFACTORING,
                    AgentCapability.DEBUG_ASSISTANCE,
                ],
                weaknesses=[
                    "Multimodal input",
                    "High-level planning",
                    "Code review (own code)",
                ],
                when_to_use="Writing code. Explaining code. Refactoring. Finding bugs. Anything code-related.",
                delegate_to={
                    "needs_review": "reviewer",  # Code written, needs validation
                    "unclear_requirements": "planner",  # Need better task breakdown
                    "messy_input": "preprocessor",  # Input needs preprocessing
                }
            ),
            
            "reviewer": AgentProfile(
                name="Reviewer",
                model="Qwen 32B (quality assurance)",
                strengths=[
                    AgentCapability.CODE_REVIEW,
                    AgentCapability.SECURITY_AUDIT,
                    AgentCapability.TEST_VALIDATION,
                    AgentCapability.STANDARDS_COMPLIANCE,
                ],
                weaknesses=[
                    "Code generation",
                    "Planning",
                    "Multimodal input",
                ],
                when_to_use="Reviewing code quality. Finding bugs. Security audits. Validating tests work.",
                delegate_to={
                    "needs_fixes": "coder",  # Found issues, need Coder to fix
                    "needs_replan": "planner",  # Architecture is wrong, need new plan
                }
            ),
            
            "voter": AgentProfile(
                name="Voter",
                model="Qwen 1.5B (consensus)",
                strengths=[
                    AgentCapability.CONSENSUS_BUILDING,
                    AgentCapability.QUALITY_COMPARISON,
                ],
                weaknesses=[
                    "Everything except voting",
                ],
                when_to_use="MAKER voting: choosing best candidate from multiple options.",
                delegate_to={
                    "not_voting": "coder",  # If not voting, probably Coder's job
                }
            ),
        }
    
    def should_agent_handle(self, agent_name: str, task_type: str) -> tuple[bool, Optional[str]]:
        """
        Check if agent should handle this task or delegate.
        
        Returns:
            (should_handle, delegate_to_agent)
        """
        agent = self.agents.get(agent_name)
        if not agent:
            return (False, "preprocessor")  # Default to preprocessor if unknown
        
        # Map task types to capabilities
        task_capability_map = {
            "multimodal": AgentCapability.MULTIMODAL,
            "understand_content": AgentCapability.UNDERSTANDING,
            "summarize": AgentCapability.SUMMARIZATION,
            "detect_intent": AgentCapability.INTENT_DETECTION,
            "break_down_task": AgentCapability.TASK_BREAKDOWN,
            "analyze_dependencies": AgentCapability.DEPENDENCY_ANALYSIS,
            "write_code": AgentCapability.CODE_GENERATION,
            "explain_code": AgentCapability.CODE_UNDERSTANDING,
            "refactor": AgentCapability.REFACTORING,
            "debug": AgentCapability.DEBUG_ASSISTANCE,
            "review_code": AgentCapability.CODE_REVIEW,
            "security_audit": AgentCapability.SECURITY_AUDIT,
            "vote": AgentCapability.CONSENSUS_BUILDING,
        }
        
        required_capability = task_capability_map.get(task_type)
        
        if required_capability and required_capability in agent.strengths:
            return (True, None)  # Agent can handle it
        
        # Agent can't handle it - who should?
        if task_type in ["multimodal", "understand_content", "summarize", "detect_intent"]:
            return (False, "preprocessor")
        elif task_type in ["break_down_task", "analyze_dependencies"]:
            return (False, "planner")
        elif task_type in ["write_code", "explain_code", "refactor", "debug"]:
            return (False, "coder")
        elif task_type in ["review_code", "security_audit"]:
            return (False, "reviewer")
        elif task_type == "vote":
            return (False, "voter")
        
        return (False, "preprocessor")  # Default fallback
    
    def get_agent_purpose(self, agent_name: str) -> str:
        """Get agent's purpose description"""
        agent = self.agents.get(agent_name)
        return agent.when_to_use if agent else "Unknown agent"
    
    def suggest_next_agent(self, current_agent: str, task_completed: str) -> Optional[str]:
        """
        Based on what current agent just did, who should go next?
        
        This enables smart workflow transitions.
        """
        transitions = {
            ("preprocessor", "understood_input"): "planner",
            ("preprocessor", "extracted_content"): "planner",
            ("planner", "created_plan"): "coder",
            ("planner", "unclear"): "preprocessor",
            ("coder", "wrote_code"): "reviewer",
            ("coder", "need_clarification"): "planner",
            ("reviewer", "approved"): None,  # Done!
            ("reviewer", "needs_fixes"): "coder",
            ("voter", "selected_winner"): "reviewer",
        }
        
        return transitions.get((current_agent, task_completed))


# Singleton instance
coordinator = AgentCoordinator()
