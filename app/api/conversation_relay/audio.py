"""
Audio utilities for ConversationRelay.

This module is deprecated as Twilio ConversationRelay handles all
audio processing (STT/TTS) when using the url attribute.
"""

import logging

logger = logging.getLogger(__name__)

# This module is deprecated - Twilio ConversationRelay handles all audio processing
# When using <ConversationRelay url="...">, Twilio performs:
# - Speech-to-Text (STT) and sends transcribed text in "prompt" events
# - Text-to-Speech (TTS) when we send "text" messages back

logger.warning("audio.py is deprecated - ConversationRelay handles all audio processing")