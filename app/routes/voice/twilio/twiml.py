"""
TwiML generation for Twilio Media Streams integration.

This module provides functions to generate TwiML responses for
Twilio voice calls, configuring Media Streams for real-time audio.
"""

import logging
import time
import os
from twilio.twiml.voice_response import VoiceResponse, Connect, Start, Stream

# Set up logger
logger = logging.getLogger(__name__)

def generate_media_streams_twiml(call_sid, hostname, environment_name="PRODUCTION"):
    """
    Generate TwiML for a voice call with Media Streams.
    
    Args:
        call_sid: The Twilio call SID
        hostname: The hostname for WebSocket connections
        environment_name: The environment name for greeting
        
    Returns:
        TwiML response as a string
    """
    try:
        logger.info(f"[TWIML:{call_sid}] Generating TwiML response with Media Streams")
        
        # Make sure we're using a proper hostname with no trailing slash
        hostname = hostname.rstrip('/')
        
        # Always use wss:// for Twilio Media Streams
        ws_url = f"wss://{hostname}/ws/voice/media"
        logger.info(f"[TWIML:{call_sid}] WebSocket URL for Media Streams: {ws_url}")
        
        # Create the TwiML response
        response = VoiceResponse()
        
        # Add a greeting message with environment name
        greeting_message = f"Welcome to {environment_name} Red Bar Sushi AI ordering system."
        logger.info(f"[TWIML:{call_sid}] Initial greeting: '{greeting_message}'")
        response.say(greeting_message)
        
        # Add a 1-second pause to ensure TTS completes and connection is ready
        response.pause(length=1)
        
        # Start Media Stream with the WebSocket endpoint using a separate endpoint for inbound
        ws_url_inbound = f"wss://{hostname}/ws/voice/media"
        logger.info(f"[TWIML:{call_sid}] Adding Media Stream start with URL: {ws_url_inbound}, track: inbound_track")
        start = Start()
        start.stream(url=ws_url_inbound, track="inbound_track", name="inbound_stream")
        response.append(start)
        
        # Add another small pause to ensure the first connection is established
        response.pause(length=0.5)
        
        # Connect bidirectional audio stream with parameters to improve stability
        ws_url_both = f"wss://{hostname}/ws/voice/media"
        logger.info(f"[TWIML:{call_sid}] Adding Media Stream connect with URL: {ws_url_both}, track: both_tracks")
        connect = Connect()
        connect.stream(url=ws_url_both, track="both_tracks", name="both_tracks_stream")
        response.append(connect)
        
        # Return the TwiML as a string
        return str(response)
        
    except Exception as e:
        logger.error(f"[TWIML:{call_sid}] Error generating TwiML: {str(e)}")
        
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
    
    # Otherwise use the host from the request
    return host