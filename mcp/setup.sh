#!/bin/bash

# Script to set up the MCP environment for testing refactored code
# This sets up the necessary Python environment and registers the MCP server

# Set up colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}====================================${NC}"
echo -e "${YELLOW}   SETTING UP MCP TEST ENVIRONMENT  ${NC}"
echo -e "${YELLOW}====================================${NC}"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi

# Create a Python virtual environment for MCP
if [ ! -d "mcp/venv" ]; then
    echo -e "${YELLOW}Creating Python virtual environment...${NC}"
    python3 -m venv mcp/venv
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: Failed to create virtual environment${NC}"
        exit 1
    fi
fi

# Activate the virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source mcp/venv/bin/activate

# Install required packages
echo -e "${YELLOW}Installing required packages...${NC}"
pip install --upgrade pip
pip install mcp[cli]

# Make the server script executable
echo -e "${YELLOW}Making MCP server executable...${NC}"
chmod +x mcp/refactor_test_server.py

# Get the absolute path to the server script
SERVER_PATH=$(realpath mcp/refactor_test_server.py)

# Create or update the claude.json config file
echo -e "${YELLOW}Updating Claude configuration...${NC}"

# Check if the Claude config directory exists
CONFIG_DIR="$HOME/.config/claude"
if [ ! -d "$CONFIG_DIR" ]; then
    mkdir -p "$CONFIG_DIR"
fi

# Check if claude.json exists
CONFIG_FILE="$HOME/.claude.json"
if [ -f "$CONFIG_FILE" ]; then
    # Add our MCP server to the existing configuration
    echo -e "${YELLOW}Adding MCP server to existing configuration...${NC}"
    
    # Create a temporary file with the updated configuration
    jq --arg path "$SERVER_PATH" '.mcpServers = (.mcpServers // {}) | .mcpServers["redbarsushi-test"] = {"command": $path}' "$CONFIG_FILE" > "${CONFIG_FILE}.tmp"
    
    # Replace the original config file with the updated one
    mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
else
    # Create a new configuration file
    echo -e "${YELLOW}Creating new Claude configuration file...${NC}"
    
    echo '{
  "mcpServers": {
    "redbarsushi-test": {
      "command": "'"$SERVER_PATH"'"
    }
  }
}' > "$CONFIG_FILE"
fi

echo -e "${GREEN}MCP server registered successfully!${NC}"
echo -e "${YELLOW}Configuration file: ${CONFIG_FILE}${NC}"

echo -e "${GREEN}Setup complete!${NC}"
echo -e "${YELLOW}To test your refactored code, restart Claude and use the MCP server:${NC}"
echo -e "${YELLOW}  /mcp redbarsushi-test test_imports project_path=\"$(pwd)\"${NC}"
echo -e "${YELLOW}  /mcp redbarsushi-test test_flask project_path=\"$(pwd)\"${NC}"
echo -e "${YELLOW}  /mcp redbarsushi-test test_all project_path=\"$(pwd)\"${NC}"

# Deactivate the virtual environment
deactivate