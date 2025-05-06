#!/bin/bash
# Script to run the FastMCP server in Docker for RedBarSushiAI

# Set default environment values
export MCP_PORT=${MCP_PORT:-4000}
export POSTGRES_PORT=${POSTGRES_PORT:-5433}
export REDIS_PORT=${REDIS_PORT:-6380}
export POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-postgres}
export ENVIRONMENT=${ENVIRONMENT:-staging}
export DEBUG=${DEBUG:-True}
export LOG_LEVEL=${LOG_LEVEL:-INFO}

# Print configuration
echo "Starting RedBarSushi MCP server with the following configuration:"
echo "MCP_PORT=$MCP_PORT"
echo "POSTGRES_PORT=$POSTGRES_PORT"
echo "REDIS_PORT=$REDIS_PORT"
echo "ENVIRONMENT=$ENVIRONMENT"
echo "DEBUG=$DEBUG"
echo "LOG_LEVEL=$LOG_LEVEL"

# Stop any running containers
echo "Stopping any running containers..."
docker-compose -f docker-compose-fastmcp.yml down

# Build and start the containers
echo "Building and starting containers..."
docker-compose -f docker-compose-fastmcp.yml up -d --build

# Wait for the server to start
echo "Waiting for FastMCP server to start..."
attempts=0
max_attempts=12
until $(curl --output /dev/null --silent --fail http://localhost:$MCP_PORT/health); do
    attempts=$((attempts+1))
    if [ $attempts -ge $max_attempts ]; then
        echo "Error: FastMCP server failed to start after $max_attempts attempts"
        echo "Check logs with: docker-compose -f docker-compose-fastmcp.yml logs fastmcp"
        exit 1
    fi
    echo "Waiting for server to be ready... ($attempts/$max_attempts)"
    sleep 5
done

# Test the server
echo "Testing FastMCP server..."
curl -s http://localhost:$MCP_PORT/health

echo ""
echo "✅ FastMCP server is running in Docker at http://localhost:$MCP_PORT"
echo ""
echo "Available services:"
echo "• MCP Server: http://localhost:$MCP_PORT"
echo "• PostgreSQL: localhost:$POSTGRES_PORT (user: postgres, password: $POSTGRES_PASSWORD, db: redbarsushi)"
echo "• Redis: localhost:$REDIS_PORT"
echo ""
echo "You can use the following command to register it with Claude:"
echo "claude mcp add redbarsushi-mcp http://localhost:$MCP_PORT"
echo ""
echo "Available tools:"
echo "• echo: Simple echo test"
echo "• get_environment_status: Get status of environment components"
echo "• run_test: Run tests against the environment"
echo "• setup_docker_environment: Set up a Docker environment for testing"
echo "• stop_docker_environment: Stop the Docker environment"
echo "• view_container_logs: View logs for a specific container"
echo "• lookup_menu_item: Find a menu item by name"
echo "• get_menu_categories: Get all menu categories"
echo "• get_menu_items: Get menu items, optionally filtered by category"
echo "• get_current_cart: Get the current cart for a session"
echo "• add_to_cart: Add an item to the cart"
echo "• place_order: Place an order from the cart"
echo "• poll_order_status: Check the status of an order"
echo ""
echo "To stop the server, run: ./cleanup_fastmcp.sh"