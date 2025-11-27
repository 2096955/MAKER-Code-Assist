# Model-Specific Prompt Design

This document explains how each agent's system prompt is tailored to its specific model's characteristics and instruction-following patterns.

## Design Philosophy

**Key Insight**: Different models have different instruction-following characteristics. Smaller models work better with concise, direct prompts, while larger models can handle more structure. Each prompt is tailored to its model's strengths.

## Model Lineup

| Role | Model | Size | Characteristics |
|------|-------|------|------------------|
| Preprocessor | Gemma 2 2B IT | 2B | Google, instruction-tuned, simple instructions |
| Planner | Nemotron Nano 8B Instruct | 8B | NVIDIA, based on Mistral, needs clear examples |
| Coder | Devstral 24B Instruct | 24B | Mistral, code-specialized, minimal changes philosophy |
| Reviewer | Qwen Coder 32B Instruct | 32B | Alibaba, code-specialized, practical approach |
| Voter | Qwen 2.5 1.5B Instruct | 1.5B | Alibaba, small/fast, ultra-minimal prompts |

## Prompt Design Principles

### 1. Concise Over Verbose
- **Smaller models** (Gemma 2B, Qwen 1.5B) don't benefit from verbose instructions
- **Removed**: "CRITICAL RULES (REPEATED 3x)" - overkill for these models
- **Result**: Direct, actionable instructions work better

### 2. Model-Specific Tone
- **Devstral 24B**: Workflow-oriented language, matches "minimal changes" philosophy
- **Nemotron 8B**: Clear examples, plain text output (no JSON)
- **Qwen Coder 32B**: Practical checklist style, brief approvals
- **Qwen 2.5 1.5B**: Ultra-minimal, single letter output

### 3. Orchestrator-Handled Context
- **MCP tool references removed** from prompts
- **Orchestrator handles** all MCP queries and provides context to agents
- **Agents focus** on their core task, not tool management

## Individual Prompt Analysis

### Preprocessor (Gemma 2 2B)

**Design**: Minimal, structured JSON output

**Key Features**:
- Simple identity statement
- Clear input types (Audio, Image, Text)
- Structured JSON output format
- Minimal rules (concise output, no interpretation)

**Why This Works**:
- Gemma 2B is instruction-tuned but small - needs simple, clear structure
- JSON format is enforced by structure, not verbose repetition
- No reasoning required - just conversion

### Planner (Nemotron Nano 8B)

**Design**: Clear examples, plain text output

**Key Features**:
- Direct request type classification
- Concrete examples for questions and complex tasks
- Plain text/markdown output (no JSON)
- Reasonable assumptions over clarification

**Why This Works**:
- Nemotron 8B is based on Mistral - benefits from clear examples
- Documentation notes it "may not perform optimally" without clear structure
- Examples show exact input→output format

### Coder (Devstral 24B)

**Design**: Workflow-oriented, minimal changes philosophy

**Key Features**:
- Workflow steps (understand → write → output)
- Principles aligned with Devstral's "minimal changes" approach
- Clean code with minimal comments
- Simple, readable solutions over clever ones

**Why This Works**:
- Devstral is code-specialized and designed for agentic workflows
- Matches Devstral's SYSTEM_PROMPT.txt philosophy from Mistral
- Temperature 0.3 recommended (orchestrator uses 0.3-0.7 for candidates)

### Reviewer (Qwen Coder 32B)

**Design**: Practical checklist style

**Key Features**:
- Brief checklist (Correctness, Security, Readability)
- Simple response format ("Looks good" or "Issue on line X")
- Practical rules (be brief, only flag real problems)
- Approve working code even if imperfect

**Why This Works**:
- Qwen Coder 32B is code-specialized and practical
- Brief format prevents over-analysis
- Focuses on what matters (correctness, security) vs. style

### Voter (Qwen 2.5 1.5B)

**Design**: Ultra-minimal, single letter output

**Key Features**:
- Single sentence identity
- Simple selection criteria (solves task, runs without errors, simple/clear)
- Decision rules (working beats apologies, simple beats complex)
- Single letter output (A, B, C, D, E)

**Why This Works**:
- Qwen 2.5 1.5B is very small - needs ultra-minimal instructions
- Single letter output is simple and unambiguous
- Decision rules are clear and actionable

## Comparison: Before vs. After

### Before (Verbose, Generic)
```
# CODER AGENT

## Identity
You write code. Output working code directly in markdown code blocks.

## CRITICAL RULES (REPEATED 3x with escalation):
1. **Output code in markdown code blocks** - NO JSON wrapping
2. **Use MCP tools to read files FIRST** - Understand existing code patterns before writing
3. **NO explanations unless asked** - Just working code
4. **Report progress** - "Reading file X...", "Generating code..."

## Tool Usage
- **Read files in parallel** if you need multiple files
- **Use `find_references`** to find where functions/classes are used
...
```

### After (Concise, Model-Specific)
```
# CODER (Devstral 24B)

You are a code generation agent. Your job is to write working code that solves the given task.

## Workflow
1. Understand the task requirements
2. Write clean, minimal code that solves the problem
3. Output code in markdown code blocks

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

**Key Differences**:
-  Removed verbose repetition ("REPEATED 3x")
-  Removed MCP tool references (orchestrator handles this)
-  Added model-specific workflow language
-  Aligned with Devstral's "minimal changes" philosophy
-  More concise and direct

## Results

**Testing Results** (from terminal 976-1019):
-  Simple code requests: Clean output, no JSON wrapping
-  Questions: Direct, helpful answers
-  Complex requests: Working code generation

**Key Improvements**:
1. **No JSON wrapping** - Prompts enforce markdown code blocks
2. **No apologies** - Direct code output
3. **No "I can't help"** - Agents make reasonable assumptions
4. **Cleaner output** - Model-specific prompts produce better results

## References

- [Claude Code Analysis](https://southbridge-research.notion.site/claude-code-an-agentic-cleanroom-analysis)
- [Devstral Documentation](https://huggingface.co/mistralai/Devstral-Small-2505)
- [Nemotron Documentation](https://huggingface.co/nvidia/Nemotron-Mini-4B-Instruct)
- [Qwen Coder Documentation](https://huggingface.co/Qwen/Qwen2.5-Coder-32B-Instruct)

