#!/usr/bin/env python3
"""
Enhanced MCP Server for comprehensive testing of RedBarSushiAI.

This MCP server provides Claude with the ability to execute various
types of tests against the application, including Docker-based
integration tests and full E2E testing.
"""
import json
import sys
import subprocess
import os
import logging
import time
from datetime import datetime
from pathlib import Path

# Set up project paths
PROJECT_ROOT = Path(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = PROJECT_ROOT / "enhanced_mcp.log"

# Setup logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("enhanced-mcp")

# Initialize the log file
with open(LOG_FILE, "w") as f:
    f.write(f"Enhanced MCP Server started at {datetime.now()}\n")


class MCPServer:
    """Enhanced MCP Server for running tests via Docker"""
    
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
                    "name": "RedBarSushiAI-TestMCP",
                    "version": "2.0.0"
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
                    },
                    {
                        "name": "docker_start",
                        "description": "Start Docker containers for testing",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "test_type": {
                                    "type": "string",
                                    "description": "Type of Docker containers to start (integration, e2e, all)"
                                }
                            },
                            "required": ["test_type"]
                        }
                    },
                    {
                        "name": "docker_stop",
                        "description": "Stop Docker containers",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "test_type": {
                                    "type": "string",
                                    "description": "Type of Docker containers to stop (integration, e2e, all)"
                                }
                            },
                            "required": ["test_type"]
                        }
                    },
                    {
                        "name": "docker_test",
                        "description": "Run integration tests using Docker",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "test_file": {
                                    "type": "string",
                                    "description": "Specific test file to run, or 'all' for all integration tests"
                                }
                            },
                            "required": ["test_file"]
                        }
                    },
                    {
                        "name": "docker_status",
                        "description": "Check status of Docker containers",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
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
        elif name == "docker_start":
            test_type = arguments.get("test_type", "all")
            return self.docker_start(request_id, test_type)
        elif name == "docker_stop":
            test_type = arguments.get("test_type", "all")
            return self.docker_stop(request_id, test_type)
        elif name == "docker_test":
            test_file = arguments.get("test_file", "all")
            return self.docker_test(request_id, test_file)
        elif name == "docker_status":
            return self.docker_status(request_id)
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
            script_path = str(PROJECT_ROOT / "test_staging_e2e.sh")
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
    
    def docker_start(self, request_id, test_type):
        """Start Docker containers for testing"""
        logger.info(f"Starting Docker containers for: {test_type}")
        
        try:
            # Determine which docker-compose file to use
            if test_type == "integration":
                compose_file = "tests/docker-compose-test.yml"
            elif test_type == "e2e":
                compose_file = "docker-compose-e2e.yml"
            else:  # all
                # Start both integration and e2e containers
                integration_cmd = f"docker-compose -f tests/docker-compose-test.yml up -d"
                e2e_cmd = f"docker-compose -f docker-compose-e2e.yml up -d"
                
                # Run the commands in sequence
                integration_process = subprocess.run(integration_cmd, shell=True, capture_output=True, text=True)
                logger.info(f"Integration containers: {integration_process.returncode}")
                
                e2e_process = subprocess.run(e2e_cmd, shell=True, capture_output=True, text=True)
                logger.info(f"E2E containers: {e2e_process.returncode}")
                
                # Combine the output
                output = "Starting all containers:\n\n"
                output += "== Integration Containers ==\n"
                output += integration_process.stdout.strip() + "\n"
                if integration_process.stderr:
                    output += integration_process.stderr.strip() + "\n"
                
                output += "\n== E2E Containers ==\n"
                output += e2e_process.stdout.strip() + "\n"
                if e2e_process.stderr:
                    output += e2e_process.stderr.strip() + "\n"
                
                # Wait for containers to be ready
                time.sleep(10)
                
                # Get current status
                status_cmd = "docker ps"
                status_process = subprocess.run(status_cmd, shell=True, capture_output=True, text=True)
                output += "\n== Container Status ==\n"
                output += status_process.stdout.strip()
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{
                            "type": "text",
                            "text": output
                        }]
                    }
                }
            
            # For single environment, use the determined compose file
            cmd = f"docker-compose -f {compose_file} up -d"
            logger.info(f"Running command: {cmd}")
            
            # Run with full output capturing
            process = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            # Get the output
            output = process.stdout.strip()
            if not output and process.stderr:
                output = process.stderr.strip()
            
            # Wait for containers to be ready
            time.sleep(10)
            
            # Get current status
            status_cmd = "docker ps"
            status_process = subprocess.run(status_cmd, shell=True, capture_output=True, text=True)
            output += "\n\n== Container Status ==\n"
            output += status_process.stdout.strip()
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{
                        "type": "text",
                        "text": output or "No output from docker start"
                    }]
                }
            }
        except Exception as e:
            logger.error(f"Error starting Docker: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"Error starting Docker: {str(e)}"
                }
            }
    
    def docker_stop(self, request_id, test_type):
        """Stop Docker containers"""
        logger.info(f"Stopping Docker containers for: {test_type}")
        
        try:
            # Determine which docker-compose file to use
            if test_type == "integration":
                compose_file = "tests/docker-compose-test.yml"
            elif test_type == "e2e":
                compose_file = "docker-compose-e2e.yml"
            else:  # all
                # Stop both integration and e2e containers
                integration_cmd = f"docker-compose -f tests/docker-compose-test.yml down -v"
                e2e_cmd = f"docker-compose -f docker-compose-e2e.yml down -v"
                
                # Run the commands in sequence
                integration_process = subprocess.run(integration_cmd, shell=True, capture_output=True, text=True)
                e2e_process = subprocess.run(e2e_cmd, shell=True, capture_output=True, text=True)
                
                # Combine the output
                output = "Stopping all containers:\n\n"
                output += "== Integration Containers ==\n"
                output += integration_process.stdout.strip() + "\n"
                if integration_process.stderr:
                    output += integration_process.stderr.strip() + "\n"
                
                output += "\n== E2E Containers ==\n"
                output += e2e_process.stdout.strip() + "\n"
                if e2e_process.stderr:
                    output += e2e_process.stderr.strip() + "\n"
                
                # Get current status
                status_cmd = "docker ps"
                status_process = subprocess.run(status_cmd, shell=True, capture_output=True, text=True)
                output += "\n== Current Container Status ==\n"
                output += status_process.stdout.strip()
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{
                            "type": "text",
                            "text": output
                        }]
                    }
                }
            
            # For single environment, use the determined compose file
            cmd = f"docker-compose -f {compose_file} down -v"
            logger.info(f"Running command: {cmd}")
            
            # Run with full output capturing
            process = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            # Get the output
            output = process.stdout.strip()
            if not output and process.stderr:
                output = process.stderr.strip()
            
            # Get current status
            status_cmd = "docker ps"
            status_process = subprocess.run(status_cmd, shell=True, capture_output=True, text=True)
            output += "\n\n== Current Container Status ==\n"
            output += status_process.stdout.strip()
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{
                        "type": "text",
                        "text": output or "No output from docker stop"
                    }]
                }
            }
        except Exception as e:
            logger.error(f"Error stopping Docker: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"Error stopping Docker: {str(e)}"
                }
            }
    
    def docker_test(self, request_id, test_file):
        """Run integration tests using Docker"""
        logger.info(f"Running Docker integration test: {test_file}")
        
        try:
            if test_file == "all":
                # Run all tests
                cmd = f"./run_docker_integration_tests.sh -v"
            else:
                # Run specific test file
                test_path = test_file
                if not test_file.startswith("tests/"):
                    test_path = f"tests/integration/{test_file}"
                
                cmd = f"docker-compose -f tests/docker-compose-test.yml run --rm test-runner pytest {test_path} -v"
            
            logger.info(f"Running command: {cmd}")
            
            # Run with full output capturing
            process = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            # Get the output
            output = process.stdout.strip()
            if not output and process.stderr:
                output = process.stderr.strip()
            
            # Add test execution details
            output_with_details = f"Test File(s): {test_file}\n"
            output_with_details += f"Exit Code: {process.returncode}\n"
            output_with_details += f"Status: {'Successful' if process.returncode == 0 else 'Failed'}\n\n"
            output_with_details += output
            
            # Highlight the result in the output
            if process.returncode == 0:
                output_with_details += "\n\n✅ DOCKER TESTS PASSED SUCCESSFULLY! ✅"
            else:
                output_with_details += "\n\n❌ DOCKER TESTS FAILED - SEE OUTPUT FOR DETAILS ❌"
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{
                        "type": "text",
                        "text": output_with_details or "No output from docker test"
                    }]
                }
            }
        except Exception as e:
            logger.error(f"Error running Docker test: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"Error running Docker test: {str(e)}"
                }
            }
    
    def docker_status(self, request_id):
        """Check status of Docker containers"""
        logger.info("Checking Docker container status")
        
        try:
            # Check running containers
            ps_cmd = "docker ps"
            ps_process = subprocess.run(ps_cmd, shell=True, capture_output=True, text=True)
            
            # Check container resources
            stats_cmd = "docker stats --no-stream"
            stats_process = subprocess.run(stats_cmd, shell=True, capture_output=True, text=True)
            
            # Get Docker Compose status for integration tests
            integration_cmd = "docker-compose -f tests/docker-compose-test.yml ps"
            integration_process = subprocess.run(integration_cmd, shell=True, capture_output=True, text=True)
            
            # Get Docker Compose status for E2E tests
            e2e_cmd = "docker-compose -f docker-compose-e2e.yml ps"
            e2e_process = subprocess.run(e2e_cmd, shell=True, capture_output=True, text=True)
            
            # Combine the output
            output = "== Docker Container Status ==\n\n"
            output += ps_process.stdout.strip() + "\n\n"
            
            output += "== Container Resources ==\n\n"
            output += stats_process.stdout.strip() + "\n\n"
            
            output += "== Integration Test Containers ==\n\n"
            output += integration_process.stdout.strip() + "\n\n"
            
            output += "== E2E Test Containers ==\n\n"
            output += e2e_process.stdout.strip()
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{
                        "type": "text",
                        "text": output or "No Docker containers found"
                    }]
                }
            }
        except Exception as e:
            logger.error(f"Error checking Docker status: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"Error checking Docker status: {str(e)}"
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