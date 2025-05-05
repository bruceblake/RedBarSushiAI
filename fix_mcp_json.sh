#!/bin/bash

# Fix MCP server configuration in .claude.json
# This script updates the Claude configuration to point to the Docker test server

# Set up colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}====================================${NC}"
echo -e "${YELLOW}   FIXING MCP SERVER CONFIG        ${NC}"
echo -e "${YELLOW}====================================${NC}"

# Get the absolute path to the server script
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
DOCKER_SERVER_PATH=$(realpath "${PROJECT_DIR}/mcp/docker_test_server.py")

echo -e "${YELLOW}Docker server path: ${DOCKER_SERVER_PATH}${NC}"

# Make the server scripts executable
chmod +x "$DOCKER_SERVER_PATH"

# Create and set up a virtual environment if it doesn't exist
VENV_DIR="${PROJECT_DIR}/mcp/venv"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to create virtual environment.${NC}"
        exit 1
    fi
fi

# Activate the virtual environment and install MCP
echo -e "${YELLOW}Activating virtual environment and installing MCP SDK...${NC}"
source "${VENV_DIR}/bin/activate"
pip install "mcp[cli]"
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to install MCP SDK.${NC}"
    deactivate
    exit 1
else
    echo -e "${GREEN}MCP SDK installed successfully.${NC}"
fi

# Update .claude.json file to use the Python script directly
CONFIG_FILE="$HOME/.claude.json"

echo -e "${YELLOW}Updating Claude configuration at ${CONFIG_FILE}${NC}"

# Check if file exists and is valid JSON
if [ -f "$CONFIG_FILE" ] && jq empty "$CONFIG_FILE" 2>/dev/null; then
    echo -e "${YELLOW}Updating existing configuration file...${NC}"
    
    # Create a temporary file with the updated MCP servers
    TMP_FILE=$(mktemp)
    
    # Extract the project path from the config file
    PROJECT_PATH="/home/proxyie/MySoftware/RedBarSushiAI"
    
    # Update the MCP server configuration for redbarsushi-test to use the Python script directly
    jq --arg docker_path "$DOCKER_SERVER_PATH" --arg project_path "$PROJECT_PATH" '
    .projects[$project_path].mcpServers."redbarsushi-test".command = $docker_path
    ' "$CONFIG_FILE" > "$TMP_FILE"
    
    # Check if jq command succeeded
    if [ $? -eq 0 ]; then
        mv "$TMP_FILE" "$CONFIG_FILE"
        echo -e "${GREEN}MCP server configuration updated successfully!${NC}"
    else
        echo -e "${RED}Failed to update configuration file.${NC}"
        rm "$TMP_FILE"
        deactivate
        exit 1
    fi
else
    echo -e "${RED}Configuration file not found or not valid JSON.${NC}"
    deactivate
    exit 1
fi

# Kill any existing MCP server processes
echo -e "${YELLOW}Killing any existing MCP server processes...${NC}"
pkill -f "python.*docker_test_server.py" 2>/dev/null || true

# Start the MCP server with the virtual environment
echo -e "${YELLOW}Starting MCP server...${NC}"
nohup "${VENV_DIR}/bin/python" "$DOCKER_SERVER_PATH" > "${PROJECT_DIR}/mcp_server.log" 2>&1 &
SERVER_PID=$!
echo -e "${GREEN}MCP server started with PID ${SERVER_PID}${NC}"
echo -e "${YELLOW}Check the log file at ${PROJECT_DIR}/mcp_server.log for any errors${NC}"

# Deactivate the virtual environment
deactivate

echo -e "${GREEN}Fix complete!${NC}"
echo -e "${YELLOW}You can now use the MCP server with:${NC}"
echo -e "  /mcp redbarsushi-test setup_docker_env project_path=\"${PROJECT_DIR}\""
echo -e "  /mcp redbarsushi-test run_docker_test project_path=\"${PROJECT_DIR}\" test_type=\"imports\""
echo -e "  /mcp redbarsushi-test check_docker_status"
echo -e "${YELLOW}Restart Claude to apply the changes${NC}"