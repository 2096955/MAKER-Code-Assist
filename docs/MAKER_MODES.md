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
# Start High mode orchestrator (port 8080)
bash scripts/start-maker.sh high

# Or start both High and Low modes simultaneously
bash scripts/start-maker.sh all
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
# Start Low mode orchestrator (port 8081)
bash scripts/start-maker.sh low

# Or start both High and Low modes simultaneously
bash scripts/start-maker.sh all
```

**Note**: With the dual-orchestrator architecture, both modes can run simultaneously on different ports. No need to switch - just select the model you want in Continue!

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

**With the dual-orchestrator architecture, you don't need to switch modes!** Both High and Low orchestrators run simultaneously on different ports. Simply select the model you want in Continue:

- **MakerCode - High** → Port 8080 (Reviewer validation)
- **MakerCode - Low** → Port 8081 (Planner reflection)

### Starting Both Modes (Recommended)

```bash
# Start both High and Low orchestrators simultaneously
bash scripts/start-maker.sh all
```

This gives you instant switching - just select a different model in Continue, no restarts needed!

### Starting Only One Mode

If you only want one mode running:

```bash
# High mode only (port 8080)
bash scripts/start-maker.sh high

# Low mode only (port 8081)
bash scripts/start-maker.sh low
```

### Legacy Method (Single Orchestrator)

If you're using the old single-orchestrator setup, you can still switch modes:

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

**Note**: The dual-orchestrator setup (recommended) eliminates the need for mode switching entirely.

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

## Example: Using Both Modes

```bash
# 1. Start both High and Low orchestrators
bash scripts/start-maker.sh all

# Output shows:
# ✅ Orchestrator High (8080): Running
# ✅ Orchestrator Low (8081): Running
#
# 📊 Both modes available:
#    High Mode (port 8080): Reviewer validation, ~128GB RAM
#    Low Mode (port 8081): Planner reflection, ~40-50GB RAM

# 2. In Continue extension:
#    - Select "MakerCode - High" → Uses port 8080 (Reviewer)
#    - Select "MakerCode - Low" → Uses port 8081 (Planner reflection)
#    - Switch instantly, no restarts needed!
```

### Example: Using Only Low Mode

```bash
# Start only Low mode orchestrator
bash scripts/start-maker.sh low

# In Continue, select "MakerCode - Low (40GB RAM)"
# System uses Planner reflection for validation
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
