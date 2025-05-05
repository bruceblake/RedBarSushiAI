"""
Route definitions for voice endpoints in RedBarSushiAI.

This module defines the voice-related HTTP endpoints, including
Twilio webhook handlers and voice call entry points.
"""

import logging
import uuid
import os
from flask import request, Response

from app.routes.voice.blueprints import realtime_voice_bp, voice_debug_bp
from app.routes.voice.twilio.improved_twiml import generate_optimized_media_streams_twiml, get_environment_name, get_host_for_ws

# Set up logger
logger = logging.getLogger(__name__)

@realtime_voice_bp.route("/", methods=["GET", "POST"])
@realtime_voice_bp.route("/voice", methods=["GET", "POST"])
@realtime_voice_bp.route("/webhook/voice", methods=["GET", "POST"])
def receive_call():
    """
    Handle an incoming voice call with the Realtime API integration.
    Uses Twilio Media Streams for real-time audio processing.
    
    This endpoint is accessible at multiple paths for compatibility
    with different Twilio webhook configurations.
    """
    # Create a log file for this specific call
    call_sid = request.values.get("CallSid", str(uuid.uuid4()))
    log_dir = os.path.join(os.getcwd(), 'logs')
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except:
            pass  # If we can't create the dir, we'll fallback to default logging
    
    # Set up call-specific logging
    try:
        # Create a call-specific file handler
        call_log_file = os.path.join(log_dir, f'call_{call_sid}.log')
        call_file_handler = logging.FileHandler(call_log_file)
        call_file_handler.setLevel(logging.DEBUG)
        call_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
        call_file_handler.setFormatter(call_formatter)
        logger.addHandler(call_file_handler)
        
        # Also log to a common calls log file
        calls_log_file = os.path.join(log_dir, 'incoming_calls.log')
        calls_file_handler = logging.FileHandler(calls_log_file)
        calls_file_handler.setLevel(logging.INFO)
        calls_file_handler.setFormatter(call_formatter)
        logger.addHandler(calls_file_handler)
        
        logger.info(f"================== NEW CALL RECEIVED - SID: {call_sid} ==================")
    except Exception as log_error:
        logger.error(f"Failed to set up call-specific logging: {log_error}")
    
    try:
        # Log extensive details about the request to diagnose routing issues
        logger.info("==== INCOMING REALTIME CALL DETAILS ====")
        logger.info(f"Call SID: {call_sid}")
        logger.info(f"Request came from: {request.remote_addr}")
        logger.info(f"User agent: {request.user_agent}")
        logger.info(f"Host header: {request.host}")
        logger.info(f"URL: {request.url}")
        logger.info(f"Request method: {request.method}")
        logger.info(f"Environment: {os.environ.get('FLASK_ENV', 'undefined')}")
        logger.info(f"Current working directory: {os.getcwd()}")
        
        # Log all request values for debugging
        logger.info("Full request values:")
        for key, value in request.values.items():
            logger.info(f"  - {key}: {value}")
            
        # Get environment name for greeting
        environment_name = get_environment_name()
        logger.info(f"Environment identified as: {environment_name}")
        
        # Get host for WebSocket connections
        host = get_host_for_ws(request)
        
        # Generate optimized TwiML response with bidirectional stream
        twiml = generate_optimized_media_streams_twiml(call_sid, host, environment_name)
        
        # Log timing and return response
        logger.info(f"Optimized TwiML response generated for call {call_sid}")
        
        # Remove the handlers to prevent logging to this file for other requests
        if 'call_file_handler' in locals():
            logger.removeHandler(call_file_handler)
        if 'calls_file_handler' in locals():
            logger.removeHandler(calls_file_handler)
            
        return Response(twiml, mimetype="text/xml")
        
    except Exception as e:
        logger.error(f"Error handling incoming call: {str(e)}")
        logger.error(f"Error traceback: {e}")
        
        # Try to generate an error response
        try:
            from twilio.twiml.voice_response import VoiceResponse
            error_response = VoiceResponse()
            error_response.say("We're sorry, but an error occurred while processing your call. Please try again later.")
            return Response(str(error_response), mimetype="text/xml")
        except:
            return Response("Error processing call", status=500)
            
    finally:
        # Clean up the handlers
        try:
            if 'call_file_handler' in locals():
                logger.removeHandler(call_file_handler)
            if 'calls_file_handler' in locals():
                logger.removeHandler(calls_file_handler)
        except:
            pass


@realtime_voice_bp.route("/routes-debug", methods=["GET"])
def debug_routes():
    """
    Debug endpoint to show all registered routes.
    """
    from flask import current_app
    routes = []
    for rule in current_app.url_map.iter_rules():
        routes.append({
            "endpoint": rule.endpoint,
            "methods": list(rule.methods),
            "path": str(rule)
        })
    return {"routes": routes, "count": len(routes)}

@voice_debug_bp.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint for the voice system.
    Verifies that components are properly initialized.
    """
    # Try to initialize required components
    try:
        from app.agents.factory_with_orchestration import enhanced_agent_factory
        from app.utils.realtime_audio_sdk import get_realtime_processor
        
        # Try to initialize the frontline agent
        frontline = enhanced_agent_factory.create_agents()
        agent_status = "initialized" if frontline else "failed"
        
        # Try to initialize the Realtime processor
        realtime_processor = get_realtime_processor()
        realtime_status = "available" if realtime_processor else "unavailable"
        
        # Check for fallback mode
        is_fallback = False
        if hasattr(realtime_processor, 'is_fallback'):
            is_fallback = realtime_processor.is_fallback
        
        # Check Redis connection
        redis_status = "unknown"
        try:
            from app.utils.conversation_store import redis_client
            if redis_client and redis_client.ping():
                redis_status = "connected"
            else:
                redis_status = "disconnected"
        except Exception as redis_error:
            redis_status = f"error: {str(redis_error)}"
        
        # Compile the response
        return {
            "status": "ok" if agent_status == "initialized" and realtime_status == "available" else "error",
            "service": "voice_realtime",
            "agents": agent_status,
            "realtime": realtime_status,
            "realtime_fallback": is_fallback,
            "redis": redis_status,
            "environment": os.environ.get('FLASK_ENV', 'development')
        }
    except Exception as e:
        return {
            "status": "error",
            "service": "voice_realtime",
            "error": str(e)
        }