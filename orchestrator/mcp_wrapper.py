#!/usr/bin/env python3
"""
MCP Wrapper: Exposes the multi-agent orchestrator as an MCP server.
"""

import json
import sys
import asyncio
import httpx
from typing import Dict, Any, List

from mcp.server.stdio import stdio_server
from mcp.server import Server
from mcp.types import Tool, TextContent


class MultiAgentMCPServer:
    def __init__(self, orchestrator_url: str = "http://localhost:8080"):
        self.orchestrator_url = orchestrator_url
        self.server = Server("multi-agent-orchestrator")
        self._setup_handlers()
    
    def _setup_handlers(self):
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            return [
                Tool(
                    name="code_task",
                    description="Submit a coding task to the multi-agent system (Preprocessor, Planner, Coder, Reviewer)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "task": {
                                "type": "string",
                                "description": "The coding task to perform"
                            }
                        },
                        "required": ["task"]
                    }
                ),
                Tool(
                    name="read_file",
                    description="Read a file from the codebase",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path relative to codebase root"}
                        },
                        "required": ["path"]
                    }
                ),
                Tool(
                    name="analyze_codebase",
                    description="Get codebase structure overview",
                    inputSchema={"type": "object", "properties": {}}
                ),
                Tool(
                    name="find_references",
                    description="Find all references to a symbol",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string", "description": "Symbol name to search for"}
                        },
                        "required": ["symbol"]
                    }
                ),
                Tool(
                    name="search_docs",
                    description="Search documentation files",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"}
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="git_diff",
                    description="Get recent git changes",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file": {"type": "string", "description": "Optional specific file"}
                        }
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            try:
                if name == "code_task":
                    return await self._code_task(arguments)
                else:
                    return await self._mcp_tool(name, arguments)
            except Exception as e:
                print(f"Error in tool {name}: {e}", file=sys.stderr)
                return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def _code_task(self, arguments: Dict[str, Any]) -> List[TextContent]:
        task = arguments.get("task", "")
        if not task:
            return [TextContent(type="text", text="Error: No task provided")]
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                response = await client.post(
                    f"{self.orchestrator_url}/v1/chat/completions",
                    json={
                        "model": "multi-agent",
                        "messages": [{"role": "user", "content": task}],
                        "stream": False
                    }
                )
                
                if response.status_code != 200:
                    return [TextContent(type="text", text=f"Error: Orchestrator returned {response.status_code}")]
                
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "No response")
                return [TextContent(type="text", text=content)]
                
            except httpx.ConnectError:
                return [TextContent(type="text", text="Error: Cannot connect to orchestrator. Run: docker compose up -d")]
            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def _mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        mcp_url = self.orchestrator_url.replace(":8080", ":9001")
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{mcp_url}/api/mcp/tool",
                    json={"tool": tool_name, "args": arguments}
                )
                
                if response.status_code != 200:
                    return [TextContent(type="text", text=f"Error: MCP server returned {response.status_code}")]
                
                result = response.json()
                content = result.get("result", "No result")
                if isinstance(content, dict):
                    content = json.dumps(content, indent=2)
                return [TextContent(type="text", text=str(content))]
                
            except httpx.ConnectError:
                return [TextContent(type="text", text="Error: Cannot connect to MCP server. Run: docker compose up -d")]
            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    async def run(self):
        print("Multi-Agent MCP Server starting...", file=sys.stderr)
        init_options = self.server.create_initialization_options()
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, init_options)


async def main():
    server = MultiAgentMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
