"""
Voice routes package. This package contains the voice route modules for the RedBarSushiAI application.
"""

from flask import Blueprint

# Create Blueprint for voice-related routes
voice_bp = Blueprint("voice", __name__)

# Import all route modules to register them with the blueprint
from . import voice_core
from . import voice_call_flow
from . import voice_menu
from . import voice_transfer
from . import voice_api
from . import voice_websockets

# Export the blueprint
__all__ = ["voice_bp"]