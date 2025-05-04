#!/bin/bash
# Simple script to run the MCP test server

# Kill any existing MCP servers
pkill -f "python.*simple_test_mcp.py" || true

# Make sure scripts are executable
chmod +x simple_test_mcp.py
chmod +x test_staging_e2e.sh

# Register with Claude directly
echo "Registering MCP server with Claude..."
claude mcp add staging-test "./simple_test_mcp.py"

echo "MCP server registered as 'staging-test'"
echo "You can use it with:"
echo "  /mcp run_test test_type=\"basic\"      - Run basic tests"
echo "  /mcp echo message=\"Testing\"          - Test echo functionality"
echo ""

# Run the script
python simple_test_mcp.py