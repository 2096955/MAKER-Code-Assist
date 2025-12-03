#!/usr/bin/env python3
"""
Kùzu-based Shared Workflow Memory

Enables "melodic line" - coherent reasoning chain across all agents.
Each agent writes its reasoning to a shared graph, later agents read the full chain.

This solves the problem of agents operating "all over the place" with no shared context.
"""

import os
import time
import json
from typing import Optional, Dict, Any, List
from pathlib import Path
from dataclasses import dataclass

try:
    import kuzu
    KUZU_AVAILABLE = True
except ImportError:
    KUZU_AVAILABLE = False
    print("[WARNING] Kùzu not installed. Melodic line memory disabled.")
    print("         Install with: pip install kuzu==0.6.0")


@dataclass
class AgentAction:
    """Single action in the workflow melodic line"""
    action_id: str
    task_id: str
    agent: str
    action_type: str
    input_data: str
    output_data: str
    reasoning: str
    temperature: float
    timestamp: float


class SharedWorkflowMemory:
    """
    Kùzu graph database for maintaining melodic line across agents.

    Instead of passing strings between agents, they all read/write to this shared graph.
    This preserves the full reasoning chain (melodic line) throughout the workflow.

    Example:
        memory = SharedWorkflowMemory()

        # Preprocessor writes
        memory.add_action(
            task_id="task_1",
            agent="preprocessor",
            reasoning="User wants JWT auth. Security requirement detected."
        )

        # Planner reads preprocessor's reasoning
        context = memory.get_context_for_agent("task_1", "planner")
        # context includes: "Security requirement detected"

        # Planner writes
        memory.add_action(
            task_id="task_1",
            agent="planner",
            reasoning="Based on security focus, planning defensive JWT impl"
        )

        # Coder reads BOTH preprocessor + planner
        context = memory.get_context_for_agent("task_1", "coder")
        # context includes BOTH reasonings!
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize shared workflow memory.

        Args:
            db_path: Path to Kùzu database directory (default: ./kuzu_workflow_db)
        """
        if not KUZU_AVAILABLE:
            self.enabled = False
            self.db = None
            self.conn = None
            return

        self.enabled = True
        self.db_path = db_path or os.getenv("KUZU_DB_PATH", "./kuzu_workflow_db")

        # Create directory if needed
        Path(self.db_path).mkdir(parents=True, exist_ok=True)

        # Initialize Kùzu database
        try:
            self.db = kuzu.Database(self.db_path)
            self.conn = kuzu.Connection(self.db)
            self._init_schema()
            print(f"[KùzuMemory] Initialized workflow memory at {self.db_path}")
        except Exception as e:
            print(f"[KùzuMemory] Failed to initialize: {e}")
            self.enabled = False
            self.db = None
            self.conn = None

    def _init_schema(self):
        """Create graph schema for workflow memory"""
        if not self.enabled:
            return

        try:
            # Task nodes
            self.conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS Task(
                    task_id STRING,
                    user_input STRING,
                    status STRING,
                    created_at INT64,
                    PRIMARY KEY(task_id)
                )
            """)

            # Agent action nodes (each agent's reasoning)
            self.conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS AgentAction(
                    action_id STRING,
                    task_id STRING,
                    agent STRING,
                    action_type STRING,
                    input_data STRING,
                    output_data STRING,
                    reasoning STRING,
                    temperature DOUBLE,
                    created_at INT64,
                    PRIMARY KEY(action_id)
                )
            """)

            # Relationships
            self.conn.execute("""
                CREATE REL TABLE IF NOT EXISTS PART_OF(
                    FROM AgentAction TO Task
                )
            """)

            self.conn.execute("""
                CREATE REL TABLE IF NOT EXISTS LEADS_TO(
                    FROM AgentAction TO AgentAction,
                    causal_reasoning STRING
                )
            """)

            self.conn.execute("""
                CREATE REL TABLE IF NOT EXISTS COORDINATES_WITH(
                    FROM AgentAction TO AgentAction,
                    collaboration_type STRING
                )
            """)

            print("[KùzuMemory] Schema initialized")
        except Exception as e:
            print(f"[KùzuMemory] Schema initialization error: {e}")
            # Schema might already exist, continue

    def create_task(self, task_id: str, user_input: str) -> bool:
        """
        Create a new task node in the graph.

        Args:
            task_id: Unique task identifier
            user_input: Original user request

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            self.conn.execute("""
                CREATE (:Task {
                    task_id: $task_id,
                    user_input: $user_input,
                    status: 'preprocessing',
                    created_at: $timestamp
                })
            """, {
                "task_id": task_id,
                "user_input": user_input,
                "timestamp": int(time.time())
            })
            return True
        except Exception as e:
            print(f"[KùzuMemory] Error creating task: {e}")
            return False

    def add_action(self,
                   task_id: str,
                   agent: str,
                   action_type: str,
                   input_data: str,
                   output_data: str,
                   reasoning: str,
                   temperature: float = 0.7,
                   link_to_previous: bool = True) -> Optional[str]:
        """
        Add an agent action to the melodic line.

        Args:
            task_id: Task this action belongs to
            agent: Agent name (preprocessor, planner, coder, etc.)
            action_type: Type of action (preprocess, plan, generate_code, etc.)
            input_data: What the agent received
            output_data: What the agent produced
            reasoning: WHY the agent made this choice (the melodic line!)
            temperature: Temperature used for generation
            link_to_previous: If True, automatically link to previous action in chain

        Returns:
            action_id if successful, None otherwise
        """
        if not self.enabled:
            return None

        action_id = f"{task_id}_{agent}_{int(time.time() * 1000)}"

        try:
            # Create action node
            self.conn.execute("""
                CREATE (:AgentAction {
                    action_id: $action_id,
                    task_id: $task_id,
                    agent: $agent,
                    action_type: $action_type,
                    input_data: $input_data,
                    output_data: $output_data,
                    reasoning: $reasoning,
                    temperature: $temperature,
                    created_at: $timestamp
                })
            """, {
                "action_id": action_id,
                "task_id": task_id,
                "agent": agent,
                "action_type": action_type,
                "input_data": input_data[:5000],  # Limit to 5KB
                "output_data": output_data[:5000],  # Limit to 5KB
                "reasoning": reasoning[:2000],  # Limit to 2KB
                "temperature": temperature,
                "timestamp": int(time.time())
            })

            # Link to task
            self.conn.execute("""
                MATCH (a:AgentAction {action_id: $action_id}),
                      (t:Task {task_id: $task_id})
                CREATE (a)-[:PART_OF]->(t)
            """, {
                "action_id": action_id,
                "task_id": task_id
            })

            # Link to previous action (creates melodic line)
            if link_to_previous:
                self._link_to_previous_action(action_id, task_id, agent, reasoning)

            return action_id
        except Exception as e:
            print(f"[KùzuMemory] Error adding action: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _link_to_previous_action(self, action_id: str, task_id: str, agent: str, reasoning: str):
        """Link current action to previous action in workflow"""
        try:
            # Find most recent action in this task (before current)
            result = self.conn.execute("""
                MATCH (prev:AgentAction)-[:PART_OF]->(t:Task {task_id: $task_id})
                WHERE prev.action_id != $action_id
                RETURN prev.action_id, prev.agent, prev.created_at
                ORDER BY prev.created_at DESC
                LIMIT 1
            """, {
                "task_id": task_id,
                "action_id": action_id
            })

            prev_actions = result.get_as_df()

            if not prev_actions.empty:
                prev_action_id = prev_actions.iloc[0]['prev.action_id']
                prev_agent = prev_actions.iloc[0]['prev.agent']

                # Create causal link
                self.conn.execute("""
                    MATCH (prev:AgentAction {action_id: $prev_id}),
                          (curr:AgentAction {action_id: $curr_id})
                    CREATE (prev)-[:LEADS_TO {
                        causal_reasoning: $reasoning
                    }]->(curr)
                """, {
                    "prev_id": prev_action_id,
                    "curr_id": action_id,
                    "reasoning": f"{agent} builds on {prev_agent}'s output: {reasoning[:200]}"
                })
        except Exception as e:
            print(f"[KùzuMemory] Error linking actions: {e}")

    def get_context_for_agent(self, task_id: str, agent: str, max_tokens: int = 4000) -> str:
        """
        Get melodic line context for an agent.

        This is the key method that enables coherent reasoning!
        Each agent sees the full reasoning chain from previous agents.

        Args:
            task_id: Task identifier
            agent: Agent requesting context
            max_tokens: Maximum context length (rough estimate)

        Returns:
            Formatted context string with previous agents' reasoning
        """
        if not self.enabled:
            return ""

        try:
            # Get all previous actions in this task, ordered by time
            result = self.conn.execute("""
                MATCH (a:AgentAction)-[:PART_OF]->(t:Task {task_id: $task_id})
                RETURN a.agent, a.action_type, a.output_data, a.reasoning, a.created_at
                ORDER BY a.created_at ASC
            """, {"task_id": task_id})

            actions = result.get_as_df()

            if actions.empty:
                return ""

            # Format as context
            context_parts = ["[MELODIC LINE - Previous agent reasoning]"]
            current_tokens = 0

            for _, row in actions.iterrows():
                agent_name = row['a.agent']
                reasoning = row['a.reasoning']
                output_preview = row['a.output_data'][:200] + "..." if len(row['a.output_data']) > 200 else row['a.output_data']

                entry = f"\n{agent_name.upper()}: {reasoning}\n  Output: {output_preview}"
                entry_tokens = len(entry) // 4  # Rough estimate

                if current_tokens + entry_tokens > max_tokens:
                    context_parts.append("\n... (earlier actions truncated)")
                    break

                context_parts.append(entry)
                current_tokens += entry_tokens

            context_parts.append("\n[END MELODIC LINE]\n")

            return "\n".join(context_parts)
        except Exception as e:
            print(f"[KùzuMemory] Error getting context: {e}")
            return ""

    def get_melodic_line(self, task_id: str) -> List[Dict[str, Any]]:
        """
        Get the complete melodic line (reasoning chain) for a task.

        Returns:
            List of actions in order, each with agent, reasoning, output
        """
        if not self.enabled:
            return []

        try:
            result = self.conn.execute("""
                MATCH path = (start:AgentAction)-[:LEADS_TO*0..20]->(end:AgentAction)
                WHERE start.task_id = $task_id
                WITH path, length(path) AS depth
                ORDER BY depth DESC
                LIMIT 1
                UNWIND nodes(path) AS node
                RETURN node.agent AS agent,
                       node.action_type AS action_type,
                       node.reasoning AS reasoning,
                       node.output_data AS output,
                       node.created_at AS timestamp
                ORDER BY node.created_at ASC
            """, {"task_id": task_id})

            df = result.get_as_df()

            if df.empty:
                return []

            return [
                {
                    "agent": row['agent'],
                    "action_type": row['action_type'],
                    "reasoning": row['reasoning'],
                    "output": row['output'],
                    "timestamp": row['timestamp']
                }
                for _, row in df.iterrows()
            ]
        except Exception as e:
            print(f"[KùzuMemory] Error getting melodic line: {e}")
            return []

    def get_swarm_insights(self, task_id: str, exclude_agent: Optional[str] = None, limit: int = 10) -> str:
        """
        Get insights from other agents in a swarm (for parallel coordination).

        This enables swarm behavior: parallel agents can read each other's reasoning.

        Args:
            task_id: Task identifier
            exclude_agent: Agent to exclude (usually the requesting agent)
            limit: Maximum number of insights to return

        Returns:
            Formatted string with other agents' discoveries
        """
        if not self.enabled:
            return ""

        try:
            # Get recent actions from other agents (swarm members)
            query = """
                MATCH (a:AgentAction)-[:PART_OF]->(t:Task {task_id: $task_id})
                WHERE a.action_type = 'swarm_code'
            """

            if exclude_agent:
                query += " AND a.agent != $exclude_agent"

            query += """
                RETURN a.agent, a.reasoning, a.output_data, a.created_at
                ORDER BY a.created_at DESC
                LIMIT $limit
            """

            params = {"task_id": task_id, "limit": limit}
            if exclude_agent:
                params["exclude_agent"] = exclude_agent

            result = self.conn.execute(query, params)
            df = result.get_as_df()

            if df.empty:
                return "No other swarm members have contributed yet."

            insights = ["[SWARM INSIGHTS - What other coders discovered]"]

            for _, row in df.iterrows():
                insights.append(f"\n{row['a.agent']}: {row['a.reasoning']}")
                insights.append(f"  Approach: {row['a.output_data'][:150]}...")

            insights.append("\n[Build on these insights or propose a better approach]")

            return "\n".join(insights)
        except Exception as e:
            print(f"[KùzuMemory] Error getting swarm insights: {e}")
            return ""

    def add_swarm_coordination(self, action_id_1: str, action_id_2: str, collaboration_type: str):
        """
        Link two swarm members who coordinated.

        Args:
            action_id_1: First agent's action
            action_id_2: Second agent's action
            collaboration_type: How they collaborated (e.g., "built_on", "diverged_from")
        """
        if not self.enabled:
            return

        try:
            self.conn.execute("""
                MATCH (a1:AgentAction {action_id: $id1}),
                      (a2:AgentAction {action_id: $id2})
                CREATE (a1)-[:COORDINATES_WITH {
                    collaboration_type: $collab_type
                }]->(a2)
            """, {
                "id1": action_id_1,
                "id2": action_id_2,
                "collab_type": collaboration_type
            })
        except Exception as e:
            print(f"[KùzuMemory] Error adding coordination link: {e}")

    def update_task_status(self, task_id: str, status: str):
        """Update task status (preprocessing, planning, coding, reviewing, complete)"""
        if not self.enabled:
            return

        try:
            self.conn.execute("""
                MATCH (t:Task {task_id: $task_id})
                SET t.status = $status
            """, {"task_id": task_id, "status": status})
        except Exception as e:
            print(f"[KùzuMemory] Error updating task status: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get workflow memory statistics"""
        if not self.enabled:
            return {"enabled": False}

        try:
            # Count nodes
            tasks = self.conn.execute("MATCH (t:Task) RETURN count(t) AS count").get_as_df()
            actions = self.conn.execute("MATCH (a:AgentAction) RETURN count(a) AS count").get_as_df()

            # Count relationships
            leads_to = self.conn.execute("MATCH ()-[r:LEADS_TO]->() RETURN count(r) AS count").get_as_df()
            coords = self.conn.execute("MATCH ()-[r:COORDINATES_WITH]->() RETURN count(r) AS count").get_as_df()

            return {
                "enabled": True,
                "db_path": self.db_path,
                "total_tasks": int(tasks.iloc[0]['count']),
                "total_actions": int(actions.iloc[0]['count']),
                "melodic_line_links": int(leads_to.iloc[0]['count']),
                "swarm_coordination_links": int(coords.iloc[0]['count'])
            }
        except Exception as e:
            print(f"[KùzuMemory] Error getting stats: {e}")
            return {"enabled": True, "error": str(e)}

    def close(self):
        """Close database connection"""
        if self.enabled and self.db:
            try:
                # Kùzu auto-closes, but explicit close is good practice
                self.conn = None
                self.db = None
                print("[KùzuMemory] Closed database connection")
            except Exception as e:
                print(f"[KùzuMemory] Error closing: {e}")
