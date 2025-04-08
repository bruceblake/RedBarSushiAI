#!/usr/bin/env python
"""
Test script for SMS command handling.
This script simulates SMS commands being sent to the Flask endpoint.
"""

import os
import sys
import json
import requests
import logging
from twilio.twiml.messaging_response import MessagingResponse
from flask import Flask, request
import xml.etree.ElementTree as ET

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test phone number
TEST_PHONE_NUMBER = "+15555555555"

def test_local_sms_command(command, phone_number=TEST_PHONE_NUMBER):
    """
    Simulate sending an SMS command to the local Flask server.
    """
    from app import create_app
    
    app = create_app()
    with app.test_client() as client:
        # Create test data that simulates a Twilio SMS webhook
        data = {
            'From': phone_number,
            'Body': command
        }
        
        # Post to the SMS endpoint
        response = client.post('/sms', data=data)
        
        # Check response
        if response.status_code == 200:
            # Get the TwiML response
            twiml_response = response.data.decode('utf-8')
            
            # Parse the TwiML to extract the message
            try:
                root = ET.fromstring(twiml_response)
                message_element = root.find(".//Message")
                
                if message_element is not None and message_element.text:
                    message_text = message_element.text.strip()
                    logger.info(f"Received response for '{command}': Success")
                    print(f"\n----- Response to '{command}' -----\n")
                    print(message_text)
                    return True, message_text
                else:
                    logger.error(f"No message found in TwiML response: {twiml_response}")
                    return False, "No message found in response"
            except Exception as e:
                logger.error(f"Error parsing TwiML: {e}")
                logger.error(f"Raw response: {twiml_response}")
                return False, str(e)
        else:
            logger.error(f"Error: HTTP {response.status_code}")
            logger.error(f"Response: {response.data.decode('utf-8')}")
            return False, f"HTTP Error: {response.status_code}"

def test_all_commands():
    """
    Test all basic SMS commands.
    """
    commands = [
        "status",
        "help",
        "menu",
        "hours",
        "location",
        "contact",
        "specials",
        "random text"
    ]
    
    results = {}
    
    for command in commands:
        print(f"\nTesting command: '{command}'")
        success, response = test_local_sms_command(command)
        results[command] = success
    
    # Print summary
    print("\n===== Command Test Summary =====")
    for command, success in results.items():
        status = "✅ Working" if success else "❌ Failed"
        print(f"{command}: {status}")
    
    # Return overall success
    return all(results.values())

if __name__ == "__main__":
    print("===== Testing SMS Command Handling =====")
    
    if len(sys.argv) > 1:
        # Test a single command
        command = sys.argv[1]
        test_local_sms_command(command)
    else:
        # Test all commands
        success = test_all_commands()
        
        if success:
            print("\n✅ All SMS commands are working!")
        else:
            print("\n❌ Some SMS commands failed!")