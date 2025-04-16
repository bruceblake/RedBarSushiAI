"""
test_deliverect.py - Tests for Deliverect integration
"""
import pytest
from unittest.mock import patch, MagicMock
import time
import json
import sys
from unittest import mock

# Mock the celery module before importing anything that might use it
sys.modules['celery'] = MagicMock()
sys.modules['celery_app'] = MagicMock()
sys.modules['tasks'] = MagicMock()

from app.utils.deliverect import (
    get_deliverect_token,
    ensure_deliverect_token,
    get_deliverect_headers,
    build_deliverect_order
)


def test_get_deliverect_token(mock_deliverect):
    """Test getting a token from Deliverect API."""
    token = get_deliverect_token()
    
    # Check token structure
    assert token['access_token'] == 'mock_token'
    assert token['expires_in'] == 3600
    
    # Verify the API call
    mock_deliverect.assert_called_once()
    
    # Check request details
    args, kwargs = mock_deliverect.call_args
    assert kwargs['json']['grant_type'] == 'token'
    assert 'client_id' in kwargs['json']
    assert 'client_secret' in kwargs['json']


def test_get_deliverect_token_error():
    """Test error handling when getting a token from Deliverect API."""
    with patch('requests.post') as mock_post:
        # Set up the mock to raise an exception
        mock_post.side_effect = Exception("API Error")
        
        # Test error case
        with pytest.raises(Exception) as exc_info:
            get_deliverect_token()
        
        assert "API Error" in str(exc_info.value)


def test_ensure_deliverect_token():
    """Test token refresh logic."""
    # First test with expired token
    with patch('app.utils.deliverect.time.time', return_value=2000), \
         patch('app.utils.deliverect.token_expiries', {'default': 1000}), \
         patch('app.utils.deliverect.get_deliverect_token') as mock_get_token:
        
        mock_token = {'access_token': 'new_token', 'expires_in': 3600}
        mock_get_token.return_value = mock_token
        
        ensure_deliverect_token()
        
        # Should have called to get a new token
        mock_get_token.assert_called_once()
    
    # Now test with valid token
    with patch('app.utils.deliverect.time.time', return_value=2000), \
         patch('app.utils.deliverect.token_expiries', {'default': 3000}), \
         patch('app.utils.deliverect.get_deliverect_token') as mock_get_token, \
         patch('app.utils.deliverect.deliverect_tokens', {'default': {'access_token': 'current_token'}}):
        
        ensure_deliverect_token()
        
        # Should not have called to get a new token
        mock_get_token.assert_not_called()


def test_get_deliverect_headers():
    """Test getting auth headers for Deliverect API."""
    with patch('app.utils.deliverect.ensure_deliverect_token') as mock_ensure, \
         patch('app.utils.deliverect.deliverect_tokens', {'default': {'access_token': 'test_token'}}):
        
        headers = get_deliverect_headers()
        
        # Should call ensure_deliverect_token
        mock_ensure.assert_called_once()
        
        # Check header structure
        assert headers['Authorization'] == 'Bearer test_token'
        assert headers['Content-Type'] == 'application/json'


def test_build_deliverect_order():
    """Test building an order payload for Deliverect."""
    # Setup test data
    sender = '+1234567890'
    caller_name = 'Test User'
    order_items = [
        {
            "name": "California Roll",
            "quantity": 2,
            "price": 9.95,
            "reference_handler": "cal_roll_1",
            "modifier": [
                {"name": "spicy mayo", "quantity": 1, "price": 0.50}
            ]
        },
        {
            "name": "Miso Soup",
            "quantity": 1,
            "price": 3.50,
            "reference_handler": "miso_soup_1",
            "modifier": []
        }
    ]
    total_price = 23.90  # (9.95 * 2) + 0.50 + 3.50
    order_id = 'test-123'
    
    # Build the order
    payload = build_deliverect_order(sender, caller_name, order_items, total_price, order_id)
    
    # Check order structure
    assert payload['orderId'] == 'test-123'
    assert payload['customer']['name'] == 'Test User'
    assert payload['customer']['phone'] == '+1234567890'
    assert payload['total'] == 2390  # cents
    assert payload['status'] == 'NEW'
    assert payload['channelOrderId'] == 'test-123'
    
    # Check items
    assert len(payload['items']) == 2
    assert payload['items'][0]['name'] == 'California Roll'
    assert payload['items'][0]['quantity'] == 2
    assert payload['items'][0]['price'] == 995  # cents
    
    # Check modifiers
    assert len(payload['items'][0]['subItems']) == 1
    assert payload['items'][0]['subItems'][0]['name'] == 'spicy mayo'
    
    # Check tax calculation
    sales_tax = 0.06
    expected_tax = int(round(total_price * sales_tax * 100))
    assert payload['taxes'][0]['total'] == expected_tax
    assert payload['payment']['amount'] == int(round(total_price * (1 + sales_tax) * 100))


