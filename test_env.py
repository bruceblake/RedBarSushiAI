#!/usr/bin/env python3
"""
Simple script to test the environment variables in the container.
"""

import os
import sys
import requests

def check_env_variables():
    """Check if environment variables are set."""
    variables = [
        "OPENAI_API_KEY",
        "FLASK_ENV",
        "LOG_LEVEL",
        "VOICE_HANDLER",
    ]
    
    missing = []
    for var in variables:
        value = os.environ.get(var)
        if value:
            # Mask API keys
            if "KEY" in var or "TOKEN" in var:
                display_value = f"{value[:5]}..." if len(value) > 5 else value
            else:
                display_value = value
            print(f"✅ {var}: {display_value}")
        else:
            print(f"❌ {var}: Not set")
            missing.append(var)
    
    if missing:
        print(f"\nMissing variables: {', '.join(missing)}")
        return False
    
    return True

def test_openai_connection():
    """Test connection to OpenAI API."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY not set, skipping API test")
        return False
    
    print(f"\nTesting OpenAI API connection with key starting with: {api_key[:5]}...")
    
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
    print("===== Testing Environment Variables =====")
    
    # Check environment variables
    env_ok = check_env_variables()
    
    # If environment variables are set, test OpenAI connection
    api_ok = False
    if env_ok and os.environ.get("OPENAI_API_KEY"):
        api_ok = test_openai_connection()
    
    # Display summary
    print("\n===== Test Summary =====")
    print(f"Environment variables: {'✅ OK' if env_ok else '❌ Missing'}")
    print(f"OpenAI API connection: {'✅ OK' if api_ok else '❌ Failed'}")
    
    # Return exit code
    if env_ok and api_ok:
        print("\nAll tests passed! Your environment is properly configured.")
        return 0
    else:
        print("\nSome tests failed. Please check the output above.")
        return 1

if __name__ == "__main__":
    try:
        import requests
    except ImportError:
        print("Installing requests module...")
        import pip
        pip.main(["install", "requests"])
        import requests
    
    sys.exit(main())