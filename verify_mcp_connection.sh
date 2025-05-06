#!/bin/bash
# Script to verify MCP server connection

echo "Testing MCP server connection..."

# Test direct connection to server
echo "Testing direct connection to MCP server at http://127.0.0.1:4243/mcp"
curl -N http://127.0.0.1:4243/mcp &
CURL_PID=$!
sleep 3
kill $CURL_PID 2>/dev/null

# Test health endpoint
echo -e "\nChecking server health..."
curl http://127.0.0.1:4243/health

echo -e "\n\nVerify Claude configuration..."
echo "Current MCP server configuration in ~/.claude.json:"
grep -A 5 "redbarsushi-mcp" ~/.claude.json

echo -e "\nIf you see SSE data flow above and the configuration looks correct,"
echo "you should restart Claude and run /mcp to check the connection status."
echo "To restart the server if needed, use the following commands:"
echo "  cd /home/proxyie/MySoftware/RedBarSushiAI/mcp && source mcp_venv/bin/activate && python simple_mcp_server.py"