#!/usr/bin/env python3
"""
Simple script to test OpenAI API connection with the key from .env.development
"""

import os
import sys
import requests

def get_openai_api_key():
    """Get OpenAI API key from environment or .env file."""
    # Try environment first
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        return api_key
    
    # Try .env.development
    env_file = ".env.development"
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                if line.startswith("OPENAI_API_KEY="):
                    api_key = line.strip().split("=", 1)[1]
                    # Remove any quotes
                    api_key = api_key.strip("'\"")
                    return api_key
    
    return None

def test_openai_connection(api_key):
    """Test connection to OpenAI API."""
    print(f"Testing OpenAI API connection with key starting with: {api_key[:5]}...")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    url = "https://api.openai.com/v1/models"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        print(f"✅ Connection successful! Status code: {response.status_code}")
        print(f"Available models: {len(response.json()['data'])}")
        
        # Print a few available models
        for model in response.json()["data"][:3]:
            print(f"- {model['id']}")
        
        return True
    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        return False

def main():
    """Main function."""
    print("Testing OpenAI API connection...")
    
    # Get API key
    api_key = get_openai_api_key()
    if not api_key:
        print("❌ Could not find OpenAI API key in environment or .env.development")
        sys.exit(1)
    
    # Test connection
    success = test_openai_connection(api_key)
    
    if success:
        print("✅ OpenAI API connection test passed!")
        sys.exit(0)
    else:
        print("❌ OpenAI API connection test failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()