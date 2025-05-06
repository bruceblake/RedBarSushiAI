#!/bin/bash

echo "===== Fixing MCP Server (HTTP-only mode) ====="

# Kill any existing MCP server processes
pkill -f "python.*enhanced_mcp_server.py" || true
echo "✅ Cleaned up any running MCP server processes"

# Set environment variables for the MCP server - IMPORTANT: SKIP_STDIO=1
export MCP_PORT=4242
export SKIP_STDIO=1
export CONTAINER_MODE=1
echo "✅ Set MCP environment variables"

# Configure Claude's MCP settings
CONFIG_DIR="$HOME/.local/share/Claude"
CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"

# Create the config directory if it doesn't exist
mkdir -p "$CONFIG_DIR"

# Create or update the config file
if [ -f "$CONFIG_FILE" ]; then
    # Make a backup of the existing config
    cp "$CONFIG_FILE" "${CONFIG_FILE}.bak"
    echo "✅ Backed up existing config to ${CONFIG_FILE}.bak"
else
    # Create minimal config if it doesn't exist
    echo '{"mcpServers":{}}' > "$CONFIG_FILE"
    echo "✅ Created new Claude config file"
fi

# Update the config with the correct MCP server settings
# We'll use jq to modify the JSON
if command -v jq &> /dev/null; then
    jq --arg name "redbarsushi-mcp" --arg url "http://127.0.0.1:$MCP_PORT/mcp" \
       '.mcpServers[$name] = {"url": $url, "type": "http"}' \
       "$CONFIG_FILE" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
    echo "✅ Updated Claude config with HTTP transport type"
else
    echo "⚠️ Warning: jq is not installed. Manual config update required."
    echo "Please ensure your config at $CONFIG_FILE contains:"
    echo '{"mcpServers":{"redbarsushi-mcp":{"url":"http://127.0.0.1:4242/mcp","type":"http"}}}'
fi

# Make sure the MCP server directory exists
MCP_DIR="/home/proxyie/MySoftware/RedBarSushiAI/mcp"
if [ ! -d "$MCP_DIR" ]; then
    echo "❌ Error: MCP directory not found at $MCP_DIR"
    exit 1
fi

# Change to the MCP directory
cd "$MCP_DIR"

# Make sure we have the virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment for MCP server..."
    python -m venv venv
fi

# Activate the virtual environment
source venv/bin/activate

# Install required packages
pip install flask==2.0.1 werkzeug==2.0.1 redis==4.3.4 sqlalchemy==1.4.40 psycopg2-binary

# Make sure the enhanced_mcp_server.py exists
if [ ! -f "enhanced_mcp_server.py" ]; then
    echo "❌ Error: MCP server script not found at $MCP_DIR/enhanced_mcp_server.py"
    exit 1
fi

# Fix the server URLs and ports
sed -i 's|REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")|REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")|g' enhanced_mcp_server.py
sed -i 's|DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/redbarsushi")|DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/redbarsushi")|g' enhanced_mcp_server.py
sed -i "s|port = int(os.environ.get(\"MCP_PORT\", 4000))|port = int(os.environ.get(\"MCP_PORT\", $MCP_PORT))|g" enhanced_mcp_server.py

# Start the MCP server in HTTP-only mode
echo "Starting MCP server on port $MCP_PORT in HTTP-only mode..."
nohup python enhanced_mcp_server.py > enhanced_mcp.log 2>&1 &
SERVER_PID=$!

# Give the server time to start
sleep 5

# Check if the server started successfully
if ps -p $SERVER_PID > /dev/null; then
    echo "✅ MCP server started successfully with PID $SERVER_PID"
else
    echo "❌ Error: MCP server failed to start."
    echo "   Please check the log at $MCP_DIR/enhanced_mcp.log"
    tail -n 20 "$MCP_DIR/enhanced_mcp.log"
    exit 1
fi

# Test the server with curl
echo "Testing server health endpoint..."
curl -s "http://127.0.0.1:$MCP_PORT/health"

# Test the MCP endpoint
echo -e "\n\nTesting MCP endpoint with initialize request..."
TEST_REQUEST='{"jsonrpc":"2.0","id":"test-1","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test-client","version":"1.0.0"}}}'
curl -s -X POST "http://127.0.0.1:$MCP_PORT/mcp" \
     -H "Content-Type: application/json" \
     -d "$TEST_REQUEST"

echo -e "\n\n===== FIX COMPLETE ====="
echo "The MCP server has been started in HTTP-only mode."
echo "The Claude config has been updated to use the HTTP transport type."
echo "Please restart Claude Desktop to reconnect to the server."
echo "If you still have issues, check the server logs with:"
echo "  tail -f $MCP_DIR/enhanced_mcp.log"
echo "=========================="