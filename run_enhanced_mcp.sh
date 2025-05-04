#!/bin/bash
# Script to run the enhanced MCP server

# Exit on error
set -e

# Define colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $SCRIPT_DIR

# Check if Claude CLI is installed
if ! command -v claude &> /dev/null; then
    echo -e "${RED}Claude CLI is not installed. Please install it first.${NC}"
    exit 1
fi

# Kill any running MCP servers
echo -e "${BLUE}Stopping any existing MCP servers...${NC}"
pkill -f "python.*enhanced_mcp.py" || true
sleep 1

# Make sure script is executable
chmod +x enhanced_mcp.py

# Register with Claude
echo -e "${BLUE}Registering enhanced MCP server with Claude...${NC}"
claude mcp remove docker-test 2>/dev/null || true
claude mcp add docker-test "./enhanced_mcp.py"

echo -e "${GREEN}MCP server registered as 'docker-test'${NC}"
echo -e "Available tools:"
echo -e "  ${YELLOW}/mcp docker-test run_test test_type=\"basic\"${NC}       - Run basic tests on staging"
echo -e "  ${YELLOW}/mcp docker-test docker_start test_type=\"integration\"${NC} - Start integration test containers"
echo -e "  ${YELLOW}/mcp docker-test docker_start test_type=\"e2e\"${NC}      - Start E2E test containers"
echo -e "  ${YELLOW}/mcp docker-test docker_test test_file=\"all\"${NC}       - Run all integration tests"
echo -e "  ${YELLOW}/mcp docker-test docker_test test_file=\"test_specific_file.py\"${NC} - Run specific test"
echo -e "  ${YELLOW}/mcp docker-test docker_status${NC}                - Check Docker container status"
echo -e "  ${YELLOW}/mcp docker-test docker_stop test_type=\"all\"${NC}       - Stop all containers"
echo -e ""

# Run in the background
echo -e "${BLUE}Starting MCP server in the background...${NC}"
nohup python enhanced_mcp.py > /dev/null 2>&1 &

# Wait a moment to ensure it's running
sleep 1
echo -e "${GREEN}MCP server is now running in the background${NC}"
echo -e "Verify with: ${YELLOW}/mcp${NC}"

# Confirm registration
echo -e "\nTesting connection to MCP server..."
claude /mcp