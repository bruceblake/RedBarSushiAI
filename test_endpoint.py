#!/usr/bin/env python3
"""
Script to test the menu_update endpoint directly.
This simulates what would happen when Deliverect sends an update.
"""
import json
import os
import requests
from flask import Flask
from app.routes.menu import menu_bp

def test_menu_endpoint():
    """Test the menu update endpoint with sample data"""
    # Create a minimal Flask app for testing
    app = Flask(__name__)
    app.register_blueprint(menu_bp)
    app.config['TESTING'] = True
    
    # Load test data
    with open('testing_data/test_deliverect_payload.json', 'r') as f:
        data = json.load(f)
    
    # Start the app client for testing
    client = app.test_client()
    
    # Send request to endpoint
    print("Testing menu_update endpoint...")
    response = client.post(
        '/menu_update',
        data=json.dumps(data),
        content_type='application/json'
    )
    
    # Print response
    print(f"Status code: {response.status_code}")
    print(f"Response: {response.get_json()}")
    
    return response

if __name__ == "__main__":
    test_menu_endpoint()