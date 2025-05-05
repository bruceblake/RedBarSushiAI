#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Basic MCP Server for RedBarSushiAI testing.
A minimalist implementation to ensure the server runs.
"""

import os
import sys
import json
import asyncio
import subprocess
from typing import Dict, Any, Optional

class BasicMCPServer:
    def __init__(self):
        self.protocol_version = "2024-11-05"
        self.project_path = "/home/proxyie/MySoftware/RedBarSushiAI"
        
    async def handle_initialize(self, request_id):
        """Handle initialize method."""
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": self.protocol_version,
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "RedBarSushiAI Basic Test Server",
                    "version": "1.0.0"
                }
            }
        }
        return response
    
    async def handle_tools_list(self, request_id):
        """Handle tools/list method."""
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
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
        return response
    
    async def handle_tool_call(self, request_id, params):
        """Handle tool/call method."""
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        
        result = {
            "content": [
                {
                    "type": "text",
                    "text": "Tool result not available"
                }
            ]
        }
        
        if tool_name == "echo":
            message = tool_args.get("message", "No message provided")
            result = {
                "content": [
                    {
                        "type": "text",
                        "text": f"Echo: {message}"
                    }
                ]
            }
        elif tool_name == "check_docker_status":
            try:
                docker_version = subprocess.run(["docker", "--version"], check=True, capture_output=True, text=True)
                compose_version = subprocess.run(["docker-compose", "--version"], check=True, capture_output=True, text=True)
                containers = subprocess.run(["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"], check=True, capture_output=True, text=True)
                
                output = f"🐳 {docker_version.stdout.strip()}\n\n"
                output += f"🐙 {compose_version.stdout.strip()}\n\n"
                output += "📊 Running Containers:\n"
                output += containers.stdout
                
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": output
                        }
                    ]
                }
            except Exception as e:
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": f"❌ Error checking Docker status: {str(e)}"
                        }
                    ]
                }
        
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }
        return response
    
    async def process_request(self, request_json):
        """Process an incoming request."""
        try:
            request = json.loads(request_json)
            request_id = request.get("id")
            method = request.get("method")
            params = request.get("params", {})
            
            if method == "initialize":
                return await self.handle_initialize(request_id)
            elif method == "tools/list":
                return await self.handle_tools_list(request_id)
            elif method == "tool/call":
                return await self.handle_tool_call(request_id, params)
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id if 'request_id' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
    
    async def run(self):
        """Run the MCP server on stdin/stdout."""
        while True:
            try:
                # Read a line from stdin
                line = await asyncio.to_thread(sys.stdin.readline)
                if not line:
                    break
                
                # Process the request
                response = await self.process_request(line)
                
                # Write response to stdout
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except Exception as e:
                sys.stderr.write(f"Error: {str(e)}\n")
                sys.stderr.flush()

if __name__ == "__main__":
    server = BasicMCPServer()
    asyncio.run(server.run())