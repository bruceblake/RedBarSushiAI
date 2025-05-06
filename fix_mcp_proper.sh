#!/bin/bash
# Script to properly configure Claude CLI for RedBarSushiAI MCP server

# Set variables
MCP_SERVER_NAME="redbarsushi-mcp"
MCP_SERVER_URL="http://127.0.0.1:4243/mcp"
MCP_SERVER_TYPE="sse"
CONFIG_FILE="$HOME/.claude.json"

# Create minimal configuration if it doesn't exist
if [ ! -f "$CONFIG_FILE" ]; then
  echo "Creating new Claude configuration file..."
  echo '{"mcpServers":{}}' > "$CONFIG_FILE"
fi

# Use jq to update only the mcpServers section
jq --arg name "$MCP_SERVER_NAME" --arg url "$MCP_SERVER_URL" --arg type "$MCP_SERVER_TYPE" '.mcpServers[$name] = {"url": $url, "type": $type}' "$CONFIG_FILE" > "$CONFIG_FILE.tmp" && mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"

echo "Claude CLI configuration updated successfully"
echo "Configuration at $CONFIG_FILE now contains:"
cat "$CONFIG_FILE"

echo "Run the following script to start the MCP server:"
echo "python /home/proxyie/MySoftware/RedBarSushiAI/mcp/simple_mcp_server.py"
echo "Then restart Claude CLI to connect to the MCP server"