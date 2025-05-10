"""
Pydantic models for API requests and responses.

This module defines Pydantic models for API requests and responses,
providing validation, serialization, and documentation.
"""

from typing import List, Dict, Any, Optional, Union, Generic, TypeVar
from datetime import datetime
from pydantic import BaseModel, Field

# Generic type for response data
T = TypeVar('T')

class BaseResponse(BaseModel):
    """Base model for API responses with common metadata."""
    
    success: bool = True
    message: str = "Operation successful"
    timestamp: datetime = Field(default_factory=datetime.now)

class ErrorResponse(BaseResponse):
    """Error response model for API endpoints."""
    
    success: bool = False
    message: str = "An error occurred"
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class DataResponse(BaseResponse, Generic[T]):
    """Data response model for API endpoints."""
    
    data: T

class PaginatedResponse(DataResponse, Generic[T]):
    """Paginated response model for API endpoints."""
    
    page: int = 1
    page_size: int = 50
    total_pages: int = 1
    total_items: int = 0

# Voice/WebSocket API models

class WebSocketMessage(BaseModel):
    """Base model for WebSocket messages."""
    
    event: str
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)

class TwilioConnectedEvent(BaseModel):
    """Model for Twilio 'connected' WebSocket event."""
    
    event: str = "connected"
    protocol: str
    twilioSignature: Optional[str] = None
    callSid: Optional[str] = None

class TwilioStartEvent(BaseModel):
    """Model for Twilio 'start' WebSocket event."""
    
    event: str = "start"
    start: Dict[str, Any]
    streamSid: str = Field(..., alias="start.streamSid")

class TwilioMediaEvent(BaseModel):
    """Model for Twilio 'media' WebSocket event."""
    
    event: str = "media"
    media: Dict[str, Any]
    streamSid: str = Field(..., alias="media.streamSid")
    chunk: int = Field(..., alias="media.chunk")
    payload: str = Field(..., alias="media.payload")
    track: str = Field(..., alias="media.track")

class TwilioStopEvent(BaseModel):
    """Model for Twilio 'stop' WebSocket event."""
    
    event: str = "stop"
    streamSid: str

class WelcomeResponse(BaseModel):
    """Model for welcome response sent back to Twilio."""
    
    type: str = "connected"
    message: str = "Connected to RedBarSushi AI (FastAPI)"
    call_sid: str
    stream_sid: Optional[str] = None

class TranscriptEvent(BaseModel):
    """Model for transcript events."""
    
    type: str = "transcript"
    text: str
    is_final: bool = True

class AgentResponseEvent(BaseModel):
    """Model for agent response events."""
    
    type: str = "agent_response"
    text: str
    agent: str = "frontline"
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AudioResponse(BaseModel):
    """Model for audio responses sent to Twilio."""
    
    type: str = "audio"
    payload: str  # Base64-encoded audio data
    format: str = "mulaw"

class VoiceResponseModel(BaseModel):
    """Model for voice response API in FastAPI routes."""
    
    say_text: Optional[str] = None
    play_url: Optional[str] = None
    hangup: bool = False
    redirect_url: Optional[str] = None
    gather_params: Optional[Dict[str, Any]] = None