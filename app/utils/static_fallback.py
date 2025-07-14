"""
Static Fallback Mode for RedBarSushiAI.

This module provides hardcoded fallback responses when the AI system
is unavailable due to OpenAI API failures. It implements a minimal
viable ordering system that can handle basic call flow without AI.
"""

import logging
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)

class FallbackState(Enum):
    """States in the static fallback system."""
    GREETING = "greeting"
    MAIN_MENU = "main_menu"
    LEAVE_MESSAGE = "leave_message"
    COLLECT_PHONE = "collect_phone"
    CONFIRM_MESSAGE = "confirm_message"
    GOODBYE = "goodbye"

class StaticFallbackHandler:
    """
    Handles voice ordering when AI is unavailable.
    
    Provides a minimal but functional ordering experience using
    pre-recorded messages and DTMF input collection.
    """
    
    def __init__(self):
        self.state = FallbackState.GREETING
        self.customer_phone = None
        self.customer_message = None
        logger.info("Static fallback handler initialized")
    
    def generate_twiml_response(self, dtmf_input: Optional[str] = None) -> str:
        """
        Generate TwiML response based on current state and DTMF input.
        
        Args:
            dtmf_input: DTMF digit pressed by user
            
        Returns:
            TwiML XML string
        """
        if self.state == FallbackState.GREETING:
            return self._greeting_twiml()
        elif self.state == FallbackState.MAIN_MENU:
            return self._main_menu_twiml(dtmf_input)
        elif self.state == FallbackState.LEAVE_MESSAGE:
            return self._leave_message_twiml()
        elif self.state == FallbackState.COLLECT_PHONE:
            return self._collect_phone_twiml()
        elif self.state == FallbackState.CONFIRM_MESSAGE:
            return self._confirm_message_twiml(dtmf_input)
        elif self.state == FallbackState.GOODBYE:
            return self._goodbye_twiml()
        else:
            return self._error_twiml()
    
    def _greeting_twiml(self) -> str:
        """Generate greeting TwiML."""
        self.state = FallbackState.MAIN_MENU
        return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">
        Hello! This is Red Bar Sushi. Our AI ordering system is currently unavailable, 
        but we're here to help you. Please press 1 to leave a message with your order 
        and phone number, and we'll call you back shortly. Press 2 to speak with someone now, 
        or hang up to try again later.
    </Say>
    <Gather numDigits="1" timeout="10" action="/voice/fallback">
        <Say voice="alice">Press 1 to leave a message, or 2 to speak with staff.</Say>
    </Gather>
    <Redirect>/voice/fallback?timeout=true</Redirect>
</Response>"""
    
    def _main_menu_twiml(self, dtmf_input: Optional[str]) -> str:
        """Generate main menu TwiML based on DTMF input."""
        if dtmf_input == "1":
            self.state = FallbackState.LEAVE_MESSAGE
            return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">
        Perfect! After the beep, please tell us your name, phone number, and your order. 
        We'll call you back within 15 minutes to confirm and process your order.
    </Say>
    <Record maxLength="180" action="/voice/fallback-recording" transcribe="true" />
</Response>"""
        
        elif dtmf_input == "2":
            # Try to transfer to human staff
            from app.config import settings
            transfer_number = getattr(settings, 'HUMAN_HANDOFF_NUMBER', None)
            
            if transfer_number:
                return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Please hold while I connect you with our staff.</Say>
    <Dial timeout="30">
        <Number>{transfer_number}</Number>
    </Dial>
    <Say voice="alice">
        I'm sorry, but our staff is currently busy. Please press 1 to leave a message 
        or call back later.
    </Say>
    <Gather numDigits="1" timeout="10" action="/voice/fallback">
        <Say voice="alice">Press 1 to leave a message.</Say>
    </Gather>
    <Hangup/>
