#!/bin/bash

# Kill any existing MCP server processes
pkill -f "python.*redbarsushi_mcp.py" || true
echo "Killed any running RedBarSushi MCP server processes"

# Set environment variables for the MCP server
MCP_PORT=4000
TRANSPORT=sse
HOST=0.0.0.0
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/redbarsushi
REDIS_URL=redis://localhost:6379/0
export MCP_PORT HOST TRANSPORT DATABASE_URL REDIS_URL
echo "Set MCP port to $MCP_PORT with transport $TRANSPORT"

# Add the MCP server with claude command line tool
MCP_URL="http://127.0.0.1:$MCP_PORT"
MCP_NAME="redbarsushi-mcp"

echo "Adding RedBarSushi MCP server '$MCP_NAME' with URL '$MCP_URL' to Claude configuration"
claude mcp add "$MCP_NAME" "$MCP_URL"
echo "Server added to Claude configuration"

# Start the MCP server in the background
cd "$(dirname "$0")"

# Check if virtual environment exists
if [ -d "mcp_venv" ]; then
    echo "Using existing virtual environment"
else
    echo "Creating new virtual environment"
    python -m venv mcp_venv
    source mcp_venv/bin/activate
    pip install -r mcp/requirements.txt
fi

# Activate the virtual environment
source mcp_venv/bin/activate

# Set PYTHONPATH to include current directory
cd mcp
export PYTHONPATH=$(pwd):$PYTHONPATH

# Start the RedBarSushi MCP server (detached from stdin/stdout)
echo "Starting RedBarSushi MCP server on port $MCP_PORT..."
nohup python redbarsushi_mcp.py > redbarsushi_mcp.log 2>&1 &
SERVER_PID=$!
sleep 3
# Check if server started successfully
attempts=0
max_attempts=6
until $(curl --output /dev/null --silent --fail http://127.0.0.1:$MCP_PORT/health); do
    attempts=$((attempts+1))
    if [ $attempts -ge $max_attempts ]; then
        echo "Error: MCP server failed to start. Check redbarsushi_mcp.log for details."
        exit 1
    fi
    echo "Waiting for server to start... ($attempts/$max_attempts)"
    sleep 2
done

echo "✅ RedBarSushi MCP server started with PID $SERVER_PID"
echo "You can check server status with: curl http://127.0.0.1:$MCP_PORT/health"
echo ""
echo "Available endpoints:"
echo "  - Health check: http://127.0.0.1:$MCP_PORT/health"
echo "  - MCP JSON-RPC: http://127.0.0.1:$MCP_PORT/mcp"
echo ""
echo "Available tools:"
echo "  - echo: Simple echo test"
echo "  - get_environment_status: Get status of environment components"
echo "  - run_test: Run tests against the environment"
echo "  - setup_docker_environment: Set up a Docker environment for testing"
echo "  - stop_docker_environment: Stop the Docker environment"
echo "  - view_container_logs: View logs for a specific container"
echo "  - get_database_schema: Get database schema information"
echo "  - execute_query: Execute a SQL query against the database"
echo "  - get_redis_keys: Get Redis keys matching a pattern"
echo "  - get_redis_value: Get the value of a Redis key"
echo "  - lookup_menu_item: Find a menu item by name"
echo "  - get_menu_categories: Get all menu categories"
echo "  - get_menu_items: Get menu items, optionally filtered by category"
echo "  - search_menu_items: Search menu items by name or description"
echo "  - get_current_cart: Get the current cart for a session"
echo "  - add_to_cart: Add an item to the cart"
echo "  - place_order: Place an order from the cart"
echo "  - poll_order_status: Check the status of an order"
echo ""
echo "Example use with curl:"
echo "curl -X POST http://127.0.0.1:$MCP_PORT/mcp -H \"Content-Type: application/json\" -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"echo\",\"params\":{\"message\":\"Hello\"}}'"
echo ""
echo "To stop the server: ./cleanup_fastmcp.sh"