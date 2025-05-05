#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Debug script for MCP server.
"""

import os
import sys
import asyncio
import traceback
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='mcp_debug.log'
)

# Try to import MCP SDK
try:
    from mcp.server.fastmcp import FastMCP
    from mcp.server.stdio import stdio_server
    print("MCP SDK imported successfully")
except ImportError as e:
    print(f"Error importing MCP SDK: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Unexpected error importing MCP SDK: {e}")
    traceback.print_exc()
    sys.exit(1)

# Create a simple MCP server
mcp = FastMCP("Debug", version="1.0.0", description="Debug MCP server")

@mcp.tool(description="Echo a message back")
def echo(ctx, message: str) -> str:
    """
    Echo a message back.
    
    Args:
        message: Message to echo
    
    Returns:
        The same message
    """
    return f"Echo: {message}"

async def run_server():
    """Run the MCP server with detailed error handling."""
    try:
        print("Starting MCP server...")
        logging.info("Starting MCP server...")
        async with stdio_server() as (read_stream, write_stream):
            await mcp.run(read_stream, write_stream)
    except asyncio.CancelledError:
        print("Server was cancelled")
        logging.info("Server was cancelled")
    except Exception as e:
        error_msg = f"Error running server: {e}"
        print(error_msg)
        logging.error(error_msg)
        traceback.print_exc()
        logging.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    print("Starting debug MCP server...")
    asyncio.run(run_server())