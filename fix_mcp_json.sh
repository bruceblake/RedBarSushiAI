#!/bin/bash

# Script to fix MCP server configuration for RedBarSushiAI
echo "===== RedBarSushiAI MCP Server Setup ====="

# Kill any existing MCP server processes
pkill -f "python.*enhanced_mcp_server.py" || true
echo "✅ Cleaned up any running MCP server processes"

# Update MCP server URLs
cd /home/proxyie/MySoftware/RedBarSushiAI/mcp

# Set environment variables
MCP_PORT=4242
SKIP_STDIO=1
export MCP_PORT SKIP_STDIO

# Fix URLs in enhanced_mcp_server.py
sed -i 's|REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")|REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")|g' enhanced_mcp_server.py
sed -i 's|DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/redbarsushi")|DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/redbarsushi")|g' enhanced_mcp_server.py
echo "✅ Updated connection URLs in enhanced_mcp_server.py"

# Activate virtual environment
source venv/bin/activate

# Install required packages
pip install flask==2.0.1 werkzeug==2.0.1 redis==4.3.4 sqlalchemy==1.4.40 psycopg2-binary
echo "✅ Installed required Python packages"

# Update Claude configuration
CONFIG_FILE="$HOME/.claude.json"
MCP_NAME="redbarsushi-mcp"
MCP_URL="http://127.0.0.1:$MCP_PORT/mcp"

# Create a backup of the current config
cp "$CONFIG_FILE" "${CONFIG_FILE}.bak"
echo "✅ Created backup of Claude configuration at ${CONFIG_FILE}.bak"

# Update the MCP server configuration using jq - update both mcpServers and servers entries
jq --arg mcp_name "$MCP_NAME" \
   --arg mcp_url "$MCP_URL" \
   '.mcpServers[$mcp_name] = {"url": $mcp_url, "type": "sse"} | .servers[$mcp_name] = {"url": $mcp_url, "type": "sse"}' \
   "$CONFIG_FILE" > "${CONFIG_FILE}.tmp"

# Check if jq command succeeded
if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to update MCP server configuration"
    exit 1
fi

# Replace the original file with the updated one
mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
echo "✅ Updated MCP server '$MCP_NAME' with URL '$MCP_URL' in Claude configuration"

# Start the MCP server in the background
echo "🚀 Starting MCP server on port $MCP_PORT..."
nohup python enhanced_mcp_server.py > enhanced_mcp.log 2>&1 &
SERVER_PID=$!

# Wait for server to start
sleep 2

# Check if the server started successfully
if ps -p $SERVER_PID > /dev/null; then
    echo "✅ MCP server started successfully with PID $SERVER_PID"
else
    echo "❌ Error: MCP server failed to start. Check the log at mcp/enhanced_mcp.log"
    exit 1
fi

# Verify server health
echo "🔍 Checking server health..."
HEALTH_CHECK=$(curl -s http://127.0.0.1:$MCP_PORT/health)
echo "Server health: $HEALTH_CHECK"

echo ""
echo "========= SETUP COMPLETE ========="
echo "You can check server health with: curl http://127.0.0.1:$MCP_PORT/health"
echo "Restart Claude Code to apply the changes"
echo "===================================="
