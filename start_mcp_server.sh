#!/bin/bash
# Start the MCP server and leave it running
cd /home/proxyie/MySoftware/RedBarSushiAI
nohup ./minimal_mcp.sh > mcp_server.log 2>&1 &
echo "MCP server started with PID \0"
echo "Check mcp_server.log for output"
