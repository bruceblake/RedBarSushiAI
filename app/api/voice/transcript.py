"""
Transcript processing for voice interactions.

This module contains functions for processing transcripts from the OpenAI Realtime API,
including handling partial and final transcripts, and routing them to the appropriate agents.
"""

import logging
import traceback
from typing import Dict, Any, Optional

from app.utils.agent_orchestration_async import async_agent_orchestrator
from app.utils.fsm_async import async_fsm_manager, ConversationState, ConversationEvent

# Set up logging
logger = logging.getLogger(__name__)

async def process_transcript(
    call_sid: str,
    transcript: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Process a transcript from OpenAI.
    
    This function routes the transcript to the appropriate agent based on the current
    FSM state, and returns the agent's response.
    
    Args:
        call_sid: The Twilio call SID
        transcript: The text transcript to process
        context: Additional context for processing (optional)
        
    Returns:
        The agent's response
    """
    logger.info(f"[{call_sid}] Processing transcript: {transcript}")
    
    try:
        # Default context if none provided
        if context is None:
            context = {}
            
        # Process the input with the agent orchestrator
        response = await async_agent_orchestrator.process_voice_input(
            call_sid, transcript, context
        )
        
        logger.info(f"[{call_sid}] Agent response: {response.get('text', '[no text]')}")
        return response
    except Exception as e:
        logger.error(f"[{call_sid}] Error processing transcript: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "error": str(e),
            "text": "I'm sorry, I'm having trouble processing that. Could you please repeat?"
        }

async def handle_partial_transcript(
    call_sid: str,
    partial_transcript: str
) -> None:
    """
    Handle a partial transcript from OpenAI.
    
    This function is used for real-time feedback and logging but doesn't
    trigger a response from the agent.
    
    Args:
        call_sid: The Twilio call SID
        partial_transcript: The partial transcript text
    """
    # For now, just log the partial transcript
    logger.debug(f"[{call_sid}] Partial transcript: {partial_transcript}")

async def format_response_for_tts(
    response: Dict[str, Any],
    call_sid: str
) -> str:
    """
    Format an agent response for text-to-speech.
    
    This function takes the response from an agent and formats it for TTS,
    applying any necessary adjustments for better speech quality.
    
    Args:
        response: The agent's response
        call_sid: The Twilio call SID
        
    Returns:
        The formatted text for TTS
    """
    # Extract the text from the response
    text = response.get("text", "")
    
    # If no text, return empty string
    if not text:
        return ""
        
    # Basic reformatting for better TTS
    
    # Replace URLs with more speakable text
    import re
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
    text = re.sub(url_pattern, "our website", text)
    
    # Ensure proper spacing after punctuation
    text = re.sub(r'([.,!?])([^\s])', r'\1 \2', text)
    
    # Replace special characters with speakable alternatives
    text = text.replace("&", "and")
    text = text.replace("-", " ")
    text = text.replace("*", "")
    
    # Log the formatted text
    logger.debug(f"[{call_sid}] Formatted for TTS: {text}")
    
    return text