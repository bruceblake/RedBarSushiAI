import json
import pytest
from app import create_app
from flask import Flask
from unittest.mock import patch, MagicMock

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_async_menu_update(client):
    """Test that menu_update endpoint correctly handles the async menu format."""
    # Create a sample async menu format
    sample_menu = {
        "body": {
            "menus": [
                {
                    "categories": [
                        {
                            "id": "cat1",
                            "name": "Sushi Rolls",
                            "products": [
                                {
                                    "id": "prod1",
                                    "name": "California Roll",
                                    "price": 995,  # in cents
                                    "plu": "CAL-ROLL",
                                    "description": "Crab, avocado and cucumber roll",
                                    "available": True
                                },
                                {
                                    "id": "prod2",
                                    "name": "Spicy Tuna Roll",
                                    "price": 1295,  # in cents
                                    "plu": "SPICY-TUNA",
                                    "description": "Spicy tuna roll with cucumber",
                                    "available": True
                                }
                            ]
                        }
                    ]
                }
            ],
            "stores": ["store1"],
            "callback": "https://api.staging.deliverect.com/channelName/menuStatus/1234567890"
        }
    }
    
    # Mock requests.post to avoid actually calling the callback URL
    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Send request to menu_update endpoint
        response = client.post('/menu_update', json=sample_menu)
        
        # Check response
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['items'] == 3  # Items include the category and the two menu items
        
        # Verify callback was called with ONLINE status
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://api.staging.deliverect.com/channelName/menuStatus/1234567890"
        assert call_args[1]['json']['status'] == "ONLINE"

def test_async_menu_update_no_items(client):
    """Test that menu_update endpoint correctly handles the async menu format with no valid items."""
    # Create a sample async menu format with no products
    sample_menu = {
        "body": {
            "menus": [
                {
                    "categories": [
                        {
                            "id": "cat1",
                            "name": "Sushi Rolls",
                            "products": []
                        }
                    ]
                }
            ],
            "stores": ["store1"],
            "callback": "https://api.staging.deliverect.com/channelName/menuStatus/1234567890"
        }
    }
    
    # Mock requests.post to avoid actually calling the callback URL
    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Send request to menu_update endpoint
        response = client.post('/menu_update', json=sample_menu)
        
        # Check response - we should get success with the category as an item
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['items'] == 1  # Just the category itself is an item
        
        # Verify callback was called with ONLINE status
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://api.staging.deliverect.com/channelName/menuStatus/1234567890"
        assert call_args[1]['json']['status'] == "ONLINE"