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

from app.utils.twilio_twiml import generate_media_streams_twiml, TwimlParameter, TwimlStreamParameter
from app.utils.twilio_twiml import get_environment_name

# Set up logging
logger = logging.getLogger(__name__)
# Force DEBUG level for this module specifically
logger.setLevel(logging.DEBUG)

# Add a console handler for immediate visibility
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Ensure our logs are seen even if parent loggers have higher levels
logger.propagate = False

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

@router.post("/", response_class=PlainTextResponse)
@router.post("/webhook", response_class=PlainTextResponse) 
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
        logger.critical(f"***** WEBHOOK ENDPOINT ACCESSED SUCCESSFULLY: {request.url.path} *****")
        logger.info("==== INCOMING REALTIME CALL DETAILS ====")
        logger.info(f"Call SID: {call_sid}")
        logger.info(f"Request came from: {request.client.host}")
        logger.info(f"User agent: {request.headers.get('user-agent', 'unknown')}")
        logger.info(f"Host header: {request.headers.get('host', 'unknown')}")
        logger.info(f"URL: {request.url}")
        logger.info(f"Path: {request.url.path}")
        logger.info(f"Request method: {request.method}")
        logger.info(f"Environment: {os.environ.get('FASTAPI_ENV', 'undefined')}")
        logger.info(f"Current working directory: {os.getcwd()}")
        
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
        
        # Get the URL scheme (http or https)
        scheme = request.url.scheme
        
        # For Render deployment, always use wss:// for WebSocket connections
        # Render provides HTTPS by default for all deployments
        ws_scheme = "wss"
        
        # TEMPORARILY USING THE TEST ENDPOINTS for diagnostic purposes
        # Original URL: 
        # websocket_url = f"{ws_scheme}://{host}/realtime/ws/media/{call_sid}"
        
        # Test endpoint options:
        # 1. Generic test endpoint directly on the FastAPI app object - USING THIS ONE NOW
        # This endpoint works with browsers, let's see if Twilio can also connect to it
        websocket_url = f"{ws_scheme}://{host}/ws-test/{call_sid}"
        
        # 2. Twilio-specific pattern following the blog post exactly
        # websocket_url = f"{ws_scheme}://{host}/twilio-ws-test/{call_sid}"
        
        # Log this URL multiple times in different formats to make it absolutely unmissable
        logger.critical(f"❗❗❗ TEMP TEST WEBSOCKET URL SET IN TWIML: {websocket_url} ❗❗❗")
        logger.critical(f"WEBSOCKET SCHEME: {ws_scheme}")
        logger.critical(f"WEBSOCKET HOST: {host}")
        logger.critical(f"WEBSOCKET PATH: /ws-test/{call_sid}")
        logger.critical(f"RESULTING FULL URL: {websocket_url}")
        logger.critical(f"❗❗❗ TWIML NOW POINTS TO GENERIC /ws-test/: {websocket_url} ❗❗❗")
        logger.critical(f"ATTENTION: Using browser-proven generic WebSocket endpoint!")
        
        # Create Stream parameters with production settings
        # Add parameters to help with debugging (they'll be passed as query params)
        from urllib.parse import urlencode
        debug_params = {
            "debug": "true",  
            "client": "twilio",  # Mark this as from Twilio
            "time": str(int(time.time()))  # Timestamp to trace this specific request
        }
        
        # Add the query parameters to the URL
        websocket_url_with_params = f"{websocket_url}?{urlencode(debug_params)}"
        logger.critical(f"❗❗❗ FINAL WEBSOCKET URL WITH QUERY PARAMS: {websocket_url_with_params} ❗❗❗")
        
        stream_params = TwimlStreamParameter(
            url=websocket_url_with_params,
            track="both",  # Use both tracks for bidirectional streaming
            name="media_stream"  # Consistent name for stream tracking
        )
        
        # Create welcome message based on environment
        greeting_msg = f"Welcome to {environment_name} Red Bar Sushi AI!"
        
        # Create TwiML parameters
        twiml_params = TwimlParameter(
            voice="Polly.Amy-Neural",
            language="en-US",
            greeting_text=greeting_msg,
            fallback_text="Sorry, we couldn't connect you to our AI assistant. Please try again later.",
            stream_params=stream_params,
            call_sid=call_sid
        )
        
        # Generate TwiML response
        twiml = generate_media_streams_twiml(twiml_params)
        
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