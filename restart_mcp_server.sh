#!/bin/bash

echo "===== Restarting MCP Server on Port 4000 ====="

# Set port
export MCP_PORT=4000

# Kill any existing processes
echo "Killing any existing Python processes..."
pkill -9 -f "python" || true
sleep 2

# Change to the MCP directory
cd /home/proxyie/MySoftware/RedBarSushiAI/mcp

# Start the server
echo "Starting MCP server on port $MCP_PORT..."
python proper_sse_server.py > proper_mcp.log 2>&1 &
SERVER_PID=$!

# Wait for server to start
sleep 3

# Check if the server started
if ps -p $SERVER_PID > /dev/null; then
    echo "✅ MCP server started successfully with PID $SERVER_PID"
else
    echo "❌ Error: MCP server failed to start."
    echo "Showing logs:"
    cat proper_mcp.log
    exit 1
fi

# Update Claude's config
echo "Updating Claude configuration..."
jq '.mcpServers."redbarsushi-mcp".url = "http://host.docker.internal:4000/mcp"' ~/.claude.json > ~/.claude.json.tmp
mv ~/.claude.json.tmp ~/.claude.json
echo "✅ Configuration updated to use host.docker.internal:4000"

# Test the server
echo -e "\nTesting server connectivity..."
curl -N -H "Accept: text/event-stream" "http://127.0.0.1:4000/mcp" --max-time 1

echo -e "\n===== MCP Server Restart Complete ====="
echo "Restart Claude to connect to the updated server."