#!/usr/bin/env python3
"""
Proper SSE MCP Server for RedBarSushiAI.
Implements the SSE format expected by Claude Code.
"""

import os
import sys
import logging
import time
import uuid
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("proper_mcp.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("proper_mcp")

class MCPRequestHandler(BaseHTTPRequestHandler):
    """Simple HTTP request handler for MCP Server."""
    
    def _set_headers(self, content_type="text/event-stream"):
        self.send_response(200)
        self.send_header('Content-type', content_type)
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests for SSE."""
        if self.path == "/mcp" or self.path == "/mcp/":
            logger.info("SSE connection established")
            self._set_headers()
            
            # First send the endpoint notification
            session_id = str(uuid.uuid4()).replace("-", "")
            endpoint_msg = f"event: endpoint\ndata: /messages/?session_id={session_id}\n\n"
            self.wfile.write(endpoint_msg.encode())
            self.wfile.flush()
            
            # Now keep the connection alive with pings
            try:
                count = 0
                while True:
                    ping_msg = f"event: ping\ndata: {count}\n\n"
                    self.wfile.write(ping_msg.encode())
                    self.wfile.flush()
                    count += 1
                    time.sleep(10)  # Send a ping every 10 seconds
            except (ConnectionResetError, BrokenPipeError):
                logger.info("Client disconnected")
        
        elif self.path.startswith("/messages/?session_id="):
            logger.info("Message endpoint hit")
            self._set_headers("application/json")
            self.wfile.write(b'{"status":"ok"}')
        
        elif self.path == "/health":
            logger.info("Health check endpoint hit")
            self._set_headers("application/json")
            self.wfile.write(b'{"status":"ok","protocol":"2024-11-05"}')
        
        else:
            logger.warning(f"Unknown path requested: {self.path}")
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        """Handle POST requests."""
        if self.path.startswith("/messages"):
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            logger.info(f"Received message POST: {post_data}")
            
            self._set_headers("application/json")
            self.wfile.write(b'{"status":"ok"}')
        else:
            logger.warning(f"Unknown POST path: {self.path}")
            self.send_response(404)
            self.end_headers()
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Accept')
        self.end_headers()

class ReuseAddressHTTPServer(HTTPServer):
    """HTTP Server that allows reusing the address."""
    allow_reuse_address = True

def run_server(port=4242):
    """Run the HTTP server."""
    try:
        # Force kill any existing process on the port
        import subprocess
        try:
            subprocess.run(["fuser", "-k", f"{port}/tcp"], check=False)
        except Exception as e:
            logger.warning(f"Failed to kill processes on port {port}: {e}")

        # Use SO_REUSEADDR
        server_address = ('', port)
        httpd = ReuseAddressHTTPServer(server_address, MCPRequestHandler)
        logger.info(f"Starting server on port {port}")
        httpd.serve_forever()
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        raise

if __name__ == "__main__":
    port = int(os.environ.get("MCP_PORT", 4000))  # Default to 4000
    logger.info(f"Attempting to start server on port {port}")
    run_server(port)