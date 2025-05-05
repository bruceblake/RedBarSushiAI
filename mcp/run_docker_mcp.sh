#!/bin/bash

# Script to run the Docker MCP testing server
# This script activates the virtual environment and runs the MCP server

# Set up colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}====================================${NC}"
echo -e "${YELLOW}   STARTING DOCKER MCP SERVER      ${NC}"
echo -e "${YELLOW}====================================${NC}"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed. Please install Docker before continuing.${NC}"
    echo -e "${YELLOW}Visit https://docs.docker.com/get-docker/ for installation instructions.${NC}"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed. Please install Docker Compose before continuing.${NC}"
    echo -e "${YELLOW}Visit https://docs.docker.com/compose/install/ for installation instructions.${NC}"
    exit 1
fi

# Kill any existing MCP server processes
pkill -f "python.*docker_test_server.py" 2>/dev/null || true
echo -e "${YELLOW}Killed any existing MCP server processes${NC}"

# Check if virtual environment exists
if [ ! -d "mcp/venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv mcp/venv
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: Failed to create virtual environment${NC}"
        exit 1
    fi
fi

# Activate the virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source mcp/venv/bin/activate

# Install MCP SDK if not already installed
if ! pip show mcp &>/dev/null; then
    echo -e "${YELLOW}Installing MCP SDK...${NC}"
    pip install "mcp[cli]"
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: Failed to install MCP SDK${NC}"
        exit 1
    fi
fi

# Make sure the server is executable
chmod +x mcp/docker_test_server.py

# Get the absolute path to the server
SERVER_PATH=$(realpath mcp/docker_test_server.py)

# Register the MCP server with Claude
echo -e "${YELLOW}Registering MCP Docker server...${NC}"

# Check if Claude config directory exists
CONFIG_DIR="$HOME/.config/claude"
if [ ! -d "$CONFIG_DIR" ]; then
    mkdir -p "$CONFIG_DIR"
fi

# Create or update MCP server configuration
CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"

if [ -f "$CONFIG_FILE" ]; then
    # Check if the file is valid JSON
    if ! jq empty "$CONFIG_FILE" 2>/dev/null; then
        echo -e "${YELLOW}Existing config file is not valid JSON, creating new one...${NC}"
        echo '{
  "mcpServers": {
    "redbarsushi-docker-test": {
      "command": "'$SERVER_PATH'",
      "args": []
    }
  }
}' > "$CONFIG_FILE"
    else
        # Update existing configuration
        if jq '.mcpServers["redbarsushi-docker-test"]' "$CONFIG_FILE" | grep -q "null"; then
            # Server doesn't exist, add it
            jq --arg path "$SERVER_PATH" '.mcpServers["redbarsushi-docker-test"] = {"command": $path, "args": []}' "$CONFIG_FILE" > "$CONFIG_FILE.tmp" && mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"
        else
            # Server exists, update it
            jq --arg path "$SERVER_PATH" '.mcpServers["redbarsushi-docker-test"].command = $path' "$CONFIG_FILE" > "$CONFIG_FILE.tmp" && mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"
        fi
    fi
else
    # Create new configuration file
    echo '{
  "mcpServers": {
    "redbarsushi-docker-test": {
      "command": "'$SERVER_PATH'",
      "args": []
    }
  }
}' > "$CONFIG_FILE"
fi

echo -e "${GREEN}MCP Docker server registered successfully!${NC}"

# Start the MCP server
echo -e "${YELLOW}Starting MCP Docker server...${NC}"
exec python mcp/docker_test_server.py