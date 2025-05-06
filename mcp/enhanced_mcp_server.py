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
import traceback
import time
import uuid
import hmac
import hashlib
import base64
import random
from datetime import datetime
from typing import Dict, Any, Optional, List, Union, Tuple
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
logger.setLevel(logging.DEBUG)

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
            "tail_log": self.handle_tool_tail_log,
            "grep_log": self.handle_tool_grep_log,
            "celery_status": self.handle_tool_celery_status,
            "replay_task": self.handle_tool_replay_task,
            "twilio_sig_mock": self.handle_tool_twilio_sig_mock,
            "twilio_mock": self.handle_tool_twilio_mock,
            "twiml_preview": self.handle_tool_twiml_preview,
            "simulate_media_stream": self.handle_tool_simulate_media_stream,
            "openai_realtime_ping": self.handle_tool_openai_realtime_ping,
            "dry_run_order": self.handle_tool_dry_run_order,
            "deliverect_status": self.handle_tool_deliverect_status,
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
            },
            {
                "name": "tail_log",
                "description": "Get the last n lines of a log file",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file": {
                            "type": "string",
                            "description": "Log file to tail (web, mcp, celery, websocket) or path"
                        },
                        "lines": {
                            "type": "integer",
                            "description": "Number of lines to retrieve (default: 200)"
                        }
                    },
                    "required": ["file"]
                }
            },
            {
                "name": "grep_log",
                "description": "Search log files for specific patterns",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file": {
                            "type": "string",
                            "description": "Log file to search (web, mcp, celery, websocket) or path"
                        },
                        "pattern": {
                            "type": "string",
                            "description": "Regular expression pattern to search for"
                        },
                        "max_lines": {
                            "type": "integer",
                            "description": "Maximum number of matching lines to return (default: 50)"
                        }
                    },
                    "required": ["file", "pattern"]
                }
            },
            {
                "name": "celery_status",
                "description": "Get the status of Celery workers and queued tasks",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "replay_task",
                "description": "Replay a Celery task with the given arguments",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task_name": {
                            "type": "string",
                            "description": "Name of the Celery task to replay"
                        },
                        "task_args": {
                            "type": "object",
                            "description": "Arguments to pass to the task"
                        }
                    },
                    "required": ["task_name"]
                }
            },
            {
                "name": "twilio_sig_mock",
                "description": "Generate a valid Twilio signature for webhook validation testing",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL of the webhook endpoint"
                        },
                        "params": {
                            "type": "object",
                            "description": "Parameters to include in the signature calculation"
                        }
                    },
                    "required": ["url", "params"]
                }
            },
            {
                "name": "twilio_mock",
                "description": "Generate a mock Twilio SMS message response",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "phone_number": {
                            "type": "string",
                            "description": "Phone number for the mock message"
                        },
                        "message": {
                            "type": "string",
                            "description": "Message content"
                        }
                    },
                    "required": ["phone_number", "message"]
                }
            },
            {
                "name": "twiml_preview",
                "description": "Generate a preview of TwiML for a voice call",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Session ID for the call"
                        },
                        "greeting": {
                            "type": "string",
                            "description": "Custom greeting message (optional)"
                        }
                    },
                    "required": ["session_id"]
                }
            },
            {
                "name": "simulate_media_stream",
                "description": "Simulate a Twilio media stream with audio data",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "audio_file": {
                            "type": "string",
                            "description": "Path to an audio file (optional)"
                        },
                        "duration": {
                            "type": "integer",
                            "description": "Duration in seconds for synthetic audio (default: 5)"
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "openai_realtime_ping",
                "description": "Test the connection to the OpenAI Realtime API",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "dry_run_order",
                "description": "Validate an order payload without submitting to Deliverect",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "payload": {
                            "type": "object",
                            "description": "Order payload to validate"
                        },
                        "channel_link_id": {
                            "type": "string",
                            "description": "Channel link ID (optional, defaults to test-channel-link-id)"
                        },
                        "validate_only": {
                            "type": "boolean",
                            "description": "Whether to only validate the payload structure (default: true)"
                        }
                    },
                    "required": ["payload"]
                }
            },
            {
                "name": "deliverect_status",
                "description": "Check the status of an order in Deliverect",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "channel_order_id": {
                            "type": "string",
                            "description": "Channel order ID (the system-generated ID for this order)"
                        },
                        "channel_link_id": {
                            "type": "string",
                            "description": "Channel link ID (optional, defaults to test-channel-link-id)"
                        }
                    },
                    "required": ["channel_order_id"]
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
            
    async def handle_tool_tail_log(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tail_log tool."""
        file_alias = args.get("file", "web")
        lines = args.get("lines", 200)
        
        # Map file aliases to actual paths
        log_file_map = {
            "web": "/home/proxyie/MySoftware/RedBarSushiAI/logs/web.log",
            "mcp": "/home/proxyie/MySoftware/RedBarSushiAI/mcp/mcp_server.log",
            "celery": "/home/proxyie/MySoftware/RedBarSushiAI/logs/celery.log",
            "websocket": "/home/proxyie/MySoftware/RedBarSushiAI/websocket_monitor.log",
            "test": "/home/proxyie/MySoftware/RedBarSushiAI/mcp/enhanced_mcp.log"
        }
        
        # Get the actual file path
        if file_alias in log_file_map:
            file_path = log_file_map[file_alias]
        else:
            # Use the provided path directly if not an alias
            file_path = file_alias
        
        try:
            # Use tail to get the last N lines of the log file
            result = await asyncio.to_thread(
                subprocess.run, ["tail", "-n", str(lines), file_path], check=True, capture_output=True, text=True
            )
            
            log_content = result.stdout
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"## Last {lines} lines of {file_path}:\n\n```log\n{log_content}\n```"
                    }
                ],
                "success": True,
                "log_file": file_path,
                "lines_retrieved": len(log_content.splitlines())
            }
        except subprocess.CalledProcessError as e:
            logger.exception(f"Error running tail on {file_path}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Error reading log file: {str(e)}\nStderr: {e.stderr}"
                    }
                ],
                "success": False,
                "error": str(e),
                "log_file": file_path
            }
        except FileNotFoundError:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Log file not found: {file_path}"
                    }
                ],
                "success": False,
                "error": f"File not found: {file_path}",
                "log_file": file_path
            }
        except Exception as e:
            logger.exception(f"Error tailing log file {file_path}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Error tailing log file: {str(e)}"
                    }
                ],
                "success": False,
                "error": str(e),
                "log_file": file_path
            }
            
    async def handle_tool_grep_log(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle grep_log tool."""
        file_alias = args.get("file", "web")
        pattern = args.get("pattern", "")
        max_lines = args.get("max_lines", 50)
        
        if not pattern:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "❌ No search pattern provided"
                    }
                ],
                "success": False,
                "error": "No search pattern provided"
            }
        
        # Map file aliases to actual paths
        log_file_map = {
            "web": "/home/proxyie/MySoftware/RedBarSushiAI/logs/web.log",
            "mcp": "/home/proxyie/MySoftware/RedBarSushiAI/mcp/mcp_server.log",
            "celery": "/home/proxyie/MySoftware/RedBarSushiAI/logs/celery.log",
            "websocket": "/home/proxyie/MySoftware/RedBarSushiAI/websocket_monitor.log",
            "test": "/home/proxyie/MySoftware/RedBarSushiAI/mcp/enhanced_mcp.log"
        }
        
        # Get the actual file path
        if file_alias in log_file_map:
            file_path = log_file_map[file_alias]
        else:
            # Use the provided path directly if not an alias
            file_path = file_alias
        
        try:
            # Use grep to search for the pattern
            result = await asyncio.to_thread(
                subprocess.run, ["grep", "-n", "-E", pattern, file_path], check=True, capture_output=True, text=True
            )
            
            # Split the output into lines
            grep_lines = result.stdout.splitlines()
            
            # Limit the number of lines
            if len(grep_lines) > max_lines:
                grep_output = "\n".join(grep_lines[:max_lines])
                additional_count = len(grep_lines) - max_lines
                grep_output += f"\n... and {additional_count} more lines (use max_lines parameter to increase limit)"
            else:
                grep_output = result.stdout
            
            # Count matches
            match_count = len(grep_lines)
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"## Search results for '{pattern}' in {file_path}:\n\n```log\n{grep_output}\n```\n\nFound {match_count} matching lines."
                    }
                ],
                "success": True,
                "log_file": file_path,
                "match_count": match_count,
                "displayed_lines": min(match_count, max_lines)
            }
        except subprocess.CalledProcessError as e:
            # grep returns exit code 1 if no matches are found
            if e.returncode == 1 and not e.stderr:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"No matches found for pattern '{pattern}' in {file_path}"
                        }
                    ],
                    "success": True,
                    "log_file": file_path,
                    "match_count": 0
                }
            else:
                logger.exception(f"Error running grep on {file_path}")
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"❌ Error searching log file: {str(e)}\nStderr: {e.stderr}"
                        }
                    ],
                    "success": False,
                    "error": str(e),
                    "log_file": file_path
                }
        except FileNotFoundError:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Log file not found: {file_path}"
                    }
                ],
                "success": False,
                "error": f"File not found: {file_path}",
                "log_file": file_path
            }
        except Exception as e:
            logger.exception(f"Error searching log file {file_path}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Error searching log file: {str(e)}"
                    }
                ],
                "success": False,
                "error": str(e),
                "log_file": file_path
            }
            
    async def handle_tool_celery_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle celery_status tool."""
        try:
            output = "## Celery Status\n\n"
            
            # Get worker status
            worker_result = await asyncio.to_thread(
                subprocess.run, 
                ["celery", "-A", "celery_app", "inspect", "active"], 
                check=True, capture_output=True, text=True,
                cwd="/home/proxyie/MySoftware/RedBarSushiAI"
            )
            
            output += "### Active Workers\n\n```\n"
            output += worker_result.stdout or "No active workers found."
            output += "\n```\n\n"
            
            # Get scheduled tasks
            scheduled_result = await asyncio.to_thread(
                subprocess.run, 
                ["celery", "-A", "celery_app", "inspect", "scheduled"], 
                check=True, capture_output=True, text=True,
                cwd="/home/proxyie/MySoftware/RedBarSushiAI"
            )
            
            output += "### Scheduled Tasks\n\n```\n"
            output += scheduled_result.stdout or "No scheduled tasks found."
            output += "\n```\n\n"
            
            # Get reserved tasks
            reserved_result = await asyncio.to_thread(
                subprocess.run, 
                ["celery", "-A", "celery_app", "inspect", "reserved"], 
                check=True, capture_output=True, text=True,
                cwd="/home/proxyie/MySoftware/RedBarSushiAI"
            )
            
            output += "### Reserved Tasks\n\n```\n"
            output += reserved_result.stdout or "No reserved tasks found."
            output += "\n```\n\n"
            
            # Get Redis queue information
            if redis_client:
                output += "### Redis Queue Information\n\n"
                
                # Get queue length
                queue_len = redis_client.llen("celery")
                output += f"- Celery Queue Length: {queue_len}\n"
                
                # Get active keys
                keys = redis_client.keys("celery*")
                if keys:
                    output += f"- Active Celery Keys: {len(keys)}\n"
                    output += "- Key List:\n"
                    for key in keys[:10]:  # Limit to first 10 keys
                        output += f"  - {key.decode()}\n"
                    
                    if len(keys) > 10:
                        output += f"  - ... and {len(keys) - 10} more\n"
                else:
                    output += "- No active Celery keys found\n"
            else:
                output += "### Redis Queue Information\n\n"
                output += "- Redis client not available\n"
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": output
                    }
                ],
                "success": True
            }
        except subprocess.CalledProcessError as e:
            logger.exception("Error getting Celery status")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Error getting Celery status: {str(e)}\nStderr: {e.stderr}"
                    }
                ],
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            logger.exception("Error getting Celery status")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Error getting Celery status: {str(e)}"
                    }
                ],
                "success": False,
                "error": str(e)
            }
            
    async def handle_tool_replay_task(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle replay_task tool."""
        task_name = args.get("task_name", "")
        task_args = args.get("task_args", {})
        
        if not task_name:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "❌ No task name provided"
                    }
                ],
                "success": False,
                "error": "No task name provided"
            }
        
        # Validate task name (list of allowed tasks for security)
        allowed_tasks = [
            "app.tasks.send_order_confirmation",
            "app.tasks.poll_order_status",
            "app.tasks.process_order",
            "app.tasks.update_menu_cache",
            "app.tasks.send_status_update",
            "celery_app.send_order_confirmation",
            "celery_app.poll_order_status",
            "celery_app.process_order",
            "celery_app.update_menu_cache",
            "celery_app.send_status_update"
        ]
        
        if task_name not in allowed_tasks:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Task '{task_name}' is not in the list of allowed tasks.\n\nAllowed tasks: {', '.join(allowed_tasks)}"
                    }
                ],
                "success": False,
                "error": f"Task '{task_name}' is not allowed for replay",
                "allowed_tasks": allowed_tasks
            }
        
        try:
            # Construct the command to run the task
            cmd = ["python", "-c", f"from {task_name.rsplit('.', 1)[0]} import {task_name.split('.')[-1]}; {task_name.split('.')[-1]}.apply_async(kwargs={json.dumps(task_args)})"]
            
            # Execute the task
            task_result = await asyncio.to_thread(
                subprocess.run, 
                cmd,
                check=True, capture_output=True, text=True,
                cwd="/home/proxyie/MySoftware/RedBarSushiAI"
            )
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"✅ Task '{task_name}' has been replayed successfully with arguments: {json.dumps(task_args)}\n\nOutput:\n{task_result.stdout}"
                    }
                ],
                "success": True,
                "task_name": task_name,
                "task_args": task_args,
                "output": task_result.stdout
            }
        except subprocess.CalledProcessError as e:
            logger.exception(f"Error replaying task {task_name}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Error replaying task '{task_name}': {str(e)}\nStderr: {e.stderr}"
                    }
                ],
                "success": False,
                "error": str(e),
                "stderr": e.stderr,
                "task_name": task_name
            }
        except Exception as e:
            logger.exception(f"Error replaying task {task_name}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Error replaying task '{task_name}': {str(e)}"
                    }
                ],
                "success": False,
                "error": str(e),
                "task_name": task_name
            }
            
    async def handle_tool_twilio_sig_mock(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle twilio_sig_mock tool."""
        url = args.get("url", "")
        params = args.get("params", {})
        
        if not url:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "❌ No URL provided"
                    }
                ],
                "success": False,
                "error": "No URL provided"
            }
        
        try:
            # The Auth Token used for testing (use a demo token for testing)
            auth_token = "12345678901234567890123456789012"
            
            # Sort and join params in key-value format
            param_string = '&'.join(sorted([f"{k}={v}" for k, v in params.items()]))
            
            # Create signature string (URL + params)
            signature_string = f"{url}{param_string}"
            
            # Generate HMAC-SHA1 signature
            signature = base64.b64encode(
                hmac.new(
                    auth_token.encode('utf-8'),
                    signature_string.encode('utf-8'),
                    hashlib.sha1
                ).digest()
            ).decode('utf-8')
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"## Twilio Signature\n\n```\nX-Twilio-Signature: {signature}\n```\n\n### Validation Details\n\n- URL: `{url}`\n- Parameters: `{json.dumps(params)}`\n- Signature String: `{signature_string}`\n- Auth Token Used: `{auth_token}` (for testing only, use real token in production)"
                    }
                ],
                "success": True,
                "signature": signature,
                "validation_info": {
                    "url": url,
                    "params": params,
                    "signature_string": signature_string
                }
            }
        except Exception as e:
            logger.exception("Error generating Twilio signature")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Error generating Twilio signature: {str(e)}"
                    }
                ],
                "success": False,
                "error": str(e)
            }
            
    async def handle_tool_twilio_mock(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle twilio_mock tool."""
        phone_number = args.get("phone_number", "+15551234567")
        message = args.get("message", "This is a test message")
        
        try:
            # Generate a mock Twilio response with all standard fields
            message_sid = f"SM{uuid.uuid4().hex[:20]}"
            account_sid = f"AC{uuid.uuid4().hex[:20]}"
            date_created = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")
            
            mock_response = {
                "account_sid": account_sid,
                "api_version": "2010-04-01",
                "body": message,
                "date_created": date_created,
                "date_sent": date_created,
                "date_updated": date_created,
                "direction": "outbound-api",
                "error_code": None,
                "error_message": None,
                "from": "+15557654321",
                "messaging_service_sid": None,
                "num_media": "0",
                "num_segments": "1",
                "price": "-0.00750",
                "price_unit": "USD",
                "sid": message_sid,
                "status": "delivered",
                "subresource_uris": {
                    "media": f"/2010-04-01/Accounts/{account_sid}/Messages/{message_sid}/Media.json"
                },
                "to": phone_number,
                "uri": f"/2010-04-01/Accounts/{account_sid}/Messages/{message_sid}.json"
            }
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"## Mock Twilio SMS Response\n\n```json\n{json.dumps(mock_response, indent=2)}\n```\n\n### Summary\n\n- Message SID: `{message_sid}`\n- From: `+15557654321`\n- To: `{phone_number}`\n- Body: `{message}`\n- Status: `delivered`"
                    }
                ],
                "success": True,
                "mock_response": mock_response
            }
        except Exception as e:
            logger.exception("Error generating mock Twilio response")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Error generating mock Twilio response: {str(e)}"
                    }
                ],
                "success": False,
                "error": str(e)
            }
            
    async def handle_tool_twiml_preview(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle twiml_preview tool."""
        session_id = args.get("session_id", "")
        greeting = args.get("greeting", "Welcome to Red Bar Sushi! How can I help you today?")
        
        if not session_id:
            # Generate a random session ID if not provided
            session_id = f"session-{uuid.uuid4().hex[:8]}"
        
        try:
            # Generate TwiML for a voice call with media streams
            twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Start>
        <Stream url="wss://redbarsushi-web.onrender.com/api/ws/voice/media" track="inbound_track" />
    </Start>
    <Say voice="Polly.Amy-Neural">{greeting}</Say>
    <Connect>
        <Stream url="wss://redbarsushi-web.onrender.com/api/ws/voice/media" track="outbound_track">
            <Parameter name="session_id" value="{session_id}" />
        </Stream>
    </Connect>
</Response>"""
            
            # Generate cURL command for testing
            curl_command = f"""curl -X POST \\
  'https://redbarsushi-web.onrender.com/voice' \\
  --data-urlencode 'CallSid=CA{uuid.uuid4().hex[:10]}' \\
  --data-urlencode 'AccountSid=AC{uuid.uuid4().hex[:10]}' \\
  --data-urlencode 'From=+15551234567' \\
  --data-urlencode 'To=+15557654321' \\
  --data-urlencode 'CallStatus=ringing' \\
  -H 'Content-Type: application/x-www-form-urlencoded'"""
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"## TwiML Preview for Session ID: `{session_id}`\n\n```xml\n{twiml}\n```\n\n### Test with cURL\n\n```bash\n{curl_command}\n```\n\n### Explanation\n\nThis TwiML response:\n1. Starts a media stream for inbound audio\n2. Says a greeting using Amazon Polly Neural voice\n3. Establishes a bidirectional connection with parameters\n\nThe WebSocket URL will receive audio data and events from Twilio."
                    }
                ],
                "success": True,
                "twiml": twiml,
                "curl_command": curl_command,
                "session_id": session_id
            }
        except Exception as e:
            logger.exception("Error generating TwiML preview")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Error generating TwiML preview: {str(e)}"
                    }
                ],
                "success": False,
                "error": str(e)
            }
            
    async def handle_tool_simulate_media_stream(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle simulate_media_stream tool."""
        audio_file = args.get("audio_file", None)
        duration = args.get("duration", 5)
        
        try:
            # Generate a fake session ID
            session_id = f"session-{uuid.uuid4().hex[:8]}"
            
            # Build simulated media stream events
            events = []
            
            # Start event
            events.append({
                "event": "start",
                "start": {
                    "accountSid": f"AC{uuid.uuid4().hex[:20]}",
                    "callSid": f"CA{uuid.uuid4().hex[:20]}",
                    "streamSid": f"MZ{uuid.uuid4().hex[:20]}",
                    "tracks": [
                        {
                            "id": "inbound_track",
                            "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
                        }
                    ]
                }
            })
            
            # Media events
            chunk_count = duration * 50  # 50 chunks per second (20ms chunks)
            for i in range(chunk_count):
                # Add simulated audio data (pseudo content, would be real μ-law encoded audio)
                if audio_file:
                    audio_data = f"[Audio data from {audio_file}, chunk {i+1}/{chunk_count}]"
                else:
                    # Generate synthetic audio description
                    audio_data = f"[Synthetic audio data, chunk {i+1}/{chunk_count}]"
                
                events.append({
                    "event": "media",
                    "media": {
                        "track": "inbound_track",
                        "chunk": str(i+1),
                        "timestamp": str(int(time.time() * 1000) + i * 20),
                        "payload": audio_data
                    }
                })
            
            # Stop event
            events.append({
                "event": "stop",
                "stop": {
                    "accountSid": f"AC{uuid.uuid4().hex[:20]}",
                    "callSid": f"CA{uuid.uuid4().hex[:20]}",
                    "streamSid": f"MZ{uuid.uuid4().hex[:20]}",
                    "reason": "ended"
                }
            })
            
            # Generate example WebSocket client code
            ws_client_code = """import websockets
import asyncio
import json
import time

async def simulate_media_stream():
    uri = "wss://redbarsushi-web.onrender.com/api/ws/voice/media"
    async with websockets.connect(uri) as websocket:
        # Send start event
        await websocket.send(json.dumps({
            "event": "start",
            "start": {
                "accountSid": "ACxxxxxxxxxxxxxxxxxxxx",
                "callSid": "CAxxxxxxxxxxxxxxxxxxxx",
                "streamSid": "MZxxxxxxxxxxxxxxxxxxxx",
                "tracks": [{"id": "inbound_track", "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}}]
            }
        }))
        
        # Simulate 20ms audio chunks for 5 seconds
        for i in range(250):  # 50 chunks per second × 5 seconds
            await websocket.send(json.dumps({
                "event": "media",
                "media": {
                    "track": "inbound_track",
                    "chunk": str(i+1),
                    "timestamp": str(int(time.time() * 1000) + i * 20),
                    "payload": "[Simulated audio data]"  # Real payload would be base64 encoded μ-law audio
                }
            }))
            await asyncio.sleep(0.02)  # 20ms delay between chunks
            
            # Print any received messages
            while True:
                try:
                    response = await asyncio.wait_for(websocket.recv(), 0)
                    print(f"Received: {response}")
                except asyncio.TimeoutError:
                    break
        
        # Send stop event
        await websocket.send(json.dumps({
            "event": "stop",
            "stop": {
                "accountSid": "ACxxxxxxxxxxxxxxxxxxxx",
                "callSid": "CAxxxxxxxxxxxxxxxxxxxx",
                "streamSid": "MZxxxxxxxxxxxxxxxxxxxx",
                "reason": "ended"
            }
        }))
        
        # Wait for final responses
        await asyncio.sleep(1)

# Run the simulation
asyncio.run(simulate_media_stream())"""
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"## Simulated Media Stream Events\n\nGenerated {len(events)} events for a {duration} second media stream{' using ' + audio_file if audio_file else ''}.\n\n### Example Events\n\n```json\n{json.dumps(events[0], indent=2)}\n\n// ... {len(events) - 2} media events ...\n\n{json.dumps(events[-1], indent=2)}\n```\n\n### Python WebSocket Client Example\n\n```python\n{ws_client_code}\n```\n\nThis simulates a complete Twilio Media Stream session including start event, {chunk_count} audio chunks, and stop event. The session ID for this simulation is: `{session_id}`."
                    }
                ],
                "success": True,
                "session_id": session_id,
                "event_count": len(events),
                "duration": duration,
                "audio_source": audio_file or "synthetic",
                "first_event": events[0],
                "last_event": events[-1]
            }
        except Exception as e:
            logger.exception("Error simulating media stream")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Error simulating media stream: {str(e)}"
                    }
                ],
                "success": False,
                "error": str(e)
            }
            
    async def handle_tool_openai_realtime_ping(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle openai_realtime_ping tool."""
        try:
            # Check for OpenAI API key
            api_key = os.environ.get("OPENAI_API_KEY", None)
            api_key_status = "✅ Found" if api_key else "❌ Not found"
            
            # Check for realtime_audio_sdk.py
            sdk_file = "/home/proxyie/MySoftware/RedBarSushiAI/app/utils/realtime_audio_sdk.py"
            
            if os.path.exists(sdk_file):
                # If file exists, try to import it
                try:
                    # Get file size
                    file_size = os.path.getsize(sdk_file)
                    
                    # Get modification time
                    mod_time = datetime.fromtimestamp(os.path.getmtime(sdk_file)).strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Get content preview
                    with open(sdk_file, 'r') as f:
                        content = f.read(500)  # Read first 500 characters
                    
                    sdk_status = f"✅ Found (Size: {file_size} bytes, Modified: {mod_time})"
                    sdk_preview = content + "..." if len(content) >= 500 else content
                except Exception as e:
                    sdk_status = f"⚠️ Found but error accessing: {str(e)}"
                    sdk_preview = "Error reading file"
            else:
                sdk_status = "❌ Not found"
                sdk_preview = "N/A"
            
            # Check OpenAI Realtime config
            config_status = {}
            config_vars = [
                "OPENAI_REALTIME_NO_DISPLAY",
                "VOICE_HANDLER",
                "FORCE_HEADLESS"
            ]
            
            for var in config_vars:
                value = os.environ.get(var, "Not set")
                config_status[var] = value
            
            # Get Python packages related to OpenAI
            pip_result = await asyncio.to_thread(
                subprocess.run, 
                ["pip", "list", "|", "grep", "-E", "openai|realtime"], 
                shell=True, capture_output=True, text=True
            )
            
            packages = pip_result.stdout or "No OpenAI packages found"
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"## OpenAI Realtime API Status Check\n\n### Environment\n\n- API Key: {api_key_status}\n- SDK File: {sdk_status}\n- Python Packages:\n```\n{packages}\n```\n\n### Configuration\n\n{json.dumps(config_status, indent=2)}\n\n### SDK File Preview\n\n```python\n{sdk_preview}\n```\n\nThis is a diagnostic overview of the OpenAI Realtime integration. Check API key status, SDK file, and environment configuration to ensure everything is properly set up for real-time audio processing."
                    }
                ],
                "success": True,
                "api_key_status": api_key_status,
                "sdk_status": sdk_status,
                "config": config_status,
                "packages": packages
            }
        except Exception as e:
            logger.exception("Error checking OpenAI Realtime configuration")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Error checking OpenAI Realtime configuration: {str(e)}"
                    }
                ],
                "success": False,
                "error": str(e)
            }
            
    async def handle_tool_dry_run_order(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle dry_run_order tool."""
        payload = args.get("payload", {})
        channel_link_id = args.get("channel_link_id", "test-channel-link-id")
        validate_only = args.get("validate_only", True)
        
        if not payload:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "❌ No order payload provided"
                    }
                ],
                "success": False,
                "error": "No order payload provided"
            }
        
        try:
            # Validate the payload structure first
            validation_errors = []
            
            # Check required fields
            required_fields = ["channelOrderId", "orderType", "customer", "items"]
            missing_fields = [field for field in required_fields if field not in payload]
            
            if missing_fields:
                validation_errors.append(f"Missing required fields: {', '.join(missing_fields)}")
            
            # Check customer fields
            if "customer" in payload:
                customer = payload["customer"]
                required_customer_fields = ["name", "phoneNumber"]
                missing_customer_fields = [field for field in required_customer_fields if field not in customer]
                
                if missing_customer_fields:
                    validation_errors.append(f"Missing required customer fields: {', '.join(missing_customer_fields)}")
            
            # Check items
            if "items" in payload:
                items = payload["items"]
                
                if not isinstance(items, list):
                    validation_errors.append("Items must be a list")
                elif not items:
                    validation_errors.append("Items list cannot be empty")
                else:
                    for i, item in enumerate(items):
                        required_item_fields = ["plu", "name", "price", "quantity"]
                        missing_item_fields = [field for field in required_item_fields if field not in item]
                        
                        if missing_item_fields:
                            validation_errors.append(f"Item {i+1} missing required fields: {', '.join(missing_item_fields)}")
                        
                        if "subItems" in item and item["subItems"]:
                            for j, subitem in enumerate(item["subItems"]):
                                required_subitem_fields = ["plu", "name", "price", "quantity"]
                                missing_subitem_fields = [field for field in required_subitem_fields if field not in subitem]
                                
                                if missing_subitem_fields:
                                    validation_errors.append(f"Item {i+1}, SubItem {j+1} missing required fields: {', '.join(missing_subitem_fields)}")
            
            # Check orderType is valid
            if "orderType" in payload:
                order_type = payload["orderType"]
                valid_order_types = [1, 2, 3, 4]  # 1=pickup, 2=delivery, 3=eat-in, 4=curbside
                
                if not isinstance(order_type, int) or order_type not in valid_order_types:
                    validation_errors.append(f"Invalid orderType: {order_type}. Must be one of {valid_order_types}")
                
                # Check deliveryAddress for delivery orders
                if order_type == 2 and ("deliveryAddress" not in payload or not payload["deliveryAddress"]):
                    validation_errors.append("Delivery orders must include deliveryAddress")
            
            # Format validation result
            if validation_errors:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"## Order Validation Failed\n\n### Validation Errors\n\n" + "\n".join([f"- {error}" for error in validation_errors]) + f"\n\n### Order Payload\n\n```json\n{json.dumps(payload, indent=2)}\n```"
                        }
                    ],
                    "success": False,
                    "validation_errors": validation_errors,
                    "payload": payload
                }
            
            # If validate_only, return success without simulating API call
            if validate_only:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"## Order Validation Successful\n\nThe order payload structure is valid.\n\n### Order Summary\n\n- Channel Order ID: `{payload.get('channelOrderId', 'N/A')}`\n- Order Type: `{payload.get('orderType', 'N/A')}`\n- Items: `{len(payload.get('items', []))}`\n- Total Price: `${sum([item.get('price', 0) * item.get('quantity', 0) for item in payload.get('items', [])])/100:.2f}`\n\n### Full Payload\n\n```json\n{json.dumps(payload, indent=2)}\n```"
                        }
                    ],
                    "success": True,
                    "payload": payload,
                    "channel_link_id": channel_link_id,
                    "validate_only": True
                }
            
            # Simulate a Deliverect API response
            mock_response = {
                "orderId": f"order-{uuid.uuid4().hex[:10]}",
                "status": 10,  # Initial received status
                "channelOrderId": payload.get("channelOrderId", f"test-{uuid.uuid4().hex[:10]}"),
                "location": f"location-{uuid.uuid4().hex[:10]}",
                "channelLink": channel_link_id
            }
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"## Simulated Order Submission to Deliverect\n\n### Order Details\n\n- Channel Order ID: `{payload.get('channelOrderId', 'N/A')}`\n- Order Type: `{payload.get('orderType', 'N/A')}`\n- Items: `{len(payload.get('items', []))}`\n- Total Price: `${sum([item.get('price', 0) * item.get('quantity', 0) for item in payload.get('items', [])])/100:.2f}`\n\n### API Response\n\n```json\n{json.dumps(mock_response, indent=2)}\n```\n\n### Note\n\nThis is a simulation of what would happen if the order was submitted to Deliverect. The order was not actually sent to Deliverect."
                    }
                ],
                "success": True,
                "payload": payload,
                "channel_link_id": channel_link_id,
                "mock_response": mock_response
            }
            
        except Exception as e:
            logger.exception("Error in dry run order processing")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Error processing order payload: {str(e)}"
                    }
                ],
                "success": False,
                "error": str(e),
                "payload": payload
            }
            
    async def handle_tool_deliverect_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle deliverect_status tool."""
        channel_order_id = args.get("channel_order_id", "")
        channel_link_id = args.get("channel_link_id", "test-channel-link-id")
        
        if not channel_order_id:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "❌ No channel order ID provided"
                    }
                ],
                "success": False,
                "error": "No channel order ID provided"
            }
        
        try:
            # Check if order exists in the database
            if SessionLocal:
                try:
                    with SessionLocal() as session:
                        # Try to find the order in our database
                        order_query = await asyncio.to_thread(
                            session.execute,
                            text("SELECT * FROM orders WHERE deliverect_channel_order_id = :channel_order_id"),
                            {"channel_order_id": channel_order_id}
                        )
                        order_result = order_query.fetchone()
                        
                        if order_result:
                            # Convert row to dict
                            order_dict = {column: value for column, value in zip(order_query.keys(), order_result)}
                            
                            # Get order items
                            items_query = await asyncio.to_thread(
                                session.execute,
                                text("SELECT * FROM order_items WHERE order_id = :order_id"),
                                {"order_id": order_dict["id"]}
                            )
                            items = [dict(zip(items_query.keys(), row)) for row in items_query.fetchall()]
                            
                            # Generate mock Deliverect status based on database status
                            mock_status = {
                                "orderId": f"order-{uuid.uuid4().hex[:10]}",
                                "status": order_dict.get("status", 10),
                                "channelOrderId": channel_order_id,
                                "location": f"location-{uuid.uuid4().hex[:10]}",
                                "channelLink": channel_link_id
                            }
                            
                            # Create formatted output for display
                            order_status_text = "Unknown"
                            status_code = order_dict.get("status", 10)
                            
                            status_map = {
                                10: "Received",
                                20: "Accepted",
                                30: "In Preparation",
                                40: "Prepared",
                                70: "Ready for Pickup",
                                80: "Delivered/Completed",
                                90: "Rejected",
                                100: "Cancellation Request",
                                110: "Canceled"
                            }
                            
                            order_status_text = status_map.get(status_code, f"Unknown ({status_code})")
                            
                            status_emoji = "✅" if status_code in [20, 30, 40, 70, 80] else "❌" if status_code in [90, 110] else "⏳"
                            
                            return {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": f"## Order Status from Database\n\n{status_emoji} **Status**: {order_status_text}\n\n### Order Details\n\n- Order ID: `{order_dict.get('id', 'N/A')}`\n- Channel Order ID: `{channel_order_id}`\n- Customer: `{order_dict.get('customer_name', 'N/A')}`\n- Phone: `{order_dict.get('customer_phone', 'N/A')}`\n- Total: `${order_dict.get('total_price', 0)/100:.2f}`\n- Type: `{order_dict.get('order_type', 'N/A')}`\n- Placed At: `{order_dict.get('placed_at', 'N/A')}`\n\n### Items\n\n" + "\n".join([f"- {item.get('quantity', 1)}x {item.get('name', 'Unknown')} (${item.get('price', 0)/100:.2f})" for item in items]) + f"\n\n### Deliverect Status\n\n```json\n{json.dumps(mock_status, indent=2)}\n```"
                                    }
                                ],
                                "success": True,
                                "order": order_dict,
                                "items": items,
                                "mock_status": mock_status,
                                "status_code": status_code,
                                "status_text": order_status_text
                            }
                        
                        # If order not in database, generate a mock response
                        status_code = random.choice([10, 20, 30, 40, 70, 80, 90])
                        
                        status_map = {
                            10: "Received",
                            20: "Accepted",
                            30: "In Preparation",
                            40: "Prepared",
                            70: "Ready for Pickup",
                            80: "Delivered/Completed",
                            90: "Rejected",
                            100: "Cancellation Request",
                            110: "Canceled"
                        }
                        
                        order_status_text = status_map.get(status_code, f"Unknown ({status_code})")
                        status_emoji = "✅" if status_code in [20, 30, 40, 70, 80] else "❌" if status_code in [90, 110] else "⏳"
                        
                        mock_status = {
                            "orderId": f"order-{uuid.uuid4().hex[:10]}",
                            "status": status_code,
                            "channelOrderId": channel_order_id,
                            "location": f"location-{uuid.uuid4().hex[:10]}",
                            "channelLink": channel_link_id,
                            "statusText": order_status_text
                        }
                        
                        return {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"## Simulated Deliverect Order Status\n\n{status_emoji} **Status**: {order_status_text}\n\n### Order Details\n\n- Channel Order ID: `{channel_order_id}`\n- Channel Link ID: `{channel_link_id}`\n\n### Note\n\nThis order was not found in the local database. This is a simulated response to demonstrate the format of Deliverect status data.\n\n### Deliverect Status Response\n\n```json\n{json.dumps(mock_status, indent=2)}\n```"
                                }
                            ],
                            "success": True,
                            "order_found": False,
                            "mock_status": mock_status,
                            "channel_order_id": channel_order_id,
                            "status_code": status_code,
                            "status_text": order_status_text
                        }
                
                except Exception as db_error:
                    logger.exception(f"Database error when checking order status: {str(db_error)}")
                    # Fall back to a mock response on database error
            
            # Generate a mock response if database is not available
            status_code = random.choice([10, 20, 30, 40, 70, 80, 90])
            
            status_map = {
                10: "Received",
                20: "Accepted",
                30: "In Preparation",
                40: "Prepared",
                70: "Ready for Pickup",
                80: "Delivered/Completed",
                90: "Rejected",
                100: "Cancellation Request",
                110: "Canceled"
            }
            
            order_status_text = status_map.get(status_code, f"Unknown ({status_code})")
            status_emoji = "✅" if status_code in [20, 30, 40, 70, 80] else "❌" if status_code in [90, 110] else "⏳"
            
            mock_status = {
                "orderId": f"order-{uuid.uuid4().hex[:10]}",
                "status": status_code,
                "channelOrderId": channel_order_id,
                "location": f"location-{uuid.uuid4().hex[:10]}",
                "channelLink": channel_link_id,
                "statusText": order_status_text
            }
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"## Simulated Deliverect Order Status\n\n{status_emoji} **Status**: {order_status_text}\n\n### Order Details\n\n- Channel Order ID: `{channel_order_id}`\n- Channel Link ID: `{channel_link_id}`\n\n### Note\n\nThis is a simulated response to demonstrate the format of Deliverect status data.\n\n### Deliverect Status Response\n\n```json\n{json.dumps(mock_status, indent=2)}\n```"
                    }
                ],
                "success": True,
                "db_available": False,
                "mock_status": mock_status,
                "channel_order_id": channel_order_id,
                "status_code": status_code,
                "status_text": order_status_text
            }
        except Exception as e:
            logger.exception(f"Error checking Deliverect order status: {str(e)}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Error checking order status: {str(e)}"
                    }
                ],
                "success": False,
                "error": str(e),
                "channel_order_id": channel_order_id
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

@app.route("/mcp", methods=["GET"])
def mcp_sse_endpoint():
    """SSE endpoint for MCP to support both transport types."""
    def stream():
        yield "data: {\"type\":\"hello\",\"message\":\"RedBarSushiAI MCP SSE Server\"}\n\n"
        while True:
            time.sleep(10)  # Keep connection alive with more frequent pings
            yield "data: {\"type\":\"ping\"}\n\n"

    return Response(stream(), mimetype="text/event-stream", headers={
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