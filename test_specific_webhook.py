#!/usr/bin/env python
"""
Test script for a specific webhook from the logs.
"""

import os
import sys
import json
import time
import hmac
import base64
import hashlib
import requests
import argparse

# Create an argument parser
parser = argparse.ArgumentParser(description="Test a specific webhook from logs")
parser.add_argument("--url", default="http://localhost:5000", help="Base URL of the application")
parser.add_argument("--secret", help="Webhook signing secret (required)")
args = parser.parse_args()

# Verify args
if not args.secret:
    print("Error: --secret is required")
    sys.exit(1)

# Base URL
base_url = args.url.rstrip("/")
webhook_url = f"{base_url}/webhooks/deploy"
webhook_secret = args.secret

# Use the specific values from the logs
webhook_id = "evt-cvqt1r7gi27c73fthpsg"
timestamp = "1744163058"
signature = "v1,tR52/WcUT8K5N4MOgLBlPO8fZxFMB60A6LjCFI0lyAg="

# The exact payload from the request
payload = {
    "type": "deploy_ended",
    "timestamp": "2025-04-09T01:37:52.231077095Z",
    "data": {
        "id": "evt-cvqsus7gi27c73f8sqmg", 
        "serviceId": "srv-cvp8bj15pdvs73e74d2g"
    }
}

# Convert to JSON with different formats
payload_json = json.dumps(payload)  # Normal format
payload_compact = json.dumps(payload, separators=(',', ':'))  # Compact format

print("=== Testing Webhook Signature with Specific Log Values ===")
print(f"Webhook URL: {webhook_url}")
print(f"Webhook ID: {webhook_id}")
print(f"Timestamp: {timestamp}")
print(f"Received Signature: {signature}")
print(f"Secret (first 3 chars): {webhook_secret[:3]}...")

# Try different message formats
message_formats = [
    ("Standard format", f"{webhook_id}.{timestamp}.{payload_json}.{webhook_secret}"),
    ("Compact JSON", f"{webhook_id}.{timestamp}.{payload_compact}.{webhook_secret}"),
    ("Raw received values", f"{webhook_id}.{timestamp}.{json.dumps(payload)}.{webhook_secret}"),
    ("Original event ID", f"evt-cvqsus7gi27c73f8sqmg.{timestamp}.{payload_compact}.{webhook_secret}"),
    ("Alternate timestamp", f"{webhook_id}.{int(time.time())}.{payload_compact}.{webhook_secret}")
]

# Try different methods
print("\n=== Signature Calculation Attempts ===")
for name, message in message_formats:
    # Calculate signature
    computed_sig = hmac.new(
        webhook_secret.encode("utf-8"),
        message.encode("utf-8"),
        digestmod=hashlib.sha256
    ).digest()
    computed_sig_b64 = base64.b64encode(computed_sig).decode("utf-8")
    
    # Compare with received signature
    received_sig = signature.split(',')[1] if ',' in signature else signature
    matches = hmac.compare_digest(received_sig, computed_sig_b64)
    
    print(f"\n{name}:")
    print(f"  Message format: {message[:50]}...")
    print(f"  Computed signature: {computed_sig_b64}")
    print(f"  Matches received: {'✅ YES' if matches else '❌ NO'}")

# Send a test request with the exact values from logs
print("\n=== Sending Test Request with Original Values ===")
headers = {
    "Content-Type": "application/json",
    "Webhook-Id": webhook_id,
    "Webhook-Timestamp": timestamp,
    "Webhook-Signature": signature
}

try:
    response = requests.post(webhook_url, headers=headers, json=payload)
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.text}")
except Exception as e:
    print(f"Error sending request: {e}")

# Send a modified request with our own signature
print("\n=== Sending Test Request with Our Signature ===")
# Calculate our own signature
message = f"{webhook_id}.{timestamp}.{payload_compact}.{webhook_secret}"
computed_sig = hmac.new(
    webhook_secret.encode("utf-8"),
    message.encode("utf-8"),
    digestmod=hashlib.sha256
).digest()
computed_sig_b64 = base64.b64encode(computed_sig).decode("utf-8")

headers = {
    "Content-Type": "application/json",
    "Webhook-Id": webhook_id,
    "Webhook-Timestamp": timestamp,
    "Webhook-Signature": f"v1,{computed_sig_b64}"
}

try:
    response = requests.post(webhook_url, headers=headers, json=payload)
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.text}")
except Exception as e:
    print(f"Error sending request: {e}")

# Final check - try with bypass mode
if os.environ.get("BYPASS_WEBHOOK_VALIDATION") != "true":
    print("\n=== Sending Test Request with Bypass Mode ===")
    os.environ["BYPASS_WEBHOOK_VALIDATION"] = "true"
    
    headers = {
        "Content-Type": "application/json",
        "Webhook-Id": webhook_id,
        "Webhook-Timestamp": timestamp,
        "Webhook-Signature": signature
    }
    
    try:
        response = requests.post(webhook_url, headers=headers, json=payload)
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
    except Exception as e:
        print(f"Error sending request: {e}")
        
    # Reset environment
    del os.environ["BYPASS_WEBHOOK_VALIDATION"]