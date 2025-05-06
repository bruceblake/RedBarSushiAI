#!/bin/bash

# Kill any existing MCP server processes
pkill -f "python.*enhanced_mcp_server.py" || true
echo "Killed any running MCP server processes"

# Change to MCP directory
cd /home/proxyie/MySoftware/RedBarSushiAI/mcp

# Activate the virtual environment
source venv/bin/activate

# Install psycopg2-binary instead of psycopg2 (avoids compilation issues)
echo "Installing psycopg2-binary..."
pip install psycopg2-binary

# Edit the enhanced_mcp_server.py file to fix the PostgreSQL URL
sed -i 's|DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/redbarsushi")|DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/redbarsushi")|g' /home/proxyie/MySoftware/RedBarSushiAI/mcp/enhanced_mcp_server.py
echo "Updated PostgreSQL URL in enhanced_mcp_server.py"

# Set environment variables for the MCP server
MCP_PORT=4242
SKIP_STDIO=1
export MCP_PORT SKIP_STDIO
echo "Set MCP port to $MCP_PORT"

# Start the MCP server (detached from stdin/stdout)
echo "Starting MCP server on port $MCP_PORT..."
nohup python enhanced_mcp_server.py > enhanced_mcp.log 2>&1 &
sleep 2
echo "MCP server started with PID $!"
echo "You can check server status with: curl http://127.0.0.1:$MCP_PORT/health"