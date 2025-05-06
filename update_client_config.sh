#!/bin/bash

echo "===== Updating Claude Client Config to use HTTP transport ====="

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

# Update the config with HTTP transport type
if command -v jq &> /dev/null; then
    jq --arg name "redbarsushi-mcp" --arg url "http://127.0.0.1:4242/mcp" \
       '.mcpServers[$name] = {"url": $url, "type": "http"}' \
       "$CONFIG_FILE" > "${CONFIG_FILE}.tmp" && mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
    echo "✅ Updated Claude config with HTTP transport type"
else
    echo "⚠️ Warning: jq is not installed. Manual config update required."
    echo "Please ensure your config at $CONFIG_FILE contains:"
    echo '{"mcpServers":{"redbarsushi-mcp":{"url":"http://127.0.0.1:4242/mcp","type":"http"}}}'
fi

# Also check if there's a .claude.json in the home directory
HOME_CONFIG_FILE="$HOME/.claude.json"
if [ -f "$HOME_CONFIG_FILE" ]; then
    cp "$HOME_CONFIG_FILE" "${HOME_CONFIG_FILE}.bak"
    if command -v jq &> /dev/null; then
        jq --arg name "redbarsushi-mcp" --arg url "http://127.0.0.1:4242/mcp" \
           '.mcpServers[$name] = {"url": $url, "type": "http"}' \
           "$HOME_CONFIG_FILE" > "${HOME_CONFIG_FILE}.tmp" && mv "${HOME_CONFIG_FILE}.tmp" "$HOME_CONFIG_FILE"
        echo "✅ Updated home directory Claude config with HTTP transport type"
    fi
fi

echo -e "\n===== CONFIG UPDATE COMPLETE ====="
echo "Claude's configuration has been updated to use HTTP transport instead of SSE."
echo ""
echo "Please restart Claude Desktop to apply the changes."
echo "=========================="