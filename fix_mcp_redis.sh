#!/bin/bash

# Kill any existing MCP server processes
pkill -f "python.*enhanced_mcp_server.py" || true
echo "Killed any running MCP server processes"

# Edit the enhanced_mcp_server.py file to fix the Redis URL
sed -i 's|REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")|REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")|g' /home/proxyie/MySoftware/RedBarSushiAI/mcp/enhanced_mcp_server.py
echo "Updated Redis URL in enhanced_mcp_server.py"

# Set environment variables for the MCP server
MCP_PORT=4242
SKIP_STDIO=1
export MCP_PORT SKIP_STDIO
echo "Set MCP port to $MCP_PORT"

# Change to MCP directory and restart the server
cd /home/proxyie/MySoftware/RedBarSushiAI/mcp
source venv/bin/activate

# Start the MCP server (detached from stdin/stdout)
echo "Starting MCP server on port $MCP_PORT..."
nohup python enhanced_mcp_server.py > enhanced_mcp.log 2>&1 &
sleep 2
echo "MCP server started with PID $!"
echo "You can check server status with: curl http://127.0.0.1:$MCP_PORT/health"