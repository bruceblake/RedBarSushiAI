"""
TwiML generation for ConversationRelay.
"""

import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)


def generate_conversation_relay_twiml(
    call_sid: str,
    service_sid: Optional[str] = None,
    connector_name: Optional[str] = None,
    greeting_text: Optional[str] = None,
    websocket_url: Optional[str] = None,
    host: Optional[str] = None
) -> str:
    """
    Generate TwiML response with Twilio ConversationRelay using direct URL approach.
    
    Args:
        call_sid: The Twilio call SID
        service_sid: Optional - Twilio Conversation Service SID (for service-based approach)
        connector_name: Optional - Connector name (for service-based approach)
        greeting_text: Optional greeting text (not used in ConversationRelay TwiML)
        websocket_url: Optional custom WebSocket URL
        host: Optional host for WebSocket URL generation
        
    Returns:
        TwiML XML string
    """
    # Check if we're using the service-based approach (with serviceSid and connectorName)
    service_sid = service_sid or getattr(settings, 'TWILIO_CONVERSATION_SERVICE_SID', '')
    connector_name = connector_name or getattr(settings, 'TWILIO_CONNECTOR_NAME', '')
    
    if service_sid and connector_name:
        # Service-based approach
        logger.info(f"Generating ConversationRelay TwiML with service approach for call {call_sid}")
        logger.info(f"Service SID: {service_sid}, Connector: {connector_name}")
        
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <ConversationRelay serviceSid="{service_sid}" connectorName="{connector_name}" />
    </Connect>
</Response>"""
    else:
        # Direct URL approach (simpler, recommended for TwiML Apps)
        if not websocket_url:
            # Generate WebSocket URL
            if not host:
                # Try to get from settings or use default
                base_url = getattr(settings, 'BASE_URL', '')
                if base_url:
                    host = base_url.replace('http://', '').replace('https://', '')
                else:
                    # Fallback to localhost for development
                    host = 'localhost:8000'
                    logger.warning(f"No BASE_URL configured, using {host}")
            
            # Use wss for production/ngrok, ws for local development
            ws_scheme = "wss" if ("localhost" not in host and "127.0.0.1" not in host) or "ngrok" in host else "ws"
            
            # Point to our ConversationRelay WebSocket endpoint
            websocket_url = f"{ws_scheme}://{host}/api/conversation-relay"
        
        logger.info(f"Generating ConversationRelay TwiML with direct URL for call {call_sid}")
        logger.info(f"WebSocket URL: {websocket_url}")
        
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <ConversationRelay url="{websocket_url}" />
    </Connect>
</Response>"""
    
    logger.debug(f"Generated TwiML: {twiml}")
    
    return twiml