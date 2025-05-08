"""
Mock API endpoints for testing.

This package provides mock implementations of external API endpoints
that can be used during testing to avoid making actual API calls.
"""

from flask import Blueprint
from .deliverect import mock_deliverect_bp

# Create a blueprint for mock endpoints
mock_bp = Blueprint('mock', __name__, url_prefix='/mock')

# Register the mock Deliverect blueprint
mock_bp.register_blueprint(mock_deliverect_bp)

# Function to register the mock endpoints with the app
def register_mock_endpoints(app):
    """
    Register mock endpoints with the Flask app.
    
    Args:
        app: The Flask app
    """
    app.register_blueprint(mock_bp)