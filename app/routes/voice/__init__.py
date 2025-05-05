"""
Voice routes package for RedBarSushiAI application.

This package provides voice processing functionality using WebSockets
and OpenAI's Realtime API for interactive voice ordering.
"""

import os
import sys
import logging
import json
import time
import asyncio
import traceback
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

# Flag to track WebSocket route registration status
_websocket_routes_registered = False
_voice_routes_initialized = False
_debug_websocket_registered = False

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

def init_voice_system(flask_app):
    """
    Initialize the voice system with all required components.
    
    Args:
        flask_app: The Flask application instance
        
    Returns:
        dict: Information about the initialized voice system
    """
    # Prevent multiple initializations
    global _voice_routes_initialized
    if _voice_routes_initialized:
        logger.info("Voice system already initialized, skipping")
        return {
            "status": "success",
            "components": ["frontline_agent", "fsm_orchestrator", "tool_registry"],
            "routes_initialized": True,
            "already_initialized": True
        }
    
    logger.info("Initializing voice system with OpenAI Realtime API")
    
    # Initialize voice components
    try:
        # Import agent components here to avoid circular imports
        from app.agents.factory_with_orchestration import enhanced_agent_factory
        from app.utils.agent_orchestration import FSMOrchestrator
        from app.routes.voice.utils.tools_registry import ToolRegistry, register_default_tools
        
        # Create agents using the factory
        frontline_agent = enhanced_agent_factory.create_agents()
        fsm_orchestrator = FSMOrchestrator()
        
        # Create tool registry and register default tools
        tool_registry = ToolRegistry()
        register_default_tools(tool_registry)
        
        # Set global components
        set_global_components(
            frontline_agent=frontline_agent,
            fsm_orchestrator=fsm_orchestrator,
            tool_registry=tool_registry
        )
        
        logger.info("Voice system components initialized successfully")
        
        # Initialize routes with the Flask app
        init_voice_routes(flask_app)
        
        # Set initialization flag
        _voice_routes_initialized = True
        
        return {
            "status": "success",
            "components": ["frontline_agent", "fsm_orchestrator", "tool_registry"],
            "routes_initialized": True
        }
    except Exception as e:
        logger.error(f"Error initializing voice system: {str(e)}")
        logger.error(f"Error details: {traceback.format_exc()}")
        raise RuntimeError(f"Failed to initialize voice system: {str(e)}")

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
    
    # Set a flag to indicate routes initialization is in progress
    # This prevents circular initialization
    global _voice_routes_initialized
    if getattr(init_voice_routes, '_in_progress', False):
        logger.warning("Voice routes initialization already in progress, skipping WebSocket registration")
        return
        
    # Mark initialization as in progress to prevent circular calls
    setattr(init_voice_routes, '_in_progress', True)
    
    # Register WebSocket routes - only if we have a valid Flask app
    if hasattr(flask_app, 'config'):  # Simple check for Flask app-like object
        try:
            from app import sock
            
            # Import enhanced logging and handler early to avoid scope issues
            from app.routes.voice.utils.websocket_logging import websocket_handler
            from app.routes.voice.realtime.enhanced_stream_handler import handle_enhanced_media_stream
            
            # Only register WebSocket routes if we haven't already
            # Improve route registration check to properly handle Flask-Sock
            # Log the current sock._rules structure to help with debugging
            logger.info(f"WebSocket routes before registration: {getattr(sock, '_rules', {})}")
            
            # Map existing route paths
            existing_routes = list(getattr(sock, '_rules', {}).keys())
            # More robust way to get function names
            existing_funcs = []
            for route_func in getattr(sock, '_rules', {}).values():
                if hasattr(route_func, '__name__'):
                    existing_funcs.append(route_func.__name__)
                elif hasattr(route_func, 'func_name'):
                    existing_funcs.append(route_func.func_name)
                    
            # Log what we found
            logger.info(f"Existing WebSocket routes: {existing_routes}")
            logger.info(f"Existing WebSocket functions: {existing_funcs}")
            
            # Use global flags to check if routes were already registered
            global _websocket_routes_registered, _debug_websocket_registered
            
            # Media stream WebSocket route
            if _websocket_routes_registered or "/ws/voice/media" in existing_routes or "media_stream_ws" in existing_funcs:
                logger.info("WebSocket routes already registered, skipping registration")
            else:
                @sock.route("/ws/voice/media")
                @websocket_handler
                async def media_stream_ws(ws):
                    """WebSocket endpoint for Twilio Media Streams API with enhanced connection handling."""
                    # Log connection information with appropriate log level
                    logger.info(f"[MEDIA_STREAM] WebSocket connection established to /ws/voice/media")
                    logger.info(f"[MEDIA_STREAM] Connection ID: {getattr(ws, '_log_id', 'unknown')}")
                    
                    # Get request info if available
                    if hasattr(ws, 'request') and hasattr(ws.request, 'headers'):
                        headers = ws.request.headers
                        logger.debug(f"[MEDIA_STREAM] Headers: {headers}")
                        # Check if this is a Twilio connection
                        user_agent = headers.get('User-Agent', '')
                        is_twilio = 'twilio' in user_agent.lower()
                        logger.info(f"[MEDIA_STREAM] User-Agent: {user_agent}")
                        logger.info(f"[MEDIA_STREAM] Is Twilio: {is_twilio}")
                    
                    # Use the enhanced stream handler for robust connection management
                    await handle_enhanced_media_stream(ws)
                
                logger.info("Registered /ws/voice/media WebSocket route with improved connection handling")
                
                # Set the global flag to prevent duplicate registration
                _websocket_routes_registered = True
            
            # Debug WebSocket route - separate flag for this route
            if _debug_websocket_registered or "/ws/voice/debug" in existing_routes or "debug_websocket" in existing_funcs:
                logger.info("Debug WebSocket route already registered, skipping registration")
            else:
                @sock.route("/ws/voice/debug")
                @websocket_handler
                async def debug_websocket(ws):
                    """Simple WebSocket endpoint to verify WebSocket connectivity."""
                    logger.info("[DEBUG WEBSOCKET] WebSocket connection established to /ws/voice/debug")
                    
                    # Store the start time for diagnostics
                    setattr(ws, '_start_time', time.time())
                    
                    # Log detailed information about the WebSocket connection
                    logger.debug(f"[DEBUG WEBSOCKET] WebSocket info: {ws}")
                    if hasattr(ws, 'request'):
                        logger.debug(f"[DEBUG WEBSOCKET] Request headers: {ws.request.headers}")
                    logger.info(f"[DEBUG WEBSOCKET] Environment: {os.environ.get('FLASK_ENV')}")
                    
                    try:
                        # Send a simple message to the client
                        logger.info("[DEBUG WEBSOCKET] Sending initial connection message")
                        connection_message = {
                            "type": "connected",
                            "message": "WebSocket connection established successfully",
                            "time": time.time(),
                            "server_info": {
                                "python_version": sys.version,
                                "flask_env": os.environ.get('FLASK_ENV', 'unknown'),
                                "server_time": time.time()
                            }
                        }
                        
                        # Always use strings for WebSocket to avoid potential encoding issues
                        await ws.send(json.dumps(connection_message))
                        logger.info("[DEBUG WEBSOCKET] Initial message sent successfully")
                        
                        # Echo any messages back to the client with additional diagnostics
                        while True:
                            try:
                                logger.debug("[DEBUG WEBSOCKET] Waiting for client message")
                                message = await asyncio.wait_for(ws.receive(), timeout=5.0)
                                logger.debug(f"[DEBUG WEBSOCKET] Received message: {message[:100]}...")
                                
                                # Echo the message back with diagnostics
                                response = {
                                    "type": "echo",
                                    "original": message if len(str(message)) < 100 else message[:100] + "...(truncated)",
                                    "time": time.time(),
                                    "diagnostics": {
                                        "connection_id": getattr(ws, '_log_id', 'unknown'),
                                        "session_time": time.time() - getattr(ws, '_start_time', time.time())
                                    }
                                }
                                await ws.send(json.dumps(response))
                                logger.debug("[DEBUG WEBSOCKET] Echo response sent")
                            except asyncio.TimeoutError:
                                # Send a ping to keep the connection alive with diagnostics
                                logger.debug("[DEBUG WEBSOCKET] Timeout waiting for message, sending ping")
                                ping_message = {
                                    "type": "ping",
                                    "time": time.time(),
                                    "message": "Keep-alive ping",
                                    "diagnostics": {
                                        "connection_id": getattr(ws, '_log_id', 'unknown'),
                                        "session_time": time.time() - getattr(ws, '_start_time', time.time())
                                    }
                                }
                                try:
                                    await ws.send(json.dumps(ping_message))
                                    logger.debug("[DEBUG WEBSOCKET] Ping sent successfully")
                                except Exception as ping_error:
                                    logger.warning(f"[DEBUG WEBSOCKET] Error sending ping: {ping_error}")
                                    # Try with a simple string message as fallback
                                    try:
                                        await ws.send("ping")
                                        logger.info("[DEBUG WEBSOCKET] Simple ping sent successfully")
                                    except Exception as simple_ping_error:
                                        logger.error(f"[DEBUG WEBSOCKET] Error sending simple ping: {simple_ping_error}")
                                        raise
                            except Exception as e:
                                logger.error(f"[DEBUG WEBSOCKET] Error during echo: {str(e)}")
                                logger.error(traceback.format_exc())
                                break
                    except Exception as e:
                        logger.error(f"[DEBUG WEBSOCKET] Error during session: {str(e)}")
                        logger.error(traceback.format_exc())
                    
                    logger.info("[DEBUG WEBSOCKET] WebSocket connection closed")
                logger.info("Registered /ws/voice/debug WebSocket route with enhanced logging")
                
                # Set the global flag to prevent duplicate registration
                _debug_websocket_registered = True
                
        except Exception as socket_error:
            logger.error(f"Failed to register WebSocket routes: {socket_error}")
    
    # Reset the initialization flag
    setattr(init_voice_routes, '_in_progress', False)
    
    logger.info("Voice routes initialized successfully")

# Export the blueprints and initialization functions
__all__ = ["voice_bp", "realtime_voice_bp", "voice_debug_bp", "init_voice_routes", "init_voice_system",
           "set_global_components", "get_global_component"]