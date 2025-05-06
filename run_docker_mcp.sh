#\!/bin/bash
# run_docker_mcp.sh - Script to run the RedBarSushiAI MCP server in Docker

# Stop and remove existing containers
echo "Stopping any existing redbarsushi-mcp containers..."
docker stop redbarsushi-mcp 2>/dev/null || true
docker rm redbarsushi-mcp 2>/dev/null || true

# Build the Docker image
echo "Building Docker image..."
cd /home/proxyie/MySoftware/RedBarSushiAI/mcp
docker build -f docker/Dockerfile.fastmcp -t redbarsushi-mcp .

# Run the container
echo "Running Docker container..."
docker run -d --name redbarsushi-mcp -p 4244:4244 redbarsushi-mcp

# Check if container started successfully
if [ $? -eq 0 ]; then
    echo "MCP server started successfully in Docker container"
    echo "Logs can be viewed with: docker logs -f redbarsushi-mcp"
    echo "To stop the container: docker stop redbarsushi-mcp"
else
    echo "Failed to start Docker container"
fi
