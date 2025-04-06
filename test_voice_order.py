#!/usr/bin/env python3
# test_voice_order.py
import requests
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s: %(message)s'
)

# Test endpoint URL - change to your local server address
BASE_URL = "http://localhost:5000"

def test_take_order():
    """Test the take_order endpoint to ensure menu is available"""
    url = f"{BASE_URL}/take_order"
    
    # Simulate a Twilio POST request
    data = {
        'From': '+12025550123',
        'SpeechResult': 'I would like to order a hamburger with fries'
    }
    
    print("Testing order endpoint...")
    response = requests.post(url, data=data)
    
    print(f"Status code: {response.status_code}")
    
    # Check if we got a response with the menu unavailable message
    if "menu is currently unavailable" in response.text:
        print("ERROR: Menu still shows as unavailable!")
    else:
        print("SUCCESS: Menu is available!")
        
    # Print the response for inspection
    print("\nResponse content:")
    print(response.text[:500] + "..." if len(response.text) > 500 else response.text)

if __name__ == "__main__":
    test_take_order()