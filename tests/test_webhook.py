#!/usr/bin/env python
"""
Test script for Render webhook functionality.
This script can simulate Render webhook events to test our webhook handlers.
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

# Only parse arguments when running as a script, not when imported by pytest
if __name__ == "__main__":
    # Create an argument parser
    parser = argparse.ArgumentParser(description="Test Render webhook functionality")
    parser.add_argument(
        "--url", default="http://localhost:5000", help="Base URL of the application"
    )
    parser.add_argument(
        "--event",
        default="deploy_ended",
        choices=["deploy_started", "deploy_ended", "build_ended"],
        help="Event type to simulate",
    )
    parser.add_argument(
        "--secret",
        help="Webhook signing secret (if not provided, will check RENDER_WEBHOOK_SECRET env var)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Just test the webhook endpoint without sending an event",
    )
    args = parser.parse_args()
else:
    # Define a dummy args object for when imported by pytest
    class Args:
        url = "http://localhost:5000"
        event = "deploy_ended"
        secret = None
        test = False

    args = Args()

# Get the webhook secret
webhook_secret = args.secret or os.environ.get("RENDER_WEBHOOK_SECRET")
if not webhook_secret and not args.test:
    if __name__ == "__main__":
        print(
            "Error: No webhook secret provided. Use --secret or set RENDER_WEBHOOK_SECRET environment variable."
        )
        sys.exit(1)
    else:
        print(
            "Warning: No webhook secret provided. Tests using this module may not function correctly."
        )
        webhook_secret = "dummy_secret_for_testing"

# Base URL
base_url = args.url.rstrip("/")

# Only execute the webhook testing functionality when running as a script
if __name__ == "__main__":
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

    # Create a webhook payload
    event_id = "evt-simulated" + str(int(time.time()))
    service_id = "srv-simulated" + str(int(time.time()))[5:]

    webhook_payload = {
        "type": args.event,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime()),
        "data": {"id": event_id, "serviceId": service_id},
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
        digestmod=hashlib.sha256,
    ).digest()
    signature_b64 = base64.b64encode(signature).decode("utf-8")

    # Headers for the request
    headers = {
        "Content-Type": "application/json",
        "webhook-id": event_id,
        "webhook-timestamp": timestamp,
        "webhook-signature": f"v1,{signature_b64}",
    }

    # URL for the webhook
    webhook_url = urljoin(base_url + "/", "webhooks/deploy")

    print(f"Sending simulated {args.event} webhook to {webhook_url}...")
    print(f"Event ID: {event_id}")
    print(f"Service ID: {service_id}")

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
