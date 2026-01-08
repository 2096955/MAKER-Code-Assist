#!/usr/bin/env python3
"""
Expositional Engineering Enhanced Planner Agent
Implements Spec Section 3.1 - Narrative-aware task decomposition
"""

import logging

logger = logging.getLogger(__name__)
from typing import List, Dict, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
import json
import os
from orchestrator.ee_world_model import CodebaseWorldModel, MelodicLine, ArchitecturalPattern

if TYPE_CHECKING:
    from orchestrator.orchestrator import Orchestrator, AgentName


@dataclass
class EnhancedSubtask:
    """Subtask with narrative context (Spec Section 3.1)"""
    description: str
    target_modules: List[str]
    relevant_narratives: List[str]  # Business flows to preserve
    dependencies: List[str]  # Other subtasks that must complete first
    warnings: List[str]  # Architectural integrity warnings
    confidence: float  # Bayesian belief in correctness
    preserves_patterns: List[str] = field(default_factory=list)  # Architectural patterns


class EEPlannerAgent:
    """
    Expositional Engineering Enhanced Planner
    Replaces flat MCP queries with hierarchical narrative understanding
    """
    
    def __init__(
        self,
        codebase_path: str = ".",
        mcp_client=None,
        model_name: str = "nemotron-nano-8b"
    ):
        self.model_name = model_name
        self.mcp = mcp_client
        
        # Initialize EE World Model
        logger.info("Initialising Expositional Engineering World Model...")
        self.world_model = CodebaseWorldModel(
            codebase_path=codebase_path,
            mcp_client=mcp_client
        )
        logger.info("World Model ready.")
    
    def plan_task(self, task_description: str) -> List[EnhancedSubtask]:
        """
        Decompose task with narrative awareness
        Main method called by MAKER orchestrator
        """
        logger.info(f1)
        logger.info(f1)
        logger.info(f1)
        logger.info(f1)
        
        # Step 1: Query world model hierarchically
        logger.info("[1/4] Querying hierarchical world model...")
        context = self.world_model.query_with_context(task_description)
        
        logger.info(f1)
        logger.info(f1)
        logger.info(f1)
        
        # Step 2: Generate narrative-aware prompt
        logger.info("[2/4] Constructing narrative-aware prompt...")
        prompt = self._construct_narrative_prompt(task_description, context)
        
        # Step 3: LLM task decomposition (would use actual LLM)
        logger.info("[3/4] Generating subtasks...")
        # For now, generate a simple plan structure
        # In full implementation, would call: raw_subtasks = self.llm.generate(prompt)
        raw_subtasks = self._generate_initial_subtasks(task_description, context)
        
        # Step 4: Augment with EE context
        logger.info("[4/4] Augmenting with narrative context...")
        enhanced_subtasks = self._augment_with_narrative_context(raw_subtasks, context)
        
        # Display summary
        self._display_plan_summary(enhanced_subtasks, context)
        
        return enhanced_subtasks
    
    def _construct_narrative_prompt(
        self,
        task_description: str,
        context: Dict,
        file_content: Optional[str] = None
    ) -> str:
        """
        Build prompt that includes narrative flows and architectural context
        Spec Section 3.1 - Comprehensive prompt engineering
        """
        narrative_section = self._format_melodic_lines(context['melodic_lines'])
        pattern_section = self._format_patterns(context['patterns'])
        module_section = self._format_modules(context['modules'], context['confidence'])
        dependency_section = self._format_dependencies(context['dependencies'])
        warning_section = self._format_warnings(context['warnings'])

        # Add source file content section if available
        source_file_section = ""
        if file_content:
            source_file_section = f"""
SOURCE FILE TO CONVERT:

```
{file_content}
```

CRITICAL: You MUST inventory ALL functions, classes, interfaces, and types from the source file above before creating subtasks.
"""

        prompt = f"""You are an expert software architect with deep understanding of this codebase.

TASK: {task_description}

{source_file_section}

BUSINESS NARRATIVE CONTEXT:

{narrative_section}

ARCHITECTURAL PATTERNS:

{pattern_section}

RELEVANT MODULES:

{module_section}

CRITICAL DEPENDENCIES:

{dependency_section}

ARCHITECTURAL WARNINGS:

{warning_section}

INSTRUCTIONS:

Decompose this task into subtasks that:

1. PRESERVE business narrative flows - do not break thematic coherence
2. RESPECT architectural patterns identified above
3. MAINTAIN critical dependencies between modules
4. ADDRESS architectural warnings

For each subtask, specify:

- Clear description of what needs to be done
- Which modules it affects
- Which business narratives it must preserve
- Any dependencies on other subtasks
- Confidence level (0-1) in the approach

Output format (JSON):

{{
  "subtasks": [
    {{
      "description": "...",
      "target_modules": ["module1", "module2"],
      "preserves_narratives": ["narrative1"],
      "depends_on": [],
      "confidence": 0.85
    }}
  ]
}}

Begin:
"""
        return prompt
    
    def _format_melodic_lines(self, melodic_lines: List[MelodicLine]) -> str:
        """Format business narratives for prompt"""
        if not melodic_lines:
            return "No dominant business narratives detected for this task."
        
        sections = []
        for i, line in enumerate(melodic_lines, 1):
            sections.append(f"""
{i}. {line.name} (coherence: {line.coherence_score:.2f}, persistence: {line.persistence:.2f})
   Description: {line.business_description}
   Modules involved: {' → '.join(line.modules)}
   Critical paths: {len(line.critical_paths)} dependency flows
""")
        return "\n".join(sections)
    
    def _format_patterns(self, patterns: List[ArchitecturalPattern]) -> str:
        """Format architectural patterns"""
        if not patterns:
            return "No specific architectural patterns detected."
        
        sections = []
        for pattern in patterns:
            sections.append(f"""
- {pattern.pattern_type}: {len(pattern.instances)} instances (coherence: {pattern.coherence:.2f})
""")
        return "\n".join(sections)
    
    def _format_modules(self, modules: List[str], confidence: Dict[str, float]) -> str:
        """Format module information with Bayesian confidence"""
        if not modules:
            return "No specific modules identified."
        
        sections = []
        for module in sorted(modules, key=lambda m: confidence.get(m, 0), reverse=True):
            conf = confidence.get(module, 0)
            sections.append(f"- {module} (relevance: {conf:.3f})")
        
        return "\n".join(sections)
    
    def _format_dependencies(self, dependencies: List[Dict]) -> str:
        """Format critical dependencies"""
        if not dependencies:
            return "No critical inter-module dependencies detected."
        
        sections = []
        for dep in dependencies:
            criticality = "🔴 CRITICAL" if dep.get('critical', False) else "⚪ Normal"
            sections.append(f"- {dep['from']} → {dep['to']} [{criticality}]")
        
        return "\n".join(sections)
    
    def _format_warnings(self, warnings: List[str]) -> str:
        """Format architectural warnings"""
        if not warnings:
            return "No architectural integrity warnings."
        
        return "\n".join(f"[WARNING]  {warning}" for warning in warnings)
    
    def _generate_initial_subtasks(self, task_description: str, context: Dict) -> Dict:
        """
        Generate initial subtask structure using actual LLM
        This will be called by the orchestrator with the actual Planner agent
        """
        # Return the prompt - orchestrator will call LLM with it
        # For now, create a simple structure based on modules
        modules = context.get('modules', [])[:3]  # Limit to 3 modules
        
        subtasks = []
        for i, module in enumerate(modules):
            subtasks.append({
                "description": f"Update {module} for {task_description}",
                "target_modules": [module],
                "preserves_narratives": [ml.name for ml in context.get('melodic_lines', [])[:1]],
                "depends_on": [] if i == 0 else [f"subtask_{i}"],
                "confidence": 0.7
            })
        
        return {"subtasks": subtasks}
    
    async def _read_source_file_if_needed(self, task_description: str, orchestrator) -> Optional[str]:
        """
        Detect if this is a file conversion task and read the source file.

        Patterns detected:
        - "convert <file> to <language>"
        - "translate <file> to <language>"
        - "port <file> to <language>"
        - File path in task description

        Returns:
            File contents if file conversion task detected, None otherwise
        """
        import re
        from pathlib import Path

        # Patterns that indicate file conversion
        conversion_patterns = [
            r'convert\s+([^\s]+\.\w+)\s+to',
            r'translate\s+([^\s]+\.\w+)\s+to',
            r'port\s+([^\s]+\.\w+)\s+to',
            r'([^\s]+\.(ts|js|py|rs|go|java|cpp|c|h))\s*-\s*can you convert',
        ]

        file_path = None
        for pattern in conversion_patterns:
            match = re.search(pattern, task_description, re.IGNORECASE)
            if match:
                file_path = match.group(1)
                break

        if not file_path:
            return None

        # Try to read file via MCP
        try:
            logger.info(f1)

            # Call MCP read_file tool
            mcp_url = os.getenv("MCP_URL", "http://host.docker.internal:9001")
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{mcp_url}/api/mcp/tool",
                    json={"tool": "read_file", "args": {"path": file_path}}
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result.get("result", "")
                        if content and not content.startswith(" File not found"):
                            logger.info(f1)
                            return content
                        else:
                            logger.info(f1)
                            return None
                    else:
                        logger.info(f1)
                        return None
        except Exception as e:
            logger.info(f1)
            return None

    async def plan_task_async(self, task_description: str, orchestrator, planner_agent) -> List[EnhancedSubtask]:
        """
        Async version that uses actual MAKER Planner LLM
        Called by orchestrator with real agent
        """
        logger.info(f1)
        logger.info(f1)
        logger.info(f1)
        logger.info(f1)
        
        # Step 1: Query world model hierarchically
        logger.info("[1/4] Querying hierarchical world model...")
        context = self.world_model.query_with_context(task_description)
        
        logger.info(f1)
        logger.info(f1)
        logger.info(f1)

        # Step 2: Read source file if this is a file conversion task
        file_content = await self._read_source_file_if_needed(task_description, orchestrator)

        # Step 3: Generate narrative-aware prompt
        logger.info("[2/4] Constructing narrative-aware prompt...")
        prompt = self._construct_narrative_prompt(task_description, context, file_content=file_content)

        # Step 4: Call actual MAKER Planner LLM
        logger.info("[3/4] Generating subtasks with MAKER Planner...")
        planner_prompt = orchestrator._load_system_prompt("planner")
        
        # Call the actual planner agent
        plan_json = ""
        async for chunk in orchestrator.call_agent(planner_agent, planner_prompt, prompt, temperature=0.3, max_tokens=2048):
            plan_json += chunk
        
        # Parse LLM response
        try:
            raw_subtasks = json.loads(plan_json)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', plan_json, re.DOTALL)
            if json_match:
                try:
                    raw_subtasks = json.loads(json_match.group())
                except Exception:
                    # Fallback to simple structure
                    raw_subtasks = self._generate_initial_subtasks(task_description, context)
            else:
                raw_subtasks = self._generate_initial_subtasks(task_description, context)
        
        # Step 4: Augment with EE context
        logger.info("[4/4] Augmenting with narrative context...")
        enhanced_subtasks = self._augment_with_narrative_context(raw_subtasks, context)
        
        # Display summary
        self._display_plan_summary(enhanced_subtasks, context)
        
        return enhanced_subtasks
    
    def _augment_with_narrative_context(
        self,
        raw_subtasks: Dict,
        context: Dict
    ) -> List[EnhancedSubtask]:
        """Take LLM-generated subtasks and augment with EE context"""
        enhanced = []
        
        for subtask in raw_subtasks.get('subtasks', []):
            # Map melodic line names to actual objects
            relevant_narratives = []
            for narrative_name in subtask.get('preserves_narratives', []):
                for line in context['melodic_lines']:
                    if line.name == narrative_name:
                        relevant_narratives.append(line.name)
            
            # Generate warnings specific to this subtask
            subtask_warnings = []
            for module in subtask.get('target_modules', []):
                for warning in context['warnings']:
                    if module in warning:
                        subtask_warnings.append(warning)
            
            # Extract patterns
            patterns = []
            for pattern in context.get('patterns', []):
                for instance in pattern.instances:
                    if instance['module'] in subtask.get('target_modules', []):
                        patterns.append(pattern.pattern_type)
            
            enhanced.append(EnhancedSubtask(
                description=subtask['description'],
                target_modules=subtask.get('target_modules', []),
                relevant_narratives=relevant_narratives,
                dependencies=subtask.get('depends_on', []),
                warnings=subtask_warnings,
                confidence=subtask.get('confidence', 0.5),
                preserves_patterns=list(set(patterns))
            ))
        
        return enhanced
    
    def _display_plan_summary(
        self, 
        subtasks: List[EnhancedSubtask],
        context: Dict
    ) -> None:
        """Display execution plan summary"""
        logger.info(f1)
        logger.info("EXECUTION PLAN SUMMARY")
        logger.info(f1)
        
        logger.info(f1)
        logger.info(f1)
        if subtasks:
            logger.info(f1)
        
        logger.info("Subtasks:")
        for i, subtask in enumerate(subtasks, 1):
            logger.info(f1)
            logger.info(f1)
            if subtask.relevant_narratives:
                logger.info(f1)
            if subtask.preserves_patterns:
                logger.info(f1)
            if subtask.warnings:
                logger.info(f1)
            logger.info(f1)
        
        logger.info(f1)