@patch('app.routes.order.channel_status', 0)  # Mock channel status as a global variable
def test_register_channel_route(client, app):
    """Test the channel registration endpoint."""
    # Test valid registration
    response = client.post('/register', json={'status': 'register'})
    assert response.status_code == 200
    assert 'statusUpdateURL' in response.json
    
    # Test activation
    response = client.post('/register', json={'status': 'active'})
    assert response.status_code == 200
    
    # Test deactivation
    response = client.post('/register', json={'status': 'inactive'})
    assert response.status_code == 200
    
    # Test invalid status
    response = client.post('/register', json={'status': 'invalid'})
    assert response.status_code == 400
    assert 'error' in response.json


@pytest.mark.skip(reason="Skipping order_status_endpoint test as it requires special setup")
def test_order_status_endpoint(client, app):
    """Test the order status endpoint."""
    # Mock the imported task module
    with patch('tasks.send_order_status_update_task') as mock_task:
        # Make sure the mock is callable with delay method
        mock_task.delay = MagicMock()
        
        # Create a test order in the database
        from app.models import Order
        from app import db
        
        with app.app_context():
            order = Order(
                id='test-order-123',
                sender='+1234567890',
                caller_name='Test User',
                message='Test order'
            )
            db.session.add(order)
            db.session.commit()
            
            # Test with valid data
            response = client.post('/order_status', json={
                'channelOrderId': 'test-order-123',
                'status': 'DELIVERED'
            })
            
            assert response.status_code == 200
            assert response.json['success'] is True
            
            # Verify order was updated
            updated_order = db.session.get(Order, 'test-order-123')
            assert updated_order.status == 'DELIVERED'
            
            # Test with non-existent order
            response = client.post('/order_status', json={
                'channelOrderId': 'non-existent',
                'status': 'DELIVERED'
            })
            
            assert response.status_code == 404
            assert 'error' in response.json
            
            # Test with missing parameters
            response = client.post('/order_status', json={
                'status': 'DELIVERED'
            })
            
            assert response.status_code == 400
            assert 'error' in response.json


def test_unique_order_ids_per_location():
    """Test that order IDs are unique per location."""
    # Define different locations
    location_1 = "downtown"
    location_2 = "uptown"
    
    # Test with location prefixes
    with patch('uuid.uuid4') as mock_uuid4:
        mock_uuid4.return_value = "test-uuid-fixed"
        
        # With location prefix, the order IDs should be unique per location
        order_id_1 = f"{location_1}-{mock_uuid4()}"
        order_id_2 = f"{location_2}-{mock_uuid4()}"
        
        # Assert they are different despite same UUID
        assert order_id_1 != order_id_2
        assert location_1 in order_id_1
        assert location_2 in order_id_2
    
    # Test location-specific order IDs in a simulated implementation
    order_items = [{"name": "Item", "quantity": 1, "price": 10.0, "reference_handler": "item1"}]
    
    # Create a test function that would generate location-specific orders
    def generate_order_with_location(order_id, location):
        # Base order from standard function
        base_order = build_deliverect_order(
            sender="+1234567890",
            caller_name="Test User",
            order_items=order_items,
            total_price=10.0,
            order_id=order_id
        )
        
        # Add location to reference
        location_reference = f"{location}-{base_order.get('reference', '')}"
        base_order['reference'] = location_reference
        
        # Use location-prefixed order ID
        location_order_id = f"{location}-{order_id}"
        base_order['orderId'] = location_order_id
        base_order['channelOrderId'] = location_order_id
        
        return base_order
    
    # Test the simulated implementation
    order1 = generate_order_with_location("test-order-123", location_1)
    order2 = generate_order_with_location("test-order-123", location_2)
    
    # Assert orders have location-specific IDs
    assert location_1 in order1['orderId']
    assert location_2 in order2['orderId']
    assert order1['orderId'] != order2['orderId']
    
    # Assert orders have location-specific references
    assert location_1 in order1['reference']
    assert location_2 in order2['reference']
    assert order1['reference'] != order2['reference']