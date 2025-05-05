#!/usr/bin/env python3
"""
Standalone client for testing the RedBarSushiAI refactoring MCP server.
This client directly connects to the MCP server and executes tests.
"""

import os
import sys
import json
import argparse
import asyncio
from typing import Dict, List, Any, Optional

from mcp import ClientSession, StdioServerParameters, types

async def run_client(server_path: str, project_path: str, test_type: str = "all"):
    """
    Run the MCP client to test the refactored code.
    
    Args:
        server_path: Path to the MCP server script
        project_path: Path to the RedBarSushiAI project
        test_type: Type of test to run (imports, database, redis, flask, all)
    """
    # Create server parameters
    server_params = StdioServerParameters(
        command=server_path,
        args=[],
        env=None,
    )
    
    # Connect to the server
    from mcp.client.stdio import stdio_client
    
    print(f"🔄 Connecting to MCP server at: {server_path}")
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the session
                print("🔄 Initializing MCP session...")
                await session.initialize()
                
                # List available tools
                print("🔄 Listing available tools...")
                tools = await session.list_tools()
                print(f"📋 Available tools: {', '.join(tool.name for tool in tools)}")
                
                # First set up the test environment
                print(f"🔄 Setting up test environment for: {project_path}")
                setup_result = await session.call_tool(
                    "setup_test_env",
                    arguments={"project_path": project_path}
                )
                
                # Print setup results
                for content in setup_result.content:
                    print(f"📝 {content.text}")
                
                # Run the tests
                print(f"🔄 Running tests of type: {test_type}")
                test_result = await session.call_tool(
                    "run_test",
                    arguments={
                        "project_path": project_path,
                        "test_type": test_type
                    }
                )
                
                # Print test results
                for content in test_result.content:
                    print(f"📝 {content.text}")
                
                # Clean up
                print("🔄 Cleaning up test environment...")
                cleanup_result = await session.call_tool(
                    "cleanup_environment",
                    arguments={"project_path": project_path}
                )
                
                # Print cleanup results
                for content in cleanup_result.content:
                    print(f"📝 {content.text}")
                
                print("✅ Test run completed!")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

def main():
    """Parse command line arguments and run the client."""
    parser = argparse.ArgumentParser(description="Test RedBarSushiAI refactored code using MCP")
    parser.add_argument("--server", required=True, help="Path to the MCP server script")
    parser.add_argument("--project", required=True, help="Path to the RedBarSushiAI project")
    parser.add_argument("--test-type", default="all", choices=["imports", "database", "redis", "flask", "all"],
                       help="Type of test to run (imports, database, redis, flask, all)")
    
    args = parser.parse_args()
    
    # Check if paths exist
    if not os.path.exists(args.server):
        print(f"❌ Error: Server path does not exist: {args.server}")
        sys.exit(1)
    
    if not os.path.exists(args.project):
        print(f"❌ Error: Project path does not exist: {args.project}")
        sys.exit(1)
    
    # Run the client
    asyncio.run(run_client(args.server, args.project, args.test_type))

if __name__ == "__main__":
    main()