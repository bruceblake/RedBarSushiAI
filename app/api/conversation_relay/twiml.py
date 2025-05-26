"""
ConversationRelay TwiML generation.

This module generates TwiML for Twilio's ConversationRelay feature,
which provides improved latency and reliability for voice interactions.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def generate_conversation_relay_twiml(
    call_sid: str,
    greeting_text: str,
    service_sid: Optional[str] = None,
    connector_name: Optional[str] = None,
    host: Optional[str] = None,
    tts_provider: str = "ElevenLabs",
    tts_voice: Optional[str] = None,
    language: str = "en-US",
    transcription_provider: str = "Google",
    speech_model: str = "telephony",
    interruptible: str = "any",
    dtmf_detection: bool = False
) -> str:
    """
    Generate TwiML for ConversationRelay.
    
    Args:
        call_sid: The Twilio call SID
        greeting_text: Initial greeting message
        service_sid: The Twilio Conversation Service SID (for service/connector mode)
        connector_name: The name of the configured connector (for service/connector mode)
        host: The host for URL mode
        tts_provider: TTS provider ("ElevenLabs", "Google", "Amazon")
        tts_voice: Voice ID for the TTS provider
        language: Language code (e.g., "en-US")
        transcription_provider: STT provider ("Google", "Deepgram")
        speech_model: Speech model for transcription
        interruptible: When AI can be interrupted ("any", "speech", "dtmf", "never")
        dtmf_detection: Whether to detect DTMF tones
        
    Returns:
        TwiML XML string
    """
    
    if service_sid and connector_name:
        # Service/Connector mode (not commonly used)
        logger.info(f"Generating ConversationRelay TwiML with serviceSid={service_sid}, connectorName={connector_name}")
        
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <ConversationRelay 
            serviceSid="{service_sid}" 
            connectorName="{connector_name}"
            welcomeGreeting="{greeting_text}"
            language="{language}"
            ttsProvider="{tts_provider}"
            {"voice='" + tts_voice + "'" if tts_voice else ""}
            transcriptionProvider="{transcription_provider}"
            speechModel="{speech_model}"
            interruptible="{interruptible}"
            {"dtmfDetection='true'" if dtmf_detection else ""}
        />
    </Connect>
</Response>"""
    else:
        # URL mode (primary method)
        logger.info("Generating ConversationRelay TwiML with URL mode")
        
        # Construct WebSocket URL
        ws_scheme = "wss" if "ngrok" in host or "render" in host or "https" in host else "ws"
        websocket_url = f"{ws_scheme}://{host}/api/conversation-relay"
        
        # Build attributes
        attributes = [
            f'url="{websocket_url}"',
            f'welcomeGreeting="{greeting_text}"',
            f'language="{language}"',
            f'ttsProvider="{tts_provider}"',
            f'transcriptionProvider="{transcription_provider}"',
            f'speechModel="{speech_model}"',
            f'interruptible="{interruptible}"'
        ]
        
        # Add optional attributes
        if tts_voice:
            attributes.append(f'voice="{tts_voice}"')
        if dtmf_detection:
            attributes.append('dtmfDetection="true"')
            
        # For ElevenLabs, we might want to enable text normalization
        if tts_provider == "ElevenLabs":
            attributes.append('elevenlabsTextNormalization="true"')
        
        # Join attributes with proper spacing
        attributes_str = "\n            ".join(attributes)
        
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <ConversationRelay 
            {attributes_str}
        />
    </Connect>
</Response>"""
    
    logger.debug(f"Generated ConversationRelay TwiML: {twiml}")
    return twiml