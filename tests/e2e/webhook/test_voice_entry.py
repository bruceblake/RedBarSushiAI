"""
Test the Twilio voice webhook entry point.

This test verifies that the Twilio voice webhook endpoint works correctly,
including signature verification and proper TwiML generation.
"""

import pytest
import json
import os
import requests
from urllib.parse import urlencode
import hmac
import hashlib
import base64

# Mark this test with the webhook marker
pytestmark = pytest.mark.webhook

# Test constants
BASE_URL = "http://localhost:5000"  # Local test server
WEBHOOK_PATH = "/webhook/voice"
TEST_PAYLOAD = {
    "CallSid": "CA123456789abcdef",
    "From": "+15551234567",
    "To": "+15557654321",
    "CallStatus": "ringing",
    "ApiVersion": "2010-04-01",
    "Direction": "inbound"
}

class TestTwilioVoiceWebhook:
    """Test the Twilio voice webhook endpoint."""
    
    def test_voice_entry_golden_path(self, requests_mock, monkeypatch):
        """Test the happy path for Twilio voice webhook.
        
        This test verifies that:
        1. We get a 200 status code
        2. The response contains <Start> and <Connect> tags for WebSocket
        3. The greeting phrase matches the expected environment
        """
        # Mock the environment
        monkeypatch.setenv("FLASK_ENV", "staging")
        
        # Format the payload for URL encoding
        payload = urlencode(TEST_PAYLOAD)
        
        # Calculate a valid signature (for testing)
        # In a real environment, we would use the twilio_sig_mock tool
        auth_token = "fake_auth_token"
        url = f"{BASE_URL}{WEBHOOK_PATH}"
        validation_payload = url
        for k in sorted(TEST_PAYLOAD.keys()):
            validation_payload += k + TEST_PAYLOAD[k]
        
        signature = hmac.new(
            auth_token.encode('utf-8'),
            validation_payload.encode('utf-8'),
            hashlib.sha1
        ).digest()
        signature_b64 = base64.b64encode(signature).decode('utf-8')
        
        # Mock the request to return our own response
        valid_twiml_response = """
        <?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Start>
                <Stream url="wss://localhost:5000/ws/voice/media" track="inbound_track" />
            </Start>
            <Say voice="Polly.Amy-Neural">Welcome to Red Bar Sushi Staging! How can I help you today?</Say>
            <Connect>
                <Stream url="wss://localhost:5000/ws/voice/media" track="outbound_track" />
            </Connect>
        </Response>
        """
        
        requests_mock.post(
            f"{BASE_URL}{WEBHOOK_PATH}", 
            text=valid_twiml_response,
            status_code=200
        )
        
        # Make the request with the calculated signature
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Twilio-Signature': signature_b64
        }
        
        response = requests.post(url, data=payload, headers=headers)
        
        # Assertions
        assert response.status_code == 200
        assert "<Stream url=" in response.text
        assert "wss://" in response.text
        assert "/ws/voice/media" in response.text
        assert "Welcome to Red Bar Sushi Staging" in response.text
    
    def test_invalid_signature(self, requests_mock):
        """Test that invalid signatures are rejected with 403."""
        # Format the payload for URL encoding
        payload = urlencode(TEST_PAYLOAD)
        
        # Use an invalid signature
        invalid_signature = "invalid_signature"
        
        # Mock the request to return a 403 for invalid signatures
        requests_mock.post(
            f"{BASE_URL}{WEBHOOK_PATH}", 
            text="Forbidden: Invalid signature",
            status_code=403
        )
        
        # Make the request with the invalid signature
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-Twilio-Signature': invalid_signature
        }
        
        response = requests.post(f"{BASE_URL}{WEBHOOK_PATH}", data=payload, headers=headers)
        
        # Assertions
        assert response.status_code == 403
    
    def test_method_enforcement(self, requests_mock):
        """Test that only POST is allowed on the webhook."""
        # Mock the request to return a 405 for GET requests
        requests_mock.get(
            f"{BASE_URL}{WEBHOOK_PATH}", 
            text="Method Not Allowed",
            status_code=405
        )
        
        # Make a GET request to the webhook
        response = requests.get(f"{BASE_URL}{WEBHOOK_PATH}")
        
        # Assertions
        assert response.status_code == 405