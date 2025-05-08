#!/bin/bash
# Script to update Claude's MCP configuration for RedBarSushiAI

# Set up variables
PROJECT_PATH="/home/proxyie/MySoftware/RedBarSushiAI"
MCP_SERVER_PATH="${PROJECT_PATH}/mcp/src/redbarsushi_mcp.py"
CONFIG_FILE="$HOME/.claude.json"
MCP_NAME="redbarsushi-mcp"

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo "Error: jq is required but not installed."
    echo "Please install jq with your package manager, e.g.: sudo apt install jq"
    exit 1
fi

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Claude config file does not exist at $CONFIG_FILE"
    echo "Creating default config file..."
    mkdir -p $(dirname "$CONFIG_FILE")
    echo '{
      "projects": {}
    }' > "$CONFIG_FILE"
fi

# Create a temporary file
TMP_FILE=$(mktemp)

# Update the MCP server configuration
echo "Updating MCP server configuration for project: $PROJECT_PATH"

# First, ensure the project exists in the config
jq --arg path "$PROJECT_PATH" '.projects[$path] = (.projects[$path] // {})' "$CONFIG_FILE" > "$TMP_FILE"
mv "$TMP_FILE" "$CONFIG_FILE"

# Then, ensure the mcpServers section exists
jq --arg path "$PROJECT_PATH" '.projects[$path].mcpServers = (.projects[$path].mcpServers // {})' "$CONFIG_FILE" > "$TMP_FILE"
mv "$TMP_FILE" "$CONFIG_FILE"

# Finally, add or update the redbarsushi-mcp server
jq --arg path "$PROJECT_PATH" --arg mcp "$MCP_NAME" --arg server_path "$MCP_SERVER_PATH" '
.projects[$path].mcpServers[$mcp] = {
  "command": $server_path,
  "options": {
    "port": 4244,
    "transport": "sse",
    "host": "0.0.0.0",
    "environment": {
      "REDIS_HOST": "redis",
      "REDIS_PORT": 6379,
      "POSTGRES_HOST": "postgres",
      "POSTGRES_PORT": 5432,
      "POSTGRES_DB": "redbarsushi_staging_db",
      "POSTGRES_USER": "redbarsushi_staging_db_user",
      "POSTGRES_PASSWORD": "testing_password",
      "APP_URL": "http://app:8080",
      "ALLOW_MUTATIONS": true
    }
  }
}' "$CONFIG_FILE" > "$TMP_FILE"
mv "$TMP_FILE" "$CONFIG_FILE"

echo "MCP server configuration updated successfully"
echo "You can now use the MCP tools in Claude with the Docker environment"
echo "Example: /mcp echo message=\"Hello from Claude\""