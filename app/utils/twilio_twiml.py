"""
Twilio TwiML utilities for voice call handling.

This module provides utility functions for TwiML generation and environment detection.
"""

import os
from typing import Optional
from pydantic import BaseModel
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class TwimlStreamParameter(BaseModel):
    """Parameters for configuring the TwiML stream."""
    url: str
    track: str
    name: str


def get_environment_name() -> str:
    """
    Get a human-readable environment name for use in TwiML greetings.
    
    Returns:
        str: Environment name like "Development", "Staging", or "Production"
    """
    fastapi_env = os.environ.get("FASTAPI_ENV", "").lower()
    
    if fastapi_env == "production":
        return "Production"
    elif fastapi_env == "staging" or os.environ.get("IS_STAGING"):
        return "Staging"
    elif fastapi_env == "development":
        return "Development"
    else:
        # Default to Development for unknown environments
        return "Development"


def get_twiml_host(request_host: Optional[str] = None) -> str:
    """
    Determine the appropriate host for TwiML WebSocket connections.
    
    Args:
        request_host: The host header from the incoming request
        
    Returns:
        str: The host to use for WebSocket connections
    """
    # Use request host if provided
    if request_host:
        host = request_host
    else:
        host = "localhost"
    
    # Check for ngrok tunnels
    if 'ngrok' in host:
        logger.info(f"Detected ngrok tunnel: Using actual host: {host}")
        return host
    
    # For development environment, use the actual host
    if os.environ.get("FASTAPI_ENV") == "development":
        logger.info(f"Development mode: Using actual host: {host}")
        return host
    
    # For Render, use the public-facing hostname if available
    if render_external_hostname := os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
        logger.info(f"Using RENDER_EXTERNAL_HOSTNAME: {render_external_hostname}")
        return render_external_hostname
    
    # For staging environment, use hardcoded hostname
    if os.environ.get("IS_STAGING") or os.environ.get("FASTAPI_ENV") == "staging":
        staging_hostname = "redbarsushiai-staging.onrender.com"
        logger.info(f"Using hardcoded staging hostname: {staging_hostname}")
        return staging_hostname
    
    # For production, also hardcode to ensure consistency
    if os.environ.get("FASTAPI_ENV") == "production":
        production_hostname = "redbarsushi-web.onrender.com"
        logger.info(f"Using hardcoded production hostname: {production_hostname}")
        return production_hostname
    
    # Default to the provided host
    return host


def get_websocket_protocol(host: str) -> str:
    """
    Determine the appropriate WebSocket protocol (ws or wss) based on the host.
    
    Args:
        host: The host to check
        
    Returns:
        str: Either "ws" or "wss"
    """
    # Use wss:// for production/staging, ws:// for local development
    if host in ["localhost", "127.0.0.1", "app"]:
        return "ws"
    else:
        return "wss"


def generate_conversation_relay_twiml(
    call_sid: str,
    caller: str,
    host: str,
    environment_name: str,
    greeting_message: Optional[str] = None
) -> str:
    """
    Generate TwiML for ConversationRelay voice interactions.
    
    Args:
        call_sid: The Twilio call SID
        caller: The caller's phone number
        host: The host for WebSocket connections
        environment_name: The environment name for the greeting
        greeting_message: Optional custom greeting message
        
    Returns:
        str: The generated TwiML XML
    """
    # Create welcome message based on environment
    if not greeting_message:
        greeting_message = f"Welcome to {environment_name} Red Bar Sushi AI!"
    
    # Determine WebSocket URL for ConversationRelay
    ws_protocol = get_websocket_protocol(host)
    
    # Get the configured app domain from settings if available
    try:
        from app.config import settings
        app_domain = getattr(settings, 'APP_DOMAIN', host)
        if app_domain:
            host = app_domain
    except Exception:
        # If settings can't be imported, use the provided host
        pass
            
    ws_url = f"{ws_protocol}://{host}/conversation-relay/{call_sid}"
    logger.info(f"Generated WebSocket URL for ConversationRelay: {ws_url}")
    
    # Generate TwiML with <Connect><ConversationRelay>
    # No welcomeGreeting - let the conversation logic handle all greetings
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <ConversationRelay url="{ws_url}" 
                          interruptible="any"
                          ttsProvider="ElevenLabs"
                          transcriptionProvider="Google"
                          language="en-US"
                          debug="debugging speaker-events">
            <Parameter name="call_sid" value="{call_sid}" />
            <Parameter name="customer_phone" value="{caller}" />
            <Parameter name="environment" value="{environment_name}" />
        </ConversationRelay>
    </Connect>
</Response>"""
    
    return twiml


def generate_error_twiml(error_message: Optional[str] = None) -> str:
    """
    Generate a simple error TwiML response.
    
    Args:
        error_message: Optional custom error message
        
    Returns:
        str: The generated error TwiML XML
    """
    if not error_message:
        error_message = "We're sorry, but an error occurred while processing your call. Please try again later."
    
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Amy-Neural">{error_message}</Say>
</Response>"""