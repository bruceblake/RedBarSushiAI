#!/bin/bash
# Restart the MCP server with fixed configuration

echo "Stopping existing MCP server container..."
docker stop redbarsushi_mcp

echo "Removing existing MCP server container..."
docker rm redbarsushi_mcp

echo "Setting HOST environment variable to 0.0.0.0..."
export HOST="0.0.0.0"

echo "Rebuilding MCP server image..."
docker build -t redbarsushiai-mcp -f mcp/docker/Dockerfile.mcp .

echo "Starting MCP server with fixed configuration..."
docker run --name redbarsushi_mcp \
  --network redbarsushiai_default \
  -p 4244:4244 \
  -e HOST=0.0.0.0 \
  -e PORT=4244 \
  -e REDIS_HOST=redbarsushi_redis \
  -e POSTGRES_HOST=redbarsushi_postgres \
  -e APP_URL=http://redbarsushi_web:8080 \
  -e TRANSPORT=sse \
  -d redbarsushiai-mcp

echo "MCP server restarted. Checking status..."
sleep 3
docker ps | grep redbarsushi_mcp

echo "MCP server logs:"
docker logs redbarsushi_mcp

echo "Testing MCP connectivity..."
python test_mcp_connectivity.py