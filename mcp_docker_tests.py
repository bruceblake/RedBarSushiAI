#!/usr/bin/env python3
"""
MCP Server with Docker Integration Test Support for RedBarSushiAI
"""
import json
import sys
import subprocess
import os
import logging
import time
from datetime import datetime

# Setup logging
LOG_FILE = "/home/proxyie/MySoftware/RedBarSushiAI/mcp_docker_tests.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp-docker-tests")

# Initialize the log file
with open(LOG_FILE, "w") as f:
    f.write(f"MCP Docker Tests Server started at {datetime.now()}\n")

class DockerMCPServer:
    """MCP Server with Docker support for RedBarSushiAI testing"""
    
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
                    "name": "DockerTestMCP",
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
            test_type = arguments.get("test_type", "integration")
            return self.docker_start(request_id, test_type)
        elif name == "docker_stop":
            test_type = arguments.get("test_type", "integration")
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
    
    def docker_start(self, request_id, test_type):
        """Start Docker containers for testing"""
        logger.info(f"Starting Docker containers for {test_type} tests")
        
        try:
            if test_type == "integration":
                # Start containers for integration tests
                cmd = "docker-compose -f /home/proxyie/MySoftware/RedBarSushiAI/tests/docker-compose-test.yml up -d"
            elif test_type == "e2e":
                # Start containers for E2E tests (if available)
                cmd = "docker-compose -f /home/proxyie/MySoftware/RedBarSushiAI/tests/docker-compose-e2e.yml up -d"
            elif test_type == "all":
                # Start all containers
                cmd1 = "docker-compose -f /home/proxyie/MySoftware/RedBarSushiAI/tests/docker-compose-test.yml up -d"
                process1 = subprocess.run(cmd1, shell=True, capture_output=True, text=True)
                
                cmd2 = "docker-compose -f /home/proxyie/MySoftware/RedBarSushiAI/tests/docker-compose-e2e.yml up -d"
                process2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True)
                
                output = f"Integration Containers:\n{process1.stdout}\n\nE2E Containers:\n{process2.stdout}"
                
                if process1.returncode == 0 and process2.returncode == 0:
                    status = "✅ ALL CONTAINERS STARTED SUCCESSFULLY"
                else:
                    status = "❌ SOME CONTAINERS FAILED TO START"
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{
                            "type": "text",
                            "text": f"{output}\n\n{status}"
                        }]
                    }
                }
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": f"Invalid test_type: {test_type}. Must be 'integration', 'e2e', or 'all'"
                    }
                }
            
            # Run the command to start containers
            process = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            # Get the output
            output = process.stdout.strip()
            if not output and process.stderr:
                output = process.stderr.strip()
            
            # Wait for containers to be healthy
            time.sleep(3)
            
            # Check container status
            status_cmd = "docker ps"
            status_process = subprocess.run(status_cmd, shell=True, capture_output=True, text=True)
            status_output = status_process.stdout.strip()
            
            combined_output = f"Container Start Output:\n{output}\n\nContainer Status:\n{status_output}"
            
            # Format in the correct structure for Claude Code MCP tools
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{
                        "type": "text",
                        "text": combined_output
                    }]
                }
            }
        except Exception as e:
            logger.error(f"Error starting Docker containers: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"Error starting Docker containers: {str(e)}"
                }
            }
    
    def docker_stop(self, request_id, test_type):
        """Stop Docker containers"""
        logger.info(f"Stopping Docker containers for {test_type} tests")
        
        try:
            if test_type == "integration":
                # Stop containers for integration tests
                cmd = "docker-compose -f /home/proxyie/MySoftware/RedBarSushiAI/tests/docker-compose-test.yml down"
            elif test_type == "e2e":
                # Stop containers for E2E tests (if available)
                cmd = "docker-compose -f /home/proxyie/MySoftware/RedBarSushiAI/tests/docker-compose-e2e.yml down"
            elif test_type == "all":
                # Stop all containers
                cmd1 = "docker-compose -f /home/proxyie/MySoftware/RedBarSushiAI/tests/docker-compose-test.yml down"
                process1 = subprocess.run(cmd1, shell=True, capture_output=True, text=True)
                
                cmd2 = "docker-compose -f /home/proxyie/MySoftware/RedBarSushiAI/tests/docker-compose-e2e.yml down"
                process2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True)
                
                output = f"Integration Containers:\n{process1.stdout}\n\nE2E Containers:\n{process2.stdout}"
                
                if process1.returncode == 0 and process2.returncode == 0:
                    status = "✅ ALL CONTAINERS STOPPED SUCCESSFULLY"
                else:
                    status = "❌ SOME CONTAINERS FAILED TO STOP"
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{
                            "type": "text",
                            "text": f"{output}\n\n{status}"
                        }]
                    }
                }
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": f"Invalid test_type: {test_type}. Must be 'integration', 'e2e', or 'all'"
                    }
                }
            
            # Run the command to stop containers
            process = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            # Get the output
            output = process.stdout.strip()
            if not output and process.stderr:
                output = process.stderr.strip()
            
            # Format in the correct structure for Claude Code MCP tools
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{
                        "type": "text",
                        "text": f"Docker containers stopped:\n{output}"
                    }]
                }
            }
        except Exception as e:
            logger.error(f"Error stopping Docker containers: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"Error stopping Docker containers: {str(e)}"
                }
            }
    
    def docker_test(self, request_id, test_file):
        """Run integration tests using Docker"""
        logger.info(f"Running Docker integration test: {test_file}")
        
        try:
            # Use the shell script directly to run the tests as it handles venv setup
            # and other environment issues
            
            # Ensure containers are running first
            docker_ps_cmd = "docker ps | grep 'postgres\\|redis'"
            docker_ps_process = subprocess.run(docker_ps_cmd, shell=True, capture_output=True, text=True)
            
            if not docker_ps_process.stdout.strip():
                # Containers not running, start them
                start_cmd = "docker-compose -f /home/proxyie/MySoftware/RedBarSushiAI/tests/docker-compose-test.yml up -d"
                start_process = subprocess.run(start_cmd, shell=True, capture_output=True, text=True)
                logger.info(f"Started containers: {start_process.stdout}")
                
                # Wait for containers to become healthy
                time.sleep(10)
            
            # Use the run_docker_integration_tests.sh script with non-interactive mode
            if test_file == "all":
                test_cmd = "/home/proxyie/MySoftware/RedBarSushiAI/run_docker_integration_tests.sh -n"
            else:
                test_cmd = f"/home/proxyie/MySoftware/RedBarSushiAI/run_docker_integration_tests.sh -n {test_file}"
            
            # Run the test command
            logger.info(f"Running test command: {test_cmd}")
            process = subprocess.run(test_cmd, shell=True, capture_output=True, text=True)
            
            # Get the output
            output = process.stdout.strip()
            if not output and process.stderr:
                output = process.stderr.strip()
            
            # Format the output with details
            result_output = f"Docker Integration Test: {test_file}\n"
            result_output += f"Exit Code: {process.returncode}\n"
            result_output += f"Status: {'Successful' if process.returncode == 0 else 'Failed'}\n\n"
            result_output += output
            
            # Highlight the result
            if process.returncode == 0:
                result_output += "\n\n✅ DOCKER INTEGRATION TESTS PASSED! ✅"
            else:
                result_output += "\n\n❌ DOCKER INTEGRATION TESTS FAILED - SEE OUTPUT FOR DETAILS ❌"
            
            # Format in the correct structure for Claude Code MCP tools
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{
                        "type": "text",
                        "text": result_output
                    }]
                }
            }
        except Exception as e:
            logger.error(f"Error running Docker integration test: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"Error running Docker integration test: {str(e)}"
                }
            }
    
    def docker_status(self, request_id):
        """Check status of Docker containers"""
        logger.info("Checking Docker container status")
        
        try:
            # Run docker ps to check container status
            cmd = "docker ps"
            process = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            # Get the output
            output = process.stdout.strip()
            if not output:
                output = "No containers running"
            
            # Check for PostgreSQL and Redis containers specifically
            postgres_cmd = "docker ps | grep postgres"
            postgres_process = subprocess.run(postgres_cmd, shell=True, capture_output=True, text=True)
            postgres_running = bool(postgres_process.stdout.strip())
            
            redis_cmd = "docker ps | grep redis"
            redis_process = subprocess.run(redis_cmd, shell=True, capture_output=True, text=True)
            redis_running = bool(redis_process.stdout.strip())
            
            # Check container health
            if postgres_running:
                health_cmd = "docker inspect --format='{{.State.Health.Status}}' $(docker ps -q --filter name=postgres)"
                health_process = subprocess.run(health_cmd, shell=True, capture_output=True, text=True)
                postgres_health = health_process.stdout.strip() or "unknown"
            else:
                postgres_health = "not running"
            
            if redis_running:
                health_cmd = "docker inspect --format='{{.State.Health.Status}}' $(docker ps -q --filter name=redis)"
                health_process = subprocess.run(health_cmd, shell=True, capture_output=True, text=True)
                redis_health = health_process.stdout.strip() or "unknown"
            else:
                redis_health = "not running"
            
            # Format status message
            status_message = "Docker Container Status\n"
            status_message += "======================\n\n"
            status_message += f"PostgreSQL: {'✅' if postgres_running else '❌'} {postgres_health}\n"
            status_message += f"Redis: {'✅' if redis_running else '❌'} {redis_health}\n\n"
            status_message += "All Containers:\n"
            status_message += output
            
            # Format in the correct structure for Claude Code MCP tools
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{
                        "type": "text",
                        "text": status_message
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
    server = DockerMCPServer()
    
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