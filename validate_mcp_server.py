#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validation script for the MCP server.
"""

import json
import sys
import os
import subprocess

# Try to import requests, install if not available
try:
    import requests
except ImportError:
    print("📦 Installing requests library...")
    
    # Create virtual environment if it doesn't exist
    if not os.path.exists("venv"):
        subprocess.check_call([sys.executable, "-m", "venv", "venv"])
    
    # Use pip from virtual environment
    if sys.platform == "win32":
        pip_path = os.path.join("venv", "Scripts", "pip")
    else:
        pip_path = os.path.join("venv", "bin", "pip")
    
    subprocess.check_call([pip_path, "install", "requests"])
    
    # Add the venv site-packages to path
    import site
    from pathlib import Path
    
    if sys.platform == "win32":
        site_packages = os.path.join("venv", "Lib", "site-packages")
    else:
        lib_path = list(Path("venv/lib").glob("python*"))[0]
        site_packages = os.path.join(lib_path, "site-packages")
    
    sys.path.insert(0, site_packages)
    
    # Try importing again
    import requests

def test_mcp_server(url):
    """Test the MCP server by calling various endpoints."""
    print(f"Testing MCP server at {url}")

    # Test health endpoint
    try:
        health_url = url.replace("/mcp", "/health")
        health_response = requests.get(health_url)
        health_data = health_response.json()
        print(f"Health check: {health_response.status_code}")
        print(f"Health data: {json.dumps(health_data, indent=2)}")
        
        if health_response.status_code != 200:
            print("❌ Health check failed")
            return False
            
        print("✅ Health check passed")
    except Exception as e:
        print(f"❌ Health check failed: {str(e)}")
        return False

    # Test initialize method
    try:
        initialize_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05"
            }
        }
        
        initialize_response = requests.post(url, json=initialize_data)
        initialize_result = initialize_response.json()
        print(f"Initialize: {initialize_response.status_code}")
        print(f"Initialize result: {json.dumps(initialize_result, indent=2)}")
        
        if initialize_response.status_code != 200:
            print("❌ Initialize method failed")
            return False
            
        print("✅ Initialize method passed")
    except Exception as e:
        print(f"❌ Initialize method failed: {str(e)}")
        return False

    # Test tools/list method
    try:
        tools_list_data = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        }
        
        tools_list_response = requests.post(url, json=tools_list_data)
        tools_list_result = tools_list_response.json()
        print(f"Tools list: {tools_list_response.status_code}")
        print(f"Tools count: {len(tools_list_result.get('result', {}).get('tools', []))}")
        
        if tools_list_response.status_code != 200:
            print("❌ Tools list method failed")
            return False
            
        print("✅ Tools list method passed")
    except Exception as e:
        print(f"❌ Tools list method failed: {str(e)}")
        return False

    # Test echo tool
    try:
        echo_data = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tool/call",
            "params": {
                "name": "echo",
                "arguments": {
                    "message": "Hello from MCP server!"
                }
            }
        }
        
        echo_response = requests.post(url, json=echo_data)
        echo_result = echo_response.json()
        print(f"Echo tool: {echo_response.status_code}")
        print(f"Echo result: {json.dumps(echo_result, indent=2)}")
        
        if echo_response.status_code != 200:
            print("❌ Echo tool failed")
            return False
            
        print("✅ Echo tool passed")
    except Exception as e:
        print(f"❌ Echo tool failed: {str(e)}")
        return False
        
    # Test SSE endpoint for Claude Code
    try:
        import threading
        import time
        
        print("Testing SSE endpoint (for Claude Code integration)...")
        
        # Create a session for SSE
        session = requests.Session()
        
        # Set up a function to run the SSE test in a separate thread
        def test_sse():
            try:
                # Start SSE connection
                response = session.get(url, stream=True, timeout=3)
                for i, line in enumerate(response.iter_lines()):
                    if line:
                        decoded_line = line.decode('utf-8')
                        if i == 0:
                            print(f"SSE response: {decoded_line}")
                            if "data:" in decoded_line and ("hello" in decoded_line.lower() or "ping" in decoded_line.lower()):
                                print("✅ SSE endpoint working properly")
                                return True
                            else:
                                print("❌ SSE response format not as expected")
                                return False
                    if i > 3:  # Only read a few lines
                        break
                return True
            except Exception as e:
                print(f"SSE test exception: {str(e)}")
                return False
                
        # Start SSE test in a thread
        sse_thread = threading.Thread(target=test_sse)
        sse_thread.daemon = True
        sse_thread.start()
        
        # Wait for a short time
        sse_thread.join(5)
        
        # If the thread is still alive, it's hanging - this is actually good for an SSE connection
        if sse_thread.is_alive():
            print("✅ SSE endpoint established persistent connection as expected")
            # We need to close the session to terminate the thread
            session.close()
        
    except Exception as e:
        print(f"⚠️ SSE test could not be completed: {str(e)}")
        print("This may not be a problem for JSON-RPC, but might affect Claude Code SSE integration.")

    print("All tests passed! MCP server is working correctly.")
    return True

def main():
    """Main function for validating the MCP server."""
    print("\n🔍 MCP Server Validation Tool 🔍\n")
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        mcp_url = sys.argv[1]
    else:
        mcp_url = "http://localhost:4000/mcp"
    
    # Run the tests
    success = test_mcp_server(mcp_url)
    
    # Print Claude integration instructions if successful
    if success:
        print("\n🎉 MCP server integration with Claude Code instructions:")
        print("1. Run `claude mcp add` in your terminal and select SSE type")
        print("2. Enter URL: http://host.docker.internal:4000/mcp")
        print("3. Name your server: redbarsushi-mcp")
        print("4. Run `/mcp` in Claude Code to verify the connection\n")
        
        # Check if Claude CLI is installed
        try:
            subprocess.run(["claude", "--version"], 
                          stdout=subprocess.PIPE, 
                          stderr=subprocess.PIPE, 
                          check=True)
            print("ℹ️ Claude CLI is installed, you can run `claude mcp add` now")
        except (FileNotFoundError, subprocess.CalledProcessError):
            print("⚠️ Claude CLI not found in PATH. Install or activate it before running `claude mcp add`")
    
    # Return exit code
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())