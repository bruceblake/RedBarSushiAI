"""
Improved TwiML generation for Twilio Media Streams integration.

This module provides optimized functions to generate TwiML responses for
Twilio voice calls, configuring Media Streams for real-time audio with a 
simplified bidirectional stream approach.
"""

import logging
import os
from twilio.twiml.voice_response import VoiceResponse, Start, Stream, Connect

# Set up logger
logger = logging.getLogger(__name__)

def generate_optimized_media_streams_twiml(call_sid, hostname, environment_name="PRODUCTION"):
    """
    Generate optimized TwiML for a voice call with a bidirectional Media Stream.
    Uses <Connect><Stream> for bidirectional streaming with Twilio Media Streams,
    which allows both receiving audio from the caller and sending audio back.
    
    Args:
        call_sid: The Twilio call SID
        hostname: The hostname for WebSocket connections
        environment_name: The environment name for greeting
        
    Returns:
        TwiML response as a string
    """
    try:
        logger.info(f"[TWIML:{call_sid}] Generating bidirectional TwiML with Connect")
        
        # Make sure we're using a proper hostname with no trailing slash
        hostname = hostname.rstrip('/')
        # Use the registered and enhanced /ws/media endpoint instead of /ws/voice/media
        ws_url = f"wss://{hostname}/ws/media"
        logger.debug(f"[TWIML:{call_sid}] Streaming via {ws_url} (using enhanced media handler)")
        
        # Create the TwiML response
        response = VoiceResponse()
        
        # Add a greeting message with environment name
        greeting_message = f"Welcome to {environment_name} Red Bar Sushi AI!"
        logger.info(f"[TWIML:{call_sid}] Initial greeting: '{greeting_message}'")
        response.say(greeting_message)
        
        # Add a 1-second pause to ensure TTS completes and connection is ready
        response.pause(length=1)
        
        # Connect is required for bidirectional streaming
        # Important: This blocks all subsequent TwiML until the WebSocket disconnects
        connect = Connect()
        # Stream element inside Connect enables bidirectional streaming
        # Note: For bidirectional streams, only inbound track is supported
        # Important: Pass the CallSid to the WebSocket URL as a query parameter
        stream = Stream(
            url=f"{ws_url}?CallSid={call_sid}",
            track="inbound_track",
            name="media_stream"
        )
        connect.append(stream)

        response.append(connect)
        
        # Log the complete TwiML for debugging
        twiml_str = str(response)
        logger.debug(f"[TWIML:{call_sid}] TwiML:\n{twiml_str}")
        
        # Return the TwiML as a string
        return twiml_str
        
    except Exception as e:
        logger.error(f"[TWIML:{call_sid}] Error generating optimized TwiML: {str(e)}")
        
        # Create an error response if TwiML generation fails
        error_response = VoiceResponse()
        error_response.say("We're sorry, but an error occurred while processing your call. Please try again later.")
        return str(error_response)

def get_environment_name():
    """
    Determine the current environment name for TwiML greetings.
    
    Returns:
        String indicating the environment (STAGING or PRODUCTION)
    """
    # Determine environment by checking environment variables
    if os.environ.get("IS_STAGING") or os.environ.get("FLASK_ENV") == "staging":
        return "STAGING"
    return "PRODUCTION"

def get_host_for_ws(request):
    """
    Get the appropriate host for WebSocket connections.
    
    Args:
        request: The Flask request object
        
    Returns:
        Hostname string to use in WebSocket URLs
    """
    # Try to get the host from request headers
    host = request.headers.get('Host') or request.host
    
    # For Render, use the public-facing hostname if available
    render_external_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if render_external_hostname:
        logger.info(f"[WEBSOCKET_HOST] Using RENDER_EXTERNAL_HOSTNAME: {render_external_hostname}")
        return render_external_hostname
    
    # For staging environment, we know the exact hostname
    if os.environ.get("IS_STAGING") or os.environ.get("FLASK_ENV") == "staging":
        staging_hostname = "redbarsushiai-staging.onrender.com"
        logger.info(f"[WEBSOCKET_HOST] Using hardcoded staging hostname: {staging_hostname}")
        return staging_hostname
    
    # For production, also hardcode to ensure we don't get mismatches
    if os.environ.get("FLASK_ENV") == "production":
        production_hostname = "redbarsushi-web.onrender.com"
        logger.info(f"[WEBSOCKET_HOST] Using hardcoded production hostname: {production_hostname}")
        return production_hostname
    
    # Otherwise use the host from the request
    logger.info(f"[WEBSOCKET_HOST] Using request host: {host}")
    return host
