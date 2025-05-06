#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple test client for the FastMCP server.
"""

import requests
import json
import sys
import time

BASE_URL = "http://localhost:8050"

def test_echo():
    """Test the echo tool."""
    payload = {
        "jsonrpc": "2.0",
        "method": "execute_tool",
        "params": {
            "name": "echo",
            "arguments": {
                "message": "Hello, FastMCP!"
            }
        },
        "id": 1
    }
    
    try:
        response = requests.post(f"{BASE_URL}/tools", json=payload)
        result = response.json()
        
        if "result" in result:
            print("Echo test successful!")
            print(f"Result: {result['result']}")
        else:
            print("Echo test failed!")
            print(f"Error: {result.get('error', 'Unknown error')}")
        
        return result
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

def test_restaurant_info():
    """Test the get_restaurant_info tool."""
    payload = {
        "jsonrpc": "2.0",
        "method": "execute_tool",
        "params": {
            "name": "get_restaurant_info_tool",
            "arguments": {}
        },
        "id": 2
    }
    
    try:
        response = requests.post(f"{BASE_URL}/tools", json=payload)
        result = response.json()
        
        if "result" in result:
            print("Restaurant info test successful!")
            restaurant_info = json.loads(result['result'])
            print(f"Restaurant name: {restaurant_info['info']['name']}")
            print(f"Restaurant address: {restaurant_info['info']['address']}")
            print(f"Restaurant phone: {restaurant_info['info']['phone']}")
        else:
            print("Restaurant info test failed!")
            print(f"Error: {result.get('error', 'Unknown error')}")
        
        return result
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

def test_cart_operations():
    """Test the cart operations."""
    session_id = f"test-session-{int(time.time())}"
    print(f"Using session ID: {session_id}")
    
    # 1. Clear cart (should return empty cart)
    payload = {
        "jsonrpc": "2.0",
        "method": "execute_tool",
        "params": {
            "name": "clear_cart",
            "arguments": {
                "session_id": session_id
            }
        },
        "id": 3
    }
    
    try:
        response = requests.post(f"{BASE_URL}/tools", json=payload)
        result = response.json()
        
        if "result" in result:
            print("Clear cart test successful!")
            cart_data = json.loads(result['result'])
            print(f"Empty cart: {cart_data['cart']}")
            
            # 2. Add item to cart (using dummy PLU, will fail without real DB data)
            print("\nAttempting to add item to cart (may fail without real DB data)...")
            add_payload = {
                "jsonrpc": "2.0",
                "method": "execute_tool",
                "params": {
                    "name": "add_to_cart",
                    "arguments": {
                        "session_id": session_id,
                        "item_plu": "DUMMY-PLU",
                        "quantity": 2
                    }
                },
                "id": 4
            }
            
            try:
                response = requests.post(f"{BASE_URL}/tools", json=add_payload)
                result = response.json()
                print("Add to cart response:", json.dumps(result, indent=2))
            except Exception as e:
                print(f"Error adding to cart: {str(e)}")
        else:
            print("Clear cart test failed!")
            print(f"Error: {result.get('error', 'Unknown error')}")
        
        return result
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

def test_health():
    """Test the health endpoint."""
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("Health check successful!")
            print(f"Status code: {response.status_code}")
            print(f"Response: {response.text}")
        else:
            print("Health check failed!")
            print(f"Status code: {response.status_code}")
            print(f"Response: {response.text}")
        
        return response
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

def test_tools_endpoint():
    """Test the /tools endpoint to get list of available tools."""
    try:
        response = requests.get(f"{BASE_URL}/tools")
        if response.status_code == 200:
            print("Tools endpoint check successful!")
            
            try:
                tools = response.json()
                print(f"Available tools: {len(tools)}")
                for tool in tools:
                    print(f"- {tool.get('name')}: {tool.get('description')}")
            except:
                print(f"Response: {response.text}")
        else:
            print("Tools endpoint check failed!")
            print(f"Status code: {response.status_code}")
            print(f"Response: {response.text}")
        
        return response
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

if __name__ == "__main__":
    print("Testing FastMCP server...")
    
    # Test the health endpoint
    print("\n=== Testing Health Endpoint ===")
    test_health()
    
    # Test tools endpoint
    print("\n=== Testing Tools Endpoint ===")
    test_tools_endpoint()
    
    # Test the echo tool
    print("\n=== Testing Echo Tool ===")
    test_echo()
    
    # Test the restaurant info tool
    print("\n=== Testing Restaurant Info Tool ===")
    test_restaurant_info()
    
    # Test cart operations
    print("\n=== Testing Cart Operations ===")
    test_cart_operations()
    
    print("\nTests completed.")