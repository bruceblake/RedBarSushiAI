#!/usr/bin/env python
"""
Render webhook testing script that follows Render's exact specification.
This script helps to test webhook functionality with the exact signature format Render uses.
"""

import os
import sys
import json
import time
import hmac
import base64
import hashlib
import logging
import argparse
import requests
from pprint import pprint

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create an argument parser
parser = argparse.ArgumentParser(description="Test Render webhook functionality following their exact specification")
parser.add_argument("--url", default="http://localhost:5000", help="Base URL of the application")
parser.add_argument("--event", default="deploy_ended", choices=["deploy_started", "deploy_ended", "build_ended"], 
                    help="Event type to simulate")
parser.add_argument("--secret", help="Webhook signing secret (if not provided, will check RENDER_WEBHOOK_SECRET env var)")
parser.add_argument("--bypass", action="store_true", help="Set BYPASS_WEBHOOK_VALIDATION=true for testing")
parser.add_argument("--debug-endpoint", action="store_true", help="Use the debug endpoint instead of the deploy endpoint")
args = parser.parse_args()

# Get the webhook secret
webhook_secret = args.secret or os.environ.get("RENDER_WEBHOOK_SECRET")
if not webhook_secret and not args.bypass:
    print("Error: No webhook secret provided. Use --secret or set RENDER_WEBHOOK_SECRET environment variable.")
    print("Alternatively, use --bypass to enable bypass mode for testing.")
    sys.exit(1)

# Base URL
base_url = args.url.rstrip("/")

# Create a webhook payload
event_id = "evt-" + base64.b64encode(os.urandom(8)).decode('utf-8').replace('=', '').replace('+', '-').replace('/', '_')
service_id = "srv-" + base64.b64encode(os.urandom(8)).decode('utf-8').replace('=', '').replace('+', '-').replace('/', '_')

# Create webhook payload matching Render's format
webhook_payload = {
    "type": args.event,
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime()),
    "data": {
        "id": event_id,
        "serviceId": service_id
    }
}

# Convert payload to JSON - IMPORTANT: Use same formatting as Render
payload_json = json.dumps(webhook_payload, separators=(',', ':'))

# Current timestamp
timestamp = str(int(time.time()))

# Create headers
headers = {
    "Content-Type": "application/json"
}

# Calculate signature if not bypassing
if not args.bypass:
    # Create the signature according to Render's specification
    message = f"{event_id}.{timestamp}.{payload_json}.{webhook_secret}"
    
    print("=== Signature Calculation ===")
    print(f"Event ID: {event_id}")
    print(f"Timestamp: {timestamp}")
    print(f"Payload: {payload_json}")
    print(f"Secret: {webhook_secret[:3]}...{webhook_secret[-3:] if len(webhook_secret) > 6 else ''}")
    print(f"Message: {event_id}.{timestamp}.[payload].{webhook_secret[:3]}...")
    
    signature = hmac.new(
        webhook_secret.encode("utf-8"),
        message.encode("utf-8"),
        digestmod=hashlib.sha256
    ).digest()
    signature_b64 = base64.b64encode(signature).decode("utf-8")
    
    # Add Render's specific headers
    headers["Webhook-Id"] = event_id
    headers["Webhook-Timestamp"] = timestamp
    headers["Webhook-Signature"] = f"v1,{signature_b64}"
    
    print(f"Signature: v1,{signature_b64}")

# Choose the endpoint
if args.debug_endpoint:
    webhook_url = f"{base_url}/webhooks/debug"
else:
    webhook_url = f"{base_url}/webhooks/deploy"

print(f"\nSending webhook to: {webhook_url}")
print("Headers:")
for key, value in headers.items():
    if key == "Webhook-Signature":
        print(f"  {key}: v1,{value.split(',')[1][:10]}..." if "," in value else value)
    else:
        print(f"  {key}: {value}")

# Add bypass environment variable if requested
if args.bypass:
    os.environ["BYPASS_WEBHOOK_VALIDATION"] = "true"
    print("\n⚠️ BYPASS_WEBHOOK_VALIDATION enabled for this request")

# Send the webhook
try:
    response = requests.post(webhook_url, headers=headers, data=payload_json)
    status = response.status_code
    
    print(f"\nResponse Status: {status}")
    print(f"Response Headers: {dict(response.headers)}")
    
    # Try to parse response as JSON
    try:
        response_json = response.json()
        print("\nResponse Body:")
        print(json.dumps(response_json, indent=2))
    except:
        print("\nResponse Body (not JSON):")
        print(response.text[:500])
    
    if status >= 200 and status < 300:
        print("\n✅ Webhook request succeeded!")
        sys.exit(0)
    else:
        print(f"\n❌ Webhook request failed with status {status}")
        sys.exit(1)
        
except Exception as e:
    print(f"\n❌ Error sending webhook: {e}")
    sys.exit(1)