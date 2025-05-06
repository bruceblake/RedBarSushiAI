#!/bin/bash

echo "===== Starting MCP Server on Alternative Port ====="

# Use a less common port
export MCP_PORT=9876

# Kill any existing Python MCP server processes
echo "Killing any existing MCP server processes..."
pkill -f "python.*sse_server" || true
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
jq '.mcpServers."redbarsushi-mcp".url = "http://127.0.0.1:'$MCP_PORT'/mcp"' ~/.claude.json > ~/.claude.json.tmp
mv ~/.claude.json.tmp ~/.claude.json
echo "✅ Configuration updated to use 127.0.0.1:$MCP_PORT"

# Test the server
echo -e "\nTesting server connectivity..."
curl -N -H "Accept: text/event-stream" "http://127.0.0.1:$MCP_PORT/mcp" --max-time 1

echo -e "\n===== MCP Server Setup Complete ====="
echo "Restart Claude to connect to the updated server."