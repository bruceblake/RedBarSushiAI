#!/bin/bash
# start_redbarsushi_mcp.sh - Script to start the RedBarSushiAI MCP server for testing

# Set up variables
PROJECT_PATH="/home/proxyie/MySoftware/RedBarSushiAI"
MCP_SERVER_PATH="${PROJECT_PATH}/mcp/basic_mcp_server.py"
CONFIG_FILE="$HOME/.claude.json"
MCP_NAME="redbarsushi-test"

# Make sure simple_mcp_server.py is executable
chmod +x ${MCP_SERVER_PATH}

# Kill any existing MCP server processes
echo "Killing any existing MCP server processes..."
pkill -f "python.*mcp/simple_mcp_server.py" || true

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker."
    exit 1
fi

# Update the MCP server configuration in .claude.json
echo "Updating MCP server configuration..."
# Create a temporary file
TMP_FILE=$(mktemp)

# Update the MCP server configuration
jq --arg server_path "$MCP_SERVER_PATH" --arg project_path "$PROJECT_PATH" '.projects[$project_path].mcpServers."redbarsushi-test".command = $server_path' "$CONFIG_FILE" > "$TMP_FILE"

# Check if the jq command succeeded
if [ $? -ne 0 ]; then
    echo "Error: Failed to update MCP server configuration."
    rm "$TMP_FILE"
    exit 1
fi

# Move the temporary file to the original file
mv "$TMP_FILE" "$CONFIG_FILE"

# Start the MCP server
echo "Starting MCP server..."
nohup python3 ${MCP_SERVER_PATH} > ${PROJECT_PATH}/mcp_server.log 2>&1 &
PID=$!

# Wait a moment to see if the server stays up
sleep 2
if ps -p $PID > /dev/null; then
    echo "MCP server started successfully with PID $PID"
    echo "Log file is at ${PROJECT_PATH}/mcp_server.log"
else
    echo "Error: MCP server failed to start. Check the log file at ${PROJECT_PATH}/mcp_server.log"
    exit 1
fi

echo ""
echo "To test the MCP server, use Claude with commands like:"
echo "  /mcp check_docker_status"
echo "  /mcp setup_docker_env project_path=\"${PROJECT_PATH}\""
echo "  /mcp run_test test_type=\"basic\""
echo "  /mcp run_test test_type=\"menu\""
echo "  /mcp run_test test_type=\"order\""
echo "  /mcp run_test test_type=\"full_menu\""
echo "  /mcp run_test test_type=\"full_order\""
echo "  /mcp run_test test_type=\"all\""
echo ""
echo "To stop the MCP server:"
echo "  pkill -f \"python.*mcp/simple_mcp_server.py\""