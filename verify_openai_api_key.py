#!/usr/bin/env python
"""
Script to verify the OpenAI API key and other critical environment variables.
Run this on Render to check environment configuration.
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv

# Try to load .env files (this is a fallback, won't override existing env vars)
load_dotenv()

print("\n=== OpenAI API Key Verification ===\n")

# Check if the API key is set
openai_api_key = os.environ.get("OPENAI_API_KEY", "")
if not openai_api_key:
    print("❌ ERROR: OPENAI_API_KEY environment variable is NOT SET!")
    print("   Please set this variable in your environment or .env file.")
    print("   On Render, set it in the Environment tab for your service.")
    sys.exit(1)

# Check key format
if not openai_api_key.startswith("sk-"):
    print(f"⚠️  WARNING: OPENAI_API_KEY doesn't start with 'sk-', which is unusual.")
    print(f"   Current format: {openai_api_key[:4]}... (length: {len(openai_api_key)})")
else:
    print(f"✅ OPENAI_API_KEY format appears valid: starts with 'sk-' (length: {len(openai_api_key)})")

# Make a simple OpenAI API request to verify the key
print("\nPerforming API key validation with OpenAI...\n")

try:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}"
    }
    
    # Use the models endpoint for a simple validation
    response = requests.get("https://api.openai.com/v1/models", headers=headers)
    
    if response.status_code == 200:
        print("✅ SUCCESS: API key is valid and active!")
        available_models = response.json().get("data", [])
        realtime_models = [model["id"] for model in available_models if "realtime" in model["id"]]
        
        if realtime_models:
            print(f"\n✅ Your account has access to Realtime API models:")
            for model in realtime_models:
                print(f"   - {model}")
        else:
            print("\n⚠️  WARNING: No Realtime API models found in your available models.")
            print("   Your account may not have access to the Realtime API.")
    elif response.status_code == 401:
        print("❌ ERROR: Invalid API key. The API key provided is not valid.")
        print("   Please check for typos or generate a new key.")
    elif response.status_code == 403:
        print("❌ ERROR: Forbidden. Your API key doesn't have permission to use this endpoint.")
        print("   This could mean your account has restrictions or lacks necessary permissions.")
    else:
        print(f"❌ ERROR: API request failed with status code {response.status_code}")
        print(f"Response: {response.text}")
except Exception as e:
    print(f"❌ ERROR: Exception occurred when validating API key: {str(e)}")

# Check other critical environment variables
print("\n=== Other Critical Environment Variables ===\n")

critical_vars = [
    "OPENAI_REALTIME_MODEL",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_PHONE_NUMBER",
    "DATABASE_URL",
    "REDIS_URL"
]

for var in critical_vars:
    value = os.environ.get(var, "")
    if value:
        # Show censored version for sensitive values
        if "AUTH_TOKEN" in var or "SID" in var:
            display_value = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "[TOO SHORT]"
        else:
            display_value = value
            
        print(f"✅ {var}: {display_value}")
    else:
        print(f"⚠️  {var} is not set!")

print("\n=== Environment Info ===\n")
print(f"FASTAPI_ENV: {os.environ.get('FASTAPI_ENV', 'not set')}")
print(f"FLASK_ENV: {os.environ.get('FLASK_ENV', 'not set')}")
print(f"RENDER: {os.environ.get('RENDER', 'not set')}")
print(f"IS_STAGING: {os.environ.get('IS_STAGING', 'not set')}")
print(f"Working directory: {os.getcwd()}")

print("\nVerification complete.")