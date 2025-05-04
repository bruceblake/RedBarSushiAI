#!/bin/bash
# Script to run the fixed MCP server

# Kill any running MCP servers
pkill -f "python .*mcp.*py" || true
sleep 1

# Make scripts executable
chmod +x fixed_simple_mcp.py
chmod +x test_staging_e2e.sh

# Register with Claude
echo "Registering fixed MCP server with Claude..."
claude mcp remove staging-test 2>/dev/null || true
claude mcp add staging-test "./fixed_simple_mcp.py"

echo "MCP server registered as 'staging-test'"
echo "You can now use:"
echo "  /mcp run_test test_type=\"basic\"      - Run basic tests"
echo "  /mcp echo message=\"Testing\"          - Echo test"
echo ""

# Run in the background
nohup python fixed_simple_mcp.py > /dev/null 2>&1 &

# Wait a moment to ensure it's running
sleep 1
echo "MCP server is now running in the background"
echo "Verify with: /mcp"