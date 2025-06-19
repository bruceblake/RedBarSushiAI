"""
WebSocket handler for Twilio ConversationRelay.

This module handles ConversationRelay WebSocket connections, redirecting to the proper handler.
Legacy Media Streams support has been removed - use ConversationRelay only.
"""

import logging
from fastapi import WebSocket, WebSocketDisconnect, Query

logger = logging.getLogger(__name__)

async def handle_media_stream(
    websocket: WebSocket,
    call_sid: str,
    debug: bool = Query(False),
    client: str = Query("twilio"),
    time: str = Query("")
):
    """
    Handle WebSocket connection - redirects to ConversationRelay handler.
    
    Legacy Media Streams implementation has been removed.
    This now only supports ConversationRelay for improved reliability.
    
    Args:
        websocket: FastAPI WebSocket instance
        call_sid: Twilio call SID
        debug: Enable debug logging
        client: Client type (twilio)
        time: Timestamp from TwiML
    """
    logger.info(f"Redirecting WebSocket connection to ConversationRelay for call {call_sid}")
    
    try:
        # Accept the WebSocket connection
        await websocket.accept()
        logger.info(f"WebSocket connection accepted for call {call_sid}")
        
        # Use ConversationRelay handler only
        from app.api.conversation_relay.handler import handle_conversation_relay
        logger.info(f"Using ConversationRelay handler for call {call_sid}")
        await handle_conversation_relay(websocket, call_sid)
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for call {call_sid}")
    except Exception as e:
        logger.error(f"WebSocket error for call {call_sid}: {e}", exc_info=True)
    finally:
        logger.info(f"WebSocket handler completed for call {call_sid}")


# Export the handler
__all__ = ["handle_media_stream"]