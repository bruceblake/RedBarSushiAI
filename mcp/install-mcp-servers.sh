#!/bin/bash

# Script to install and register both MCP servers (basic and Docker)
# This script calls both setup scripts to ensure all MCP servers are properly registered

# Set up colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}====================================${NC}"
echo -e "${YELLOW}   INSTALLING MCP SERVERS          ${NC}"
echo -e "${YELLOW}====================================${NC}"

# Get the current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${YELLOW}Project directory: ${PROJECT_DIR}${NC}"

# Create the Claude config directory if it doesn't exist
CONFIG_DIR="$HOME/.config/claude"
if [ ! -d "$CONFIG_DIR" ]; then
    echo -e "${YELLOW}Creating Claude config directory...${NC}"
    mkdir -p "$CONFIG_DIR"
fi

# Get the absolute paths to the server scripts
REFACTOR_SERVER_PATH=$(realpath "${PROJECT_DIR}/mcp/refactor_test_server.py")
DOCKER_SERVER_PATH=$(realpath "${PROJECT_DIR}/mcp/docker_test_server.py")

echo -e "${YELLOW}Refactor server path: ${REFACTOR_SERVER_PATH}${NC}"
echo -e "${YELLOW}Docker server path: ${DOCKER_SERVER_PATH}${NC}"

# Make the server scripts executable
chmod +x "$REFACTOR_SERVER_PATH"
chmod +x "$DOCKER_SERVER_PATH"

# Create or update the config file
CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"

echo -e "${YELLOW}Updating Claude configuration at ${CONFIG_FILE}${NC}"

# Create a new config file with both servers
echo '{
  "mcpServers": {
    "redbarsushi-test": {
      "command": "'$REFACTOR_SERVER_PATH'",
      "args": []
    },
    "redbarsushi-docker-test": {
      "command": "'$DOCKER_SERVER_PATH'",
      "args": []
    }
  }
}' > "$CONFIG_FILE"

echo -e "${GREEN}MCP servers registered successfully!${NC}"
echo -e "${YELLOW}Configuration file: ${CONFIG_FILE}${NC}"

echo -e "${GREEN}Installation complete!${NC}"
echo -e "${YELLOW}You can now use the following MCP servers in Claude:${NC}"
echo -e "${YELLOW}  - redbarsushi-test: Basic refactor test server${NC}"
echo -e "${YELLOW}  - redbarsushi-docker-test: Docker-based test server${NC}"

echo -e "${YELLOW}To use these servers, try the following commands in Claude:${NC}"
echo -e "${GREEN}Basic server commands:${NC}"
echo -e "  /mcp redbarsushi-test test_imports project_path=\"${PROJECT_DIR}\""
echo -e "  /mcp redbarsushi-test test_all project_path=\"${PROJECT_DIR}\""

echo -e "${GREEN}Docker server commands:${NC}"
echo -e "  /mcp redbarsushi-docker-test check_docker_status"
echo -e "  /mcp redbarsushi-docker-test run_docker_test project_path=\"${PROJECT_DIR}\" test_type=\"imports\""