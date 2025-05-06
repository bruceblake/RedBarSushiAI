#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validation script for the local MCP server environment.
Runs through a series of checks to ensure the environment is working correctly.
"""

import argparse
import json
import requests
import sys
import time
import logging
from typing import Dict, Any, Optional, List, Union

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_validation")

def check_service(url: str, description: str) -> bool:
    """
    Check if a service is available at the given URL.
    
    Args:
        url: The URL to check
        description: A description of the service
        
    Returns:
        True if the service is available, False otherwise
    """
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f"✅ {description} is available")
            return True
        else:
            print(f"❌ {description} returned status code {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ {description} is not available: {str(e)}")
        return False

def call_mcp_method(base_url: str, method: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Call a method on the MCP server.
    
    Args:
        base_url: The base URL of the MCP server
        method: The method to call
        params: The parameters to pass to the method
        
    Returns:
        The JSON-RPC response, or None if the request failed
    """
    if params is None:
        params = {}
    
    url = f"{base_url}/mcp"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to call MCP method {method}: {str(e)}")
        return None

def main():
    parser = argparse.ArgumentParser(description='Validate local MCP server setup.')
    parser.add_argument('--host', default='localhost', help='Host where MCP server is running')
    parser.add_argument('--port', default=4000, type=int, help='Port where MCP server is running')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    args = parser.parse_args()
    
    # Enable verbose logging if requested
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    base_url = f"http://{args.host}:{args.port}"
    
    print("\n----- Local MCP Server Validation -----\n")
    
    # Step 1: Check if MCP server is running
    print("Checking if MCP server is running...")
    if not check_service(f"{base_url}/health", "MCP server health endpoint"):
        sys.exit(1)
    
    # Step 2: Check MCP echo method
    print("\nTesting MCP echo method...")
    echo_result = call_mcp_method(base_url, "tool/call", {
        "name": "echo",
        "arguments": {
            "message": "Hello, MCP!"
        }
    })
    if echo_result and "result" in echo_result:
        print("✅ MCP echo method working")
    else:
        print("❌ MCP echo method failed")
        sys.exit(1)
    
    # Step 3: Check MCP run_test basic method
    print("\nTesting MCP run_test basic method...")
    test_result = call_mcp_method(base_url, "tool/call", {
        "name": "run_test",
        "arguments": {
            "test_type": "basic"
        }
    })
    if test_result and "result" in test_result and test_result["result"].get("success") == True:
        print("✅ MCP run_test basic method working")
    else:
        print("❌ MCP run_test basic method failed")
        sys.exit(1)
    
    # Step 4: Check database connection
    print("\nTesting database connection through MCP...")
    db_result = call_mcp_method(base_url, "tool/call", {
        "name": "run_test",
        "arguments": {
            "test_type": "database"
        }
    })
    if db_result and "result" in db_result and db_result["result"].get("success") == True:
        print("✅ Database connection working")
    else:
        print("❌ Database connection failed")
        sys.exit(1)
    
    # Step 5: Check Redis connection
    print("\nTesting Redis connection through MCP...")
    redis_result = call_mcp_method(base_url, "tool/call", {
        "name": "run_test",
        "arguments": {
            "test_type": "redis"
        }
    })
    if redis_result and "result" in redis_result and redis_result["result"].get("success") == True:
        print("✅ Redis connection working")
    else:
        print("❌ Redis connection failed")
        sys.exit(1)
    
    # Step 6: Check menu functionality
    print("\nTesting menu functionality through MCP...")
    menu_result = call_mcp_method(base_url, "tool/call", {
        "name": "run_test",
        "arguments": {
            "test_type": "menu"
        }
    })
    if menu_result and "result" in menu_result and menu_result["result"].get("success") == True:
        print("✅ Menu functionality working")
    else:
        print("❌ Menu functionality failed")
        sys.exit(1)
    
    # Step 7: Check order functionality
    print("\nTesting order functionality through MCP...")
    order_result = call_mcp_method(base_url, "tool/call", {
        "name": "run_test",
        "arguments": {
            "test_type": "order"
        }
    })
    if order_result and "result" in order_result and order_result["result"].get("success") == True:
        print("✅ Order functionality working")
    else:
        print("❌ Order functionality failed")
        sys.exit(1)
    
    print("\n----- Validation Complete -----")
    print("✅ Local MCP server environment is working correctly")
    print("\nYou can now use the MCP server with tools like Claude Code.")
    print(f"Server URL: {base_url}/mcp")
    
    print("\nAvailable test types:")
    print("  - basic: Basic connectivity tests")
    print("  - database: Database schema and CRUD operations")
    print("  - redis: Redis connection and operations")
    print("  - menu: Menu functionality tests")
    print("  - order: Order processing tests")
    print("  - full_menu: Comprehensive menu integration tests")
    print("  - full_order: Comprehensive order integration tests")
    print("  - all: End-to-end tests across all components")
    
    print("\nExample curl command:")
    print(f"curl -X POST {base_url}/mcp -H \"Content-Type: application/json\" -d '{{\"jsonrpc\":\"2.0\", \"id\":1, \"method\":\"tool/call\", \"params\":{{\"name\":\"run_test\", \"arguments\":{{\"test_type\":\"basic\"}}}}}}'")

if __name__ == "__main__":
    main()