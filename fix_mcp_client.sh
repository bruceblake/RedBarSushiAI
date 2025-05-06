#!/bin/bash

echo "===== MCP Client Configuration for RedBarSushiAI ====="

# Check if pip is installed
if ! command -v pip &> /dev/null; then
    echo "Error: pip is not installed. Please install pip first."
    exit 1
fi

# Install or update MCP client libraries
echo "Installing/updating MCP client libraries..."
pip install mcp anthropic python-dotenv

# Check for environment variables
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "Warning: ANTHROPIC_API_KEY environment variable not set."
    echo "Creating a .env file template..."
    
    # Create .env file if it doesn't exist
    if [ ! -f ".env" ]; then
        echo "ANTHROPIC_API_KEY=<your-api-key-here>" > .env
        echo "Created .env file. Please edit it to add your Anthropic API key."
    else
        echo ".env file already exists. Please ensure it contains your ANTHROPIC_API_KEY."
    fi
    
    # Add to .gitignore if not already there
    if [ -f ".gitignore" ] && ! grep -q "^.env$" .gitignore; then
        echo ".env" >> .gitignore
        echo "Added .env to .gitignore for security."
    fi
fi

# Create a simple MCP client for testing
echo "Creating an MCP client test script..."
cat > mcp_client_test.py << 'EOF'
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
EOF

chmod +x mcp_client_test.py

# Check for MCP server script
echo "Checking for MCP server script..."
if [ -f "/home/proxyie/MySoftware/RedBarSushiAI/mcp/enhanced_mcp_server.py" ]; then
    echo "Found MCP server at: /home/proxyie/MySoftware/RedBarSushiAI/mcp/enhanced_mcp_server.py"
    
    # Check if the server is currently running
    SERVER_PID=$(pgrep -f "python.*enhanced_mcp_server.py")
    if [ -n "$SERVER_PID" ]; then
        echo "MCP server is currently running with PID: $SERVER_PID"
    else
        echo "MCP server is not currently running."
        echo "To start the server, run: bash fix_mcp_json.sh"
    fi
else
    echo "MCP server script not found at the expected location."
    echo "Please check your installation."
fi

echo ""
echo "===== SETUP COMPLETE ====="
echo "To test the MCP client connection, run:"
echo "python mcp_client_test.py /home/proxyie/MySoftware/RedBarSushiAI/mcp/enhanced_mcp_server.py"
echo ""
echo "For more information on MCP, visit: https://modelcontextprotocol.io/"
echo "=========================="