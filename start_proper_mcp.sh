#!/bin/bash

echo "===== Starting Proper MCP Server ====="

# Kill any existing MCP server processes
pkill -f "python.*mcp.*server.py" || true
echo "✅ Cleaned up any running MCP server processes"

# Set environment variables
export MCP_PORT=4000
echo "✅ Set MCP port to $MCP_PORT"

# Change to the MCP directory
cd /home/proxyie/MySoftware/RedBarSushiAI/mcp

# Create a virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# Activate the virtual environment
source venv/bin/activate

# Install Flask
echo "Installing Flask..."
pip install flask==2.0.1 werkzeug==2.0.1

# Make sure the proper SSE server script is executable
chmod +x proper_sse_server.py

# Start the server in the background
echo "Starting MCP server on port $MCP_PORT..."
nohup python proper_sse_server.py > proper_mcp.log 2>&1 &
SERVER_PID=$!

# Wait for server to start
sleep 3

# Check if the server started successfully
if ps -p $SERVER_PID > /dev/null; then
    echo "✅ MCP server started successfully with PID $SERVER_PID"
else
    echo "❌ Error: MCP server failed to start."
    echo "   Please check the log at mcp/proper_mcp.log"
    cat proper_mcp.log
    exit 1
fi

# Test the SSE endpoint
echo "Testing SSE endpoint - press Ctrl+C after a few seconds to stop:"
curl -N -H "Accept: text/event-stream" "http://127.0.0.1:$MCP_PORT/mcp"

# Update the MCP server configuration in .claude.json
echo "Updating MCP server configuration..."
CONFIG_FILE="$HOME/.claude.json"

# Create a backup of the current config
cp "$CONFIG_FILE" "${CONFIG_FILE}.bak"
echo "✅ Created backup of Claude configuration at ${CONFIG_FILE}.bak"

# Update the MCP server configuration using jq
jq --arg url "http://host.docker.internal:$MCP_PORT/mcp" \
   '.mcpServers."redbarsushi-mcp".url = $url' \
   "$CONFIG_FILE" > "${CONFIG_FILE}.tmp"

# Check if jq command succeeded
if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to update MCP server configuration"
    exit 1
fi

# Replace the original file with the updated one
mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
echo "✅ Updated MCP server URL to http://host.docker.internal:$MCP_PORT/mcp in Claude configuration"

echo ""
echo "===== MCP Server Setup Complete ====="
echo "MCP server 'redbarsushi-mcp' is now running on port $MCP_PORT"
echo "The Claude config has been updated to use http://host.docker.internal:$MCP_PORT/mcp"
echo "Restart Claude Code to reconnect to the server"