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
    """
    Enhanced health check endpoint for the voice service.
    
    Verifies that all required components are properly initialized:
    - Agent orchestration system
    - Realtime processor
    - Redis connection
    
    Returns:
        Dict with status and component information
    """
    import os
    
    try:
        # Check agent orchestration
        try:
            from app.utils.agent_orchestration_async import async_agent_orchestrator
            agent_status = "initialized" if hasattr(async_agent_orchestrator, 'is_initialized') and async_agent_orchestrator.is_initialized else "not_initialized"
        except ImportError:
            agent_status = "not_available"
        
        # Try to check the FSM manager
        try:
            from app.utils.fsm_async import async_fsm_manager
            fsm_status = "available" if hasattr(async_fsm_manager, 'is_initialized') and async_fsm_manager.is_initialized else "not_available"
        except ImportError:
            fsm_status = "not_available"
        
        # Check for realtime processor
        try:
            from app.utils.realtime_audio_async import get_realtime_processor
            realtime_processor = await get_realtime_processor()
            realtime_status = "available" if realtime_processor else "unavailable"
            
            # Check for fallback mode
            is_fallback = False
            if hasattr(realtime_processor, 'is_fallback'):
                is_fallback = realtime_processor.is_fallback
                
        except Exception as realtime_error:
            logger.error(f"Error checking realtime processor: {str(realtime_error)}")
            realtime_status = "error"
            is_fallback = False
        
        # Check Redis connection
        redis_status = "unknown"
        try:
            from app.redis_async import get_redis
            redis_client = await get_redis()
            if redis_client and await redis_client.ping():
                redis_status = "connected"
            else:
                redis_status = "disconnected"
        except Exception as redis_error:
            redis_status = f"error: {str(redis_error)}"
        
        # Get active connections
        try:
            from app.dependencies import connection_manager
            active_connections = len(connection_manager.active_connections)
        except Exception:
            active_connections = 0
        
        # Compile the response
        return {
            "status": "ok" if agent_status == "initialized" and realtime_status == "available" else "error",
            "service": "voice_realtime",
            "agents": agent_status,
            "fsm": fsm_status,
            "realtime": realtime_status,
            "realtime_fallback": is_fallback,
            "redis": redis_status,
            "active_connections": active_connections,
            "environment": os.environ.get('FASTAPI_ENV', 'development'),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error in health check: {str(e)}")
        return {
            "status": "error",
            "service": "voice_realtime",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/routes-debug")
async def debug_routes(request: Request) -> Dict[str, Any]:
    """
    Debug endpoint to show all registered routes.
    
    This endpoint provides information about all registered routes in the FastAPI app,
    which is useful for debugging routing issues and understanding the API surface.
    
    Args:
        request: The HTTP request
        
    Returns:
        Dict with routes information
    """
    from fastapi.routing import APIRoute
    
    # Get the main FastAPI app instance
    app = request.app
    
    # Collect route information
    routes = []
    
    # Process all routes
    for route in app.routes:
        if isinstance(route, APIRoute):
            routes.append({
                "path": route.path,
                "name": route.name,
                "methods": list(route.methods) if route.methods else [],
                "endpoint": route.endpoint.__name__ if hasattr(route.endpoint, "__name__") else str(route.endpoint),
                "summary": route.summary or "",
                "tags": route.tags or []
            })
        else:
            # For non-API routes like WebSocket routes
            routes.append({
                "path": route.path,
                "type": route.__class__.__name__,
            })
    
    # Sort routes by path for readability
    routes.sort(key=lambda r: r.get("path", ""))
    
    return {
        "routes": routes,
        "count": len(routes),
        "app_title": getattr(app, "title", "FastAPI"),
        "app_version": getattr(app, "version", "unknown")
    }