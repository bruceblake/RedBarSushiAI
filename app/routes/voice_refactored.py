"""
Entry point for voice integration in RedBarSushiAI.

This module provides compatibility for integrating the refactored
voice system with the existing application structure.
"""

import logging
import importlib

# Set up logger
logger = logging.getLogger(__name__)

# Import the refactored voice package with the same blueprint name
from app.routes.voice.blueprints import realtime_voice_bp

# Import the initialization function
from app.routes.voice.main import initialize_voice_routes

def init_voice_system(app):
    """
    Initialize the voice system with the Flask app.
    
    Args:
        app: The Flask application instance
        
    Returns:
        Dictionary with initialization status
    """
    # Initialize the refactored voice routes
    return initialize_voice_routes(app)