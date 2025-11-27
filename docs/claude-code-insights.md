# Claude Code Insights Applied to Multi-Agent System

**Source**: [Claude Code: An Agentic Cleanroom Analysis](https://southbridge-research.notion.site/claude-code-an-agentic-cleanroom-analysis) by Southbridge Research

This document distills key architectural insights from Claude Code's analysis and applies them to our multi-agent coding system.

## Core Principles

### 1. Streaming First Architecture
**Claude Code Insight**: Every operation designed for incremental updates

**Applied to Our System**:
- ✅ All agent calls use streaming (`stream=True`)
- ✅ Orchestrator yields chunks as they arrive
- ✅ UI receives real-time updates (Continue.dev, Open WebUI)
- 🔄 **Enhancement Opportunity**: Add backpressure management for slow consumers

### 2. Safety Through Layers
**Claude Code Insight**: Multiple independent protection mechanisms that fail safely

**Applied to Our System**:
- ✅ Context truncation (2000 char limit in `generate_candidates`)
- ✅ File size limits in codebase server (1MB max)
- ✅ File count limits (500 max files)
- ✅ Path traversal protection in MCP server
- 🔄 **Enhancement Opportunity**: Add permission system for tool execution

### 3. Model-Specific Prompt Design
**Claude Code Insight**: Different models need different prompting approaches

**Applied to Our System**:
- ✅ **Concise prompts** - Smaller models (Gemma 2B, Qwen 1.5B) work better with direct instructions
- ✅ **Model-tailored structure** - Each prompt matches the model's characteristics:
  - Devstral 24B: Workflow-oriented, minimal changes philosophy
  - Nemotron 8B: Clear examples, plain text output
  - Qwen Coder 32B: Practical checklist style
- ✅ **No verbose repetition** - Removed "CRITICAL RULES (REPEATED 3x)" - overkill for these models
- ✅ **Orchestrator-handled context** - MCP tool references removed from prompts (orchestrator provides context)

### 4. Architecture Over Optimization
**Claude Code Insight**: Performance through design, not tweaks

**Applied to Our System**:
- ✅ Parallel candidate generation (5 Coders)
- ✅ Parallel voting (5 Voters)
- ✅ Native llama.cpp Metal for 2-3x speed
- ✅ Read-only tools can run in parallel (MCP queries)
- ✅ Write operations serialize (code generation → review)

### 5. Understanding LLM Psychology
**Claude Code Insight**: Exploiting how models actually behave

**Applied to Our System**:
- ✅ Clear constraints prevent decision paralysis
- ✅ Direct output format instructions ("Output code in markdown blocks")
- ✅ Temperature variations for diversity (0.3-0.7 for candidates)
- 🔄 **Enhancement**: Add negative examples ("Don't do X") for common mistakes

## Agent-Specific Insights

### Preprocessor Agent

**Claude Code Insight**: Input routing and normalization

**Current State**:
- Handles multimodal inputs (audio, images, text)
- Outputs structured JSON

**Enhancements from Claude Code**:
1. **Error Formatting**: Format errors for LLM consumption (not human)
   - Include actionable suggestions
   - Preserve critical debugging info (stdout/stderr)
   - Format validation errors in natural language

2. **Input Classification**: More sophisticated routing
   - Detect command patterns (like Claude Code's `/`, `!`, `#` detection)
   - Route to appropriate agent based on intent

### Planner Agent

**Claude Code Insight**: Dynamic context assembly with intelligent prioritization

**Current State**:
- Receives codebase context from MCP
- Creates execution plans
- Classifies requests (simple vs complex)

**Enhancements from Claude Code**:
1. **Priority-Based Context Truncation**:
   - Preserve most important context first
   - Hierarchical loading with override semantics
   - Dynamic alternatives (e.g., reduce directory depth if too large)

2. **Context Assembly**:
   - Model-specific prompt adaptations
   - Smart summarization fallbacks
   - Priority-based ordering (recent files > old files)

3. **Model-Specific Prompt Design**:
   - Tailored to each model's characteristics (Nemotron 8B needs clear examples)
   - Concise instructions (smaller models don't benefit from verbosity)
   - Direct output format constraints
   - Clear examples of good vs bad plans

**Actual Prompt Structure (Model-Tailored)**:
```
# PLANNER (Nemotron Nano 8B)

You analyze requests and provide direct answers or break down complex tasks into steps.

## Request Types
**Answer directly** for: [list]
**Break into steps** only for: [list]

## For Questions
Provide a direct, concise answer.
[Example]

## For Complex Tasks
List 3-5 concrete steps with files to modify.
[Example]

## Output Rules
- Use plain text or markdown
- No JSON structure
- No elaborate plans for simple tasks
- Make reasonable assumptions rather than asking questions
```

### Coder Agent

**Claude Code Insight**: Tool execution with state machines and progress reporting

**Current State**:
- Generates code directly
- Uses MCP tools for context
- Outputs markdown code blocks

**Enhancements from Claude Code**:
1. **Model-Specific Design**:
   - Devstral 24B: Workflow-oriented, matches "minimal changes" philosophy
   - Concise instructions (not verbose repetition)
   - Direct code output in markdown blocks

2. **Output Format Enforcement**:
   - Output code in markdown blocks only
   - NO JSON wrapping
   - NO explanations unless asked
   - Direct, working code only

**Actual Prompt Structure (Model-Tailored)**:
```
# CODER (Devstral 24B)

You are a code generation agent. Your job is to write working code that solves the given task.

## Workflow
1. Understand the task requirements
2. Write clean, minimal code that solves the problem
3. Output code in markdown code blocks

## Output Format
\`\`\`language
// your code here
\`\`\`

## Principles
- Write clean code with minimal comments
- Make minimal changes needed to solve the problem
- Prefer simple, readable solutions over clever ones
- Make reasonable assumptions rather than asking for clarification

## Constraints
- Output code in markdown code blocks only
- No JSON wrapping
- No apologies or refusals
- No clarifying questions for simple tasks
```

**Note**: MCP tool references removed from prompts - orchestrator handles MCP queries and provides context to agents.

### Reviewer Agent

**Claude Code Insight**: Error formatting pipeline for LLM consumption

**Current State**:
- Reviews code for correctness, security, readability
- Provides feedback

**Enhancements from Claude Code**:
1. **Model-Specific Design**:
   - Qwen Coder 32B: Practical checklist style
   - Brief approvals, specific issues
   - Concise error format (not verbose structured format)

2. **Error Format**:
   - Simple, direct format: "Issue on line X: [problem]. Fix: [suggestion]."
   - Practical, not pedantic
   - Focus on correctness, security, readability

**Actual Prompt Structure (Model-Tailored)**:
```
# REVIEWER (Qwen Coder 32B)

You evaluate code for correctness and security. Be practical, not pedantic.

## What to Check
1. **Correctness** - Will it run without errors?
2. **Security** - No hardcoded secrets, no injection vulnerabilities
3. **Readability** - Is it understandable?

## Response Format
**If code is good:**
"Looks good. [Brief note on what works well.]"

**If there's an issue:**
"Issue on line X: [problem]. Fix: [suggestion]."

## Rules
- Be brief
- Only flag real problems
- Don't require tests unless asked
- Don't block for style preferences
- Approve working code even if imperfect
```

**Note**: Simplified from verbose structured format - Qwen Coder 32B works better with concise, practical instructions.
- Comprehensive test coverage
- Documentation
```

## Orchestration Enhancements

### 1. Six-Phase Control Flow

**Claude Code Pattern**:
1. Context Window Management (compaction if needed)
2. Dynamic System Prompt Assembly
3. Streaming State Machine
4. Tool Execution Pipeline (parallel/sequential)
5. Permission Control Flow
6. Recursive Turn Management

**Our Current Flow**:
1. Preprocessing
2. Planning (with MCP context)
3. Coding (MAKER: 5 candidates → voting)
4. Reviewing
5. Iteration (max 3 rounds)

**Enhancement Opportunities**:
- Add context compaction phase (if conversation history too long)
- Implement parallel tool execution for read-only MCP queries
- Add recursive turn management for multi-step tasks

### 2. Parallel Tool Execution

**Claude Code Insight**: Read-only tools run in parallel, write operations serialize

**Applied to Our System**:
- ✅ MAKER voting: 5 Coders in parallel
- ✅ MAKER voting: 5 Voters in parallel
- 🔄 **Enhancement**: Planner can query multiple MCP tools in parallel
- 🔄 **Enhancement**: Coder can read multiple files in parallel

### 3. Error Recovery

**Claude Code Insight**: Sophisticated error recovery strategies

**Applied to Our System**:
- ✅ JSON parsing fallback (regex extraction)
- ✅ Context truncation on token overflow
- 🔄 **Enhancement**: Retry failed agent calls with backoff
- 🔄 **Enhancement**: Graceful degradation (fallback to simpler approach)

### 4. Progress Aggregation

**Claude Code Insight**: Coordinate progress from multiple concurrent operations

**Applied to Our System**:
- ✅ MAKER voting shows vote counts
- ✅ Streaming shows agent stages
- 🔄 **Enhancement**: Rich progress reporting (percentage, ETA)
- 🔄 **Enhancement**: Progress aggregation for parallel operations

## Implementation Status

### ✅ Completed
1. **Model-Specific Prompt Design**: All prompts tailored to each model's characteristics
   - Gemma 2 2B (Preprocessor): Minimal, structured JSON output
   - Nemotron Nano 8B (Planner): Clear examples, plain text output
   - Devstral 24B (Coder): Workflow-oriented, minimal changes philosophy
   - Qwen Coder 32B (Reviewer): Practical checklist style
   - Qwen 2.5 1.5B (Voter): Ultra-minimal, single letter output

2. **Concise Instructions**: Removed verbose repetition - smaller models work better with direct, concise prompts

3. **Orchestrator-Handled MCP**: MCP tool references removed from prompts - orchestrator handles all MCP queries and provides context

### Future Enhancements
1. **Progress Reporting**: Add progress updates to Coder agent (optional enhancement)
2. **Parallel MCP Queries**: Allow Planner to query multiple tools in parallel (orchestrator-level)

### Medium Priority (Performance)
1. **Context Compaction**: Implement conversation history summarization
2. **Backpressure Management**: Handle slow consumers gracefully
3. **Tool Execution Optimization**: Parallel read-only, sequential writes

### Low Priority (Polish)
1. **Permission System**: Add fine-grained tool permissions
2. **Advanced Error Recovery**: Retry with backoff, graceful degradation
3. **Progress Aggregation UI**: Rich progress visualization

## References

- [Claude Code Analysis](https://southbridge-research.notion.site/claude-code-an-agentic-cleanroom-analysis)
- [Novel Components](https://southbridge-research.notion.site/Novel-Components-The-Innovations-That-Define-Claude-Code-2055fec70db181fdae5bd485823986c4)
- [Control Flow](https://southbridge-research.notion.site/Control-Flow-The-Orchestration-Engine-2055fec70db181d0b215e1b8584d03fa)
- [Prompt Engineering](https://southbridge-research.notion.site/Prompt-Engineering-The-Art-of-Instructing-AI-2055fec70db181369002dcdea7d9e732)

