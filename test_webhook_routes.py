#!/usr/bin/env python
"""
Test script to verify Twilio webhook route accessibility.

This script tests the webhook routes that Twilio uses to initiate voice calls
in the RedBarSushiAI system. It sends a POST request to the webhook endpoints
and verifies that proper TwiML is returned.

Usage:
    python test_webhook_routes.py [--url URL]

Options:
    --url URL    Base URL to test (default: http://localhost:5000)
"""

import argparse
import logging
import sys
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

def test_webhook_route(url, path):
    """
    Test a webhook route by sending a POST request with Twilio-like parameters.
    
    Args:
        url: Base URL of the server
        path: Path to test (e.g., "/webhook/voice")
        
    Returns:
        bool: True if test passed, False otherwise
    """
    full_url = f"{url.rstrip('/')}{path}"
    logger.info(f"Testing webhook route: {full_url}")
    
    # Mimic Twilio POST parameters
    data = {
        "CallSid": "TEST12345678901234567890123456789012",
        "AccountSid": "ACTEST1234567890123456789012345",
        "From": "+15551234567",
        "To": "+15559876543",
        "CallStatus": "ringing",
        "ApiVersion": "2010-04-01",
        "Direction": "inbound",
    }
    
    # Add headers to mimic Twilio
    headers = {
        "User-Agent": "TwilioProxy/1.1",
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Twilio-Signature": "test_signature"
    }
    
    try:
        # Send POST request
        response = requests.post(full_url, data=data, headers=headers, timeout=10)
        
        # Check response status code
        if response.status_code != 200:
            logger.error(f"Received non-200 status code: {response.status_code}")
            logger.error(f"Response content: {response.text}")
            return False
        
        # Check content type
        content_type = response.headers.get("Content-Type", "")
        if "text/xml" not in content_type and "application/xml" not in content_type:
            logger.error(f"Expected XML content type, got: {content_type}")
            return False
        
        # Parse TwiML and verify structure
        try:
            root = ET.fromstring(response.text)
            
            # Check if it's a valid TwiML response (should have <Response> root)
            if root.tag != "Response":
                logger.error(f"Expected <Response> root element, got: {root.tag}")
                return False
            
            # Check for essential TwiML elements: should have either <Say>, <Connect>, or both
            has_essential_elements = False
            for child in root:
                if child.tag in {"Say", "Connect", "Gather", "Dial"}:
                    has_essential_elements = True
                    break
            
            if not has_essential_elements:
                logger.error("TwiML response missing essential elements")
                return False
            
            logger.info(f"Route {path} returned valid TwiML: {response.text[:100]}...")
            return True
            
        except ET.ParseError as e:
            logger.error(f"Failed to parse TwiML: {e}")
            logger.error(f"Response content: {response.text}")
            return False
            
    except requests.RequestException as e:
        logger.error(f"Request failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Test Twilio webhook routes")
    parser.add_argument("--url", default="http://localhost:5000", help="Base URL to test")
    args = parser.parse_args()
    
    # Validate URL format
    url = args.url
    parsed_url = urlparse(url)
    if not parsed_url.scheme or not parsed_url.netloc:
        logger.error(f"Invalid URL format: {url}")
        return 1
    
    # Routes to test
    routes = [
        "/",
        "/voice",
        "/webhook/voice",
    ]
    
    # Run tests
    results = {}
    for route in routes:
        results[route] = test_webhook_route(url, route)
    
    # Print summary
    logger.info("\n=============== TEST RESULTS ===============")
    all_passed = True
    for route, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status}: {route}")
        if not passed:
            all_passed = False
    
    # Final result
    if all_passed:
        logger.info("\n🎉 All webhook routes passed!")
        return 0
    else:
        logger.error("\n❗ Some webhook routes failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())