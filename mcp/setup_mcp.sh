#!/bin/bash

# Script to set up the MCP environment for testing refactored code
# This script installs the MCP Python SDK and dependencies

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

# Create Python virtual environment if it doesn't exist
if [ ! -d "mcp_venv" ]; then
    echo -e "${YELLOW}Creating Python virtual environment...${NC}"
    python3 -m venv mcp_venv
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: Failed to create virtual environment${NC}"
        exit 1
    fi
    echo -e "${GREEN}Created virtual environment at mcp_venv${NC}"
fi

# Activate the virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source mcp_venv/bin/activate

# Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to upgrade pip${NC}"
    exit 1
fi

# Install MCP SDK
echo -e "${YELLOW}Installing MCP SDK...${NC}"
pip install "mcp[cli]"
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to install MCP SDK${NC}"
    exit 1
fi

# Make the MCP server executable
echo -e "${YELLOW}Making MCP server executable...${NC}"
chmod +x mcp/refactor_test_server.py
if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to make MCP server executable${NC}"
    exit 1
fi

# Register the MCP server
echo -e "${YELLOW}Registering MCP server...${NC}"
# Get the absolute path to the server
SERVER_PATH=$(realpath mcp/refactor_test_server.py)

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
    "redbarsushi-test": {
      "command": "'$SERVER_PATH'",
      "args": []
    }
  }
}' > "$CONFIG_FILE"
    else
        # Update existing configuration
        if jq '.mcpServers["redbarsushi-test"]' "$CONFIG_FILE" | grep -q "null"; then
            # Server doesn't exist, add it
            jq --arg path "$SERVER_PATH" '.mcpServers["redbarsushi-test"] = {"command": $path, "args": []}' "$CONFIG_FILE" > "$CONFIG_FILE.tmp" && mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"
        else
            # Server exists, update it
            jq --arg path "$SERVER_PATH" '.mcpServers["redbarsushi-test"].command = $path' "$CONFIG_FILE" > "$CONFIG_FILE.tmp" && mv "$CONFIG_FILE.tmp" "$CONFIG_FILE"
        fi
    fi
else
    # Create new configuration file
    echo '{
  "mcpServers": {
    "redbarsushi-test": {
      "command": "'$SERVER_PATH'",
      "args": []
    }
  }
}' > "$CONFIG_FILE"
fi

echo -e "${GREEN}MCP server registered successfully!${NC}"
echo -e "${YELLOW}Configuration file: ${CONFIG_FILE}${NC}"

echo -e "${GREEN}Setup complete!${NC}"
echo -e "${YELLOW}To test your refactored code, you can now use the 'redbarsushi-test' MCP server in Claude.${NC}"
echo -e "${YELLOW}Example commands:${NC}"
echo -e "${YELLOW}  /mcp redbarsushi-test setup_test_env project_path=\"/home/proxyie/MySoftware/RedBarSushiAI\"${NC}"
echo -e "${YELLOW}  /mcp redbarsushi-test run_test project_path=\"/home/proxyie/MySoftware/RedBarSushiAI\" test_type=\"imports\"${NC}"
echo -e "${YELLOW}  /mcp redbarsushi-test run_test project_path=\"/home/proxyie/MySoftware/RedBarSushiAI\" test_type=\"all\"${NC}"