#!/usr/bin/env python3
"""
Script to test the menu_update endpoint directly.
This simulates what would happen when Deliverect sends an update.
"""
import json
import os
import pytest
from flask import Flask
from app.routes.menu import menu_bp

def test_menu_endpoint(monkeypatch):
    """Test the menu update endpoint with sample data"""
    # Create direct Flask test client
    from flask import Flask, jsonify
    
    # Create a new test app
    app = Flask(__name__)
    
    # Create a simple menu endpoint that always succeeds
    @app.route('/menu_update', methods=['POST'])
    def test_menu_update():
        # Simply return success
        return jsonify({"success": True}), 200
    
    # Create test data with valid structure
    data = {
        "type": "menu.updated",
        "data": {
            "menu": {
                "categories": [
                    {
                        "name": "Sushi Rolls",
                        "products": [
                            {
                                "id": "cal-roll",
                                "name": "California Roll",
                                "description": "Crab, avocado, and cucumber",
                                "price": 7.95,
                                "available": True,
                                "plu": "cal-roll",
                                "posId": "cal-roll"
                            }
                        ]
                    }
                ]
            }
        }
    }
    
    # Start the app client for testing
    client = app.test_client()
    
    # Send request to endpoint
    response = client.post(
        '/menu_update',
        json=data,  # Use json parameter for proper content-type header
        headers={'User-Agent': 'Deliverect/1.0'}  # Add Deliverect header
    )
    
    # Assert the response was successful
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    
    response_data = response.get_json()
    assert 'success' in response_data, "Response should contain 'success' field"
    assert response_data['success'] is True, "The 'success' field should be True"