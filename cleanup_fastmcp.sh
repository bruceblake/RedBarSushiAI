#!/bin/bash
# Script to stop the RedBarSushi MCP server and clean up

echo "RedBarSushi MCP Server Cleanup"
echo "-----------------------------"

# Kill any running MCP server processes
echo "Stopping any running MCP server processes..."
pkill -f "python.*redbarsushi_mcp.py" || true

# Handle Docker cleanup based on arguments
if [ "$1" == "--stop-docker" ] || [ "$1" == "--full-cleanup" ]; then
    echo "Stopping FastMCP Docker environment..."
    docker-compose -f docker-compose-fastmcp.yml down
    
    echo "Stopping main Docker environment..."
    docker-compose -p redbarsushiai down
    
    if [ "$1" == "--full-cleanup" ]; then
        echo "Removing Docker volumes..."
        docker-compose -f docker-compose-fastmcp.yml down -v
        docker-compose -p redbarsushiai down -v
    fi
fi

# Optionally remove the MCP server from Claude configuration
if [ "$1" == "--remove-config" ] || [ "$1" == "--full-cleanup" ]; then
    MCP_NAME="redbarsushi-mcp"
    
    # Remove using claude CLI
    echo "Removing MCP server from Claude configuration..."
    claude mcp remove "$MCP_NAME" 2>/dev/null || true
    
    echo "RedBarSushi MCP server '$MCP_NAME' has been removed from your Claude configuration"
    echo "Remember to restart Claude Code to apply the changes"
fi

# Check if all processes were actually stopped
if pgrep -f "python.*redbarsushi_mcp.py" > /dev/null; then
    echo "Warning: Some MCP server processes are still running."
    echo "You may need to manually kill them with: pkill -9 -f \"python.*redbarsushi_mcp.py\""
else
    echo "✅ All MCP server processes successfully stopped"
fi

# Verify Docker containers are stopped
if [ "$1" == "--stop-docker" ] || [ "$1" == "--full-cleanup" ]; then
    if docker ps | grep -q "redbarsushi"; then
        echo "Warning: Some RedBarSushi Docker containers are still running."
        echo "You may need to manually stop them with: docker-compose down"
    else
        echo "✅ All RedBarSushi Docker containers successfully stopped"
    fi
fi

echo ""
echo "Cleanup completed"
echo ""
echo "Usage:"
echo "  ./cleanup_fastmcp.sh                  - Stop the MCP server"
echo "  ./cleanup_fastmcp.sh --stop-docker    - Stop the MCP server and Docker environment"
echo "  ./cleanup_fastmcp.sh --remove-config  - Stop the MCP server and remove from Claude config"
echo "  ./cleanup_fastmcp.sh --full-cleanup   - Stop everything and remove all data"