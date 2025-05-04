#!/usr/bin/env python3
"""
Fixed Simple MCP Server for testing the staging environment
"""
import json
import sys
import subprocess
import os
import logging
from datetime import datetime

# Setup logging
LOG_FILE = "/home/proxyie/MySoftware/RedBarSushiAI/fixed_simple_mcp.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("fixed-simple-mcp")

# Initialize the log file
with open(LOG_FILE, "w") as f:
    f.write(f"Fixed Simple MCP Server started at {datetime.now()}\n")

class MCPServer:
    """MCP Server for testing staging environment"""
    
    def process_request(self, request_str):
        """Process a single MCP request"""
        logger.info(f"Received: {request_str}")
        
        try:
            # Parse the request
            request = json.loads(request_str)
            
            # Extract method and ID
            method = request.get("method")
            request_id = request.get("id")
            
            # Log method and ID
            logger.info(f"Method: {method}, ID: {request_id}")
            
            # Process the request based on method
            if method == "initialize":
                return self.handle_initialize(request_id)
            elif method == "tools/list":
                return self.handle_tools_list(request_id)
            elif method == "tools/call":
                name = request.get("params", {}).get("name")
                arguments = request.get("params", {}).get("arguments", {})
                return self.handle_tools_call(request_id, name, arguments)
            else:
                # Default response for unknown methods
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {}
                }
                
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id if 'request_id' in locals() else None,
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
    
    def handle_initialize(self, request_id):
        """Handle initialize request"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "StagingTestMCP",
                    "version": "1.0.0"
                }
            }
        }
    
    def handle_tools_list(self, request_id):
        """Handle tools/list request"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": "run_test",
                        "description": "Run tests on the staging environment",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "test_type": {
                                    "type": "string",
                                    "description": "Type of test to run (basic, voice, menu, order, all)"
                                }
                            },
                            "required": ["test_type"]
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
    
    def handle_tools_call(self, request_id, name, arguments):
        """Handle tools/call request"""
        logger.info(f"Tool call: {name} with arguments: {arguments}")
        
        if name == "echo":
            message = arguments.get("message", "")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{
                        "type": "text",
                        "text": message
                    }]
                }
            }
        elif name == "run_test":
            test_type = arguments.get("test_type", "basic")
            return self.run_test(request_id, test_type)
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool: {name}"
                }
            }
    
    def run_test(self, request_id, test_type):
        """Run a test on the staging environment"""
        logger.info(f"Running test: {test_type}")
        
        try:
            # Run the test command
            script_path = "/home/proxyie/MySoftware/RedBarSushiAI/test_staging_e2e.sh"
            cmd = f"bash {script_path} {test_type}"
            logger.info(f"Running command: {cmd}")
            
            # Run with full output capturing
            process = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            # Get the output
            output = process.stdout.strip()
            if not output and process.stderr:
                output = process.stderr.strip()
            
            # Add test execution details
            output_with_details = f"Test Type: {test_type}\n"
            output_with_details += f"Exit Code: {process.returncode}\n"
            output_with_details += f"Status: {'Successful' if process.returncode == 0 else 'Failed'}\n\n"
            output_with_details += output
            
            # Highlight the result in the output
            if process.returncode == 0:
                output_with_details += "\n\n✅ ALL TESTS PASSED SUCCESSFULLY! ✅"
            else:
                output_with_details += "\n\n❌ TESTS FAILED - SEE OUTPUT FOR DETAILS ❌"
            
            # Format in the correct structure for Claude Code MCP tools
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{
                        "type": "text",
                        "text": output_with_details or "No output from test execution"
                    }]
                }
            }
        except Exception as e:
            logger.error(f"Error running test: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"Error running test: {str(e)}"
                }
            }

def main():
    """Main entry point for the MCP server"""
    server = MCPServer()
    
    # Process requests from stdin and send responses to stdout
    logger.info("Server started, waiting for requests...")
    
    for line in sys.stdin:
        try:
            line = line.strip()
            if not line:
                continue
                
            # Process the request
            response = server.process_request(line)
            
            # Send the response if there is one
            if response:
                json_response = json.dumps(response)
                logger.info(f"Sending response: {json_response}")
                print(json_response, flush=True)
                
        except Exception as e:
            logger.error(f"Unhandled error: {e}")

if __name__ == "__main__":
    main()