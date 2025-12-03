# Intelligent Codebase Analysis

## Overview

The MAKER system now provides intelligent codebase analysis with memory, smart README extraction, and context-first output formatting.

## Features

### 1. Redis Memory for Codebase Analysis

**Problem Solved**: System was re-analyzing the same codebase every time (wasteful, slow).

**Solution**: First-time analysis is cached in Redis for 7 days.

**How It Works**:
- First query: Analyzes codebase (walks directory, reads README, counts files) → saves to Redis
- Subsequent queries: Instantly recalls from Redis with `[MEMORY]` tag

**Example**:
```
# First time
[ANALYST] Analyzing /Users/anthonylui/DeepCode/...
DeepCode is a multi-agent coding system for...
Files: 96, Lines: 33,513, Code: .py (51)

# Second time (instant)
[MEMORY] Recalled from previous analysis:
DeepCode is a multi-agent coding system for...
Files: 96, Lines: 33,513, Code: .py (51)
```

**Redis Keys**:
- `codebase_overview:{path}` - Cached analysis (7 day TTL)
- Stored locally in Docker volume (not sent externally)

### 2. Smart README Extraction with Gemma2-2B

**Problem Solved**: Regex parsing failed on HTML-heavy READMEs (badges, images, ASCII art).

**Solution**: Use Preprocessor (Gemma2-2B) to intelligently extract description.

**How It Works**:
```python
# Instead of regex parsing
description = extract_readme_with_regex(readme_content)  # ❌ Fails on HTML

# Use AI to understand content
summary_prompt = "Extract the main purpose/description of this codebase in 1-2 sentences. Ignore badges, images, and formatting. Focus on WHAT this project does."
description = await call_agent_sync(
    AgentName.PREPROCESSOR,  # Gemma2-2B
    summary_prompt,
    f"README content:\n{readme_content[:3000]}"
)
```

**Benefits**:
- Handles HTML-heavy READMEs (DeepCode, etc.)
- Extracts actual purpose, not markup
- Works for both external and current codebases

### 3. Context-First, Stats-Second Output

**Format**:
1. **Description** (what the codebase is about) - from README
2. **Metrics** (files, lines, languages, structure)

**Example Output**:
```
DeepCode is a multi-agent coding system for advancing code generation with multi-agent systems.

Files: 96
Lines: 33,513
Code: .py (51)
Structure: assets, cli, config, prompts, schema, tools, ui, utils
```

**Before**: Stats first, no context  
**After**: Context first, then stats

### 4. External Codebase Access

**Problem Solved**: Orchestrator containerized, couldn't access external paths like `/Users/anthonylui/DeepCode/`.

**Solution**: Docker volume mounts + path mapping.

**Configuration** (`docker-compose.yml`):
```yaml
orchestrator-high:
  volumes:
    - /Users/anthonylui:/host/Users/anthonylui:ro  # External codebase access
```

**Path Mapping**:
- User asks: `/Users/anthonylui/DeepCode/`
- System maps: `/host/Users/anthonylui/DeepCode/`
- Reads directly from filesystem

**Security**: Read-only mounts, path validation

## Usage

### Querying External Codebases

```bash
# Ask about any codebase
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "multi-agent",
    "messages": [{
      "role": "user",
      "content": "What can you tell me about this codebase /Users/anthonylui/DeepCode/"
    }]
  }'
```

**Response**:
- First time: `[ANALYST] Analyzing...` (3-5 seconds)
- Subsequent: `[MEMORY] Recalled from previous analysis` (instant)

### Querying Current Codebase

```bash
# Ask about BreakingWind itself
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "multi-agent",
    "messages": [{
      "role": "user",
      "content": "What can you tell me about this codebase?"
    }]
  }'
```

**Response**: Same format - description first, then metrics.

## Implementation Details

### Codebase Analysis Flow

1. **Detect codebase question** (keywords: "codebase", "tell me about", etc.)
2. **Check Redis memory** (`codebase_overview:{path}`)
3. **If cached**: Return instantly with `[MEMORY]` tag
4. **If not cached**:
   - Walk directory structure
   - Read README (if exists)
   - Use Gemma2-2B to extract description
   - Count files, lines, languages
   - Save to Redis (7 day TTL)
   - Return analysis

### README Extraction

**Location**: `orchestrator/orchestrator.py:1501-1530`

**Process**:
1. Read README file (first 3000 chars)
2. Call Preprocessor (Gemma2-2B) with extraction prompt
3. Get AI-generated description (1-2 sentences)
4. Cache in Redis with full analysis

### Memory Management

**Redis Keys**:
- `codebase_overview:{normalized_path}` - Full analysis JSON
- TTL: 7 days (604800 seconds)
- Format: `{"path": str, "description": str, "total_files": int, "total_lines": int, "lang_counts": dict, "top_dirs": list, "analyzed_at": timestamp}`

**Cache Invalidation**:
- Automatic: 7 day TTL
- Manual: `docker compose exec redis redis-cli del "codebase_overview:{path}"`

## Configuration

### Environment Variables

```bash
# Enable/disable codebase memory (default: true)
ENABLE_CODEBASE_MEMORY=true

# Redis connection (default: localhost:6379)
REDIS_HOST=localhost
REDIS_PORT=6379
```

### Docker Volumes

```yaml
# For external codebase access
volumes:
  - /Users/anthonylui:/host/Users/anthonylui:ro
```

## Benefits

1. **Faster Responses**: Cached analysis returns instantly
2. **Better Understanding**: AI extracts actual purpose, not markup
3. **Context-First**: Description before stats (more useful)
4. **External Access**: Can analyze any codebase on host system
5. **Smart Memory**: System remembers what it learns

## Examples

### Example 1: First-Time Analysis

**Query**: "What can you tell me about this codebase /Users/anthonylui/DeepCode/"

**Response**:
```
[ANALYST] Analyzing /Users/anthonylui/DeepCode/...

DeepCode is a multi-agent coding system for advancing code generation with multi-agent systems, built by HKU Data Intelligence Lab.

Files: 96
Lines: 33,513
Code: .py (51)
Structure: assets, cli, config, prompts, schema, tools, ui, utils
```

### Example 2: Cached Analysis

**Query**: "What can you tell me about this codebase /Users/anthonylui/DeepCode/"

**Response**:
```
[MEMORY] Recalled from previous analysis:

DeepCode is a multi-agent coding system for advancing code generation with multi-agent systems, built by HKU Data Intelligence Lab.

Files: 96
Lines: 33,513
Code: .py (51)
Structure: assets, cli, config, prompts, schema, tools, ui, utils
```

## Troubleshooting

### Issue: "Cannot access /Users/anthonylui/DeepCode/"

**Solution**: Ensure Docker volume mount is configured:
```yaml
volumes:
  - /Users/anthonylui:/host/Users/anthonylui:ro
```

### Issue: Bad cached description (HTML markup)

**Solution**: Clear Redis cache:
```bash
docker compose exec redis redis-cli del "codebase_overview:/Users/anthonylui/DeepCode/"
```

### Issue: Memory not working

**Solution**: Check Redis is running:
```bash
docker compose ps redis
curl http://localhost:6379
```

## Related Documentation

- [Agent Intelligence](AGENT_INTELLIGENCE.md) - How agents use Gemma2-2B proactively
- [Collective Brain](COLLECTIVE_BRAIN.md) - Multi-agent consensus for complex questions
- [Melodic Line Memory](KUZU_MELODIC_LINE_PROPOSAL.md) - Coherent reasoning across agents

