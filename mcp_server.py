#!/usr/bin/env python3
"""
Simple MCP server for Claude Code integration.

This server listens on localhost:8080 and handles Claude Code MCP commands.
"""
import argparse
import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Load the MCP configuration
CONFIG_FILE = Path(__file__).parent / ".claude-mcp.json"
with open(CONFIG_FILE, "r") as f:
    MCP_CONFIG = json.load(f)

class McpHandler(BaseHTTPRequestHandler):
    """HTTP handler for MCP requests."""
    
    def _send_json_response(self, data, status=200):
        """Send a JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests."""
        # Parse the path
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)
        
        # Handle /healthcheck endpoint
        if path == "/healthcheck":
            self._send_json_response({
                "status": "ok",
                "message": "MCP server is running"
            })
            return
        
        # Handle /environment endpoint
        if path == "/environment":
            self._send_json_response({
                "environment": "staging",
                "version": "1.0.0"
            })
            return
        
        # Handle /tests endpoint
        if path == "/tests":
            env_name = query.get("environment", ["staging"])[0]
            env_config = MCP_CONFIG.get("environments", {}).get(env_name, {})
            tests = env_config.get("tests", {})
            
            self._send_json_response({
                "tests": [
                    {
                        "name": name,
                        "description": test.get("description", ""),
                        "command": test.get("command", "")
                    }
                    for name, test in tests.items()
                ]
            })
            return
        
        # Handle /services endpoint
        if path == "/services":
            env_name = query.get("environment", ["staging"])[0]
            env_config = MCP_CONFIG.get("environments", {}).get(env_name, {})
            services = env_config.get("services", {})
            
            self._send_json_response({
                "services": [
                    {
                        "name": name,
                        "url": service.get("url", ""),
                        "type": service.get("type", ""),
                        "health_check": service.get("health_check", "")
                    }
                    for name, service in services.items()
                ]
            })
            return
        
        # Handle unknown endpoints
        self._send_json_response({
            "error": "Endpoint not found"
        }, status=404)
    
    def do_POST(self):
        """Handle POST requests."""
        # Parse the path
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # Read the request body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode()
        data = json.loads(body) if content_length > 0 else {}
        
        # Handle /run-test endpoint
        if path == "/run-test":
            env_name = data.get("environment", "staging")
            test_name = data.get("test", "")
            
            env_config = MCP_CONFIG.get("environments", {}).get(env_name, {})
            tests = env_config.get("tests", {})
            
            if test_name not in tests:
                self._send_json_response({
                    "error": f"Test '{test_name}' not found for environment '{env_name}'."
                }, status=404)
                return
            
            test_config = tests[test_name]
            command = test_config["command"]
            
            # Run the command
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                self._send_json_response({
                    "success": result.returncode == 0,
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr
                })
            except subprocess.TimeoutExpired:
                self._send_json_response({
                    "success": False,
                    "error": "Command timed out after 300 seconds."
                }, status=500)
            except Exception as e:
                self._send_json_response({
                    "success": False,
                    "error": str(e)
                }, status=500)
            
            return
        
        # Handle /restart-service endpoint
        if path == "/restart-service":
            env_name = data.get("environment", "staging")
            service_name = data.get("service", "")
            
            env_config = MCP_CONFIG.get("environments", {}).get(env_name, {})
            services = env_config.get("services", {})
            
            if service_name not in services:
                self._send_json_response({
                    "error": f"Service '{service_name}' not found for environment '{env_name}'."
                }, status=404)
                return
            
            # Get credentials
            credentials = env_config.get("credentials", {}).get("render", {})
            api_key = credentials.get("api_key", os.environ.get("RENDER_API_KEY"))
            service_id = credentials.get("service_id", os.environ.get("RENDER_SERVICE_ID"))
            
            if not api_key or not service_id:
                self._send_json_response({
                    "error": "Render API key or service ID not found."
                }, status=500)
                return
            
            # Replace environment variables in the API key and service ID
            api_key = api_key.replace("${RENDER_API_KEY}", os.environ.get("RENDER_API_KEY", ""))
            service_id = service_id.replace("${RENDER_SERVICE_ID}", os.environ.get("RENDER_SERVICE_ID", ""))
            
            # Make the API request to restart the service
            restart_url = f"https://api.render.com/v1/services/{service_id}/restart"
            headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            
            try:
                import requests
                response = requests.post(restart_url, headers=headers, timeout=30)
                
                if response.status_code == 200 or response.status_code == 201 or response.status_code == 202:
                    self._send_json_response({
                        "success": True,
                        "message": f"Service '{service_name}' restart initiated successfully."
                    })
                else:
                    self._send_json_response({
                        "success": False,
                        "error": f"Error restarting service. Status code: {response.status_code}",
                        "response": response.text
                    }, status=500)
            except Exception as e:
                self._send_json_response({
                    "success": False,
                    "error": str(e)
                }, status=500)
            
            return
        
        # Handle /fix-issue endpoint
        if path == "/fix-issue":
            issue_type = data.get("issue_type", "")
            
            fix_strategies = MCP_CONFIG.get("fix_strategies", {})
            if issue_type not in fix_strategies:
                self._send_json_response({
                    "error": f"Fix strategy for issue type '{issue_type}' not found."
                }, status=404)
                return
            
            strategy = fix_strategies[issue_type]
            command = strategy.get("command")
            if not command:
                self._send_json_response({
                    "error": f"No command defined for fix strategy '{issue_type}'."
                }, status=500)
                return
            
            # Replace environment variables in the command
            for key, value in os.environ.items():
                command = command.replace(f"${{{key}}}", value)
            
            # Run the command
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                self._send_json_response({
                    "success": result.returncode == 0,
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr
                })
            except subprocess.TimeoutExpired:
                self._send_json_response({
                    "success": False,
                    "error": "Command timed out after 300 seconds."
                }, status=500)
            except Exception as e:
                self._send_json_response({
                    "success": False,
                    "error": str(e)
                }, status=500)
            
            return
        
        # Handle unknown endpoints
        self._send_json_response({
            "error": "Endpoint not found"
        }, status=404)


def run_server(port=8080):
    """Run the MCP server."""
    server_address = ("", port)
    httpd = HTTPServer(server_address, McpHandler)
    print(f"Starting MCP server on port {port}...")
    httpd.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MCP server for Claude Code integration")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    args = parser.parse_args()
    
    run_server(args.port)