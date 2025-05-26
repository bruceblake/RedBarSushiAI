#!/usr/bin/env python3
"""
Test script to verify VOICE_HANDLER switch functionality.

This script simulates Twilio webhook requests to test both the old Media Streams
path and the new ConversationRelay path.
"""

import os
import sys
import requests
import json
import logging
from urllib.parse import urlencode

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration
BASE_URL = "http://localhost:8000"
WEBHOOK_ENDPOINTS = [
    "/voice/webhook",
    "/voice/",
    "/voice"
]

# Simulated Twilio webhook data
TWILIO_WEBHOOK_DATA = {
    "CallSid": "CA1234567890abcdef1234567890abcdef",
    "AccountSid": "AC1234567890abcdef1234567890abcdef",
    "From": "+15551234567",
    "To": "+15559876543",
    "CallStatus": "ringing",
    "ApiVersion": "2010-04-01",
    "Direction": "inbound",
    "Caller": "+15551234567",
    "Called": "+15559876543",
    "CallerCity": "San Francisco",
    "CallerState": "CA",
    "CallerZip": "94105",
    "CallerCountry": "US",
    "CalledCity": "New York",
    "CalledState": "NY",
    "CalledZip": "10001",
    "CalledCountry": "US"
}


def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}\n")


def test_webhook_endpoint(endpoint, voice_handler):
    """Test a single webhook endpoint with the given voice handler setting."""
    print(f"\n[Testing {endpoint} with VOICE_HANDLER={voice_handler}]")
    
    # Set the environment variable
    os.environ["VOICE_HANDLER"] = voice_handler
    
    try:
        # Make the webhook request
        response = requests.post(
            f"{BASE_URL}{endpoint}",
            data=TWILIO_WEBHOOK_DATA,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "TwilioProxy/1.1"
            }
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type', 'not set')}")
        
        if response.status_code == 200:
            # Parse and display TwiML response
            twiml = response.text
            print(f"TwiML Response (first 500 chars):\n{twiml[:500]}")
            
            # Check for expected elements
            if voice_handler == "media_streams":
                if "<Stream" in twiml:
                    print("✅ Found <Stream> element (Media Streams path)")
                else:
                    print("❌ Expected <Stream> element not found!")
                    
            elif voice_handler == "conversation_relay":
                if "<ConversationRelay" in twiml:
                    print("✅ Found <ConversationRelay> element (ConversationRelay path)")
                else:
                    print("❌ Expected <ConversationRelay> element not found!")
                    
        else:
            print(f"❌ Error Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Exception occurred: {type(e).__name__}: {str(e)}")


def test_websocket_endpoints():
    """Test that WebSocket endpoints are properly registered."""
    print_section("Testing WebSocket Endpoint Registration")
    
    try:
        # Get routes listing
        response = requests.get(f"{BASE_URL}/routes")
        
        if response.status_code == 200:
            routes_data = response.json()
            ws_routes = routes_data.get("websocket_routes", [])
            
            print("Registered WebSocket Routes:")
            for route in ws_routes:
                print(f"  - {route['path']} -> {route['endpoint']}")
            
            # Check for expected WebSocket endpoints
            expected_ws_paths = [
                "/ws/media/{call_sid}",  # Old Media Streams path
                "/realtime/ws/media/{call_sid}",  # Alternative old path
                "/api/conversation-relay"  # New ConversationRelay path
            ]
            
            found_paths = {route['path'] for route in ws_routes}
            
            print("\nExpected WebSocket Endpoints Check:")
            for expected in expected_ws_paths:
                if any(expected in path for path in found_paths):
                    print(f"  ✅ {expected} - Found")
                else:
                    print(f"  ⚠️  {expected} - Not found (might be OK)")
                    
        else:
            print(f"❌ Failed to get routes: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Exception occurred: {type(e).__name__}: {str(e)}")


def test_api_health():
    """Test basic API health."""
    print_section("Testing API Health")
    
    try:
        response = requests.get(f"{BASE_URL}/healthcheck")
        
        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ API is healthy: {health_data.get('message', 'OK')}")
            print(f"   Status: {health_data.get('status', 'unknown')}")
            print(f"   Environment: {health_data.get('environment', 'unknown')}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Cannot connect to API: {type(e).__name__}: {str(e)}")
        print("   Make sure the FastAPI server is running on http://localhost:8000")
        return False
        
    return True


def check_environment_variables():
    """Check current environment variables."""
    print_section("Environment Variables Check")
    
    important_vars = [
        "VOICE_HANDLER",
        "OPENAI_API_KEY",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_CONVERSATION_SERVICE_SID",
        "TWILIO_CONNECTOR_NAME"
    ]
    
    for var in important_vars:
        value = os.environ.get(var, "NOT SET")
        if var in ["OPENAI_API_KEY", "TWILIO_AUTH_TOKEN"] and value != "NOT SET":
            # Mask sensitive values
            value = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
        print(f"{var}: {value}")


def test_webhook_with_docker():
    """Test webhook by making request to Docker container."""
    print_section("Testing Webhook via Docker Container")
    
    # First, let's check what VOICE_HANDLER is set to in the container
    print("Checking VOICE_HANDLER in Docker container...")
    result = os.system("docker exec redbarsushi-app env | grep VOICE_HANDLER")
    
    # Test both settings by updating the container's environment
    for voice_handler in ["media_streams", "conversation_relay"]:
        print(f"\n[Setting VOICE_HANDLER={voice_handler} in container]")
        
        # Update the environment variable in the container
        os.system(f"docker exec redbarsushi-app bash -c 'export VOICE_HANDLER={voice_handler}'")
        
        # Note: This won't actually work because the app is already running
        # We need to test with the current container setting
        print("Note: Cannot dynamically change env vars in running container.")
        print("Testing with container's current VOICE_HANDLER setting...")
        
        test_webhook_endpoint("/voice/webhook", voice_handler)
        break  # Only test once since we can't change the env var


def main():
    """Run all tests."""
    print_section("VOICE_HANDLER Switch Test Suite")
    
    # Check environment
    check_environment_variables()
    
    # Test API health
    if not test_api_health():
        print("\n❌ API is not running. Please start the FastAPI server first.")
        return
    
    # Test WebSocket endpoints
    test_websocket_endpoints()
    
    # Since we're using Docker, test with current container settings
    test_webhook_with_docker()
    
    print_section("Test Complete")
    print("\nSummary:")
    print("- Check the output above for any ❌ errors")
    print("- Verify that the correct TwiML is generated for each VOICE_HANDLER setting")
    print("- Confirm WebSocket endpoints are properly registered")
    print("\nNote: To fully test both paths, you need to:")
    print("1. Stop the Docker container")
    print("2. Set VOICE_HANDLER=media_streams and restart")
    print("3. Run this test")
    print("4. Stop the container again")
    print("5. Set VOICE_HANDLER=conversation_relay and restart")
    print("6. Run this test again")


if __name__ == "__main__":
    main()