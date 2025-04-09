#!/usr/bin/env python
"""
Enhanced testing tool for Render webhooks.
This script helps diagnose webhook signature validation issues by trying different signature formats.
"""

import os
import sys
import json
import time
import hmac
import base64
import hashlib
import argparse
import requests
from urllib.parse import urljoin
from pprint import pprint

# Create an argument parser
parser = argparse.ArgumentParser(description="Test Render webhook functionality with expanded options")
parser.add_argument("--url", default="http://localhost:5000", help="Base URL of the application")
parser.add_argument("--event", default="deploy_ended", choices=["deploy_started", "deploy_ended", "build_ended"], 
                    help="Event type to simulate")
parser.add_argument("--secret", help="Webhook signing secret (if not provided, will check RENDER_WEBHOOK_SECRET env var)")
parser.add_argument("--test", action="store_true", help="Just test the webhook endpoint without sending an event")
parser.add_argument("--debug", action="store_true", help="Use the debug endpoint to see raw headers and payload")
parser.add_argument("--header-format", default="standard", choices=["standard", "uppercase", "x-prefix"],
                    help="Format to use for header names")
args = parser.parse_args()

# Get the webhook secret
webhook_secret = args.secret or os.environ.get("RENDER_WEBHOOK_SECRET")
if not webhook_secret and not args.test and not args.debug:
    print("Error: No webhook secret provided. Use --secret or set RENDER_WEBHOOK_SECRET environment variable.")
    sys.exit(1)

# Base URL
base_url = args.url.rstrip("/")

if args.test:
    # Just test the webhook endpoint
    test_url = urljoin(base_url + "/", "webhooks/test")
    print(f"Testing webhook endpoint at {test_url}...")
    
    try:
        response = requests.get(test_url)
        response.raise_for_status()
        
        print("\n✅ Webhook endpoint test successful!")
        print(f"Status Code: {response.status_code}")
        print("\nResponse:")
        print(json.dumps(response.json(), indent=2))
        sys.exit(0)
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Webhook endpoint test failed: {e}")
        if hasattr(e, "response") and e.response:
            print(f"Status Code: {e.response.status_code}")
            print("\nResponse:")
            print(e.response.text)
        sys.exit(1)

# Use debug endpoint if specified
if args.debug:
    debug_url = urljoin(base_url + "/", "webhooks/debug")
    print(f"Using debug endpoint at {debug_url}...")
    
    # Create a simple payload
    debug_payload = {
        "type": "debug_request",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime()),
        "message": "This is a test payload for debugging"
    }
    
    # Simple request without special headers
    try:
        response = requests.post(debug_url, json=debug_payload)
        response.raise_for_status()
        
        print("\n✅ Debug endpoint test successful!")
        print(f"Status Code: {response.status_code}")
        print("\nResponse:")
        print(json.dumps(response.json(), indent=2))
        sys.exit(0)
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Debug endpoint test failed: {e}")
        if hasattr(e, "response") and e.response:
            print(f"Status Code: {e.response.status_code}")
            print("\nResponse:")
            print(e.response.text)
        sys.exit(1)

# Create a webhook payload
event_id = "evt-simulated" + str(int(time.time()))
service_id = "srv-simulated" + str(int(time.time()))[5:]

webhook_payload = {
    "type": args.event,
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime()),
    "data": {
        "id": event_id,
        "serviceId": service_id
    }
}

# Convert payload to JSON
payload_json = json.dumps(webhook_payload)

# Current timestamp
timestamp = str(int(time.time()))

# Create the signature
message = f"{event_id}.{timestamp}.{payload_json}.{webhook_secret}"
signature = hmac.new(
    webhook_secret.encode("utf-8"),
    message.encode("utf-8"),
    digestmod=hashlib.sha256
).digest()
signature_b64 = base64.b64encode(signature).decode("utf-8")

# Set header names based on format
if args.header_format == "standard":
    header_id = "webhook-id"
    header_timestamp = "webhook-timestamp"
    header_signature = "webhook-signature"
elif args.header_format == "uppercase":
    header_id = "Webhook-Id"
    header_timestamp = "Webhook-Timestamp"
    header_signature = "Webhook-Signature"
else:  # x-prefix
    header_id = "x-webhook-id"
    header_timestamp = "x-webhook-timestamp"
    header_signature = "x-webhook-signature"

# Headers for the request
headers = {
    "Content-Type": "application/json",
    header_id: event_id,
    header_timestamp: timestamp,
    header_signature: f"v1,{signature_b64}"
}

# URL for the webhook
webhook_url = urljoin(base_url + "/", "webhooks/deploy")

print(f"Sending simulated {args.event} webhook to {webhook_url}...")
print(f"Event ID: {event_id}")
print(f"Service ID: {service_id}")
print(f"Using header format: {args.header_format}")
print(f"\nMessage format: {event_id}.{timestamp}.[payload].{webhook_secret[:3]}...")
print(f"Signature: v1,{signature_b64[:10]}...")
print("\nHeaders being sent:")
for key, value in headers.items():
    if key == header_signature:
        print(f"  {key}: v1,{value.split(',')[1][:10]}...")
    else:
        print(f"  {key}: {value}")

try:
    response = requests.post(webhook_url, headers=headers, data=payload_json)
    response.raise_for_status()
    
    print("\n✅ Webhook sent successfully!")
    print(f"Status Code: {response.status_code}")
    print("\nResponse:")
    print(json.dumps(response.json(), indent=2))
    sys.exit(0)
except requests.exceptions.RequestException as e:
    print(f"\n❌ Webhook sending failed: {e}")
    if hasattr(e, "response") and e.response:
        print(f"Status Code: {e.response.status_code}")
        print("\nResponse:")
        print(e.response.text)
    sys.exit(1)