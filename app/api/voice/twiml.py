"""
TwiML generation for Twilio voice calls.

This module handles the initial webhook for incoming Twilio calls and
generates TwiML that configures the WebSocket connection for real-time audio.
"""

import os
import uuid
import logging
import traceback
import time
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from starlette.status import HTTP_200_OK

from app.utils.twilio_twiml import get_environment_name
from app.utils.enhanced_logging import get_logger
from app.utils.correlation_id import set_correlation_id, get_correlation_id

# Set up logging
logger = get_logger(__name__)

# Create a dedicated router for HTTP TwiML endpoints only
router = APIRouter(tags=["Voice TwiML Webhooks"])

# Using the Pydantic model from app.utils.twilio_twiml
# instead of defining our own class
# class TwimlStreamParameter:
#     """Parameters for configuring the TwiML stream."""
#     
#     def __init__(self, url: str, track: str, name: str):
#         self.url = url
#         self.track = track
#         self.name = name

@router.post("", response_class=PlainTextResponse)  # Handle /voice (no trailing slash)
@router.post("/", response_class=PlainTextResponse)  # Handle /voice/ (with trailing slash)
@router.post("/webhook", response_class=PlainTextResponse)  # Handle /voice/webhook
async def receive_call(request: Request) -> PlainTextResponse:
    """
    Primary webhook endpoint for Twilio calls with enhanced logging and TwiML generation.
    
    This endpoint receives incoming call information from Twilio and
    generates TwiML to establish the WebSocket connection for real-time audio.
    Implements comprehensive logging and optimized TwiML generation based on
    the production-proven Flask implementation.
    
    Args:
        request: The HTTP request from Twilio
        
    Returns:
        The TwiML response to send back to Twilio
    """
    # Create a log file for this specific call
    call_sid = (await request.form()).get("CallSid", str(uuid.uuid4()))
    
    # Set up extensive logging for call tracing
    try:
        # Log critical information about the webhook access
        logger.critical(f"***** WEBHOOK ENDPOINT ACCESSED SUCCESSFULLY: {request.url.path} *****", call_sid=call_sid)
        logger.info("==== INCOMING REALTIME CALL DETAILS ====", call_sid=call_sid)
        logger.info(f"Call SID: {call_sid}", call_sid=call_sid)
        logger.info(f"Request came from: {request.client.host}", call_sid=call_sid)
        logger.info(f"User agent: {request.headers.get('user-agent', 'unknown')}", call_sid=call_sid)
        logger.info(f"Host header: {request.headers.get('host', 'unknown')}", call_sid=call_sid)
        logger.info(f"URL: {request.url}", call_sid=call_sid)
        logger.info(f"Path: {request.url.path}", call_sid=call_sid)
        logger.info(f"Request method: {request.method}", call_sid=call_sid)
        logger.info(f"Environment: {os.environ.get('FASTAPI_ENV', 'undefined')}", call_sid=call_sid)
        logger.info(f"Current working directory: {os.getcwd()}", call_sid=call_sid)
        logger.info(f"Correlation ID: {get_correlation_id()}", call_sid=call_sid)
        
        # Log all request headers for debugging (excluding sensitive ones)
        logger.info("Full request headers:")
        for header, value in request.headers.items():
            if header.lower() not in ("authorization", "cookie", "x-auth-token"):
                logger.info(f"  - {header}: {value}")
        
        # Get form data
        form_data = await request.form()
        
        # Log all request form values for debugging
        logger.info("Full request values:")
        for key, value in form_data.items():
            logger.info(f"  - {key}: {value}")
        
        # Extract call information
        call_sid = form_data.get("CallSid", "")
        caller = form_data.get("Caller", "")
        
        # Set correlation ID from call_sid
        set_correlation_id(call_sid)
        called = form_data.get("Called", "")
        
        logger.info(f"Received call: {call_sid} from {caller} to {called}")
        
        # Get environment name for greeting
        environment_name = get_environment_name()
        logger.info(f"Environment identified as: {environment_name}")
        
        # Determine the WebSocket host with extensive fallback logic
        host = request.headers.get("host", "localhost")
        
        # Check for ngrok tunnels
        if 'ngrok' in host:
            logger.info(f"[WEBSOCKET_HOST] Detected ngrok tunnel: Using actual host: {host}")
        
        # For development environment, use the actual host
        elif os.environ.get("FASTAPI_ENV") == "development":
            logger.info(f"[WEBSOCKET_HOST] Development mode: Using actual host: {host}")
        
        # For Render, use the public-facing hostname if available
        elif render_external_hostname := os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
            logger.info(f"[WEBSOCKET_HOST] Using RENDER_EXTERNAL_HOSTNAME: {render_external_hostname}")
            host = render_external_hostname
        
        # For staging environment, use hardcoded hostname
        elif os.environ.get("IS_STAGING") or os.environ.get("FASTAPI_ENV") == "staging":
            staging_hostname = "redbarsushiai-staging.onrender.com"
            logger.info(f"[WEBSOCKET_HOST] Using hardcoded staging hostname: {staging_hostname}")
            host = staging_hostname
        
        # For production, also hardcode to ensure consistency
        elif os.environ.get("FASTAPI_ENV") == "production":
            production_hostname = "redbarsushi-web.onrender.com"
            logger.info(f"[WEBSOCKET_HOST] Using hardcoded production hostname: {production_hostname}")
            host = production_hostname
        
        # ConversationRelay uses direct HTTP webhooks, not WebSocket URLs
        logger.info(f"ConversationRelay will use host: {host} for webhook connections")
        
        # Create welcome message based on environment
        greeting_msg = f"Welcome to {environment_name} Red Bar Sushi AI!"
        
        # TODO_AI_REMOVE_LEGACY_CONVERSATION_RELAY: The following ConversationRelay code is deprecated
        # and replaced with Media Streams for better control and lower latency
        
        # # OLD ConversationRelay implementation - MARKED FOR REMOVAL
        # logger.info(f"Using ConversationRelay voice handler for call {call_sid}")
        # from app.api.conversation_relay.twiml import generate_conversation_relay_twiml
        # from app.config import settings
        # twiml = generate_conversation_relay_twiml(...)
        
        # NEW: Use Twilio Media Streams with WebSocket
        logger.info(f"Using Media Streams WebSocket handler for call {call_sid}")
        
        # Determine WebSocket URL
        # Use wss:// for production/staging, ws:// for local development
        ws_protocol = "wss" if host not in ["localhost", "127.0.0.1"] else "ws"
        
        # Get the configured app domain from settings if available
        app_domain = getattr(settings, 'APP_DOMAIN', host)
        if app_domain:
            host = app_domain
            
        ws_url = f"{ws_protocol}://{host}/ws/voice/{call_sid}"
        logger.info(f"WebSocket URL for Media Streams: {ws_url}")
        
        # Generate TwiML with <Connect><Stream>
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{ws_url}" />
    </Connect>
