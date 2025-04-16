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
    # Skip this test by default since it requires a running server
    import pytest
    pytest.skip("Test requires a running server. Run manually with the server running.")
    
    url = f"{BASE_URL}/take_order"
    
    # Simulate a Twilio POST request
    data = {
        'From': '+12025550123',
        'SpeechResult': 'I would like to order a hamburger with fries'
    }
    
    print("Testing order endpoint...")
    
    try:
        response = requests.post(url, data=data, timeout=2)
        
        print(f"Status code: {response.status_code}")
        
        # Check if we got a response with the menu unavailable message
        if "menu is currently unavailable" in response.text:
            print("ERROR: Menu still shows as unavailable!")
            assert False, "Menu is showing as unavailable"
        else:
            print("SUCCESS: Menu is available!")
            assert True
            
        # Print the response for inspection
        print("\nResponse content:")
        print(response.text[:500] + "..." if len(response.text) > 500 else response.text)
    except requests.exceptions.ConnectionError:
        pytest.skip("Could not connect to server. Make sure the Flask app is running.")
    except requests.exceptions.Timeout:
        pytest.skip("Request timed out. Make sure the Flask app is running correctly.")

if __name__ == "__main__":
    test_take_order()