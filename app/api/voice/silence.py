"""
Silence detection and handling for voice interactions.

This module contains functions for detecting and handling silence periods
during voice interactions, including Voice Activity Detection (VAD) events.
"""

import logging
import time
import asyncio
from typing import Dict, Any, Optional, Callable

# Set up logging
logger = logging.getLogger(__name__)

class SilenceHandler:
    """Handler for managing silence periods during voice interactions."""
    
    def __init__(self, call_sid: str, timeout_callback: Callable = None):
        """
        Initialize the silence handler.
        
        Args:
            call_sid: The Twilio call SID
            timeout_callback: Callback function to execute on silence timeout
        """
        self.call_sid = call_sid
        self.timeout_callback = timeout_callback
        self.silence_start_time = None
        self.last_activity_time = time.time()
        self.silence_threshold_ms = 5000  # 5 seconds default
        self.timeout_task = None
        
    def update_threshold(self, threshold_ms: int) -> None:
        """
        Update the silence threshold.
        
        Args:
            threshold_ms: The silence threshold in milliseconds
        """
        self.silence_threshold_ms = threshold_ms
        logger.debug(f"[{self.call_sid}] Updated silence threshold to {threshold_ms}ms")
        
    def speech_started(self) -> None:
        """Handle speech started event."""
        self.last_activity_time = time.time()
        self.silence_start_time = None
        
        # Cancel any pending timeout task
        if self.timeout_task and not self.timeout_task.done():
            self.timeout_task.cancel()
            
        logger.debug(f"[{self.call_sid}] Speech started, reset silence timer")
        
    def speech_stopped(self) -> None:
        """Handle speech stopped event."""
        self.last_activity_time = time.time()
        self.silence_start_time = time.time()
        
        # Start the silence timeout timer
        if self.timeout_callback:
            self.timeout_task = asyncio.create_task(self._check_silence_timeout())
            
        logger.debug(f"[{self.call_sid}] Speech stopped, started silence timer")
        
    async def _check_silence_timeout(self) -> None:
        """Check for silence timeout and execute callback if threshold exceeded."""
        if not self.silence_start_time:
            return
            
        # Calculate time to wait
        wait_time = self.silence_threshold_ms / 1000.0
        
        try:
            # Wait for the silence threshold
            await asyncio.sleep(wait_time)
            
            # Check if we're still in silence
            if self.silence_start_time:
                silence_duration = time.time() - self.silence_start_time
                if silence_duration * 1000 >= self.silence_threshold_ms:
                    logger.info(f"[{self.call_sid}] Silence timeout triggered after {silence_duration:.1f}s")
                    
                    # Execute the timeout callback
                    if self.timeout_callback:
                        await self.timeout_callback(self.call_sid, silence_duration)
        except asyncio.CancelledError:
            # Task was cancelled, just exit
            pass
        except Exception as e:
            logger.error(f"[{self.call_sid}] Error in silence timeout check: {e}")

async def handle_vad_event(
    event_type: str,
    call_sid: str,
    silence_handler: SilenceHandler
) -> None:
    """
    Handle VAD events from OpenAI.
    
    Args:
        event_type: The VAD event type (speech_started, speech_stopped)
        call_sid: The Twilio call SID
        silence_handler: The silence handler instance
    """
    if event_type == "input_audio_buffer.speech_started":
        silence_handler.speech_started()
    elif event_type == "input_audio_buffer.speech_stopped":
        silence_handler.speech_stopped()

async def generate_reprompt(
    call_sid: str,
    silence_duration: float,
    openai_client: Any,
    fsm_state: str
) -> None:
    """
    Generate a reprompt message after silence timeout.
    
    Args:
        call_sid: The Twilio call SID
        silence_duration: The duration of silence in seconds
        openai_client: The OpenAI Realtime client
        fsm_state: The current FSM state
    """
    # Select an appropriate reprompt based on the current state
    if fsm_state == "GREETING":
        reprompt = "Hi there, is anyone there? I'm Red Bar Sushi's virtual assistant. How can I help you today?"
    elif fsm_state == "ORDERING":
        reprompt = "I didn't catch that. Would you like to place an order or hear about our menu?"
    elif fsm_state == "CONFIRMATION":
        reprompt = "I'll need your confirmation to proceed with the order. Would you like to continue or make changes?"
    else:
        reprompt = "I'm still here. Let me know if you need any assistance with your order."
    
    # Send the reprompt to OpenAI for TTS
    logger.info(f"[{call_sid}] Sending reprompt after {silence_duration:.1f}s silence: {reprompt}")
    
    try:
        await openai_client.request_response(reprompt)
    except Exception as e:
        logger.error(f"[{call_sid}] Error sending reprompt: {e}")