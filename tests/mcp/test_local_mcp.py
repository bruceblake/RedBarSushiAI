#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the local MCP server environment.
"""

import os
import sys
import json
import pytest
import requests
from typing import Dict, Any, Optional, List, Union

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import local_mcp_config directly
from tests.config.local_mcp_config import MCP_SERVER_URL, TestType, ErrorCode

def call_mcp_method(method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Call a method on the local MCP server using JSON-RPC.
    
    Args:
        method: The method name to call
        params: Optional parameters for the method
        
    Returns:
        The JSON-RPC response
    """
    if params is None:
        params = {}
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    response = requests.post(MCP_SERVER_URL, json=payload, headers=headers)
    
    # Check for HTTP errors
    response.raise_for_status()
    
    # Return the JSON response
    return response.json()

def test_mcp_health():
    """Test the health endpoint of the MCP server."""
    health_url = MCP_SERVER_URL.replace("/mcp", "/health")
    response = requests.get(health_url)
    
    # Check for HTTP errors
    response.raise_for_status()
    
    # Parse JSON response
    health_data = response.json()
    
    # Check health status
    assert health_data["mcp"] == "ok", "MCP server should be healthy"
    assert health_data["postgres"] == "connected", "PostgreSQL connection should be healthy"
    assert health_data["redis"] == "connected", "Redis connection should be healthy"

def test_mcp_initialize():
    """Test the initialize method of the MCP server."""
    response = call_mcp_method("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "sampling": {}
        },
        "clientInfo": {
            "name": "MCP Test Client",
            "version": "1.0.0"
        }
    })
    
    # Check response
    assert "result" in response, f"Expected 'result' in response: {response}"
    result = response["result"]
    
    # Check protocol version
    assert "protocolVersion" in result, "Missing protocolVersion in initialize response"
    assert result["protocolVersion"] == "2024-11-05", "Protocol version mismatch"
    
    # Check capabilities
    assert "capabilities" in result, "Missing capabilities in initialize response"
    assert "tools" in result["capabilities"], "Missing tools capability"
    
    # Check server info
    assert "serverInfo" in result, "Missing serverInfo in initialize response"
    assert "name" in result["serverInfo"], "Missing server name"
    assert "version" in result["serverInfo"], "Missing server version"

def test_mcp_tools_list():
    """Test the tools/list method of the MCP server."""
    response = call_mcp_method("tools/list")
    
    # Check response
    assert "result" in response, f"Expected 'result' in response: {response}"
    assert "tools" in response["result"], "Missing tools in response"
    
    # Check tools
    tools = response["result"]["tools"]
    assert isinstance(tools, list), "Tools should be a list"
    assert len(tools) > 0, "Tools list should not be empty"
    
    # Check for expected tools
    tool_names = [tool["name"] for tool in tools]
    expected_tools = ["echo", "check_docker_status", "run_test", "setup_docker_env", "cleanup_docker_env"]
    
    for tool in expected_tools:
        assert tool in tool_names, f"Missing expected tool: {tool}"
    
    # Check tool schema
    for tool in tools:
        assert "name" in tool, "Tool missing name"
        assert "description" in tool, "Tool missing description"
        assert "inputSchema" in tool, "Tool missing inputSchema"

def test_mcp_echo():
    """Test the echo tool."""
    message = "Hello, MCP!"
    response = call_mcp_method("tool/call", {
        "name": "echo",
        "arguments": {
            "message": message
        }
    })
    
    # Check response
    assert "result" in response, f"Expected 'result' in response: {response}"
    assert "content" in response["result"], "Missing content in response"
    
    # Check content
    content = response["result"]["content"]
    assert isinstance(content, list), "Content should be a list"
    assert len(content) > 0, "Content should not be empty"
    assert content[0]["type"] == "text", "Content type should be text"
    assert content[0]["text"] == message, "Echo message mismatch"

