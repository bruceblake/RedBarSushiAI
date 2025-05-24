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
    connector_name: Optional[str] = None
) -> str:
    """
    Generate TwiML response with ConversationRelay for bidirectional audio streaming.
    
    Args:
        call_sid: The Twilio call SID
        service_sid: Override for Conversation Service SID
        connector_name: Override for Connector name
        
    Returns:
        TwiML XML string
    """
    # Use provided values or fall back to settings
    service_sid = service_sid or getattr(settings, 'TWILIO_CONVERSATION_SERVICE_SID', '')
    connector_name = connector_name or getattr(settings, 'TWILIO_CONNECTOR_NAME', '')
    
    if not service_sid or not connector_name:
        logger.error(f"Missing ConversationRelay configuration for call {call_sid}")
        # Fallback to error message
        return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>We're sorry, but our voice service is temporarily unavailable. Please try again later.</Say>
</Response>"""
    
    logger.info(f"Generating ConversationRelay TwiML for call {call_sid}")
    logger.info(f"Service SID: {service_sid}, Connector: {connector_name}")
    
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <ConversationRelay serviceSid="{service_sid}" connectorName="{connector_name}" />
    </Connect>
</Response>"""
    
    return twiml