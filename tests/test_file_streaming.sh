#!/bin/bash
# Test file-based output streaming

curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d @- <<'EOF'
{
  "model": "multi-agent",
  "messages": [{"role": "user", "content": "Hello, test file output streaming"}],
  "stream": true,
  "output_file": "outputs/test_streaming.md"
}
EOF
