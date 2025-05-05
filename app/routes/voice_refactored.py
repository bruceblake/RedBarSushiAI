"""
Entry point for voice integration in RedBarSushiAI.

This module provides backwards compatibility for integrating the refactored
voice system with the existing application structure.
"""

import logging
import importlib

# Set up logger
logger = logging.getLogger(__name__)

# Import the refactored voice package
from app.routes.voice.main import get_original_voice_bp

# Export the blueprint with the original name for compatibility
realtime_voice_bp = get_original_voice_bp()

def init_voice_system(app):
    """
    Initialize the voice system with the Flask app.
    
    Args:
        app: The Flask application instance
    """
    # Import and initialize the voice routes
    from app.routes.voice.main import initialize_voice_routes
    return initialize_voice_routes(app)