#!/bin/bash

echo "===== Starting Proper MCP Server ====="

# Kill any existing MCP server processes
pkill -f "python.*proper_sse_server.py" || true
echo "✅ Cleaned up any running MCP server processes"

# Set environment variables
export MCP_PORT=4242
echo "✅ Set MCP port to $MCP_PORT"

# Change to the MCP directory
cd /home/proxyie/MySoftware/RedBarSushiAI/mcp

# Make sure the script is executable
chmod +x proper_sse_server.py

# Start the server in the background
echo "Starting MCP server on port $MCP_PORT..."
nohup python proper_sse_server.py > proper_mcp.log 2>&1 &
SERVER_PID=$!

# Wait for server to start
sleep 2

# Check if the server started successfully
if ps -p $SERVER_PID > /dev/null; then
    echo "✅ MCP server started successfully with PID $SERVER_PID"
else
    echo "❌ Error: MCP server failed to start."
    echo "   Please check the log at mcp/proper_mcp.log"
    cat proper_mcp.log
    exit 1
fi

# Update config if needed
CONFIG_FILE="$HOME/.claude.json"
if grep -q "http://host.docker.internal:4000/mcp" "$CONFIG_FILE"; then
    echo "⚠️ Notice: Config has URL http://host.docker.internal:4000/mcp but server is running on port $MCP_PORT."
    echo "You may need to update the Claude config to http://127.0.0.1:$MCP_PORT/mcp or restart Claude."
fi

# Test the SSE endpoint
echo "Testing SSE endpoint - you should see an 'event: endpoint' message:"
curl -N -H "Accept: text/event-stream" "http://127.0.0.1:$MCP_PORT/mcp" --max-time 2

echo -e "\n\n===== MCP Server Setup Complete ====="
echo "MCP server is now running on port $MCP_PORT"
echo "The server should respond with proper SSE format messages"
echo "Make sure your Claude config has the correct URL for the server"
echo "Restart Claude Code to reconnect to the server"
echo ""
echo "To stop the server: pkill -f \"python.*proper_sse_server.py\""