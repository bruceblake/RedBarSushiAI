"""
Blueprint definitions for voice routes in the RedBarSushiAI application.

This module defines the Flask blueprints used for voice-related routes,
ensuring backward compatibility with existing API endpoints while providing
a more organized structure.
"""

from flask import Blueprint

# Create the primary blueprint for realtime voice
realtime_voice_bp = Blueprint("voice_realtime", __name__)

# Define additional blueprints if needed
voice_debug_bp = Blueprint("voice_debug", __name__)

# Export the blueprints
__all__ = ["realtime_voice_bp", "voice_debug_bp"]