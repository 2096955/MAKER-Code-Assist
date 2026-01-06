#!/usr/bin/env python3
"""
Collective Brain: Multi-agent consensus for complex decisions

Instead of relying on one agent, ask multiple agents and synthesize answers.
Different models see problems differently - combine their perspectives.
"""

import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class AgentPerspective:
    """One agent's perspective on a problem"""
    agent: str
    model: str
    response: str
    confidence: float  # How confident the agent seems (0-1)
    reasoning: str  # Why this agent's view matters


class CollectiveBrain:
    """
    Multi-agent consensus: Ask multiple agents, synthesize best answer.
    
    When to use:
    - Important architectural decisions
    - Debugging complex issues
    - Unclear requirements
    - Code review disagreements
    - "Should I do X or Y?" questions
    
    How it works:
    1. Ask multiple agents the same question
    2. Collect their perspectives
    3. Use synthesizer to combine insights
    4. Return consensus + dissenting opinions
    """
    
    def __init__(self, orchestrator):
        self.orch = orchestrator
        
        # Define which agents to consult for different problem types
        self.expert_panels = {
            "architecture": ["planner", "coder", "reviewer"],  # Qwen 32B + Devstral + Nemotron
            "debugging": ["coder", "reviewer"],  # Devstral + Qwen 32B
            "planning": ["preprocessor", "planner"],  # Gemma + Nemotron (understand + strategize)
            "code_review": ["coder", "reviewer"],  # Devstral + Qwen 32B
            "understanding": ["preprocessor", "planner", "coder"],  # All three perspectives
            "security": ["reviewer", "coder"],  # Qwen 32B (audit) + Devstral (implementation knowledge)
        }
    
    async def consult_collective(
        self,
        problem: str,
        problem_type: str = "understanding",
        context: str = "",
        user_question: str = ""
    ) -> Dict[str, Any]:
        """
        Ask multiple agents about a problem and synthesize their answers.
        
        Args:
            problem: The problem statement
            problem_type: Type of problem (architecture, debugging, etc.)
            context: Additional context
            user_question: Original user question (for framing)
            
        Returns:
            {
                'consensus': str,  # Synthesized answer
                'perspectives': List[AgentPerspective],  # Individual views
                'dissenting': Optional[str],  # Important disagreements
                'confidence': float,  # Overall confidence (0-1)
            }
        """
        agents = self.expert_panels.get(problem_type, ["preprocessor", "planner", "coder"])
        
        # Ask all agents in parallel
        perspectives = await asyncio.gather(*[
            self._ask_agent(agent, problem, context, user_question)
            for agent in agents
        ])
        
        # Filter out errors
        valid_perspectives = [p for p in perspectives if p.response and not p.response.startswith("Error:")]
        
        if not valid_perspectives:
            return {
                'consensus': f"Unable to get consensus from agents. Problem: {problem}",
                'perspectives': [],
                'dissenting': None,
                'confidence': 0.0,
            }
        
        # Synthesize using Planner (best at strategic thinking)
        consensus = await self._synthesize_perspectives(valid_perspectives, problem, user_question)
        
        # Detect dissenting opinions
        dissenting = self._find_dissent(valid_perspectives)
        
        # Calculate confidence (higher if agents agree)
        confidence = self._calculate_confidence(valid_perspectives)
        
        return {
            'consensus': consensus,
            'perspectives': valid_perspectives,
            'dissenting': dissenting,
            'confidence': confidence,
        }
    
    async def _ask_agent(
        self,
        agent_name: str,
        problem: str,
        context: str,
        user_question: str
    ) -> AgentPerspective:
        """Ask one agent for their perspective"""
        from orchestrator.orchestrator import AgentName
        
        agent_enum = {
            "preprocessor": AgentName.PREPROCESSOR,
            "planner": AgentName.PLANNER,
            "coder": AgentName.CODER,
            "reviewer": AgentName.REVIEWER,
        }.get(agent_name)
        
        if not agent_enum:
            return AgentPerspective(
                agent=agent_name,
                model="unknown",
                response="Error: Unknown agent",
                confidence=0.0,
                reasoning=""
            )
        
        # Frame question to leverage agent's strengths
        prompts = {
            "preprocessor": f"""You are analyzing a problem. Your strength is UNDERSTANDING and INTENT DETECTION.

Problem: {problem}

Context: {context}

User's original question: {user_question}

What does the user REALLY want? What's the core issue? (Be concise, 2-3 sentences)""",
            
            "planner": f"""You are analyzing a problem. Your strength is STRATEGIC THINKING and DEPENDENCIES.

Problem: {problem}

Context: {context}

From a strategic/architectural perspective, what's the best approach? What dependencies matter? (Be concise, 2-3 sentences)""",
            
            "coder": f"""You are analyzing a problem. Your strength is CODE UNDERSTANDING and IMPLEMENTATION.

Problem: {problem}

Context: {context}

From a code implementation perspective, what's the solution? What technical constraints matter? (Be concise, 2-3 sentences)""",
            
            "reviewer": f"""You are analyzing a problem. Your strength is QUALITY ASSURANCE and SECURITY.

Problem: {problem}

Context: {context}

From a quality/security perspective, what should we watch out for? What could go wrong? (Be concise, 2-3 sentences)""",
        }
        
        prompt = prompts.get(agent_name, f"Analyze this problem: {problem}")
        
        try:
            response = await self.orch.call_agent_sync(
                agent_enum,
                "",  # No system prompt needed, using framed question
                prompt,
                temperature=0.3
            )
            
            # Estimate confidence based on response certainty
            confidence = self._estimate_confidence(response)
            
            return AgentPerspective(
                agent=agent_name,
                model=self._get_model_name(agent_name),
                response=response.strip()[:500],  # Limit length
                confidence=confidence,
                reasoning=self._get_agent_strength(agent_name)
            )
        except Exception as e:
            return AgentPerspective(
                agent=agent_name,
                model=self._get_model_name(agent_name),
                response=f"Error: {str(e)}",
                confidence=0.0,
                reasoning=""
            )
    
    async def _synthesize_perspectives(
        self,
        perspectives: List[AgentPerspective],
        problem: str,
        user_question: str
    ) -> str:
        """Use Planner to synthesize multiple perspectives into consensus"""
        from orchestrator.orchestrator import AgentName
        
        perspectives_text = "\n\n".join([
            f"{p.agent.upper()} ({p.model}):\n{p.response}\n(Confidence: {p.confidence:.0%})"
            for p in perspectives
        ])
        
        synthesis_prompt = f"""You are synthesizing multiple agent perspectives into a clear answer.

User's question: {user_question}

Problem being analyzed: {problem}

Different agents analyzed this from their expertise:

{perspectives_text}

Your task: Synthesize these perspectives into ONE clear, actionable answer.
- Combine complementary insights
- Resolve contradictions (favor higher confidence)
- Give direct answer to user's question

Synthesized answer (2-3 sentences):"""
        
        try:
            synthesis = await self.orch.call_agent_sync(
                AgentName.PLANNER,
                "",
                synthesis_prompt,
                temperature=0.2
            )
            return synthesis.strip()
        except Exception:
            # Fallback: return highest confidence perspective
            best = max(perspectives, key=lambda p: p.confidence)
            return f"{best.response} (from {best.agent})"
    
    def _find_dissent(self, perspectives: List[AgentPerspective]) -> Optional[str]:
        """Find important disagreements between agents"""
        if len(perspectives) < 2:
            return None
        
        # Simple dissent detection: if one agent has very different keywords
        # (More sophisticated: could use semantic similarity)
        responses = [p.response.lower() for p in perspectives]
        
        # Check if any response contradicts others (contains "but", "however", "no", "don't")
        for i, p in enumerate(perspectives):
            if any(word in p.response.lower() for word in ["but ", "however", "shouldn't", "don't", "avoid"]):
                return f"{p.agent} has concerns: {p.response}"
        
        return None
    
    def _calculate_confidence(self, perspectives: List[AgentPerspective]) -> float:
        """Calculate overall confidence based on agent agreement"""
        if not perspectives:
            return 0.0
        
        # Average confidence weighted by agent certainty
        avg_confidence = sum(p.confidence for p in perspectives) / len(perspectives)
        
        # Boost if multiple agents agree (consensus bonus)
        if len(perspectives) >= 3:
            avg_confidence = min(1.0, avg_confidence * 1.2)
        
        return avg_confidence
    
    def _estimate_confidence(self, response: str) -> float:
        """Estimate how confident the agent seems (heuristic)"""
        confident_words = ["clearly", "definitely", "should", "must", "always"]
        uncertain_words = ["maybe", "possibly", "might", "could", "unsure", "unclear"]
        
        response_lower = response.lower()
        
        confident_count = sum(1 for word in confident_words if word in response_lower)
        uncertain_count = sum(1 for word in uncertain_words if word in response_lower)
        
        # Base confidence
        confidence = 0.5
        
        # Adjust based on language
        confidence += (confident_count * 0.1) - (uncertain_count * 0.15)
        
        # Longer, detailed responses suggest more confidence
        if len(response) > 200:
            confidence += 0.1
        
        return max(0.0, min(1.0, confidence))
    
    def _get_model_name(self, agent_name: str) -> str:
        """Get human-readable model name"""
        models = {
            "preprocessor": "Gemma2-2B",
            "planner": "Nemotron Nano 8B",
            "coder": "Devstral 24B",
            "reviewer": "Qwen 32B",
        }
        return models.get(agent_name, "Unknown")
    
    def _get_agent_strength(self, agent_name: str) -> str:
        """Get agent's primary strength"""
        strengths = {
            "preprocessor": "Intent detection & understanding",
            "planner": "Strategic thinking & dependencies",
            "coder": "Code implementation & debugging",
            "reviewer": "Quality assurance & security",
        }
        return strengths.get(agent_name, "")
