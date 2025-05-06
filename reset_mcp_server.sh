#!/bin/bash

echo "===== Re-setting MCP Server with Minimal Configuration ====="

# Kill any existing MCP server processes
pkill -f "python.*enhanced_mcp_server.py" || true
pkill -f "python.*fixed_mcp_server.py" || true
pkill -f "python.*fixed_sse_server.py" || true
pkill -f "python.*enhanced_sse_mcp_server.py" || true
echo "✅ Cleaned up any running MCP server processes"

# Set environment variables for the MCP server
export MCP_PORT=4242
export SKIP_STDIO=1
export CONTAINER_MODE=1
export MCP_PROTOCOL_VERSION="2024-11-05"
echo "✅ Set MCP environment variables"

# Configure Claude's MCP settings - use the exact protocol format
CONFIG_DIR="$HOME/.local/share/Claude"
CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"

# Create the config directory if it doesn't exist
mkdir -p "$CONFIG_DIR"

# Create from scratch a brand new config file with minimal configuration
echo '{"mcpServers":{"redbarsushi-mcp":{"url":"http://127.0.0.1:4242/mcp","type":"sse"}}}' > "$CONFIG_FILE"
echo "✅ Created new Claude config file with minimal configuration"

# Also check if there's a .claude.json in the home directory
HOME_CONFIG_FILE="$HOME/.claude.json"
if [ -f "$HOME_CONFIG_FILE" ]; then
    # Create from scratch a brand new config file with minimal configuration
    echo '{"mcpServers":{"redbarsushi-mcp":{"url":"http://127.0.0.1:4242/mcp","type":"sse"}}}' > "$HOME_CONFIG_FILE"
    echo "✅ Created new home directory Claude config with minimal configuration"
fi

# Make sure the MCP server directory exists
MCP_DIR="/home/proxyie/MySoftware/RedBarSushiAI/mcp"
if [ ! -d "$MCP_DIR" ]; then
    echo "❌ Error: MCP directory not found at $MCP_DIR"
    exit 1
fi

# Change to the MCP directory
cd "$MCP_DIR"

# Make sure we have the virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment for MCP server..."
    python -m venv venv
fi

# Activate the virtual environment
source venv/bin/activate

# Install required packages
pip install flask==2.0.1 werkzeug==2.0.1 redis==4.3.4 sqlalchemy==1.4.40 psycopg2-binary

# Create a minimal server implementation
cat > minimal_mcp_server.py << 'EOF'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal MCP Server implementation focusing only on SSE protocol.
"""
import os
import sys
import json
import logging
import time
import uuid
from flask import Flask, jsonify, request, Response

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("minimal_mcp.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("minimal_mcp")

# Create the Flask app
app = Flask(__name__)

# MCP protocol version 
PROTOCOL_VERSION = "2024-11-05"
logger.info(f"Using MCP protocol version: {PROTOCOL_VERSION}")

@app.route('/mcp', methods=['GET'])
def mcp_sse_endpoint():
    """SSE endpoint for MCP using proper JSON-RPC format."""
    logger.debug("SSE connection established")
    logger.debug(f"SSE request headers: {dict(request.headers)}")
    
    def stream():
        # Send initial hello as a proper JSON-RPC notification
        hello_notification = {
            "jsonrpc": "2.0",
            "method": "$/hello",
            "params": {
                "serverInfo": {
                    "name": "RedBarSushiAI Minimal MCP Server",
                    "version": "1.0.0"
                },
                "protocolVersion": PROTOCOL_VERSION
            }
        }
        logger.debug(f"Sending hello notification: {hello_notification}")
        yield f"data: {json.dumps(hello_notification)}\n\n"
        
        # Send periodic pings in the correct JSON-RPC format
        ping_count = 0
        while True:
            ping_notification = {
                "jsonrpc": "2.0",
                "method": "$/ping",
                "params": {
                    "id": str(uuid.uuid4()),
                    "timestamp": int(time.time()),
                    "sequence": ping_count
                }
            }
            logger.debug(f"Sending ping {ping_count}")
            yield f"data: {json.dumps(ping_notification)}\n\n"
            ping_count += 1
            time.sleep(1)  # Fast ping interval
    
    logger.debug("Starting SSE stream")
    return Response(
        stream(),
        mimetype='text/event-stream',
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Accept",
            "X-Accel-Buffering": "no"
        }
    )

@app.route('/mcp', methods=['POST'])
def mcp_endpoint():
    """HTTP endpoint for MCP JSON-RPC requests."""
    request_data = request.json
    logger.debug(f"Received POST request: {request_data}")
    
    # Just echo back a basic response to any request
    method = request_data.get("method")
    request_id = request_data.get("id")
    
    if method == "initialize":
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {
                        "listChanged": True
                    }
                },
                "serverInfo": {
                    "name": "RedBarSushiAI Minimal MCP Server",
                    "version": "1.0.0"
                }
            }
        }
    elif method == "tools/list":
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": "echo",
                        "description": "Echo a message back",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "message": {
                                    "type": "string",
                                    "description": "Message to echo back"
                                }
                            },
                            "required": ["message"]
                        }
                    }
                ]
            }
        }
    else:
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "success": True
            }
        }
    
    logger.debug(f"Sending response: {response}")
    return jsonify(response)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "protocol_version": PROTOCOL_VERSION
    })

@app.route('/mcp', methods=['OPTIONS'])
def handle_options():
    """Handle CORS preflight requests."""
    logger.debug("Handling OPTIONS request")
    logger.debug(f"OPTIONS request headers: {dict(request.headers)}")
    
    response = app.make_default_options_response()
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Accept')
    return response

if __name__ == "__main__":
    port = int(os.environ.get("MCP_PORT", 4242))
    logger.info(f"Starting minimal MCP server on port {port}")
    app.run(host='0.0.0.0', port=port, threaded=True)
EOF

# Make the script executable
chmod +x minimal_mcp_server.py

# Start the MCP server
echo "Starting minimal MCP server on port $MCP_PORT..."
nohup python minimal_mcp_server.py > minimal_mcp.log 2>&1 &
SERVER_PID=$!

# Give the server time to start
sleep 3

# Check if the server started successfully
if ps -p $SERVER_PID > /dev/null; then
    echo "✅ MCP server started successfully with PID $SERVER_PID"
else
    echo "❌ Error: MCP server failed to start."
    echo "   Please check the log at $MCP_DIR/minimal_mcp.log"
    tail -n 20 "$MCP_DIR/minimal_mcp.log"
    exit 1
fi

# Test the server health endpoint
echo "Testing server health endpoint..."
curl -s "http://127.0.0.1:$MCP_PORT/health"

# Test the SSE endpoint
echo -e "\n\nTesting SSE endpoint..."
curl -v -N -H "Accept: text/event-stream" "http://127.0.0.1:$MCP_PORT/mcp" &
CURL_PID=$!
sleep 2
kill $CURL_PID 2>/dev/null

echo -e "\n\n===== SETUP COMPLETE ====="
echo "A minimal MCP server has been started."
echo "The Claude config has been COMPLETELY RESET with only the minimal required configuration."
echo ""
echo "Please restart Claude Desktop to apply the changes."
echo ""
echo "If you still have issues, check the server logs with:"
echo "  tail -f $MCP_DIR/minimal_mcp.log"
echo "=========================="