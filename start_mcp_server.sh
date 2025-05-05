#!/bin/bash

# Script to start the MCP server manually
# This uses the virtual environment and the correct version of the MCP library

# Set up colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}====================================${NC}"
echo -e "${YELLOW}   STARTING MCP SERVER MANUALLY    ${NC}"
echo -e "${YELLOW}====================================${NC}"

# Get the absolute path to the current directory and server script
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
DOCKER_SERVER_PATH="${PROJECT_DIR}/mcp/docker_test_server.py"

echo -e "${YELLOW}Docker server path: ${DOCKER_SERVER_PATH}${NC}"

# Make sure the script is executable
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

# Activate the virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source "${VENV_DIR}/bin/activate"

# Install MCP SDK if it's not already installed
if ! pip show mcp &>/dev/null; then
    echo -e "${YELLOW}Installing MCP SDK...${NC}"
    pip install "mcp[cli]"
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to install MCP SDK.${NC}"
        deactivate
        exit 1
    fi
    echo -e "${GREEN}MCP SDK installed successfully.${NC}"
fi

# Kill any existing MCP server processes
echo -e "${YELLOW}Killing any existing MCP server processes...${NC}"
pkill -f "python.*docker_test_server.py" 2>/dev/null || true

# Start the MCP server in the foreground
echo -e "${YELLOW}Starting MCP server in foreground mode...${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop the server when done.${NC}"
echo -e "${GREEN}Run these commands in another terminal to test:${NC}"
echo -e "  claude /mcp               ${YELLOW}# Check MCP server status${NC}"
echo -e "  claude /mcp redbarsushi-test check_docker_status ${YELLOW}# Test a specific command${NC}"
echo -e "${YELLOW}====================================${NC}"

# Start the server
python "$DOCKER_SERVER_PATH"