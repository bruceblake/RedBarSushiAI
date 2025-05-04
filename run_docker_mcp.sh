#!/bin/bash
# Script to run the Docker-enabled MCP server

# Kill any running MCP servers
pkill -f "python .*mcp.*py" || true
sleep 1

# Make scripts executable
chmod +x mcp_docker_tests.py
chmod +x test_staging_e2e.sh
chmod +x run_docker_integration_tests.sh

# Register with Claude
echo "Registering Docker-enabled MCP server with Claude..."
claude mcp remove docker-test 2>/dev/null || true
claude mcp add docker-test "./mcp_docker_tests.py"

echo "MCP server registered as 'docker-test'"
echo "You can now use:"
echo "  /mcp docker_status                         - Check Docker container status"
echo "  /mcp docker_start test_type=\"integration\"  - Start Docker containers for integration tests"
echo "  /mcp docker_test test_file=\"all\"           - Run all integration tests with Docker"
echo "  /mcp docker_stop test_type=\"integration\"   - Stop Docker containers"
echo ""

# Run in the background
nohup python mcp_docker_tests.py > /dev/null 2>&1 &

# Wait a moment to ensure it's running
sleep 1
echo "Docker MCP server is now running in the background"
echo "Verify with: /mcp"