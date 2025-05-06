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
