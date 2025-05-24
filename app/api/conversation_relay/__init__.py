"""
Twilio ConversationRelay integration for RedBarSushiAI.

This module implements the ConversationRelay WebSocket handler for
bidirectional audio streaming with improved latency and reliability.
"""

from .handler import router as conversation_relay_router
from .twiml import generate_conversation_relay_twiml

__all__ = [
    "conversation_relay_router",
    "generate_conversation_relay_twiml"
]