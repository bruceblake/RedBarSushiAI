#!/usr/bin/env python
"""
Test script for menu updates from Deliverect

This script simulates a Deliverect menu update request to test menu integration.
"""

import json
import os
import sys
import requests
from pprint import pprint

# Configuration
BASE_URL = "http://localhost:5000"  # Adjust as needed
MENU_UPDATE_ENDPOINT = "/menu_update"
TEST_PAYLOAD_PATH = "testing_data/test_deliverect_payload.json"

def load_test_payload():
    """Load the test Deliverect payload."""
    with open(TEST_PAYLOAD_PATH, 'r') as f:
        return json.load(f)

def test_menu_update():
    """Test the menu update endpoint."""
    payload = load_test_payload()
    
    print(f"Sending Deliverect menu update with {len(payload['categories'])} categories")
    
    # Send the request
    try:
        response = requests.post(f"{BASE_URL}{MENU_UPDATE_ENDPOINT}", json=payload)
        
        # Check the response
        if response.status_code == 200:
            print(f"SUCCESS: Menu update succeeded - Status: {response.status_code}")
            print(f"Response: {response.json()}")
            return True
        else:
            print(f"ERROR: Menu update failed - Status: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"ERROR: Exception occurred: {e}")
        return False

def test_menu_queries():
    """Test menu item queries to make sure we can find items."""
    test_items = [
        "Hamburger",
        "hamburger",  # Case variant
        "Cheese Burger",  # Space variant
        "French Fries",
        "fries",  # Shortened variant
        "Coke",  # Shortened variant
        "Water"
    ]
    
    print("\nTesting menu item queries:")
    
    # For each test item, simulate a query through the find_menu_item function
    # This is a simplified approach since we can't directly call the function in this script
    # In a real test, you'd make actual API calls or use pytest
    
    for item in test_items:
        print(f"\nChecking if '{item}' can be found in menu...")
        try:
            # Use a simple GET request to a route that would use find_menu_item
            # In practice, you'd have a dedicated test endpoint that returns menu search results
            print(f"Would search for: {item}")
            print(f"Expected to find: {item.title()} or similar")
        except Exception as e:
            print(f"ERROR checking {item}: {e}")

if __name__ == "__main__":
    # Ensure the test payload exists
    if not os.path.exists(TEST_PAYLOAD_PATH):
        print(f"ERROR: Test payload not found at {TEST_PAYLOAD_PATH}")
        sys.exit(1)
        
    # Run the tests
    success = test_menu_update()
    
    if success:
        test_menu_queries()
        
    print("\nTest complete.")