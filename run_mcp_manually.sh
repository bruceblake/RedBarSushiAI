#\!/bin/bash
# run_mcp_manually.sh - Script to start the RedBarSushiAI MCP server manually

# Set up variables
PROJECT_PATH="/home/proxyie/MySoftware/RedBarSushiAI"
MCP_SERVER_PATH="${PROJECT_PATH}/mcp/src/redbarsushi_mcp.py"

# Make sure redbarsushi_mcp.py is executable
chmod +x ${MCP_SERVER_PATH}

# Kill any existing MCP server processes
echo "Killing any existing MCP server processes..."
pkill -f "python.*mcp/src/redbarsushi_mcp.py" || true

# Start the MCP server with SSE transport in foreground
echo "Starting MCP server with SSE transport in foreground..."
cd ${PROJECT_PATH}
PORT=4244 TRANSPORT=sse ${PROJECT_PATH}/mcp_venv/bin/python ${MCP_SERVER_PATH}

# Note: Press Ctrl+C to stop the server
