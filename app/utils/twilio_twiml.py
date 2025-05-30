"""
Twilio TwiML utilities for generating voice call responses.
"""

import os
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class TwimlStreamParameter:
    """Parameters for configuring the TwiML stream."""
    url: str
    track: str = "inbound_track"
    name: str = "media_stream"
    custom_parameters: Optional[List[Dict[str, str]]] = None


@dataclass
class TwimlParameter:
    """Parameters for TwiML generation."""
    voice: str
    language: str
    greeting_text: str
    fallback_text: str
    stream_params: TwimlStreamParameter
    call_sid: str


def generate_media_streams_twiml(params: TwimlParameter) -> str:
    """
    Generate TwiML for Media Streams WebSocket connection.
    
    Args:
        params: TwiML parameters including voice settings and stream configuration
        
    Returns:
        TwiML XML string for Twilio
    """
    # Build custom parameters XML if provided
    custom_params_xml = ""
    if params.stream_params.custom_parameters:
        for param in params.stream_params.custom_parameters:
            custom_params_xml += f'<Parameter name="{param["name"]}" value="{param["value"]}" />'
    
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{params.voice}" language="{params.language}">{params.greeting_text}</Say>
    <Connect>
        <Stream url="{params.stream_params.url}" track="{params.stream_params.track}" name="{params.stream_params.name}">
            {custom_params_xml}
        </Stream>
    </Connect>
    <Say voice="{params.voice}" language="{params.language}">{params.fallback_text}</Say>
</Response>"""
    
    return twiml


def get_environment_name() -> str:
    """
    Get the environment name for greeting messages.
    
    Returns:
        Environment name string
    """
    env = os.environ.get("FASTAPI_ENV", "development")
    
    if env == "production":
        return ""
    elif env == "staging":
        return "Staging"
    else:
        return "Development"