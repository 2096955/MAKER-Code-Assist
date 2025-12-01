# Architecture Diagram Generation Prompt

## New Dual-Orchestrator MAKER Architecture

Create a comprehensive architecture diagram showing the dual-orchestrator MAKER system with High and Low modes running simultaneously.

### Overall Layout

The diagram should show two parallel pipelines (High and Low modes) sharing the same backend infrastructure, with clear visual separation between the two modes.

### Top Section: Client Layer

```
┌─────────────────────────────────────────────────────────────┐
│                    IDE Client (Continue.dev)                 │
│                                                               │
│  ┌──────────────────────┐      ┌──────────────────────┐     │
│  │  MakerCode - High    │      │  MakerCode - Low      │     │
│  │  (128GB RAM)         │      │  (40GB RAM)           │     │
│  └──────────┬───────────┘      └──────────┬───────────┘     │
└─────────────┼──────────────────────────────┼─────────────────┘
              │                              │
              │ OpenAI-compatible API        │ OpenAI-compatible API
              │ POST /v1/chat/completions    │ POST /v1/chat/completions
              │                              │
```

### Middle Section: Dual Orchestrators

```
      ┌──────────────────────────┐      ┌──────────────────────────┐
      │  Orchestrator High       │      │  Orchestrator Low        │
      │  (FastAPI, Port 8080)    │      │  (FastAPI, Port 8081)    │
      │  MAKER_MODE=high          │      │  MAKER_MODE=low          │
      └───────────┬───────────────┘      └───────────┬───────────────┘
                  │                                  │
                  │                                  │
```

### Core Pipeline: High Mode (Left Side)

Show the complete 6-step MAKER pipeline:

```
┌─────────────────────────────────────────────────────────────┐
│              MAKER REASONING PIPELINE (HIGH MODE)            │
│                                                               │
│  1. PREPROCESS (Gemma2-2B, Port 8000)                        │
│     Audio/Image → Text                                         │
│     └─→                                                       │
│                                                               │
│  2. PLAN (Nemotron 8B, Port 8001)                            │
│     Decomposes task + queries MCP for codebase                │
│     └─→                                                       │
│                                                               │
│  3. GENERATE (MAKER) (Devstral 24B, Port 8002)               │
│     Coder generates N candidates in parallel with varying temps│
│     └─→                                                       │
│                                                               │
│  4. VOTE (MAKER) (Qwen2.5-1.5B, Port 8004)                   │
│     First-to-K voting selects best candidate                  │
│     └─→                                                       │
│                                                               │
│  5. REVIEW (Qwen3-Coder 32B, Port 8003) ⭐                   │
│     Validates code, runs tests, security check                │
│     └─→ [If rejected (max 3x)] ─┐                            │
│         [If approved]            │                            │
│                                 │                            │
│  6. OUTPUT                       │                            │
│     Stream back to IDE           │                            │
│                                  │                            │
│     ┌────────────────────────────┘                            │
│     │ Feedback loop to GENERATE                                │
│     └─────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────┘
```

### Core Pipeline: Low Mode (Right Side)

Show the same pipeline but with Planner Reflection instead of Reviewer:

```
┌─────────────────────────────────────────────────────────────┐
│              MAKER REASONING PIPELINE (LOW MODE)              │
│                                                               │
│  1. PREPROCESS (Gemma2-2B, Port 8000)                        │
│     Audio/Image → Text                                         │
│     └─→                                                       │
│                                                               │
│  2. PLAN (Nemotron 8B, Port 8001)                            │
│     Decomposes task + queries MCP for codebase                │
│     └─→                                                       │
│     (Plan stored for later reflection)                        │
│                                                               │
│  3. GENERATE (MAKER) (Devstral 24B, Port 8002)               │
│     Coder generates N candidates in parallel with varying temps│
│     └─→                                                       │
│                                                               │
│  4. VOTE (MAKER) (Qwen2.5-1.5B, Port 8004)                   │
│     First-to-K voting selects best candidate                  │
│     └─→                                                       │
│                                                               │
│  5. PLANNER REFLECTION (Nemotron 8B, Port 8001) ⭐           │
│     Planner validates: "Does code implement my plan?"        │
│     Uses same Planner model, no extra RAM needed              │
│     └─→ [If rejected (max 3x)] ─┐                            │
│         [If approved]            │                            │
│                                 │                            │
│  6. OUTPUT                       │                            │
│     Stream back to IDE           │                            │
│                                  │                            │
│     ┌────────────────────────────┘                            │
│     │ Feedback loop to GENERATE                                │
│     └─────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────┘
```

### Key Visual Differences

