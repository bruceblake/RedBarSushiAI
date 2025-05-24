"""
Updated TwiML generation for Twilio voice calls with ConversationRelay support.

This module handles the initial webhook for incoming Twilio calls and
generates TwiML based on the VOICE_HANDLER configuration.
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
from app.api.conversation_relay import generate_conversation_relay_twiml
from app.config import settings

# Set up logging
logger = logging.getLogger(__name__)
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


@router.post("/", response_class=PlainTextResponse)
@router.post("/webhook", response_class=PlainTextResponse) 
async def receive_call(request: Request) -> PlainTextResponse:
    """
    Primary webhook endpoint for Twilio calls with support for both
    Media Streams and ConversationRelay based on configuration.
    
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
        logger.info(f"Voice Handler Mode: {getattr(settings, 'VOICE_HANDLER', 'media_streams')}")
        
        # Get form data
        form_data = await request.form()
        
        # Extract call information
        call_sid = form_data.get("CallSid", "")
        caller = form_data.get("Caller", "")
        called = form_data.get("Called", "")
        
        logger.info(f"Received call: {call_sid} from {caller} to {called}")
        
        # Check which voice handler to use
        voice_handler = getattr(settings, 'VOICE_HANDLER', 'media_streams')
        logger.critical(f"***** USING VOICE HANDLER: {voice_handler} *****")
        
        if voice_handler == 'conversation_relay':
            # Use ConversationRelay for better performance and reliability
            logger.info("Generating ConversationRelay TwiML")
            
            # Check if required configuration is present
            service_sid = getattr(settings, 'TWILIO_CONVERSATION_SERVICE_SID', None)
            connector_name = getattr(settings, 'TWILIO_CONNECTOR_NAME', None)
            
            if not service_sid or not connector_name:
                logger.error("ConversationRelay configuration missing!")
                logger.error(f"Service SID present: {bool(service_sid)}")
                logger.error(f"Connector name present: {bool(connector_name)}")
                logger.warning("Falling back to Media Streams")
                voice_handler = 'media_streams'
            else:
                # Generate ConversationRelay TwiML
                twiml = generate_conversation_relay_twiml(
                    call_sid=call_sid,
                    service_sid=service_sid,
                    connector_name=connector_name
                )
                
                logger.info(f"Generated ConversationRelay TwiML: {twiml[:500]}...")
                logger.critical(f"***** SUCCESSFULLY RETURNING CONVERSATIONRELAY TWIML FOR CALL {call_sid} *****")
                
                return PlainTextResponse(
                    content=twiml,
                    media_type="application/xml",
                    status_code=HTTP_200_OK
                )
        
        # Default to Media Streams (existing implementation)
        if voice_handler == 'media_streams' or True:  # Fallback
            logger.info("Using Media Streams (existing implementation)")
            
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
            ws_scheme = "wss"
            
            # Main production WebSocket URL
            websocket_url = f"{ws_scheme}://{host}/realtime/ws/media/{call_sid}"
            
            logger.critical(f"❗❗❗ MEDIA STREAMS WEBSOCKET URL: {websocket_url} ❗❗❗")
            
            # Create Stream parameters with production settings
            timestamp = str(int(time.time()))
            custom_params = [
                {"name": "debug", "value": "true"},
                {"name": "client", "value": "twilio"},
                {"name": "time", "value": timestamp}
            ]
            
            # Create the TwimlStreamParameter
            stream_params = TwimlStreamParameter(
                url=websocket_url,
                track="inbound_track",
                name="media_stream",
                custom_parameters=custom_params
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
            
            logger.info(f"Generated Media Streams TwiML: {twiml[:500]}...")
            logger.critical(f"***** SUCCESSFULLY RETURNING MEDIA STREAMS TWIML FOR CALL {call_sid} *****")
            
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