"""
Voice API endpoints for Twilio integration.

This module provides HTTP endpoints for handling Twilio voice calls
and generating TwiML responses for media streaming.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import Response, JSONResponse

from app.config import settings

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["Voice"])

@router.post("/", response_class=Response)
@router.post("/voice", response_class=Response)
@router.post("/webhook/voice", response_class=Response)
async def receive_call(request: Request) -> Response:
    """
    Primary webhook endpoint for Twilio calls.
    
    This endpoint generates TwiML to instruct Twilio to connect
    to our WebSocket for real-time audio streaming.
    
    Args:
        request: The HTTP request from Twilio
        
    Returns:
        Response: TwiML response for Twilio
    """
    # Log the call
    client_host = request.headers.get("X-Forwarded-For") or request.client.host
    logger.info(f"Received Twilio call from {client_host}")
    
    # Parse form data (Twilio sends parameters as form data)
    form_data = await request.form()
    
    # Extract call parameters
    call_sid = form_data.get("CallSid", "unknown")
    caller = form_data.get("Caller", "unknown")
    called = form_data.get("Called", "unknown")
    
    logger.info(f"Call details - SID: {call_sid}, From: {caller}, To: {called}")
    
    # Generate TwiML for WebSocket connection using our improved TwiML generator
    from app.utils.twilio_twiml import (
        generate_media_streams_twiml, 
        TwimlParameter, 
        TwimlStreamParameter,
        get_host_for_ws
    )
    
    # Get the WebSocket base URL
    ws_base_url = get_host_for_ws()
    
    # Create the WebSocket URL
    ws_url = f"{ws_base_url}/realtime/ws/media/{call_sid}"
    
    # Create Stream parameters
    stream_params = TwimlStreamParameter(
        url=ws_url,
        track="both",  # Send both inbound and outbound audio
        name="RedBarSushiAI"
    )
    
    # Create TwiML parameters
    twiml_params = TwimlParameter(
        voice="Polly.Amy-Neural",
        language="en-US",
        greeting_text="Welcome to Red Bar Sushi. Please wait while we connect you to our AI assistant.",
        fallback_text="Sorry, we couldn't connect you to our AI assistant. Please try again later or call during business hours.",
        stream_params=stream_params,
        call_sid=call_sid
    )
    
    # Generate the TwiML
    twiml = generate_media_streams_twiml(twiml_params)
    
    logger.info(f"Generated TwiML with WebSocket URL: {ws_url}")
    
    # Return the TwiML response
    return Response(content=twiml, media_type="application/xml")

@router.get("/health")
async def voice_health() -> Dict[str, Any]:
    """Health check endpoint for the voice service."""
    return {
        "status": "ok",
        "service": "voice",
        "timestamp": datetime.now().isoformat()
    }