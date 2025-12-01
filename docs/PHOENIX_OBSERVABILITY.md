# Phoenix Observability & Evaluation Dashboard

Arize Phoenix provides comprehensive observability and evaluation capabilities for the MAKER multi-agent system. All agent interactions, workflow steps, and performance metrics are automatically traced and sent to Phoenix.

## Quick Access

**Phoenix UI**: http://localhost:6006

Simply open this URL in your browser to access the observability dashboard.

## What Phoenix Provides

### 1. Traces - Complete Workflow Visibility

Every request through Continue (or the API) creates a trace showing the full MAKER pipeline:

**High Mode Trace (Port 8080)**:
```
Preprocessor (Gemma2-2B) 
  └─→ Planner (Nemotron 8B) 
      └─→ Coder (Devstral 24B) - 5 parallel candidates
          └─→ Voter (Qwen2.5-1.5B) - First-to-K voting
              └─→ Reviewer (Qwen3-Coder 32B) - Validation
                  └─→ Output (if approved)
                      └─→ [Loop back to Coder if rejected, max 3x]
```

**Low Mode Trace (Port 8081)**:
```
Preprocessor (Gemma2-2B) 
  └─→ Planner (Nemotron 8B) 
      └─→ Coder (Devstral 24B) - 5 parallel candidates
          └─→ Voter (Qwen2.5-1.5B) - First-to-K voting
              └─→ Planner Reflection (Nemotron 8B) - Validation
                  └─→ Output (if approved)
                      └─→ [Loop back to Coder if rejected, max 3x]
```

### 2. Spans - Detailed Operation Breakdown

Each trace contains multiple spans showing:

- **Agent Calls**: Individual LLM requests with:
  - Input prompts
  - Output responses
  - Token counts
  - Latency (ms)
  - Temperature settings

- **MAKER Voting Process**:
  - Number of candidates generated
  - Vote distribution (A, B, C, D, E)
  - Winner selection
  - Voting latency

- **Validation Steps**:
  - **High Mode**: Reviewer validation with test results
  - **Low Mode**: Planner reflection with plan compliance check

- **MCP Queries**: Codebase access operations
  - `read_file` calls
  - `analyze_codebase` queries
  - `run_tests` executions

### 3. Evaluations - Quality Metrics

Phoenix tracks:

- **Success/Failure Rates**: Percentage of tasks that complete successfully
- **Response Times**: Average latency per agent and overall workflow
- **Error Tracking**: Exceptions and failures with stack traces
- **Token Usage**: Total tokens consumed per request
- **Iteration Counts**: How many times code was refined before approval

### 4. Projects - Organized Sessions

Traces are organized by project/session, making it easy to:
- Track progress across long-running tasks
- Compare High vs Low mode performance
- Analyze patterns in successful vs failed tasks

## Accessing Phoenix

### Step 1: Verify Phoenix is Running

```bash
curl -s http://localhost:6006/health
```

You should see HTML response (Phoenix UI). If you get a connection error, start Phoenix:

```bash
docker compose up -d phoenix
```

### Step 2: Open Phoenix UI

Open your browser and navigate to:

**🌐 http://localhost:6006**

### Step 3: View Traces

1. **Click "Projects"** tab (if available)
2. **Select your project** or view all traces
3. **Click on a trace** to see the full workflow

## What You'll See in Phoenix

### Main Dashboard

- **Trace List**: All requests through the orchestrator
- **Timeline View**: Visual representation of workflow execution
- **Performance Metrics**: Latency, token usage, success rates

### Trace Details

When you click on a trace, you'll see:

**Top Level**:
- Request ID
- Timestamp
- Total duration
- Status (success/failure)
- Mode indicator (High/Low)

**Nested Spans**:
- **preprocess**: Input preprocessing step
- **plan**: Task decomposition with MCP queries
- **maker.generate_candidates**: Parallel candidate generation
  - Shows all 5 candidates with temperatures
- **maker.vote**: Voting process
  - Vote distribution
  - Winner selection
- **review** (High mode) or **planner_reflection** (Low mode):
  - Validation results
  - Feedback provided
  - Approval/rejection decision
- **mcp.query**: Codebase access operations

### High Mode vs Low Mode Traces

**High Mode Traces** will show:
- ✅ Reviewer validation step (Qwen3-Coder 32B)
- ✅ Detailed security and quality checks
- ✅ Test execution results
- ⏱️ Longer execution times
- 📊 Higher token usage

**Low Mode Traces** will show:
- ✅ Planner reflection validation (Nemotron 8B)
- ✅ Plan compliance checking
- ✅ Faster execution times
- 📊 Lower token usage
- ⚡ No Reviewer step (saves ~40GB RAM)

## Configuration

Phoenix is automatically configured in both orchestrators:

