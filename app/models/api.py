"""
Pydantic models for API requests and responses.

This module defines Pydantic models for API requests and responses,
providing validation, serialization, and documentation.
"""

from datetime import datetime
from pydantic import BaseModel, Field

# Generic type for response data
# T = TypeVar('T') # Removed


class BaseResponse(BaseModel):
    """Base model for API responses with common metadata."""

    success: bool = True
    message: str = "Operation successful"
    timestamp: datetime = Field(default_factory=datetime.now)


# ErrorResponse removed
# DataResponse removed (as it's only used by PaginatedResponse which is also removed)
# PaginatedResponse removed

# Voice/WebSocket API models
# WebSocketMessage removed
# TwilioConnectedEvent removed
# TwilioStartEvent removed
# TwilioMediaEvent removed
# TwilioStopEvent removed
# WelcomeResponse removed
# TranscriptEvent removed
# AgentResponseEvent removed
# AudioResponse removed
# VoiceResponseModel removed
