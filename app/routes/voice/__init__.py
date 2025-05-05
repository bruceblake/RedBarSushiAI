"""
Voice routes package for RedBarSushiAI application.

This package provides voice processing functionality using WebSockets
and OpenAI's Realtime API for interactive voice ordering.
"""

import os
import logging
import json
import time
import asyncio
from flask import Blueprint

# Import the blueprints
from app.routes.voice.blueprints import realtime_voice_bp, voice_debug_bp

# Create logger
logger = logging.getLogger(__name__)

# Create a voice_bp for compatibility with app/__init__.py import
voice_bp = Blueprint('voice', __name__)

# Global components for voice processing
_global_components = {
    'frontline_agent': None,
    'agent_graph': None,
    'slot_store': None,
    'fsm_orchestrator': None,
    'model_escalator': None,
    'tool_registry': None
}

def set_global_components(**components):
    """
    Set global components for voice processing.
    
    Args:
        **components: Component instances to set globally
    """
    for name, component in components.items():
        if name in _global_components:
            _global_components[name] = component
            logger.info(f"Set global component '{name}': {type(component).__name__}")
        else:
            logger.warning(f"Unknown component name: '{name}'")

def get_global_component(name):
    """
    Get a global component by name.
    
    Args:
        name: Component name
        
    Returns:
        Component instance or None if not found
    """
    return _global_components.get(name)

def init_voice_routes(flask_app):
    """
    Initialize voice routes and register blueprints with the Flask app.
    
    Args:
        flask_app: The Flask application instance
    """
    logger.info("Initializing voice routes")
    
    # Verify we have a Flask app with the register_blueprint method
    from flask import Flask
    if not isinstance(flask_app, Flask):
        logger.error(f"Expected Flask app instance, got {type(flask_app).__name__}")
        logger.error("Cannot register voice blueprints with non-Flask app")
        return
    
    # First import routes module to register route handlers with the blueprints
    # IMPORTANT: This must be done BEFORE registering the blueprints with the app
    import app.routes.voice.routes
    
    # Now register the blueprints with routes already attached
    # Note: The realtime_voice_bp will be registered at the root level in app/__init__.py
    # Here we only register the debug blueprint
    flask_app.register_blueprint(voice_debug_bp, url_prefix="/voice/debug")
    
    # Log routes registered
    logger.info("Initialized voice routes with debug blueprint")
    
    # Register WebSocket routes - only if we have a valid Flask app
    if hasattr(flask_app, 'config'):  # Simple check for Flask app-like object
        try:
            from app import sock
            from app.routes.voice.realtime.stream_handler import handle_media_stream
            
            # Only register WebSocket routes if we haven't already
            existing_routes = getattr(sock, '_rules', {})
            if "/ws/voice/media" not in existing_routes:
                @sock.route("/ws/voice/media")
                async def media_stream_ws(ws):
                    """WebSocket endpoint for Twilio Media Streams API."""
                    await handle_media_stream(ws)
                logger.info("Registered /ws/voice/media WebSocket route")
            
            # Also provide a debug WebSocket endpoint
            if "/ws/voice/debug" not in existing_routes:
                @sock.route("/ws/voice/debug")
                async def debug_websocket(ws):
                    """Simple WebSocket endpoint to verify WebSocket connectivity."""
                    logger.critical("[DEBUG WEBSOCKET] WebSocket connection established to /ws/voice/debug")
                    
                    try:
                        # Send a simple message to the client
                        await ws.send(json.dumps({
                            "message": "WebSocket connection established successfully",
                            "time": time.time()
                        }))
                        
                        # Echo any messages back to the client
                        while True:
                            try:
                                message = await asyncio.wait_for(ws.receive(), timeout=30.0)
                                logger.critical(f"[DEBUG WEBSOCKET] Received message: {message}")
                                
                                # Echo the message back
                                await ws.send(json.dumps({
                                    "echo": message,
                                    "time": time.time()
                                }))
                            except asyncio.TimeoutError:
                                # Send a ping to keep the connection alive
                                await ws.send(json.dumps({"ping": time.time()}))
                            except Exception as e:
                                logger.critical(f"[DEBUG WEBSOCKET] Error: {str(e)}")
                                break
                    except Exception as e:
                        logger.critical(f"[DEBUG WEBSOCKET] Error: {str(e)}")
                    
                    logger.critical("[DEBUG WEBSOCKET] WebSocket connection closed")
                logger.info("Registered /ws/voice/debug WebSocket route")
        except Exception as socket_error:
            logger.error(f"Failed to register WebSocket routes: {socket_error}")
    
    logger.info("Voice routes initialized successfully")

# Export the blueprints and initialization function
__all__ = ["voice_bp", "realtime_voice_bp", "voice_debug_bp", "init_voice_routes",
           "set_global_components", "get_global_component"]