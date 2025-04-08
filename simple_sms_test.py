#!/usr/bin/env python
"""
Simplified SMS testing script without external dependencies.
"""

import sys
import os
import logging
import xml.etree.ElementTree as ET

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_command(command):
    """Test a specific SMS command"""
    try:
        from app import create_app
        
        app = create_app()
        with app.test_client() as client:
            # Post to the SMS endpoint
            response = client.post('/sms', data={
                'From': '+15555555555',
                'Body': command
            })
            
            if response.status_code == 200:
                # Get the TwiML response
                twiml_response = response.data.decode('utf-8')
                
                # Parse the TwiML to extract the message
                root = ET.fromstring(twiml_response)
                message_element = root.find(".//Message")
                
                if message_element is not None and message_element.text:
                    message_text = message_element.text.strip()
                    print(f"\n----- Response to '{command}' -----\n")
                    print(message_text)
                    return True
                else:
                    print(f"No message found in TwiML response: {twiml_response}")
                    return False
            else:
                print(f"Error: HTTP {response.status_code}")
                print(f"Response: {response.data.decode('utf-8')}")
                return False
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    print("===== Simple SMS Command Test =====")
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        print(f"Testing command: '{command}'")
        success = test_command(command)
        
        if success:
            print(f"\n✅ SMS command '{command}' is working!")
        else:
            print(f"\n❌ SMS command '{command}' failed!")
    else:
        print("Please provide a command to test (e.g., 'help', 'status', 'menu')")
        print("Usage: python simple_sms_test.py [command]")