**Environment Variables**:
```yaml
# In docker-compose.yml
environment:
  - PHOENIX_ENDPOINT=http://phoenix:6006/v1/traces
```

**Both orchestrators send traces**:
- `orchestrator-high` (port 8080) → Phoenix
- `orchestrator-low` (port 8081) → Phoenix

All telemetry data (OpenTelemetry traces) are automatically sent to Phoenix when:
- A request comes through the API
- An agent is called
- MAKER voting occurs
- Validation happens

## Using Phoenix for Evaluation

### Comparing High vs Low Mode

1. **Make requests in both modes**:
   - Use "MakerCode - High" in Continue (port 8080)
   - Use "MakerCode - Low" in Continue (port 8081)

2. **Filter traces by mode**:
   - Look for traces with different validation spans
   - Compare execution times
   - Compare success rates

3. **Analyze quality differences**:
   - Review validation feedback
   - Check iteration counts
   - Compare error rates

### Performance Analysis

**View Metrics**:
- Average response time per mode
- Token usage comparison
- Success rate by mode
- Error frequency

**Identify Bottlenecks**:
- Which agent takes longest?
- Is MAKER voting efficient?
- Are MCP queries slow?

### Quality Evaluation

**Track Success Metrics**:
- First-pass approval rate
- Average iterations needed
- Validation feedback quality
- Code quality scores (if implemented)

## Troubleshooting

### No Traces Appearing

**Problem**: Phoenix UI shows no traces

**Solutions**:
1. **Make a request first**: Traces only appear after you use the system
   - Send a request through Continue
   - Or use the API: `curl -X POST http://localhost:8080/v1/chat/completions ...`

2. **Check orchestrator logs**:
   ```bash
   docker compose logs orchestrator-high | grep Phoenix
   docker compose logs orchestrator-low | grep Phoenix
   ```
   Should show: `[Phoenix] Observability enabled, sending traces to http://phoenix:6006/v1/traces`

3. **Verify Phoenix is running**:
   ```bash
   docker compose ps phoenix
   curl http://localhost:6006/health
   ```

4. **Check OpenTelemetry dependencies**:
   ```bash
   docker compose exec orchestrator-high pip list | grep opentelemetry
   ```
   Should show: `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`

### Traces Not Complete

**Problem**: Traces are missing some spans

**Solutions**:
- Check if agents are actually being called (verify llama.cpp servers are running)
- Look for errors in orchestrator logs
- Verify all services are healthy: `./check_services.sh`

### Phoenix UI Not Loading

**Problem**: Browser shows connection error

**Solutions**:
1. **Check Phoenix container**:
   ```bash
   docker compose ps phoenix
   docker compose logs phoenix --tail 50
   ```

2. **Restart Phoenix**:
   ```bash
   docker compose restart phoenix
   sleep 5
   curl http://localhost:6006/health
   ```

3. **Check port conflicts**:
   ```bash
   lsof -i :6006
   ```

## Advanced Usage

### Filtering Traces

In Phoenix UI, you can filter by:
- **Service name**: `maker-orchestrator`
- **Mode**: Look for traces with `reviewer` vs `planner_reflection` spans
- **Status**: Success vs failure
- **Time range**: Last hour, day, week

### Exporting Data

Phoenix allows you to:
- Export trace data for analysis
- Generate reports
- Share traces with team members

### Custom Evaluations

You can add custom evaluations in Phoenix:
- Code quality scores
- Security checks
- Performance benchmarks
- Custom metrics

## Integration with Other Tools

Phoenix traces can be exported to:
- **Prometheus**: For metrics collection
- **Grafana**: For custom dashboards
- **DataDog/New Relic**: For APM integration
- **Custom analytics**: Via Phoenix API

## Best Practices

1. **Regular Monitoring**: Check Phoenix daily to spot issues early
2. **Compare Modes**: Use Phoenix to validate that Low mode maintains quality
3. **Track Trends**: Monitor success rates over time
4. **Debug Failures**: Use trace details to understand why tasks fail
5. **Optimize Performance**: Identify slow agents and optimize

## Quick Reference

| Action | Command/URL |
|--------|-------------|
| Access Phoenix UI | http://localhost:6006 |
| Check Phoenix health | `curl http://localhost:6006/health` |
| View orchestrator logs | `docker compose logs orchestrator-high \| grep Phoenix` |
| Restart Phoenix | `docker compose restart phoenix` |
| View all traces | Open Phoenix UI → Traces tab |

## See Also

- [docs/quickstart-memory-observability.md](quickstart-memory-observability.md) - Quick start guide
- [orchestrator/observability.py](../orchestrator/observability.py) - Implementation details
- [Arize Phoenix Documentation](https://docs.arize.com/phoenix) - Official Phoenix docs

