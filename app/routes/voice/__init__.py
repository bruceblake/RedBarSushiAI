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

def init_voice_routes(app):
    """
    Initialize voice routes and register blueprints with the Flask app.
    
    Args:
        app: The Flask application instance
    """
    logger.info("Initializing voice routes")
    
    # Register all voice-related blueprints
    app.register_blueprint(realtime_voice_bp, url_prefix="/voice/realtime")
    app.register_blueprint(voice_debug_bp, url_prefix="/voice/debug")
    
    # Import routes to register them with the blueprints
    import app.routes.voice.routes
    
    # Register WebSocket routes
    from app import sock
    from app.routes.voice.realtime.stream_handler import handle_media_stream
    
    @sock.route("/ws/voice/media")
    async def media_stream_ws(ws):
        """WebSocket endpoint for Twilio Media Streams API."""
        await handle_media_stream(ws)
    
    # Also provide a debug WebSocket endpoint
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
    
    logger.info("Voice routes initialized successfully")

# Export the blueprints and initialization function
__all__ = ["voice_bp", "realtime_voice_bp", "voice_debug_bp", "init_voice_routes"]