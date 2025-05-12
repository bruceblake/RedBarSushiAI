#!/usr/bin/env python3
"""
Test script to verify TwiML generation with Parameter child elements.
Run this script to see the generated TwiML and check that it's valid XML.
"""

import sys
import logging
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

try:
    # Try to import the TwiML classes
    from app.utils.twilio_twiml import TwimlStreamParameter, TwimlParameter, generate_media_streams_twiml
    logger.info("Successfully imported TwiML classes")
except ImportError as e:
    logger.error(f"Failed to import TwiML classes: {e}")
    logger.info("This script needs to be run from the root of the RedBarSushiAI project")
    sys.exit(1)

# Test TwiML generation with Parameter child elements
def test_twiml_generation():
    # Define custom parameters
    custom_params = [
        {"name": "debug", "value": "true"},
        {"name": "client", "value": "twilio"},
        {"name": "time", "value": "1234567890"}
    ]
    
    # Create the TwimlStreamParameter
    stream_params = TwimlStreamParameter(
        url="wss://redbarsushiai-staging.onrender.com/ws-test/TEST123",
        track="inbound_track",  # For <Connect><Stream>, must use inbound_track
        name="media_stream",
        custom_parameters=custom_params
    )
    
    # Create the TwimlParameter
    twiml_params = TwimlParameter(
        voice="Polly.Amy-Neural",
        language="en-US",
        greeting_text="Welcome to test",
        fallback_text="Sorry for the error",
        stream_params=stream_params,
        call_sid="TEST123"
    )
    
    # Generate the TwiML
    twiml = generate_media_streams_twiml(twiml_params)
    
    # Print the generated TwiML
    print("\n=== Generated TwiML ===")
    print(twiml)
    print("======================\n")
    
    # Verify the TwiML doesn't contain unescaped ampersands
    if "&" in twiml and "&amp;" not in twiml:
        logger.warning("⚠️ TwiML contains unescaped ampersands (&), which may cause XML parsing errors")
    else:
        logger.info("✅ TwiML doesn't contain unescaped ampersands")
    
    # Check for Parameter elements
    if "<Parameter" in twiml:
        logger.info("✅ TwiML contains Parameter elements")
    else:
        logger.warning("⚠️ TwiML doesn't contain Parameter elements")
    
    return twiml

if __name__ == "__main__":
    logger.info("Testing TwiML generation with Parameter child elements...")
    try:
        twiml = test_twiml_generation()
        logger.info("Test completed successfully")
    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1)