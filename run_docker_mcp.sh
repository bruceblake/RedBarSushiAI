#!/bin/bash
# Script to run the Docker MCP server

# Kill any existing MCP server processes
pkill -f "python.*mcp/.*server.py" || true

# Start the Docker MCP server
cd /home/proxyie/MySoftware/RedBarSushiAI
python3 mcp/docker_test_server.py