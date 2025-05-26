#!/usr/bin/env python3
"""Debug script to check ConversationRelay issues."""

import requests
import time

# Check if the WebSocket endpoint is accessible
print("Checking WebSocket endpoint...")

# First check the TwiML generation
response = requests.post("http://localhost:8000/voice/", data={
    "CallSid": "CAtest123",
    "From": "+15551234567",
    "To": "+15557654321",
    "CallStatus": "ringing"
})

print(f"TwiML Response Status: {response.status_code}")
print(f"TwiML Response:\n{response.text}")

# Check if the endpoint is registered
response = requests.get("http://localhost:8000/debug-routes")
if response.status_code == 200:
    routes = response.json()
    print("\nRegistered routes:")
    for route in routes.get("routes", []):
        if "conversation" in route.get("path", "").lower():
            print(f"  - {route['path']} ({route.get('endpoint', 'unknown')})")
else:
    print(f"Could not get routes: {response.status_code}")

print("\nDone.")