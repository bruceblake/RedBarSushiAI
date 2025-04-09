#!/usr/bin/env python
"""
Webhook verification tool for Render.
This script helps identify issues with webhook configuration and shows the expected format.
"""

import os
import sys
import json
import hmac
import time
import base64
import hashlib
import requests
import argparse
from pprint import pprint

# Parse arguments
parser = argparse.ArgumentParser(description="Verify webhook configuration for Render")
parser.add_argument("--url", default="http://localhost:5000", help="Application URL")
parser.add_argument("--secret", help="Webhook secret to check")
parser.add_argument("--check-env", action="store_true", help="Check environment variables on the server")
args = parser.parse_args()

# Get the application URL
app_url = args.url.rstrip("/")

# Check if the webhook endpoint exists
def check_webhook_endpoint():
    print("===== Checking webhook endpoint =====")
    test_url = f"{app_url}/webhooks/test"
    
    try:
        response = requests.get(test_url)
        if response.status_code == 200:
            data = response.json()
            print("✅ Webhook endpoint is available")
            print("\nEndpoint configuration:")
            for key, value in data.get("environment", {}).items():
                print(f"  {key}: {value}")
                
            # Check if webhook secret is configured
            if data.get("environment", {}).get("webhook_secret_configured"):
                print("\n✅ Webhook secret is configured")
            else:
                print("\n❌ Webhook secret is NOT configured")
                
            return True
        else:
            print(f"❌ Webhook endpoint returned error status {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"❌ Error checking webhook endpoint: {e}")
        return False

# Verify the webhook secret
def verify_secret(secret):
    if not secret:
        print("❌ No webhook secret provided")
        return False
        
    print("\n===== Verifying webhook secret =====")
    print(f"Testing with secret: {secret[:3]}...{secret[-3:] if len(secret) > 6 else ''}")
    
    # Generate test data
    test_id = "test-id-" + str(int(time.time()))
    test_timestamp = str(int(time.time()))
    test_payload = json.dumps({"test": True})
    
    # Generate signature
    message = f"{test_id}.{test_timestamp}.{test_payload}.{secret}"
    signature = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        digestmod=hashlib.sha256
    ).digest()
    signature_b64 = base64.b64encode(signature).decode("utf-8")
    
    # Send test request to debug endpoint
    debug_url = f"{app_url}/webhooks/debug"
    headers = {
        "Content-Type": "application/json",
        "Webhook-Id": test_id,
        "Webhook-Timestamp": test_timestamp,
        "Webhook-Signature": f"v1,{signature_b64}"
    }
    
    try:
        # Enable debug mode temporarily
        os.environ["ALLOW_WEBHOOK_DEBUG"] = "true"
        
        response = requests.post(debug_url, headers=headers, data=test_payload)
        if response.status_code == 200:
            print("✅ Debug request successful - signature validation likely works")
            return True
        else:
            print(f"❌ Debug request failed with status {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"❌ Error sending debug request: {e}")
        return False
    finally:
        os.environ.pop("ALLOW_WEBHOOK_DEBUG", None)

# Show Render webhook setup instructions
def show_setup_instructions():
    print("\n===== Render Webhook Setup Instructions =====")
    print("1. Go to your Render dashboard")
    print("2. Select your service")
    print("3. Go to Settings → Outbound Webhooks")
    print("4. Add a new webhook with:")
    print(f"   - Payload URL: {app_url}/webhooks/deploy")
    print("   - Event: Deploy succeeded")
    print("   - Secret: Generate a secure random string")
    print("\n5. Add the same secret to your service's environment variables:")
    print("   - Name: RENDER_WEBHOOK_SECRET")
    print("   - Value: Your generated secret")
    print("\n6. Save and redeploy your service")

# Main function
def main():
    # Check if the webhook endpoint exists
    endpoint_exists = check_webhook_endpoint()
    
    # Check if we have a secret to verify
    if args.secret:
        verify_secret(args.secret)
    
    # Show setup instructions
    if endpoint_exists:
        show_setup_instructions()
    
    # Final recommendations
    print("\n===== Recommendations =====")
    if not args.secret:
        print("→ Run this script with --secret to verify your webhook secret")
    print(f"→ Use the webhook debug endpoint: {app_url}/webhooks/debug")
    print("→ Check the application logs for detailed error messages")
    print("→ For testing, set BYPASS_WEBHOOK_VALIDATION=true in your environment")

if __name__ == "__main__":
    main()