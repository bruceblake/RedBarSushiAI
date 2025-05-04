#\!/bin/bash
# Script to connect Claude Code to the MCP server

# Set the MCP configuration
mkdir -p ~/.config/anthropic/claude-code

# Create a new configuration file
cat > ~/.config/anthropic/claude-code/config.json << 'CONFIG'
{
  "mcp": {
    "servers": {
      "python-mcp": {
        "type": "stdio",
        "command": "/home/proxyie/MySoftware/RedBarSushiAI/minimal_mcp.sh",
        "args": []
      }
    },
    "default_server": "python-mcp"
  }
}
CONFIG

# Print the configuration
echo "Claude Code MCP configuration set:"
cat ~/.config/anthropic/claude-code/config.json

# Run claude-code with the MCP configuration
echo "Running claude-code with MCP..."
echo "You can connect with: claude --mcp python-mcp"
