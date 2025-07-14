"""
Voice fallback endpoints for static mode when AI is unavailable.

These endpoints handle voice interactions when the circuit breaker
is open and the system falls back to static TwiML responses.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import Response

from app.utils.static_fallback import generate_fallback_response, process_fallback_recording
from app.services.circuit_breaker import get_circuit_breaker

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/voice/fallback")
async def handle_fallback_voice(
    request: Request,
    Digits: Optional[str] = Form(None),
    timeout: Optional[str] = Form(None)
):
    """
    Handle voice interactions in static fallback mode.
    
    This endpoint is called when the circuit breaker is open
    and AI services are unavailable.
    """
    call_sid = request.form().get('CallSid', 'unknown')
    logger.info(f"[{call_sid}] Handling fallback voice interaction - DTMF: {Digits}")
    
    # Check circuit breaker status
    circuit_breaker = get_circuit_breaker()
    logger.info(f"[{call_sid}] Circuit breaker status: {circuit_breaker.status}")
    
    try:
        # Generate static fallback TwiML
        twiml_response = generate_fallback_response(Digits)
        
        logger.info(f"[{call_sid}] Generated fallback TwiML response")
        
        return Response(
            content=twiml_response,
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.error(f"[{call_sid}] Error in fallback handler: {e}")
        
        # Final emergency fallback
        emergency_twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">
        I'm sorry, but we're experiencing technical difficulties. 
        Please call back in a few minutes or visit us in person. 
        Thank you for your patience.
    </Say>
    <Hangup/>
</Response>"""
        
        return Response(
            content=emergency_twiml,
            media_type="application/xml"
        )

@router.post("/voice/fallback-recording")
async def handle_fallback_recording(
    request: Request,
    RecordingUrl: Optional[str] = Form(None),
    TranscriptionText: Optional[str] = Form(None)
):
    """
    Handle recordings left by customers in fallback mode.
    
    Processes customer messages and provides confirmation.
    """
    call_sid = request.form().get('CallSid', 'unknown')
    logger.info(f"[{call_sid}] Processing fallback recording: {RecordingUrl}")
    
    if TranscriptionText:
        logger.info(f"[{call_sid}] Transcription: {TranscriptionText}")
    
    try:
        # Process the recording
        twiml_response = process_fallback_recording(
            RecordingUrl or "",
            TranscriptionText
        )
        
        # TODO: Save recording info to database
        # TODO: Send notification to staff
        
        logger.info(f"[{call_sid}] Processed fallback recording successfully")
        
        return Response(
            content=twiml_response,
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.error(f"[{call_sid}] Error processing fallback recording: {e}")
        
        # Emergency fallback for recording processing
        emergency_twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">
        Thank you for your message. We've received it and will contact you soon.
    </Say>
    <Hangup/>
</Response>"""
        
        return Response(
            content=emergency_twiml,
            media_type="application/xml"
        )

@router.get("/voice/circuit-breaker/status")
async def get_circuit_breaker_status():
    """
    Get current circuit breaker status.
    
    Useful for monitoring and debugging the circuit breaker state.
    """
    circuit_breaker = get_circuit_breaker()
    return {
        "circuit_breaker": circuit_breaker.status,
        "fallback_mode": circuit_breaker.is_open
    }

@router.post("/voice/circuit-breaker/reset")
async def reset_circuit_breaker():
    """
    Manually reset the circuit breaker for testing.
    
    This endpoint allows administrators to manually reset
    the circuit breaker state during development/testing.
    """
    circuit_breaker = get_circuit_breaker()
    
    # Force reset by creating a new instance
    from app.services.circuit_breaker import _circuit_breaker
    import app.services.circuit_breaker as cb_module
    cb_module._circuit_breaker = None
    
    logger.warning("Circuit breaker manually reset")
    
    return {
        "message": "Circuit breaker reset successfully",
        "previous_status": circuit_breaker.status,
        "new_status": get_circuit_breaker().status
    }