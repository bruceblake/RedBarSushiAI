"""
Silence and timeout handling for ConversationRelay.

This module provides mechanisms to handle silence and re-prompt users
when they don't respond to the AI's questions.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class SilenceHandler:
    """Handles silence detection and re-prompting in conversations."""
    
    def __init__(self, timeout_seconds: int = 8, max_retries: int = 2):
        """
        Initialize silence handler.
        
        Args:
            timeout_seconds: Seconds to wait before re-prompting
            max_retries: Maximum number of re-prompts before giving up
        """
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.active_timers: Dict[str, asyncio.Task] = {}
        self.retry_counts: Dict[str, int] = {}
        
    async def start_silence_timer(
        self, 
        call_sid: str, 
        callback: callable,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Start a silence timer for a call.
        
        Args:
            call_sid: The call identifier
            callback: Async function to call when silence detected
            context: Optional context about what we're waiting for
        """
        # Cancel existing timer if any
        await self.cancel_timer(call_sid)
        
        # Create new timer task
        self.active_timers[call_sid] = asyncio.create_task(
            self._silence_timer(call_sid, callback, context)
        )
        logger.info(f"Started silence timer for {call_sid} ({self.timeout_seconds}s)")
        
    async def _silence_timer(
        self, 
        call_sid: str, 
        callback: callable,
        context: Optional[Dict[str, Any]] = None
    ):
        """Internal timer implementation."""
        try:
            await asyncio.sleep(self.timeout_seconds)
            
            # Timer expired - user hasn't spoken
            retry_count = self.retry_counts.get(call_sid, 0)
            
            if retry_count < self.max_retries:
                self.retry_counts[call_sid] = retry_count + 1
                logger.info(f"Silence detected for {call_sid}, retry {retry_count + 1}/{self.max_retries}")
                
                # Call the callback to send re-prompt
                await callback(call_sid, retry_count + 1, context)
                
                # Restart timer for next attempt
                await self.start_silence_timer(call_sid, callback, context)
            else:
                logger.warning(f"Max retries reached for {call_sid}, giving up")
                # Could implement a "goodbye" message here
                await callback(call_sid, -1, context)  # -1 indicates final attempt
                
        except asyncio.CancelledError:
            logger.debug(f"Silence timer cancelled for {call_sid}")
            
    async def cancel_timer(self, call_sid: str):
        """Cancel active timer for a call."""
        if call_sid in self.active_timers:
            self.active_timers[call_sid].cancel()
            del self.active_timers[call_sid]
            logger.debug(f"Cancelled silence timer for {call_sid}")
            
    def reset_retry_count(self, call_sid: str):
        """Reset retry count when user responds."""
        if call_sid in self.retry_counts:
            del self.retry_counts[call_sid]
            
    async def cleanup(self, call_sid: str):
        """Clean up all resources for a call."""
        await self.cancel_timer(call_sid)
        self.reset_retry_count(call_sid)


# Global instance
silence_handler = SilenceHandler()


# Re-prompt messages based on context and retry count
def get_reprompt_message(context: Dict[str, Any], retry_count: int) -> str:
    """
    Get appropriate re-prompt message based on context.
    
    Args:
        context: Information about what we're waiting for
        retry_count: Which retry attempt this is
        
    Returns:
        Re-prompt message text
    """
    state = context.get("state", "GREETING")
    
    if retry_count == -1:  # Final message
        return "I'm sorry, I couldn't hear you. Please call back when you're ready to place an order. Goodbye!"
    
    reprompts = {
        "GREETING": [
            "I didn't catch that. Could you please tell me your name?",
            "Sorry, I'm having trouble hearing you. What's your name?"
        ],
        "MAIN_MENU": [
            "Are you still there? How can I help you today?",
            "I'm here when you're ready. Would you like to place an order?"
        ],
        "ORDERING": [
            "Would you like to add anything to your order?",
            "Take your time. What would you like to order?"
        ],
        "CONFIRM_ORDER": [
            "Would you like me to repeat your order, or are you ready to proceed?",
            "Please let me know if you'd like to confirm your order or make changes."
        ],
        "PAYMENT": [
            "How would you like to pay for your order?",
            "Are you still there? I need to know your payment preference."
        ],
        "COMPLETE": [
            "Is there anything else I can help you with today?",
            "Thank you for your order. Have a great day!"
        ]
    }
    
    messages = reprompts.get(state, ["Are you still there?", "Hello?"])
    return messages[min(retry_count - 1, len(messages) - 1)]