</Response>"""
        
        logger.info(f"Generated ConversationRelay TwiML for call {call_sid}")
        
        # Log generated TwiML (truncated for readability)
        logger.info(f"Generated TwiML: {twiml[:500]}...")
        logger.critical(f"***** SUCCESSFULLY RETURNING TWIML FOR CALL {call_sid} *****")
        
        # Return the TwiML response
        return PlainTextResponse(
            content=twiml,
            media_type="application/xml",
            status_code=HTTP_200_OK
        )
        
    except Exception as e:
        # Log the full error with traceback
        logger.critical(f"***** ERROR HANDLING INCOMING CALL *****")
        logger.error(f"Error handling incoming call: {str(e)}")
        logger.error(f"Error class: {e.__class__.__name__}")
        logger.error(f"Error traceback: {traceback.format_exc()}")
        
        # Try to generate an error response
        try:
            # Generate simple fallback TwiML
            error_twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Amy-Neural">We're sorry, but an error occurred while processing your call. Please try again later.</Say>
</Response>
"""
            logger.info(f"Generated error TwiML: {error_twiml}")
            return PlainTextResponse(
                content=error_twiml,
                media_type="application/xml",
                status_code=HTTP_200_OK
            )
        except Exception as fallback_error:
            logger.critical(f"Failed to generate error TwiML: {fallback_error}")
            return PlainTextResponse(
                content="Error processing call",
                status_code=500
            )