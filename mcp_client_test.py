#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Basic MCP client for RedBarSushiAI
Testing connectivity with MCP server
"""

import asyncio
import sys
from typing import Optional
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv
import os

load_dotenv()  # load environment variables from .env

class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        
    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server
        Args:
            server_script_path: Path to the server script (.py)
        """
        if not server_script_path.endswith('.py'):
            raise ValueError("Server script must be a .py file")
        
        command = "python"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        await self.session.initialize()
        
        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])
        return tools
        
    async def cleanup(self):
        """Cleanup and close connections"""
        if self.session:
            await self.exit_stack.aclose()
            print("Connection closed")

async def main():
    if len(sys.argv) < 2:
        print("Usage: python mcp_client_test.py <server_script_path>")
        return
        
    server_script_path = sys.argv[1]
    client = MCPClient()
    
    try:
        tools = await client.connect_to_server(server_script_path)
        print(f"Successfully connected to MCP server at {server_script_path}")
        print(f"Server offers {len(tools)} tools")
        
        # Keep the connection open for a moment to see the output
        await asyncio.sleep(2)
    except Exception as e:
        print(f"Error connecting to MCP server: {e}")
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
