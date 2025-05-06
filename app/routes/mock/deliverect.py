"""
Mock Deliverect API endpoints for testing.

This module provides mock implementations of Deliverect API endpoints
that can be used during testing to avoid making actual API calls.
"""

from flask import Blueprint, request, jsonify
import os
import time
import json
import logging

# Get the logger
logger = logging.getLogger(__name__)

# Create a blueprint for mock Deliverect endpoints
mock_deliverect_bp = Blueprint('mock_deliverect', __name__, url_prefix='/mock/deliverect')

@mock_deliverect_bp.route('', methods=['POST'])
def mock_create_order():
    """
    Mock endpoint for creating a Deliverect order.
    
    This endpoint mimics the behavior of the Deliverect API when creating a new order.
    It returns a 201 status code with a mock order response.
    
    Returns:
        JSON response with mock order data
    """
    # Check if we're in testing mode
    if os.environ.get('TESTING', 'False').lower() != 'true':
        return jsonify({'error': 'Mock endpoints are only available in testing mode'}), 403
    
    # Parse the request body
    try:
        payload = request.json
        
        # Log the received payload
        logger.info(f"Mock Deliverect received: {json.dumps(payload)}")
        
        # Extract the channel order ID
        channel_order_id = payload.get('channelOrderId', 'unknown')
        
        # Generate a mock order response
        response = {
            'orderId': f"mock-order-{int(time.time())}",
            'status': 10,  # Received
            'channelOrderId': channel_order_id,
            'location': 'mock-location-123',
            'channelLink': 'mock-channel-link-456',
            'message': 'Order created successfully'
        }
        
        # Return the mock response with a 201 (Created) status code
        return jsonify(response), 201
    
    except Exception as e:
        logger.error(f"Error in mock Deliverect endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 400

@mock_deliverect_bp.route('/<channel_order_id>', methods=['GET'])
def mock_get_order_status(channel_order_id):
    """
    Mock endpoint for getting Deliverect order status.
    
    This endpoint mimics the behavior of the Deliverect API when requesting
    the status of an existing order.
    
    Args:
        channel_order_id: The ID of the order to look up
        
    Returns:
        JSON response with mock order status
    """
    # Check if we're in testing mode
    if os.environ.get('TESTING', 'False').lower() != 'true':
        return jsonify({'error': 'Mock endpoints are only available in testing mode'}), 403
    
    # Generate a mock order status response
    response = {
        'orderId': f"mock-order-123",
        'status': int(request.args.get('status', 20)),  # Default to Accepted (20)
        'channelOrderId': channel_order_id,
        'location': 'mock-location-123',
        'channelLink': 'mock-channel-link-456'
    }
    
    # Return the mock response
    return jsonify(response), 200