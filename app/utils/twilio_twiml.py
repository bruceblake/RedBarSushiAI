"""
TwiML generation utilities for Twilio integration.

This module provides utilities for generating TwiML responses for Twilio,
particularly for WebSocket-based media streaming.
"""

import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.config import settings

# Set up logging
logger = logging.getLogger(__name__)

class TwimlStreamParameter(BaseModel):
    """
    Parameters for a TwiML Stream element.
    
    Docs: https://www.twilio.com/docs/voice/twiml/stream
    """
    
    url: str
    track: Optional[str] = "both"  # inbound, outbound, or both
    name: Optional[str] = None
    parameters: Optional[Dict[str, str]] = None

class TwimlParameter(BaseModel):
    """Common parameters for TwiML generation."""
    
    voice: str = "Polly.Amy-Neural"  # For <Say> elements
    language: str = "en-US"  # For <Say> elements
    greeting_text: Optional[str] = "Welcome to Red Bar Sushi. Please wait while we connect you."
    fallback_text: Optional[str] = "Sorry, we couldn't connect you to our AI assistant. Please try again later."
    stream_params: TwimlStreamParameter  # Allow TwimlStreamParameter instance
    call_sid: str

def generate_media_streams_twiml(params: TwimlParameter) -> str:
    """
    Generate optimized TwiML for WebSocket-based media streaming.
    
    This function generates TwiML with a <Connect><Stream> element for bidirectional
    media streaming with Twilio. It includes proper pausing and voice configuration
    based on production best practices.
    
    Args:
        params: Parameters for TwiML generation
        
    Returns:
        str: TwiML response as a string
    """
    try:
        call_sid = params.call_sid
        logger.info(f"[TWIML:{call_sid}] Generating bidirectional TwiML with Connect")
        
        # Extract parameters
        stream_url = params.stream_params.url
        track = params.stream_params.track
        stream_name = params.stream_params.name or "media_stream"
        
        # Build parameters attribute if specified
        params_attr = ""
        if params.stream_params.parameters:
            params_str = " ".join([f'{k}="{v}"' for k, v in params.stream_params.parameters.items()])
            params_attr = f' parameters="{params_str}"'
        
        # Generate TwiML
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{params.voice}" language="{params.language}">{params.greeting_text}</Say>
    <Pause length="1"/>
    <Connect>
        <Stream url="{stream_url}" track="{track}" name="{stream_name}"{params_attr} />
    </Connect>
    <Say voice="{params.voice}" language="{params.language}">{params.fallback_text}</Say>
</Response>
"""
        
        # Log the TwiML details for debugging
        logger.info(f"[TWIML:{call_sid}] Generated TwiML with WebSocket URL: {stream_url}")
        logger.debug(f"[TWIML:{call_sid}] TwiML: {twiml}")
        
        return twiml
        
    except Exception as e:
        logger.error(f"Error generating optimized TwiML: {str(e)}")
        
        # Create an error response if TwiML generation fails
        error_twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Amy-Neural">We're sorry, but an error occurred while processing your call. Please try again later.</Say>
</Response>
"""
        return error_twiml

def get_host_for_ws() -> str:
    """
    Get the hostname for WebSocket connections.
    
    Returns:
        str: The hostname for WebSocket connections
    """
    base_url = settings.BASE_URL
    
    # Ensure base_url has the correct protocol
    if not base_url.startswith(("http://", "https://")):
        base_url = f"https://{base_url}"
    
    # Convert http:// to ws:// and https:// to wss://
    ws_base_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
    
    return ws_base_url

def get_environment_name() -> str:
    """
    Get the environment name for logging.
    
    Returns:
        str: The environment name
    """
    if settings.ENVIRONMENT.lower() == "staging" or settings.RENDER:
        return "staging"
    elif settings.ENVIRONMENT.lower() == "production":
        return "production"
    else:
        return "development"