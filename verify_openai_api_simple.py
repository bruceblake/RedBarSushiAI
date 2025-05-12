#!/usr/bin/env python3
"""Simple OpenAI API key verification script without external dependencies."""

import os
import sys
import json
import time
import traceback
import socket
import ssl
import http.client
from datetime import datetime

def print_header(text):
    print(f"\n{'=' * 50}")
    print(f"  {text}")
    print(f"{'=' * 50}")

def get_openai_api_key():
    """Get OpenAI API key from environment."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    
    if not api_key:
        print("❌ OPENAI_API_KEY environment variable not set!")
        return None
    
    # Check if it has proper format (starts with sk-)
    if not api_key.startswith("sk-"):
        print(f"⚠️ Warning: API key does not start with 'sk-', which is unusual")
    
    return api_key

def test_openai_connection_http(api_key):
    """Test connection to OpenAI API using HTTP."""
    print_header("Testing OpenAI API Connection (HTTP)")
    
    if not api_key:
        print("❌ Cannot test connection: No API key provided")
        return False
    
    # We'll use the models endpoint as a simple test
    hostname = "api.openai.com"
    endpoint = "/v1/models"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    print(f"Connecting to {hostname}{endpoint}...")
    print(f"Using API key: {api_key[:4]}...{api_key[-4:]} (length: {len(api_key)})")
    
    try:
        # Create HTTPS connection
        context = ssl.create_default_context()
        conn = http.client.HTTPSConnection(hostname, timeout=10, context=context)
        
        # Make request
        start_time = time.time()
        conn.request("GET", endpoint, headers=headers)
        response = conn.getresponse()
        connect_time = time.time() - start_time
        
        # Read response
        data = response.read().decode()
        conn.close()
        
        # Parse response
        try:
            response_data = json.loads(data)
        except json.JSONDecodeError:
            print(f"❌ Failed to parse response as JSON: {data[:200]}...")
            return False
        
        # Check response
        if response.status == 200:
            print(f"✅ Connection successful! (took {connect_time:.2f}s)")
            print(f"✅ Retrieved {len(response_data.get('data', []))} models")
            
            # Print first few models
            models = response_data.get('data', [])
            if models:
                print("\nAvailable models include:")
                for model in models[:5]:  # Show first 5 models
                    print(f"- {model.get('id', 'unknown')}")
                if len(models) > 5:
                    print(f"... and {len(models) - 5} more")
            
            return True
        else:
            print(f"❌ Request failed with status code {response.status}: {response.reason}")
            print(f"Response: {data[:200]}...")
            return False
    
    except Exception as e:
        print(f"❌ Error connecting to OpenAI API: {str(e)}")
        print(traceback.format_exc())
        return False

def test_openai_socket_connection():
    """Test basic socket connection to OpenAI API endpoints."""
    print_header("Testing Socket Connection to OpenAI Endpoints")
    
    endpoints = [
        ("api.openai.com", 443, "API Endpoint"),
        ("api.openai.com", 80, "API Endpoint (HTTP)")
    ]
    
    all_passed = True
    
    for host, port, name in endpoints:
        try:
            print(f"Testing connection to {name} ({host}:{port})...")
            
            # Create socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            
            # Connect
            start_time = time.time()
            result = sock.connect_ex((host, port))
            connect_time = time.time() - start_time
            
            # Check result
            if result == 0:
                print(f"✅ Successfully connected to {name} ({host}:{port}) in {connect_time:.2f}s")
            else:
                print(f"❌ Failed to connect to {name} ({host}:{port}): Error code {result}")
                all_passed = False
            
            sock.close()
        
        except Exception as e:
            print(f"❌ Error testing connection to {name} ({host}:{port}): {str(e)}")
            all_passed = False
    
    return all_passed

def main():
    print_header("OpenAI API Key Verification")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test socket connection to OpenAI endpoints
    socket_success = test_openai_socket_connection()
    
    # Get API key
    api_key = get_openai_api_key()
    if not api_key:
        print("\n❌ No OpenAI API key available for testing.")
        return 1
    
    # Test API connection
    api_success = test_openai_connection_http(api_key)
    
    # Print summary
    print_header("Test Results Summary")
    print(f"Socket connection: {'✅' if socket_success else '❌'}")
    print(f"API key present: {'✅' if api_key else '❌'}")
    print(f"API connection: {'✅' if api_success else '❌'}")
    
    if socket_success and api_key and api_success:
        print("\n✅ All OpenAI API tests passed successfully!")
        return 0
    else:
        print("\n❌ Some OpenAI API tests failed. See details above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())