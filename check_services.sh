#!/bin/bash
# Quick service status check

echo "=== Service Status ==="
echo ""

# Docker
if docker info > /dev/null 2>&1; then
  echo "✓ Docker is running"
  docker compose ps 2>/dev/null | grep -E "redis|mcp|orchestrator" || echo "  ⚠ Docker services not started"
else
  echo "✗ Docker is NOT running"
  echo "  → Start Docker Desktop: open -a Docker"
fi

echo ""

# llama.cpp servers
echo "llama.cpp Servers:"
for port in 8000 8001 8002 8003 8004; do
  if curl -s http://localhost:$port/health > /dev/null 2>&1; then
    echo "  ✓ Port $port - RUNNING"
  else
    echo "  ✗ Port $port - NOT RUNNING"
  fi
done

echo ""

# Redis
if redis-cli ping > /dev/null 2>&1; then
  echo "✓ Redis - RUNNING"
else
  echo "✗ Redis - NOT RUNNING"
fi

# MCP Server
if curl -s http://localhost:9001/health > /dev/null 2>&1; then
  echo "✓ MCP Server - RUNNING"
else
  echo "✗ MCP Server - NOT RUNNING"
fi

# Orchestrator
if curl -s http://localhost:8080/health > /dev/null 2>&1; then
  echo "✓ Orchestrator API - RUNNING"
else
  echo "✗ Orchestrator API - NOT RUNNING"
fi

echo ""
echo "To start services:"
echo "  1. Start Docker: open -a Docker"
echo "  2. Start Docker services: docker compose up -d"
echo "  3. Start llama.cpp: bash scripts/start-llama-servers.sh"