def test_mcp_run_test_basic():
    """Test the run_test tool with basic test type."""
    response = call_mcp_method("tool/call", {
        "name": "run_test",
        "arguments": {
            "test_type": TestType.BASIC
        }
    })
    
    # Check response
    assert "result" in response, f"Expected 'result' in response: {response}"
    assert "content" in response["result"], "Missing content in response"
    assert "success" in response["result"], "Missing success in response"
    
    # Check success
    assert response["result"]["success"] == True, "Basic test should succeed"
    
    # Check content
    content = response["result"]["content"]
    assert isinstance(content, list), "Content should be a list"
    assert len(content) > 0, "Content should not be empty"
    assert "Database connection successful" in content[0]["text"], "Database connection test missing"
    assert "Redis connection successful" in content[0]["text"], "Redis connection test missing"

def test_mcp_error_handling():
    """Test error handling in the MCP server."""
    # Test missing required parameter
    response = call_mcp_method("tool/call", {
        "name": "echo",
        "arguments": {}  # Missing required 'message' parameter
    })
    
    # Response should still be successful at JSON-RPC level since the tool handles the error
    assert "result" in response, f"Expected 'result' in response: {response}"
    assert "content" in response["result"], "Missing content in response"
    assert "No message provided" in response["result"]["content"][0]["text"], "Error message incorrect"
    
    # Test invalid method
    response = call_mcp_method("non_existent_method")
    
    # Check error response
    assert "error" in response, f"Expected 'error' in response: {response}"
    assert response["error"]["code"] == ErrorCode.METHOD_NOT_FOUND, "Wrong error code"
    
    # Test invalid tool
    response = call_mcp_method("tool/call", {
        "name": "non_existent_tool",
        "arguments": {}
    })
    
    # Check error response
    assert "error" in response, f"Expected 'error' in response: {response}"
    assert response["error"]["code"] == ErrorCode.INTERNAL_ERROR, "Wrong error code"
    assert "Tool not found" in response["error"]["message"], "Error message incorrect"

@pytest.mark.parametrize("test_type", [
    TestType.DATABASE,
    TestType.REDIS,
    TestType.MENU,
    TestType.ORDER
])
def test_mcp_run_test_types(test_type):
    """Test the run_test tool with different test types."""
    response = call_mcp_method("tool/call", {
        "name": "run_test",
        "arguments": {
            "test_type": test_type
        }
    })
    
    # Check response
    assert "result" in response, f"Expected 'result' in response: {response}"
    assert "content" in response["result"], "Missing content in response"
    assert "success" in response["result"], "Missing success in response"
    
    # Check success
    assert response["result"]["success"] == True, f"{test_type} test should succeed"

if __name__ == "__main__":
    """Run the tests."""
    # First check health
    try:
        test_mcp_health()
        print("✅ Health check passed")
    except Exception as e:
        print(f"❌ Health check failed: {str(e)}")
        exit(1)
    
    # Run initialize test
    try:
        test_mcp_initialize()
        print("✅ Initialize test passed")
    except Exception as e:
        print(f"❌ Initialize test failed: {str(e)}")
        exit(1)
    
    # Run tools/list test
    try:
        test_mcp_tools_list()
        print("✅ Tools list test passed")
    except Exception as e:
        print(f"❌ Tools list test failed: {str(e)}")
        exit(1)
    
    # Run echo test
    try:
        test_mcp_echo()
        print("✅ Echo test passed")
    except Exception as e:
        print(f"❌ Echo test failed: {str(e)}")
        exit(1)
    
    # Run basic test
    try:
        test_mcp_run_test_basic()
        print("✅ Basic test passed")
    except Exception as e:
        print(f"❌ Basic test failed: {str(e)}")
        exit(1)
    
    # Run error handling test
    try:
        test_mcp_error_handling()
        print("✅ Error handling test passed")
    except Exception as e:
        print(f"❌ Error handling test failed: {str(e)}")
        exit(1)
    
    print("All tests passed!")