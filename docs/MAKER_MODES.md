# MAKER Modes: High vs Low

The MAKER system supports two operational modes to accommodate different hardware configurations:

## 🎚️ Mode Comparison

| Feature | High Mode | Low Mode |
|---------|-----------|----------|
| **RAM Requirement** | ~128GB | ~40-50GB |
| **Models Running** | 6 models | 5 models |
| **Validation** | Reviewer (Qwen 32B) | Planner Reflection (Nemotron 8B) |
| **Quality** | Highest | Good |
| **Speed** | Slower | Faster |
| **Best For** | Production, complex tasks | Development, testing, limited RAM |

## High Mode (Default)

**Recommended for**: Users with 128GB+ RAM who need maximum quality

### Models
- **Preprocessor** (Gemma2-2B): Input processing
- **Planner** (Nemotron Nano 8B): Task decomposition
- **Coder** (Devstral 24B): Code generation
- **Reviewer** (Qwen Coder 32B): Code validation & testing
- **Voter** (Qwen2.5-1.5B): MAKER voting
- **GPT-OSS-20B** (optional): Standalone Codex model

### Validation Process
1. Planner creates task plan
2. Coder generates 5 candidates in parallel
3. Voter selects best candidate (first-to-K voting)
4. **Reviewer validates**:
   - Runs tests
   - Checks security
   - Validates code quality
   - Provides detailed feedback
5. Iterates up to 3 times if needed

### Setup
```bash
# Use default High mode
export MAKER_MODE=high
bash scripts/start-llama-servers.sh
docker compose up -d
```

## Low Mode

**Recommended for**: Users with 40-64GB RAM, or for faster development/testing

### Models
- **Preprocessor** (Gemma2-2B): Input processing
- **Planner** (Nemotron Nano 8B): Task decomposition **+ reflection**
- **Coder** (Devstral 24B): Code generation
- ~~**Reviewer**~~ (skipped - uses Planner instead)
- **Voter** (Qwen2.5-1.5B): MAKER voting
- **GPT-OSS-20B** (optional): Standalone Codex model

### Validation Process
1. Planner creates task plan
2. Coder generates 5 candidates in parallel
3. Voter selects best candidate
4. **Planner reflects** (instead of Reviewer):
   - "Does this code implement my plan?"
   - Validates against original requirements
   - Checks for obvious bugs
   - Provides feedback for iteration
5. Iterates up to 3 times if needed

### Setup
```bash
# Enable Low mode
export MAKER_MODE=low
bash scripts/start-llama-servers.sh
docker compose up -d
```

Or set in `docker-compose.yml`:
```yaml
environment:
  - MAKER_MODE=low
```

## Why Planner Reflection Works

The Planner is the **perfect** validator in Low mode because:

1. **Already understands the task** - It created the plan, so it knows what's needed
2. **No extra RAM** - Reuses the 8B model that's already running
3. **Narrative awareness** - Uses EE Memory to maintain business logic coherence
4. **Faster** - 8B model vs 32B Reviewer
5. **Better than auto-approval** - Actual validation happens, just simpler

## Quality Comparison

### High Mode (Reviewer)
- ✅ Catches subtle bugs
- ✅ Security vulnerability detection
- ✅ Performance optimization suggestions
- ✅ Test coverage analysis
- ✅ Handles complex codebases

### Low Mode (Planner Reflection)
- ✅ Validates plan compliance
- ✅ Catches obvious bugs
- ✅ Maintains narrative coherence
- ✅ Checks for missing implementations
- ⚠️ May miss subtle security issues
- ⚠️ Less detailed feedback

## When to Use Each Mode

### Use High Mode When:
- Working on production code
- Security is critical
- Need maximum quality
- Have 128GB+ RAM available
- Complex multi-file refactoring

### Use Low Mode When:
- Developing/testing locally
- Prototyping
- Limited to 40-64GB RAM
- Speed is more important than perfection
- Simple tasks (single file edits, bug fixes)

## Switching Between Modes

### Method 1: Environment Variable
```bash
# High mode
export MAKER_MODE=high
bash scripts/stop-llama-servers.sh
bash scripts/start-llama-servers.sh
docker compose restart orchestrator

# Low mode
export MAKER_MODE=low
bash scripts/stop-llama-servers.sh
bash scripts/start-llama-servers.sh
docker compose restart orchestrator
```

### Method 2: docker-compose.yml
```yaml
# Edit docker-compose.yml
environment:
  - MAKER_MODE=low  # or high
```

Then:
```bash
docker compose down
bash scripts/stop-llama-servers.sh
export MAKER_MODE=low  # Match docker-compose.yml
bash scripts/start-llama-servers.sh
docker compose up -d
```

## RAM Breakdown

### High Mode (~128GB)
- Preprocessor (Gemma2-2B): ~4GB
- Planner (Nemotron 8B): ~10GB
- Coder (Devstral 24B): ~30GB
- **Reviewer (Qwen 32B): ~40GB** ⬅️ This is what we skip in Low mode
- Voter (Qwen2.5-1.5B): ~2GB
- GPT-OSS-20B (optional): ~25GB
- System overhead: ~10-15GB

### Low Mode (~40-50GB)
- Preprocessor (Gemma2-2B): ~4GB
- Planner (Nemotron 8B): ~10GB (dual use: planning + reflection)
- Coder (Devstral 24B): ~30GB
- Voter (Qwen2.5-1.5B): ~2GB
- GPT-OSS-20B (optional): ~25GB
- System overhead: ~10-15GB

**Savings: ~40GB** by skipping the Reviewer

## Performance Impact

Based on MAKER paper estimates:

| Metric | High Mode | Low Mode |
|--------|-----------|----------|
| SWE-bench Lite resolve rate | ~50% | ~45% |
| Average task time | Slower | ~20% faster |
| Iteration rate | Higher quality, more iterations | Faster iterations |
| False positives (approved bad code) | Very low | Low |

## Example: Using Low Mode

```bash
# 1. Set environment
export MAKER_MODE=low

# 2. Start only 5 models (no Reviewer)
bash scripts/start-llama-servers.sh

# Output shows:
# 🎚️  MAKER_MODE: low
#    Low mode: Skipping Reviewer (uses Planner reflection instead)
#    RAM requirement: ~40-50GB (vs 128GB in High mode)
#
#  Preprocessor started (PID: 12345, port 8000)
#  Planner started (PID: 12346, port 8001)
#  Coder started (PID: 12347, port 8002)
#  Reviewer skipped (Low mode uses Planner reflection)
#  Voter started (PID: 12348, port 8004)

# 3. Start orchestrator in Low mode
docker compose up -d

# 4. Use as normal
# The system will automatically use Planner reflection instead of Reviewer
```

## Troubleshooting

### "Reviewer not responding" in High mode
- Check if Reviewer server is running: `curl http://localhost:8003/health`
- Check RAM usage: `top` or Activity Monitor
- If out of RAM, switch to Low mode

### "Planner not available" in Low mode
- Check if Planner is running: `curl http://localhost:8001/health`
- Planner is required for both modes

### Quality issues in Low mode
- Consider switching to High mode for critical tasks
- Increase `MAKER_NUM_CANDIDATES` for better code quality
- Run manual code review after generation

## Best Practice

**Recommended workflow**:
1. **Development** - Use Low mode for speed
2. **Pre-commit** - Use High mode for final validation
3. **Production** - Use High mode always

This gives you fast iteration during development, but ensures production quality before deployment.
