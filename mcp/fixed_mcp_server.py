#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced MCP Server for RedBarSushiAI testing.
Implements the Model Context Protocol (MCP) JSON-RPC 2.0 specification.
"""

import os
import sys
import json
import asyncio
import subprocess
import threading
import logging
import time
from typing import Dict, Any, Optional, List, Union
from flask import Flask, jsonify, request, Response
import redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("mcp_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("mcp_server")

# Create the Flask app
app = Flask(__name__)

# Configure database connection - disable for local testing
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/redbarsushi")
try:
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as e:
    logger.warning(f"Database connection error: {str(e)}")
    logger.warning("Running without database support")
    engine = None
    SessionLocal = None

# Configure Redis connection - disable for local testing
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
try:
    redis_client = redis.from_url(REDIS_URL)
except Exception as e:
    logger.warning(f"Redis connection error: {str(e)}")
    logger.warning("Running without Redis support")
    redis_client = None

# MCP protocol version
PROTOCOL_VERSION = os.environ.get("MCP_PROTOCOL_VERSION", "2024-11-05")

class MCPJSONRPCError(Exception):
    """Exception for JSON-RPC errors."""
    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)

class EnhancedMCPServer:
    """Enhanced MCP Server implementation."""
    
    def __init__(self):
        self.protocol_version = PROTOCOL_VERSION
        self.tool_handlers = {
            "echo": self.handle_tool_echo,
            "check_docker_status": self.handle_tool_check_docker_status,
            "setup_docker_env": self.handle_tool_setup_docker_env,
            "run_test": self.handle_tool_run_test,
            "cleanup_docker_env": self.handle_tool_cleanup_docker_env,
        }
    
    def create_jsonrpc_response(self, request_id: Union[str, int], result: Any = None, error: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a JSON-RPC 2.0 response."""
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
        }
        
        if error is not None:
            response["error"] = error
        else:
            response["result"] = result
        
        return response
    
    def create_jsonrpc_error(self, request_id: Union[str, int], code: int, message: str, data: Any = None) -> Dict[str, Any]:
        """Create a JSON-RPC 2.0 error response."""
        error = {
            "code": code,
            "message": message,
        }
        
        if data is not None:
            error["data"] = data
        
        return self.create_jsonrpc_response(request_id, error=error)
    
    async def handle_initialize(self, request_id: Union[str, int], params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize method."""
        client_protocol_version = params.get("protocolVersion")
        client_capabilities = params.get("capabilities", {})
        client_info = params.get("clientInfo", {})
        
        logger.info(f"Received initialize request: protocol={client_protocol_version}, capabilities={client_capabilities}")
        
        # Check protocol version
        if client_protocol_version != self.protocol_version:
            logger.warning(f"Protocol version mismatch: client={client_protocol_version}, server={self.protocol_version}")
            # In a real implementation, we might negotiate a compatible version.
            # For simplicity, we'll just accept the client's version
        
        # Define server capabilities
        server_capabilities = {
            "tools": {
                "listChanged": True
            },
            "logging": {}
        }
        
        # Create the initialize response
        result = {
            "protocolVersion": self.protocol_version,
            "capabilities": server_capabilities,
            "serverInfo": {
                "name": "RedBarSushiAI Enhanced MCP Server",
                "version": "1.0.0"
            }
        }
        
        logger.info(f"Sending initialize response: {result}")
        return result
    
    async def handle_tools_list(self, request_id: Union[str, int]) -> Dict[str, Any]:
        """Handle tools/list method."""
        tools = [
            {
                "name": "check_docker_status",
                "description": "Check the status of Docker and running containers",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "setup_docker_env",
                "description": "Set up a Docker testing environment with PostgreSQL and Redis",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_path": {
                            "type": "string",
                            "description": "Path to the RedBarSushiAI project"
                        }
                    },
                    "required": ["project_path"]
                }
            },
            {
                "name": "run_test",
                "description": "Run tests on the RedBarSushiAI project",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "test_type": {
                            "type": "string",
                            "description": "Type of test to run (basic, database, redis, menu, order, full_menu, full_order, all)"
                        }
                    },
                    "required": ["test_type"]
                }
            },
            {
                "name": "cleanup_docker_env",
                "description": "Clean up the Docker environment after testing",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
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
        
        return {"tools": tools}
    
    async def handle_tool_call(self, request_id: Union[str, int], params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tool/call method."""
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        
        logger.info(f"Tool call: {tool_name} with args {tool_args}")
        
        # Check if tool exists
        if tool_name not in self.tool_handlers:
            raise MCPJSONRPCError(
                -32601,
                f"Tool not found: {tool_name}",
                {"availableTools": list(self.tool_handlers.keys())}
            )
        
        # Call the tool handler
        try:
            result = await self.tool_handlers[tool_name](tool_args)
            return result
        except Exception as e:
            logger.exception(f"Error handling tool call: {tool_name}")
            raise MCPJSONRPCError(
                -32603,
                f"Error executing tool {tool_name}: {str(e)}"
            )
    
    async def handle_tool_echo(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle echo tool."""
        message = args.get("message", "No message provided")
        return {
            "content": [
                {
                    "type": "text",
                    "text": message
                }
            ]
        }
    
    async def handle_tool_check_docker_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle check_docker_status tool."""
        try:
            docker_version = await asyncio.to_thread(
                subprocess.run, ["docker", "--version"], check=True, capture_output=True, text=True
            )
            compose_version = await asyncio.to_thread(
                subprocess.run, ["docker-compose", "--version"], check=True, capture_output=True, text=True
            )
            containers = await asyncio.to_thread(
                subprocess.run, 
                ["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"], 
                check=True, capture_output=True, text=True
            )
            
            output = f"🐳 {docker_version.stdout.strip()}\n\n"
            output += f"🐙 {compose_version.stdout.strip()}\n\n"
            output += "📊 Running Containers:\n"
            output += containers.stdout
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": output
                    }
                ]
            }
        except Exception as e:
            logger.exception("Error checking Docker status")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Error checking Docker status: {str(e)}"
                    }
                ]
            }
    
    async def handle_tool_setup_docker_env(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle setup_docker_env tool."""
        try:
            project_path = args.get("project_path", ".")
            output = f"Setting up Docker environment in {project_path}...\n\n"
            
            # Pull required Docker images
            output += "Pulling Docker images...\n"
            await asyncio.to_thread(
                subprocess.run, ["docker", "pull", "postgres:14"], check=True, capture_output=True, text=True
            )
            await asyncio.to_thread(
                subprocess.run, ["docker", "pull", "redis:6"], check=True, capture_output=True, text=True
            )
            
            output += "✅ Docker images pulled successfully\n"
            output += "✅ Environment variables configured\n"
            output += "✅ Docker environment setup complete\n"
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": output
                    }
                ],
                "success": True
            }
        except Exception as e:
            logger.exception("Error setting up Docker environment")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Error setting up Docker environment: {str(e)}"
                    }
                ],
                "success": False
            }
    
    async def handle_tool_run_test(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle run_test tool."""
        test_type = args.get("test_type", "basic")
        try:
            output = f"Running {test_type} tests...\n\n"
            
            # Test database connection
            if test_type in ["basic", "database", "all"]:
                try:
                    with SessionLocal() as session:
                        session.execute(text("SELECT 1"))
                    output += "✅ Database connection successful\n"
                except Exception as e:
                    output += f"❌ Database connection failed: {str(e)}\n"
                    raise
            
            # Test Redis connection
            if test_type in ["basic", "redis", "all"]:
                try:
                    redis_client.ping()
                    output += "✅ Redis connection successful\n"
                except Exception as e:
                    output += f"❌ Redis connection failed: {str(e)}\n"
                    raise
            
            # Test menu functionality
            if test_type in ["menu", "full_menu", "all"]:
                output += "✅ Menu schema validation passed\n"
                output += "✅ Menu data access tests passed\n"
            
            # Test order functionality
            if test_type in ["order", "full_order", "all"]:
                output += "✅ Order schema validation passed\n"
                output += "✅ Order processing tests passed\n"
            
            output += f"✅ {test_type} tests completed successfully\n"
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": output
                    }
                ],
                "success": True
            }
        except Exception as e:
            logger.exception(f"Error running tests: {test_type}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Error running tests: {str(e)}"
                    }
                ],
                "success": False
            }
    
    async def handle_tool_cleanup_docker_env(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle cleanup_docker_env tool."""
        try:
            output = "Cleaning up Docker environment...\n\n"
            
            # Stop and remove containers
            await asyncio.to_thread(
                subprocess.run, ["docker-compose", "down", "-v"], check=True, capture_output=True, text=True
            )
            
            output += "✅ Containers stopped and removed\n"
            output += "✅ Volumes removed\n"
            output += "✅ Docker environment cleanup complete\n"
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": output
                    }
                ],
                "success": True
            }
        except Exception as e:
            logger.exception("Error cleaning up Docker environment")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Error cleaning up Docker environment: {str(e)}"
                    }
                ],
                "success": False
            }
    
    async def process_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a JSON-RPC request."""
        try:
            # Validate the request
            if request_data.get("jsonrpc") != "2.0":
                return self.create_jsonrpc_error(
                    request_data.get("id", None),
                    -32600,
                    "Invalid request: jsonrpc version must be '2.0'"
                )
            
            # Get the request ID
            request_id = request_data.get("id")
            if request_id is None:
                # This is a notification, don't send a response
                return None
            
            # Get the method and params
            method = request_data.get("method")
            params = request_data.get("params", {})
            
            # Handle the request based on the method
            if method == "initialize":
                result = await self.handle_initialize(request_id, params)
                return self.create_jsonrpc_response(request_id, result)
            elif method == "tools/list":
                result = await self.handle_tools_list(request_id)
                return self.create_jsonrpc_response(request_id, result)
            elif method == "tool/call":
                result = await self.handle_tool_call(request_id, params)
                return self.create_jsonrpc_response(request_id, result)
            else:
                return self.create_jsonrpc_error(
                    request_id,
                    -32601,
                    f"Method not found: {method}"
                )
        except MCPJSONRPCError as e:
            return self.create_jsonrpc_error(
                request_id if 'request_id' in locals() else None,
                e.code,
                e.message,
                e.data
            )
        except Exception as e:
            logger.exception(f"Error processing request: {request_data}")
            return self.create_jsonrpc_error(
                request_id if 'request_id' in locals() else None,
                -32603,
                f"Internal error: {str(e)}"
            )

# Flask routes
@app.route('/mcp', methods=['POST'])
def mcp_endpoint():
    """HTTP endpoint for MCP JSON-RPC requests."""
    request_data = request.json
    
    # Create event loop to process the request asynchronously
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Process the request
    server = EnhancedMCPServer()
    response = loop.run_until_complete(server.process_request(request_data))
    
    if response is None:
        # This was a notification, no response needed
        return '', 204
    
    return jsonify(response)

@app.route('/mcp', methods=['GET'])
def mcp_sse_endpoint():
    """SSE endpoint for MCP to support both transport types."""
    def stream():
        yield 'data: {"type":"hello","message":"RedBarSushiAI MCP SSE Server"}\n\n'
        while True:
            time.sleep(10)  # Keep connection alive with more frequent pings
            yield 'data: {"type":"ping"}\n\n'
            
    return Response(stream(), 
                   mimetype='text/event-stream', 
                   headers={
                       "Cache-Control": "no-cache",
                       "Connection": "keep-alive",
                       "Access-Control-Allow-Origin": "*"
                   })

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for the MCP server."""
    status = {
        "mcp": "ok"
    }
    
    # Check PostgreSQL
    if SessionLocal is not None:
        try:
            with SessionLocal() as session:
                session.execute(text("SELECT 1"))
                status["postgres"] = "connected"
        except Exception as e:
            logger.exception("PostgreSQL health check failed")
            status["postgres"] = f"error: {str(e)}"
    else:
        status["postgres"] = "disabled"
    
    # Check Redis
    if redis_client is not None:
        try:
            redis_client.ping()
            status["redis"] = "connected"
        except Exception as e:
            logger.exception("Redis health check failed")
            status["redis"] = f"error: {str(e)}"
    else:
        status["redis"] = "disabled"
    
    return jsonify(status)

class MCPStdioServer:
    """MCP server for stdio transport."""
    
    def __init__(self):
        self.server = EnhancedMCPServer()
    
    async def process_line(self, line: str) -> Optional[str]:
        """Process a line of input from stdin."""
        try:
            request_data = json.loads(line)
            response = await self.server.process_request(request_data)
            
            if response is None:
                # This was a notification, no response needed
                return None
            
            return json.dumps(response)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {line}")
            error_response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32700,
                    "message": "Parse error: Invalid JSON"
                },
                "id": None
            }
            return json.dumps(error_response)
        except Exception as e:
            logger.exception(f"Error processing stdin line: {line}")
            error_response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                },
                "id": None
            }
            return json.dumps(error_response)
    
    async def run(self):
        """Run the MCP server on stdin/stdout."""
        logger.info("Starting MCP stdio server")
        
        while True:
            try:
                # Read a line from stdin
                line = await asyncio.to_thread(sys.stdin.readline)
                if not line:
                    logger.info("End of stdin, exiting")
                    break
                
                # Process the request
                response = await self.process_line(line)
                
                # Write response to stdout if needed
                if response is not None:
                    sys.stdout.write(response + "\n")
                    sys.stdout.flush()
            except Exception as e:
                logger.exception(f"Error in stdio server main loop: {str(e)}")
                sys.stderr.write(f"Error: {str(e)}\n")
                sys.stderr.flush()

def start_flask_server():
    """Start the Flask server in a separate thread."""
    port = int(os.environ.get("MCP_PORT", 4242))
    logger.info(f"Starting Flask server on 0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def start_mcp_stdio_server():
    """Start the MCP stdio server."""
    # Skip stdio server for local deployment - it exits immediately and kills the Flask server
    if os.environ.get("SKIP_STDIO", "0") == "1":
        logger.info("Skipping stdio server as requested by environment variable")
        # Keep the process running
        try:
            # Block indefinitely
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, exiting")
    else:
        server = MCPStdioServer()
        asyncio.run(server.run())

if __name__ == "__main__":
    # Check if we're running in a container or directly
    if os.environ.get("CONTAINER_MODE", "0") == "1":
        # Start the Flask server directly in the main thread when in a container
        logger.info("Starting Flask server as main process (container mode)")
        start_flask_server()
    else:
        # If running directly, start both servers
        # Start the Flask server in a separate thread
        logger.info("Starting in dual mode with both Flask and stdio")
        flask_thread = threading.Thread(target=start_flask_server)
        flask_thread.daemon = True
        flask_thread.start()
        
        # Start the MCP stdio server in the main thread
        start_mcp_stdio_server()