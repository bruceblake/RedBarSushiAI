#!/bin/bash

echo "===== Comprehensive MCP Fix for RedBarSushiAI ====="

# Kill any existing MCP server processes
pkill -f "python.*enhanced_mcp_server.py" || true
echo "✅ Cleaned up any running MCP server processes"

# Go to the MCP directory
cd /home/proxyie/MySoftware/RedBarSushiAI/mcp

# Set environment variables
export MCP_PORT=4242
export SKIP_STDIO=1
export CONTAINER_MODE=1

# Update the client configuration
CONFIG_DIR="$HOME/.local/share/Claude"
CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"
HOME_CONFIG_FILE="$HOME/.claude.json"

# Create backup of config files
mkdir -p "$CONFIG_DIR"
if [ -f "$CONFIG_FILE" ]; then
    cp "$CONFIG_FILE" "${CONFIG_FILE}.bak"
fi

if [ -f "$HOME_CONFIG_FILE" ]; then
    cp "$HOME_CONFIG_FILE" "${HOME_CONFIG_FILE}.bak"
fi

# Update the Claude config files to use SSE transport
if command -v jq &> /dev/null; then
    # Desktop config
    if [ -f "$CONFIG_FILE" ]; then
        jq --arg name "redbarsushi-mcp" --arg url "http://127.0.0.1:4242/mcp" \
           '.mcpServers[$name] = {"url": $url, "type": "sse"}' \
           "$CONFIG_FILE" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
        echo "✅ Updated Claude desktop config with SSE transport"
    else
        echo '{"mcpServers":{"redbarsushi-mcp":{"url":"http://127.0.0.1:4242/mcp","type":"sse"}}}' > "$CONFIG_FILE"
        echo "✅ Created new Claude desktop config file with SSE transport"
    fi

    # Home directory config
    if [ -f "$HOME_CONFIG_FILE" ]; then
        jq --arg name "redbarsushi-mcp" --arg url "http://127.0.0.1:4242/mcp" \
           '.mcpServers[$name] = {"url": $url, "type": "sse"}' \
           "$HOME_CONFIG_FILE" > "${HOME_CONFIG_FILE}.tmp" && mv "${HOME_CONFIG_FILE}.tmp" "$HOME_CONFIG_FILE"
        echo "✅ Updated home directory Claude config with SSE transport"

        # Also update the servers field if it exists
        if jq -e '.servers' "$HOME_CONFIG_FILE" > /dev/null 2>&1; then
            jq --arg name "redbarsushi-mcp" --arg url "http://127.0.0.1:4242/mcp" \
               '.servers[$name] = {"url": $url, "type": "sse"}' \
               "$HOME_CONFIG_FILE" > "${HOME_CONFIG_FILE}.tmp" && mv "${HOME_CONFIG_FILE}.tmp" "$HOME_CONFIG_FILE"
            echo "✅ Updated servers field in home directory config"
        fi
    else
        echo "⚠️ Home directory config file not found, skipping"
    fi
else
    echo "⚠️ Warning: jq is not installed. Manual config update required."
fi

# Start the MCP server in the background
echo "🚀 Starting MCP server on port $MCP_PORT..."
source venv/bin/activate
nohup python enhanced_mcp_server.py > enhanced_mcp.log 2>&1 &

# Wait for server to start
sleep 5

# Check if the server is responding to HTTP requests
echo "🔍 Checking server health..."
if curl -s --max-time 5 http://127.0.0.1:$MCP_PORT/health | grep -q "mcp"; then
    echo "✅ MCP server is running and responding to health checks"
else
    echo "❌ Error: MCP server is not responding to health checks. Check the log at mcp/enhanced_mcp.log"
    echo "Current log contents:"
    cat enhanced_mcp.log
    exit 1
fi

echo ""
echo "========= SETUP COMPLETE ========="
echo "Please restart Claude Code to apply the changes"
echo "You should now see redbarsushi-mcp as connected when running the 'mcp' command"
echo "===================================="