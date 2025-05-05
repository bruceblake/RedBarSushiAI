"""
Main module for voice routes and integration with Flask.

This module provides integration points for the voice routes in the RedBarSushiAI 
application, ensuring backward compatibility with existing code.
"""

import logging
import os
import importlib

# Set up logger
logger = logging.getLogger(__name__)

def initialize_voice_routes(app):
    """
    Initialize voice routes and components.
    
    Args:
        app: The Flask application instance
    """
    logger.info("[VOICE] Initializing voice routes and components")
    
    # Import voice routes package
    from app.routes.voice import init_voice_routes
    
    # Initialize voice routes
    init_voice_routes(app)
    
    # Log successful initialization
    logger.info("[VOICE] Voice routes and components initialized successfully")
    
    # Return the initialized components
    return {
        "status": "initialized"
    }

def get_original_voice_bp():
    """
    Get the original voice blueprint for backward compatibility.
    
    Returns:
        The voice_orchestrated_realtime blueprint
    """
    from app.routes.voice.blueprints import realtime_voice_bp
    return realtime_voice_bp