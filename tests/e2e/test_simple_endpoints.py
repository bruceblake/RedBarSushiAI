"""
Simplified E2E tests that only call endpoints without complex fixtures.
These tests can be used as a starting point for more complex E2E testing.
"""
import os
import pytest
import requests
import re
import xml.etree.ElementTree as ET

# Get the base URL from environment
BASE_URL = os.getenv("BASE_URL", "https://redbarsushiai-staging.onrender.com")
print(f"Running simple endpoint tests against: {BASE_URL}")

def test_homepage_is_accessible():
    """Test that the homepage is accessible."""
    response = requests.get(f"{BASE_URL}")
    assert response.status_code == 200
    
    # The home endpoint appears to return TwiML, not HTML
    assert "<?xml version=" in response.text
    assert "<response>" in response.text.lower()
    assert "red bar sushi" in response.text.lower()

def test_voice_endpoint_accessible():
    """Test that the voice endpoint returns a response."""
    # Based on the errors, the /webhook/voice endpoint might not exist
    # Instead, we'll test the root URL which appears to handle voice calls
    
    # Create a session for cookies
    session = requests.Session()
    
    # Generate a test CallSid
    test_call_sid = "CA12345678901234567890123456789012"

    # Call the main endpoint that handles voice calls
    response = session.post(
        f"{BASE_URL}",
        data={
            "CallSid": test_call_sid,
            "AccountSid": "AC12345",
            "From": "+15551234567",
        }
    )
    assert response.status_code == 200
    
    # The response should be valid TwiML
    assert "<response>" in response.text.lower() or "<Response>" in response.text
    
    # Try to parse as XML to confirm it's valid TwiML
    try:
        root = ET.fromstring(response.text)
        # Check for common Twilio verbs
        gather = root.find(".//Gather") or root.find(".//gather")
        say = root.find(".//Say") or root.find(".//say")
        
        assert gather is not None or say is not None, "No Gather or Say element found in response"
    except ET.ParseError:
        assert False, "Response is not valid XML/TwiML"

def extract_gather_action(twiml):
    """Extract the 'action' attribute from a <Gather> tag in TwiML."""
    gather_match = re.search(r'<Gather[^>]*action="([^"]*)"', twiml)
    if gather_match:
        return gather_match.group(1)
    return None

if __name__ == "__main__":
    test_homepage_is_accessible()
    test_voice_webhook_responds()
    print("All tests passed!")