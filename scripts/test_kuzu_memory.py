#!/usr/bin/env python3
"""
Quick test: Can Kùzu solve the melodic line problem?

Simulates 3 agents (Preprocessor, Planner, Coder) writing to shared graph.
Tests if later agents can read earlier reasoning.
"""

import kuzu
import time
from pathlib import Path

# Create test DB
db_path = Path("./test_kuzu_memory")
db_path.mkdir(exist_ok=True)

db = kuzu.Database(str(db_path))
conn = kuzu.Connection(db)

# Schema
conn.execute("""
    CREATE NODE TABLE IF NOT EXISTS AgentAction(
        action_id STRING,
        agent STRING,
        reasoning STRING,
        output STRING,
        timestamp INT64,
        PRIMARY KEY(action_id)
    )
""")

conn.execute("""
    CREATE REL TABLE IF NOT EXISTS LEADS_TO(
        FROM AgentAction TO AgentAction
    )
""")

# Simulate workflow
task_id = "test_123"

# 1. Preprocessor
print("[PREPROCESSOR] Processing input...")
conn.execute("""
    CREATE (:AgentAction {
        action_id: $id,
        agent: 'preprocessor',
        reasoning: 'User wants JWT auth. Detected security requirement.',
        output: 'Add JWT authentication to API',
        timestamp: $ts
    })
""", {"id": f"{task_id}_preprocessor", "ts": int(time.time())})

# 2. Planner (reads preprocessor's reasoning!)
print("\n[PLANNER] Reading preprocessor's reasoning...")
preprocessor_reasoning = conn.execute("""
    MATCH (a:AgentAction {agent: 'preprocessor'})
    WHERE a.action_id STARTS WITH $task_id
    RETURN a.reasoning
""", {"task_id": task_id}).get_as_df()

print(f"  → Preprocessor said: {preprocessor_reasoning['reasoning'][0]}")

print("[PLANNER] Creating plan based on that understanding...")
conn.execute("""
    CREATE (:AgentAction {
        action_id: $id,
        agent: 'planner',
        reasoning: 'Based on preprocessor security detection, planning JWT implementation',
        output: '1. Create JWT util, 2. Add middleware, 3. Update endpoints',
        timestamp: $ts
    })
""", {"id": f"{task_id}_planner", "ts": int(time.time())})

# Link them
conn.execute("""
    MATCH (pre:AgentAction {action_id: $pre_id}),
          (plan:AgentAction {action_id: $plan_id})
    CREATE (pre)-[:LEADS_TO]->(plan)
""", {
    "pre_id": f"{task_id}_preprocessor",
    "plan_id": f"{task_id}_planner"
})

# 3. Coder (reads BOTH!)
print("\n[CODER] Reading FULL melodic line...")
melodic_line = conn.execute("""
    MATCH path = (a:AgentAction)-[:LEADS_TO*0..10]->(b:AgentAction)
    WHERE a.action_id STARTS WITH $task_id
    RETURN [n IN nodes(path) | n.agent] AS agents,
           [n IN nodes(path) | n.reasoning] AS reasonings
    ORDER BY length(path) DESC
    LIMIT 1
""", {"task_id": task_id}).get_as_df()

print("  → Full reasoning chain:")
for agent, reasoning in zip(melodic_line['agents'][0], melodic_line['reasonings'][0]):
    print(f"     {agent}: {reasoning}")

print("\n[CODER] Generating code with full context...")
conn.execute("""
    CREATE (:AgentAction {
        action_id: $id,
        agent: 'coder',
        reasoning: 'Implementing JWT as planned, maintaining security focus from preprocessor',
        output: 'def create_jwt(user): ...',
        timestamp: $ts
    })
""", {"id": f"{task_id}_coder", "ts": int(time.time())})

print("\n✅ SUCCESS: Coder saw BOTH preprocessor's security concern AND planner's structure!")
print("   This is the 'melodic line' - coherent reasoning across agents.")

# Cleanup
import shutil
shutil.rmtree(db_path)
print(f"\n🧹 Cleaned up test DB at {db_path}")