</Response>"""
            else:
                # No transfer number configured
                self.state = FallbackState.LEAVE_MESSAGE
                return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">
        I'm sorry, but our staff line is currently unavailable. 
        Let me help you leave a message instead.
    </Say>
    <Redirect>/voice/fallback</Redirect>
</Response>"""
        
        else:
            # Invalid input or timeout
            return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">
        I didn't understand that selection. Please press 1 to leave a message 
        with your order, or 2 to speak with staff.
    </Say>
    <Gather numDigits="1" timeout="10" action="/voice/fallback">
        <Say voice="alice">Press 1 for message, or 2 for staff.</Say>
    </Gather>
    <Say voice="alice">Thank you for calling Red Bar Sushi. Please try again later.</Say>
    <Hangup/>
</Response>"""
    
    def _leave_message_twiml(self) -> str:
        """Generate leave message TwiML."""
        return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">
        Please leave your message after the beep. Include your name, phone number, 
        and your complete order. We'll call you back to confirm.
    </Say>
    <Record maxLength="180" action="/voice/fallback-recording" transcribe="true" />
</Response>"""
    
    def _confirm_message_twiml(self, dtmf_input: Optional[str]) -> str:
        """Generate message confirmation TwiML."""
        if dtmf_input == "1":
            self.state = FallbackState.GOODBYE
            return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">
        Perfect! We've received your message and will call you back within 15 minutes 
        to confirm your order. Thank you for choosing Red Bar Sushi!
    </Say>
    <Hangup/>
</Response>"""
        else:
            self.state = FallbackState.LEAVE_MESSAGE
            return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Let's try again. Please leave your complete message after the beep.</Say>
    <Record maxLength="180" action="/voice/fallback-recording" transcribe="true" />
</Response>"""
    
    def _goodbye_twiml(self) -> str:
        """Generate goodbye TwiML."""
        return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Thank you for calling Red Bar Sushi. Have a great day!</Say>
    <Hangup/>
</Response>"""
    
    def _error_twiml(self) -> str:
        """Generate error TwiML."""
        return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">
        I'm sorry, but we're experiencing technical difficulties. 
        Please call back in a few minutes or visit us in person. Thank you.
    </Say>
    <Hangup/>
</Response>"""
    
    def process_recording(self, recording_url: str, transcription: Optional[str] = None) -> str:
        """
        Process a customer recording and generate confirmation TwiML.
        
        Args:
            recording_url: URL of the recorded message
            transcription: Transcribed text (if available)
            
        Returns:
            TwiML for confirmation
        """
        logger.info(f"Processing fallback recording: {recording_url}")
        if transcription:
            logger.info(f"Transcription: {transcription}")
        
        # TODO: Save recording and transcription to database for staff review
        # TODO: Send notification to staff about new message
        
        self.state = FallbackState.CONFIRM_MESSAGE
        return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">
        Thank you for your message. We've recorded your order request. 
        Press 1 to confirm, or any other key to record a new message.
    </Say>
    <Gather numDigits="1" timeout="10" action="/voice/fallback">
    </Gather>
    <Redirect>/voice/fallback</Redirect>
</Response>"""

# Global fallback handler instance
_fallback_handler: Optional[StaticFallbackHandler] = None

def get_fallback_handler() -> StaticFallbackHandler:
    """Get or create the global fallback handler instance."""
    global _fallback_handler
    if _fallback_handler is None:
        _fallback_handler = StaticFallbackHandler()
    return _fallback_handler

def generate_fallback_response(dtmf_input: Optional[str] = None) -> str:
    """
    Generate a static fallback TwiML response.
    
    Args:
        dtmf_input: DTMF digit pressed by user
        
    Returns:
        TwiML XML string
    """
    handler = get_fallback_handler()
    return handler.generate_twiml_response(dtmf_input)

def process_fallback_recording(recording_url: str, transcription: Optional[str] = None) -> str:
    """
    Process a fallback mode recording.
    
    Args:
        recording_url: URL of the recorded message
        transcription: Transcribed text
        
    Returns:
        TwiML XML string
    """
    handler = get_fallback_handler()
    return handler.process_recording(recording_url, transcription)