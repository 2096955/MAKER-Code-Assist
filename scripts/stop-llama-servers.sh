#!/bin/bash
# Stop llama.cpp servers

echo "🛑 Stopping llama.cpp servers..."

for pidfile in /tmp/llama-preprocessor.pid /tmp/llama-planner.pid /tmp/llama-coder.pid /tmp/llama-reviewer.pid /tmp/llama-voter.pid /tmp/llama-gpt-oss.pid; do
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null
            echo " Stopped PID $pid"
        fi
        rm -f "$pidfile"
    fi
done

# Also kill any remaining llama-server processes
pkill -f "llama-server" 2>/dev/null && echo " Cleaned up remaining processes" || echo " All servers stopped"

