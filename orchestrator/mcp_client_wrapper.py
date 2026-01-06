#!/usr/bin/env python3
"""
MCP Client Wrapper for EE World Model
Provides MCP interface that CodebaseWorldModel expects
"""

import httpx
import logging
from typing import List, Dict, Optional
import os

logger = logging.getLogger(__name__)


class MCPClientWrapper:
    """Wrapper to make MCP server accessible to EE World Model"""
    
    def __init__(self, mcp_url: str = None):
        self.mcp_url = mcp_url or os.getenv("MCP_CODEBASE_URL", "http://localhost:9001")
        self._cache = {}
    
    async def _query_mcp(self, tool: str, args: Dict) -> str:
        """Query MCP server"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.mcp_url}/api/mcp/tool",
                    json={"tool": tool, "args": args}
                )
                if response.status_code == 200:
                    result = response.json()
                    return result.get("result", "")
                return ""
        except (httpx.HTTPError, httpx.TimeoutException, ConnectionError) as e:
            logger.error(f"[MCP Wrapper] Error: {e}")
            return ""
    
    def analyze_codebase(self) -> Dict:
        """Get codebase structure (synchronous wrapper)"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(self._query_mcp("analyze_codebase", {}))
        
        # Parse result if it's JSON string
        if isinstance(result, str):
            try:
                import json
                return json.loads(result)
            except (json.JSONDecodeError, ValueError, TypeError):
                # Return as dict with key_files
                return {
                    "key_files": [],
                    "total_files": 0
                }
        return result if isinstance(result, dict) else {}
    
    def read_file(self, file_path: str) -> str:
        """Read file from codebase (synchronous wrapper)"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(self._query_mcp("read_file", {"path": file_path}))
        return result if isinstance(result, str) else ""
    
    def list_files(self, codebase_path: str) -> List[str]:
        """List all files in codebase"""
        analysis = self.analyze_codebase()
        files = []
        
        if isinstance(analysis, dict):
            # Extract file paths from analysis
            if "key_files" in analysis:
                files = [f.get("path", "") for f in analysis["key_files"] if isinstance(f, dict)]
            elif "files" in analysis:
                files = analysis["files"]
        
        return [f for f in files if f]  # Filter empty strings

