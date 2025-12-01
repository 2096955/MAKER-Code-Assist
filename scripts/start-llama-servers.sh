#!/bin/bash
# Start llama.cpp servers natively on macOS (Metal acceleration)
# This is better than Docker for Apple Silicon

set -e

echo " Starting llama.cpp servers natively (Metal acceleration)"
echo ""

# Get MAKER_MODE from environment (default: high)
MAKER_MODE=${MAKER_MODE:-high}
echo "🎚️  MAKER_MODE: $MAKER_MODE"
if [ "$MAKER_MODE" = "low" ]; then
  echo "   Low mode: Skipping Reviewer (uses Planner reflection instead)"
  echo "   RAM requirement: ~40-50GB (vs 128GB in High mode)"
else
  echo "   High mode: All 6 models (Preprocessor, Planner, Coder, Reviewer, Voter, GPT-OSS)"
  echo "   RAM requirement: ~128GB"
fi
echo ""

# Check if llama.cpp is installed
if ! command -v llama-server &> /dev/null; then
    echo "  llama-server not found. Installing llama.cpp..."
    echo ""
    echo "Installing via Homebrew (recommended):"
    echo "  brew install llama.cpp"
    echo ""
    echo "Or build from source:"
    echo "  git clone https://github.com/ggerganov/llama.cpp.git"
    echo "  cd llama.cpp && make -j"
    echo ""
    read -p "Press Enter after installing llama.cpp, or Ctrl+C to cancel..."
fi

# Check models exist
for model in gemma-2-2b-it.Q6_K.gguf nemotron-nano-2-8b-instruct.Q6_K.gguf devstral-24b-instruct-v0.1.Q6_K.gguf qwen-coder-32b-instruct.Q6_K.gguf; do
    if [ ! -f "models/$model" ]; then
        echo " Model not found: models/$model"
        exit 1
    fi
done

echo " All models found"
echo ""

# Start servers in background
echo "Starting llama.cpp servers..."

# Preprocessor (port 8000)
llama-server \
  --model models/gemma-2-2b-it.Q6_K.gguf \
  --port 8000 \
  --host 0.0.0.0 \
  --n-gpu-layers 999 \
  --ctx-size 8192 \
  --parallel 2 \
  > logs/llama-preprocessor.log 2>&1 &
echo $! > /tmp/llama-preprocessor.pid
echo " Preprocessor started (PID: $(cat /tmp/llama-preprocessor.pid), port 8000)"

# Planner (port 8001)
llama-server \
  --model models/nemotron-nano-2-8b-instruct.Q6_K.gguf \
  --port 8001 \
  --host 0.0.0.0 \
  --n-gpu-layers 999 \
  --ctx-size 32768 \
  --parallel 4 \
  > logs/llama-planner.log 2>&1 &
echo $! > /tmp/llama-planner.pid
echo " Planner started (PID: $(cat /tmp/llama-planner.pid), port 8001)"

# Coder (port 8002)
llama-server \
  --model models/devstral-24b-instruct-v0.1.Q6_K.gguf \
  --port 8002 \
  --host 0.0.0.0 \
  --n-gpu-layers 999 \
  --ctx-size 32768 \
  --parallel 4 \
  > logs/llama-coder.log 2>&1 &
echo $! > /tmp/llama-coder.pid
echo " Coder started (PID: $(cat /tmp/llama-coder.pid), port 8002)"

# Reviewer (port 8003) - only in High mode
if [ "$MAKER_MODE" = "high" ]; then
  llama-server \
    --model models/qwen-coder-32b-instruct.Q6_K.gguf \
    --port 8003 \
    --host 0.0.0.0 \
    --n-gpu-layers 999 \
    --ctx-size 32768 \
    --parallel 4 \
    > logs/llama-reviewer.log 2>&1 &
  echo $! > /tmp/llama-reviewer.pid
  echo " Reviewer started (PID: $(cat /tmp/llama-reviewer.pid), port 8003)"
else
  echo " Reviewer skipped (Low mode uses Planner reflection)"
fi

# Voter (port 8004) - Qwen2.5-1.5B for MAKER voting
if [ -f "models/qwen2.5-1.5b-instruct-q6_k.gguf" ]; then
  llama-server \
    --model models/qwen2.5-1.5b-instruct-q6_k.gguf \
    --port 8004 \
    --host 0.0.0.0 \
    --n-gpu-layers 999 \
    --ctx-size 8192 \
    --parallel 8 \
    > logs/llama-voter.log 2>&1 &
  echo $! > /tmp/llama-voter.pid
  echo " Voter started (PID: $(cat /tmp/llama-voter.pid), port 8004)"
else
  echo "  Voter model not found (optional): models/qwen2.5-1.5b-instruct-q6_k.gguf"
fi

# GPT-OSS-20B (port 8005) - OpenAI open-weight model for Codex CLI
if [ -f "models/gpt-oss-20b.gguf" ]; then
  llama-server \
    --model models/gpt-oss-20b.gguf \
    --port 8005 \
    --host 0.0.0.0 \
    --n-gpu-layers 999 \
    --ctx-size 32768 \
    --parallel 4 \
    --jinja \
    > logs/llama-gpt-oss.log 2>&1 &
  echo $! > /tmp/llama-gpt-oss.pid
  echo " GPT-OSS-20B started (PID: $(cat /tmp/llama-gpt-oss.pid), port 8005)"
else
  echo "  GPT-OSS-20B model not found (optional): models/gpt-oss-20b.gguf"
fi

echo ""
echo " Waiting 30 seconds for servers to initialize..."
sleep 30

echo ""
echo " Server status:"
for port in 8000 8001 8002 8003 8004 8005; do
    if curl -s http://localhost:$port/health > /dev/null 2>&1; then
        echo "   Port $port: Healthy"
    else
        echo "   Port $port: Starting..."
    fi
done

echo ""
echo " All llama.cpp servers started!"
echo ""
echo "To stop servers: bash scripts/stop-llama-servers.sh"
echo "Logs: tail -f logs/llama-*.log"

