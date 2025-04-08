#!/usr/bin/env python
"""
Red Bar Sushi AI - Help Command Test

This script specifically tests the handling of the "help" SMS command.
It directly calls the handle_sms function to verify help command detection.
"""

import logging
import sys
from flask import Flask, request
from app import create_app
from app.routes.order import handle_sms
import urllib.parse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_help_command():
    """Test the help command with various input formats"""
    # Create the Flask app
    app = create_app()
    
    # List of test cases for the help command
    test_cases = [
        "help",
        "Help",
        "HELP",
        "help!",
        "help me",
        "I need help",
        "Show me help",
        "Command list",
        "?"
    ]
    
    # Test each case
    with app.test_request_context('/sms'):
        for test_case in test_cases:
            print(f"\nTesting help command: '{test_case}'")
            # Set up the request form data
            request.form = {
                'Body': test_case,
                'From': '+15555555555'
            }
            
            # Call the handle_sms function directly
            response = handle_sms()
            
            # Check if the response contains the expected help content
            response_text = response.data.decode('utf-8')
            success = "RED BAR SUSHI HELP" in response_text and "AVAILABLE COMMANDS" in response_text
            
            # Print the result
            if success:
                print(f"✅ Success! Help command '{test_case}' was correctly identified")
            else:
                print(f"❌ Failed! Help command '{test_case}' was not identified correctly")
                print("Response snippet:")
                print(response_text[:200] + "..." if len(response_text) > 200 else response_text)
            
    print("\nHelp command testing completed!")

if __name__ == "__main__":
    print("===== Testing Help Command Handling =====")
    test_help_command()