**High Mode (Left)**:
- Step 5: **REVIEW (Qwen3-Coder 32B, Port 8003)** - Dedicated Reviewer model
- Uses 6 models total
- ~128GB RAM requirement
- Highest quality validation

**Low Mode (Right)**:
- Step 5: **PLANNER REFLECTION (Nemotron 8B, Port 8001)** - Reuses Planner model
- Uses 5 models total (Reviewer skipped)
- ~40-50GB RAM requirement
- Good quality validation (validates against plan)

### Bottom Section: Shared Backend Infrastructure

Both orchestrators connect to the same backend:

```
                  │                                  │
                  │                                  │
      ┌───────────▼───────────────┐      ┌──────────▼───────────────┐
      │                           │      │                          │
      │   Shared Backend Services │      │   (Same services)        │
      │                           │      │                          │
      │  • llama.cpp Servers     │      │  • MCP Server (9001)     │
      │    (Native Metal)         │      │  • Redis (6379)          │
      │    - Preprocessor (8000) │      │  • Qdrant (6333)         │
      │    - Planner (8001)      │      │  • Phoenix (6006)        │
      │    - Coder (8002)        │      │                          │
      │    - Reviewer (8003)     │      │                          │
      │    - Voter (8004)        │      │                          │
      │    - GPT-OSS (8005)      │      │                          │
      │                           │      │                          │
      └───────────────────────────┘      └──────────────────────────┘
```

### Visual Styling Requirements

1. **Color Coding**:
   - High mode pipeline: Blue/Green tones (production quality)
   - Low mode pipeline: Orange/Yellow tones (development/testing)
   - Shared backend: Gray/Neutral
   - Client layer: Light blue

2. **Key Annotations**:
   - ⭐ Mark the validation step (Reviewer vs Planner Reflection)
   - Show RAM requirements clearly
   - Indicate which models are used in each mode
   - Show port numbers for all services

3. **Flow Indicators**:
   - Solid arrows for normal flow
   - Dashed arrows for feedback loops
   - Different line styles for shared vs dedicated connections

4. **Labels**:
   - Clear mode labels: "HIGH MODE" and "LOW MODE"
   - Port numbers: (8080) and (8081) for orchestrators
   - Model names and sizes clearly visible
   - RAM requirements: "~128GB" and "~40-50GB"

### Key Points to Emphasize

1. **Both modes run simultaneously** - not a switch, but parallel operation
2. **Same backend** - both orchestrators share llama.cpp servers, MCP, Redis, etc.
3. **Only difference**: Validation method (Reviewer vs Planner Reflection)
4. **RAM savings**: Low mode saves ~40GB by skipping Reviewer
5. **Instant switching**: User selects model in Continue, no restarts needed

### Comparison Callout Box

Include a side-by-side comparison:

```
┌─────────────────────────────────────────────────────────────┐
│                    MODE COMPARISON                           │
├──────────────────────────────┬──────────────────────────────┤
│         HIGH MODE            │         LOW MODE              │
├──────────────────────────────┼──────────────────────────────┤
│ Port: 8080                    │ Port: 8081                   │
│ RAM: ~128GB                   │ RAM: ~40-50GB                │
│ Models: 6                     │ Models: 5                    │
│ Validation: Reviewer (32B)    │ Validation: Planner (8B)     │
│ Quality: Highest              │ Quality: Good                 │
│ Speed: Slower                 │ Speed: Faster                 │
│ Best for: Production          │ Best for: Development         │
└──────────────────────────────┴──────────────────────────────┘
```

### Title and Metadata

**Title**: "MAKER Dual-Orchestrator Architecture: High & Low Modes"

**Subtitle**: "Parallel operation with instant mode switching via Continue model selection"

**Footer Note**: "Both orchestrators share the same backend infrastructure. Mode selection happens at the API endpoint level (port 8080 vs 8081)."

---

## Design Specifications

- **Format**: PNG or SVG, high resolution (at least 1920x1080)
- **Style**: Professional technical diagram, similar to the original
- **Font**: Clear, readable sans-serif (Arial, Helvetica, or similar)
- **Layout**: Landscape orientation
- **Colors**: Use a professional color palette (blues, greens, oranges, grays)
- **Icons**: Simple, clean icons for services (boxes, circles, arrows)

## Implementation Notes

The diagram should clearly show:
1. That Low mode is NOT just "High mode without Reviewer"
2. That Low mode uses Planner Reflection as an active validation step
3. That both modes can run simultaneously
4. That the backend is shared (not duplicated)
5. That switching is instant (no service restarts)

The visual should make it immediately clear that this is a dual-orchestrator system, not a single orchestrator with a toggle.

