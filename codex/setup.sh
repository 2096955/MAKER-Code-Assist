#!/bin/bash
# Setup Codex CLI to use MAKER multi-agent system

set -e

echo "Setting up Codex CLI for MAKER..."

# Install Codex CLI via npm
if ! command -v codex &> /dev/null; then
    echo "Installing Codex CLI..."
    npm install -g @openai/codex
fi

# Create config directory
mkdir -p ~/.codex

# Copy config (backup existing if present)
if [ -f ~/.codex/config.toml ]; then
    cp ~/.codex/config.toml ~/.codex/config.toml.backup
    echo "Backed up existing config to ~/.codex/config.toml.backup"
fi

cp "$(dirname "$0")/config.toml" ~/.codex/config.toml

# Set dummy API key (required by Codex but not used by local system)
export MAKER_API_KEY="local"

echo ""
echo "Setup complete!"
echo ""
echo "Usage:"
echo "  1. Start MAKER system: docker compose up -d && bash scripts/start-llama-servers.sh"
echo "  2. Run Codex: MAKER_API_KEY=local codex"
echo ""
echo "Or add to your shell profile:"
echo "  export MAKER_API_KEY=local"
