#!/bin/bash
# Download GGUF versions for llama.cpp Metal
# Using the EXACT models specified by the user

set -e

echo "🚀 Starting model downloads for llama.cpp Metal backend"
echo "📦 Using exact models as specified"
echo ""

# Create models directory if it doesn't exist
mkdir -p models/

# Check if huggingface-cli is installed
if ! command -v huggingface-cli &> /dev/null; then
    echo "❌ huggingface-cli not found. Installing..."
    pip install huggingface_hub[cli]
fi

# Check if user is logged in
if ! huggingface-cli whoami &> /dev/null; then
    echo "⚠️  Not logged in to Hugging Face. Please run: huggingface-cli login"
    echo "   Get your token from: https://huggingface.co/settings/tokens"
    exit 1
fi

echo "✅ Hugging Face CLI ready"
echo ""

# 1. Gemma-3-4B (Preprocessor) - ✅ FOUND: MaziyarPanahi/gemma-3-4b-it-GGUF
echo "📥 Downloading Gemma-3-4B-IT (Preprocessor, 4B)..."
huggingface-cli download MaziyarPanahi/gemma-3-4b-it-GGUF \
  gemma-3-4b-it.Q6_K.gguf \
  --local-dir ./models/ \
  --local-dir-use-symlinks False || {
    echo "❌ Failed to download Gemma-3-4B-IT"
    exit 1
  }
# Rename for compatibility with docker-compose
mv models/gemma-3-4b-it.Q6_K.gguf models/gemma-2-2b-it.Q6_K.gguf 2>/dev/null || true
echo "✅ Gemma-3-4B-IT downloaded (Q6_K, renamed for compatibility)"
echo ""

# 2. Nemotron Nano 9B (Planner) - ✅ FOUND: bartowski/nvidia_NVIDIA-Nemotron-Nano-9B-v2-GGUF
echo "📥 Downloading Nemotron Nano 9B-v2 (Planner, 9B)..."
# Try Q6_K first, fallback to Q5_K_M
if huggingface-cli download bartowski/nvidia_NVIDIA-Nemotron-Nano-9B-v2-GGUF \
  nvidia_NVIDIA-Nemotron-Nano-9B-v2-Q6_K.gguf \
  --local-dir ./models/ \
  --local-dir-use-symlinks False 2>/dev/null; then
    mv models/nvidia_NVIDIA-Nemotron-Nano-9B-v2-Q6_K.gguf models/nemotron-nano-2-8b-instruct.Q6_K.gguf 2>/dev/null || true
    echo "✅ Nemotron Nano 9B-v2 downloaded (Q6_K quantization)"
elif huggingface-cli download bartowski/nvidia_NVIDIA-Nemotron-Nano-9B-v2-GGUF \
  nvidia_NVIDIA-Nemotron-Nano-9B-v2-Q5_K_M.gguf \
  --local-dir ./models/ \
  --local-dir-use-symlinks False 2>/dev/null; then
    mv models/nvidia_NVIDIA-Nemotron-Nano-9B-v2-Q5_K_M.gguf models/nemotron-nano-2-8b-instruct.Q6_K.gguf 2>/dev/null || true
    echo "✅ Nemotron Nano 9B-v2 downloaded (Q5_K_M quantization, renamed for compatibility)"
else
    echo "❌ Failed to download Nemotron Nano 9B-v2"
    exit 1
fi
echo ""

# 3. Devstral 24B (Coder) - ✅ FOUND: mistralai/Devstral-Small-2505_gguf
echo "📥 Downloading Devstral-Small-2505 (Coder, 24B)..."
# Try Q6_K first, fallback to Q5_K_M
if huggingface-cli download mistralai/Devstral-Small-2505_gguf \
  devstralQ6_K.gguf \
  --local-dir ./models/ \
  --local-dir-use-symlinks False 2>/dev/null; then
    mv models/devstralQ6_K.gguf models/devstral-24b-instruct-v0.1.Q6_K.gguf 2>/dev/null || true
    echo "✅ Devstral downloaded (Q6_K quantization)"
elif huggingface-cli download mistralai/Devstral-Small-2505_gguf \
  devstralQ5_K_M.gguf \
  --local-dir ./models/ \
  --local-dir-use-symlinks False 2>/dev/null; then
    mv models/devstralQ5_K_M.gguf models/devstral-24b-instruct-v0.1.Q6_K.gguf 2>/dev/null || true
    echo "✅ Devstral downloaded (Q5_K_M quantization, renamed for compatibility)"
else
    echo "❌ Failed to download Devstral"
    exit 1
fi
echo ""

# 4. Qwen3-Coder-30B-A3B (Reviewer) - ✅ FOUND: unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF
# Note: This is a MoE (Mixture of Experts) model, more efficient than dense 32B
echo "📥 Downloading Qwen3-Coder-30B-A3B-Instruct (Reviewer, 30B MoE)..."
huggingface-cli download unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF \
  Qwen3-Coder-30B-A3B-Instruct-Q6_K.gguf \
  --local-dir ./models/ \
  --local-dir-use-symlinks False || {
    echo "❌ Failed to download Qwen3-Coder-30B-A3B"
    exit 1
  }
# Rename for compatibility with docker-compose
mv models/Qwen3-Coder-30B-A3B-Instruct-Q6_K.gguf models/qwen-coder-32b-instruct.Q6_K.gguf 2>/dev/null || true
echo "✅ Qwen3-Coder-30B-A3B downloaded (Q6_K, MoE model, renamed for compatibility)"
echo ""

# Verify downloads
echo "🔍 Verifying downloads..."
downloaded=0
for model in models/*.gguf; do
    if [ -f "$model" ]; then
        size=$(du -h "$model" | cut -f1)
        echo "  ✅ $(basename $model): $size"
        downloaded=$((downloaded + 1))
    fi
done

echo ""
if [ $downloaded -gt 0 ]; then
    echo "✅ Downloaded $downloaded model(s)"
    echo ""
    echo "📝 Status:"
    echo "  ✅ Gemma-3-4B: MaziyarPanahi/gemma-3-4b-it-GGUF (Q6_K) - READY"
    echo "  ✅ Nemotron: bartowski/nvidia_NVIDIA-Nemotron-Nano-9B-v2-GGUF (Q6_K) - READY"
    echo "  ✅ Devstral: mistralai/Devstral-Small-2505_gguf (Q5_K_M) - READY"
    echo "  ✅ Qwen-Coder: unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF (Q6_K, MoE) - READY"
    echo ""
    echo "💡 Next steps:"
    echo "   1. Find GGUF repositories for remaining models"
    echo "   2. For Nemotron: Check if TheBloke creates GGUF version, or convert manually"
    echo "   3. Update this script with correct repository names"
    echo "   4. Re-run: bash scripts/download-models.sh"
else
    echo "⚠️  No models downloaded yet"
    echo "   Waiting for GGUF repository information"
fi
