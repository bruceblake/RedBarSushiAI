#!/bin/bash

echo "===== Fixing MCP Server (SSE-only mode with Cleaner Edits) ====="

# Kill any existing MCP server processes
pkill -f "python.*enhanced_mcp_server.py" || true
echo "✅ Cleaned up any running MCP server processes"

# Set environment variables for the MCP server
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
       '.mcpServers[$name] = {"url": $url, "type": "sse"}' \
       "$CONFIG_FILE" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
    echo "✅ Updated Claude config with SSE transport type"
else
    echo "⚠️ Warning: jq is not installed. Manual config update required."
    echo "Please ensure your config at $CONFIG_FILE contains:"
    echo '{"mcpServers":{"redbarsushi-mcp":{"url":"http://127.0.0.1:4242/mcp","type":"sse"}}}'
fi

# Also check if there's a .claude.json in the home directory
HOME_CONFIG_FILE="$HOME/.claude.json"
if [ -f "$HOME_CONFIG_FILE" ]; then
    cp "$HOME_CONFIG_FILE" "${HOME_CONFIG_FILE}.bak"
    if command -v jq &> /dev/null; then
        jq --arg name "redbarsushi-mcp" --arg url "http://127.0.0.1:$MCP_PORT/mcp" \
           '.mcpServers[$name] = {"url": $url, "type": "sse"}' \
           "$HOME_CONFIG_FILE" > "${HOME_CONFIG_FILE}.tmp" && mv "${HOME_CONFIG_FILE}.tmp" "$HOME_CONFIG_FILE"
        echo "✅ Updated home directory Claude config with SSE transport type"
    fi
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

# Create a clean version of the server file with modifications
cp enhanced_mcp_server.py enhanced_mcp_server.py.bak
echo "✅ Backed up original server file"

# Fix the server URLs and ports
sed -i 's|REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")|REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")|g' enhanced_mcp_server.py
sed -i 's|DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/redbarsushi")|DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/redbarsushi")|g' enhanced_mcp_server.py
sed -i "s|port = int(os.environ.get(\"MCP_PORT\", 4000))|port = int(os.environ.get(\"MCP_PORT\", $MCP_PORT))|g" enhanced_mcp_server.py

# Replace the SSE endpoint with a completely rewritten version (no sed errors)
cat > sse_endpoint.py.tmp << 'EOF'
@app.route('/mcp', methods=['GET'])
def mcp_sse_endpoint():
    """SSE endpoint for MCP to support both transport types."""
    def stream():
        yield 'data: {"type":"hello","message":"RedBarSushiAI MCP SSE Server"}\n\n'
        while True:
            time.sleep(10)  # Keep connection alive with more frequent pings
            yield 'data: {"type":"ping"}\n\n'
            
    return Response(stream(), 
                   mimetype='text/event-stream', 
                   headers={
                       "Cache-Control": "no-cache",
                       "Connection": "keep-alive",
                       "Access-Control-Allow-Origin": "*"
                   })
EOF

# Find the old SSE endpoint and replace it
LINE_NUM=$(grep -n "@app.route('/mcp', methods=\['GET'\])" enhanced_mcp_server.py | cut -d: -f1)
if [ -n "$LINE_NUM" ]; then
    # Find the start of the next function to determine where to stop
    NEXT_FUNC=$(tail -n +$((LINE_NUM+1)) enhanced_mcp_server.py | grep -n "@app" | head -1 | cut -d: -f1)
    if [ -n "$NEXT_FUNC" ]; then
        END_LINE=$((LINE_NUM + NEXT_FUNC - 1))
        # Remove old function
        sed -i "${LINE_NUM},${END_LINE}d" enhanced_mcp_server.py
        # Insert new function
        sed -i "${LINE_NUM}r sse_endpoint.py.tmp" enhanced_mcp_server.py
    else
        echo "⚠️ Warning: Couldn't find the end of the SSE endpoint function."
        echo "Manual editing may be required."
    fi
else
    echo "⚠️ Warning: Couldn't find the SSE endpoint in the server file."
    echo "Manual editing may be required."
fi

# Clean up the temporary file
rm sse_endpoint.py.tmp

# Start the MCP server in SSE mode
echo "Starting MCP server on port $MCP_PORT in SSE mode..."
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

# Test the server health endpoint
echo "Testing server health endpoint..."
curl -s "http://127.0.0.1:$MCP_PORT/health"

# Test the SSE endpoint briefly
echo -e "\n\nTesting SSE endpoint (press Ctrl+C to stop after a few seconds)..."
curl -N -H "Accept: text/event-stream" "http://127.0.0.1:$MCP_PORT/mcp" &
CURL_PID=$!
sleep 2  # Give it 2 seconds to receive some events
kill $CURL_PID 2>/dev/null

echo -e "\n\n===== FIX COMPLETE ====="
echo "The MCP server has been started in SSE mode."
echo "The Claude config has been updated to use the SSE transport type."
echo ""
echo "Please restart Claude Desktop to reconnect to the server."
echo ""
echo "If you still have issues, check the server logs with:"
echo "  tail -f $MCP_DIR/enhanced_mcp.log"
echo ""
echo "Verify connection with curl to SSE endpoint:"
echo "  curl -N -H \"Accept: text/event-stream\" \"http://127.0.0.1:$MCP_PORT/mcp\""
echo "=========================="