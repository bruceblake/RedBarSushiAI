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
    # Create a minimal Flask app for testing
    app = Flask(__name__)
    app.register_blueprint(menu_bp)
    app.config['TESTING'] = True
    
    # Set up test output path
    test_output_path = os.path.join(os.path.dirname(__file__), '..', '..', 'testing_data', 'test_menu_output.json')
    app.config['MENU_FILE_PATH'] = test_output_path
    
    # Mock the write_menu_file function to prevent actual file writes
    def mock_write_menu_file(menu_data, menu_file_path=None):
        return True
        
    monkeypatch.setattr('app.routes.menu.write_menu_file', mock_write_menu_file)
    
    # Load test data from project root testing_data
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    test_file_path = os.path.join(root, 'testing_data', 'test_deliverect_payload.json')
    with open(test_file_path, 'r') as f:
        data = json.load(f)
    
    # Start the app client for testing
    client = app.test_client()
    
    # Send request to endpoint
    response = client.post(
        '/menu_update',
        data=json.dumps(data),
        content_type='application/json'
    )
    
    # Assert the response was successful
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    
    response_data = response.get_json()
    assert 'success' in response_data, "Response should contain 'success' field"
    assert response_data['success'] is True, "The 'success' field should be True"