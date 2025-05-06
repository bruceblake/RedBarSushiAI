#!/bin/bash
set -e

echo "Starting local MCP server environment..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "❌ Docker is not running. Please start Docker and try again."
  exit 1
fi

# Stop any existing containers
echo "Stopping any existing containers..."
docker-compose down 2>/dev/null || true

# Clean up any old volumes if requested
if [ "$1" == "--clean" ]; then
  echo "Cleaning up volumes..."
  docker volume rm $(docker volume ls -q | grep redbarsushiai) 2>/dev/null || true
fi

# Start the containers
echo "Starting containers..."
docker-compose up -d --build

# Wait for the MCP server to be healthy
echo "Waiting for services to be ready..."
for i in {1..30}; do
  if curl -s http://localhost:4000/health > /dev/null; then
    echo "✅ MCP server is up and running!"
    break
  fi
  if [ $i -eq 30 ]; then
    echo "❌ Timed out waiting for MCP server to start."
    exit 1
  fi
  echo "Waiting for MCP server to start... ($i/30)"
  sleep 2
done

echo "Validating the setup..."
python -m venv venv > /dev/null 2>&1 || true
source venv/bin/activate > /dev/null 2>&1
pip install requests > /dev/null 2>&1 || true

# Run validation
python validate_mcp_server.py

echo -e "\nLocal MCP server is now running."
echo "To test, use: python tests/mcp/test_local_mcp.py"
echo "To stop, use: docker-compose down -v"
echo ""
echo "MCP server URL: http://localhost:4000/mcp"
echo "Health endpoint: http://localhost:4000/health"
echo ""
echo "Add to Claude Code: "
echo "1. Run 'claude mcp add' and select SSE type"
echo "2. Enter URL: http://host.docker.internal:4000/mcp"
echo "3. Enter name: redbarsushi-mcp"