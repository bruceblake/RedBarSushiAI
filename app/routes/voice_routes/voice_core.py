"""
Core voice functionality module. This module contains core 
voice response functionality, configuration constants, and common helper functions.
"""

import logging
import json
import uuid
import time
from flask import session, request
from twilio.twiml.voice_response import VoiceResponse

# Import agent utilities
from app.utils.agent_utils import OrderParsingAgent

# Set up logger
logger = logging.getLogger(__name__)

# Speech timeout configuration
# Using fixed values instead of "auto" for more predictable behavior
SPEECH_TIMEOUT_SHORT = 2    # For simple responses (yes/no)
SPEECH_TIMEOUT_MEDIUM = 2   # For name, phone number
SPEECH_TIMEOUT_LONG = 3     # For orders, menu questions
SPEECH_TIMEOUT_EXTENDED = 4  # For complex orders

def setup_gather_params(
    timeout=None,
    speech_timeout=None,
    speech_model="phone_call",
    hints=None,
    finish_on_key="#",
    num_digits=None,
    input_type="dtmf speech",
    language="en-US",
    enhanced=True,
):
    """
    Set up Twilio Gather verb parameters with defaults for our application.
    
    This function centralizes gather parameter configuration and applies sensible
    defaults based on the specific call context.
    
    Args:
        timeout: Overall timeout for input in seconds
        speech_timeout: Silence timeout for speech input
        speech_model: Twilio speech recognition model to use
        hints: Phrases to recognize (improves accuracy for specific terms)
        finish_on_key: Key to end input
        num_digits: Number of digits to collect (for DTMF)
        input_type: Input types to accept (dtmf, speech, or both)
        language: Language for speech recognition
        enhanced: Whether to use enhanced speech recognition
        
    Returns:
        dict: Parameters for Twilio's Gather verb
    """
    # Start with base parameters
    params = {
        "input": input_type,
        "timeout": timeout or 5,
        "enhanced": enhanced,
        "language": language,
    }
    
    # Add speech model if accepting speech input
    if "speech" in input_type:
        params["speech_model"] = speech_model
        params["speech_timeout"] = speech_timeout or SPEECH_TIMEOUT_MEDIUM
    
    # Add DTMF-specific parameters if accepting DTMF
    if "dtmf" in input_type:
        params["finish_on_key"] = finish_on_key
        if num_digits:
            params["num_digits"] = num_digits
    
    # Add hints if provided - these improve speech recognition for specific phrases
    if hints:
        if isinstance(hints, list):
            params["hints"] = ", ".join(hints)
        else:
            params["hints"] = hints
    
    return params

def get_adaptive_timeouts(interaction_type="menu", retry_count=0):
    """
    Get adaptive timeout parameters based on interaction type and history.
    
    This function provides intelligent timeout management:
    - First-time interactions: Longer timeouts to allow for thinking
    - Repeated interactions: Shorter timeouts to avoid frustration
    - Complex interactions: Longer speech timeouts to allow for complex inputs
    
    Args:
        interaction_type: Type of interaction (menu, order, name, etc.)
        retry_count: Number of previous attempts at this interaction
        
    Returns:
        tuple: (timeout, speech_timeout) values for the interaction
    """
    # Base timeout values 
    base_timeout = 8  # Overall timeout
    base_speech_timeout = 3  # Silence detection timeout
    
    # Adjust for interaction type
    if interaction_type == "menu":
        base_timeout = 8
        base_speech_timeout = SPEECH_TIMEOUT_MEDIUM
    elif interaction_type == "order":
        base_timeout = 10
        base_speech_timeout = SPEECH_TIMEOUT_LONG
    elif interaction_type == "name":
        base_timeout = 6
        base_speech_timeout = SPEECH_TIMEOUT_MEDIUM
    elif interaction_type == "yes_no":
        base_timeout = 5
        base_speech_timeout = SPEECH_TIMEOUT_SHORT
    elif interaction_type == "complex_order":
        base_timeout = 15
        base_speech_timeout = SPEECH_TIMEOUT_EXTENDED
    
    # Adjust for retry count - shorter timeouts after multiple retries
    if retry_count > 2:
        # After several retries, reduce timeouts to speed up interaction
        timeout = max(base_timeout - (retry_count - 2), 4)
        speech_timeout = max(base_speech_timeout - 0.5, 1.5)
    elif retry_count > 0:
        # Slightly shorter timeout for first retry
        timeout = base_timeout - 0.5
        speech_timeout = base_speech_timeout - 0.2
    else:
        # First attempt - use base timeouts
        timeout = base_timeout
        speech_timeout = base_speech_timeout
    
    return timeout, speech_timeout

def handle_silence(
    response_obj, 
    prompt, 
    action_url, 
    retry_count=0, 
    interaction_type="menu",
    max_retries=3,
    fallback_url=None
):
    """
    Handle silence or no input from the user with intelligent retry logic.
    
    Provides a graceful experience when users don't respond, with:
    - Custom prompts for repeated silence
    - Automatic fallback to DTMF after repeated failures
    - Hard fallback to a different route after maximum retries
    
    Args:
        response_obj: Twilio VoiceResponse object to add prompts to
        prompt: Original prompt to repeat
        action_url: URL to redirect to for processing input
        retry_count: Current retry count for this interaction
        interaction_type: Type of interaction (menu, order, etc.)
        max_retries: Maximum retry attempts before fallback
        fallback_url: URL to redirect to after max retries
        
    Returns:
        Response with appropriate prompt and gather
    """
    # Get adaptive timeouts for this retry
    timeout, speech_timeout = get_adaptive_timeouts(interaction_type, retry_count)
    
    # Create different prompts based on retry count
    if retry_count >= max_retries:
        # After max retries, fall back to a simpler interaction or human agent
        if fallback_url:
            response_obj.say("I'm having trouble hearing you. Let me transfer you to a different menu.")
            response_obj.redirect(fallback_url)
        else:
            # No fallback URL provided, try DTMF only
            response_obj.say("I'm having trouble understanding your voice. Please use your keypad instead.")
            
            # Create DTMF-only gather
            with response_obj.gather(
                input="dtmf",
                action=action_url,
                timeout=timeout,
                finish_on_key="#",
            ) as g:
                g.say(prompt)
    elif retry_count > 1:
        # Second or third retry: encourage the user and offer a hint
        retry_prompt = f"I'm sorry, I still didn't catch that. {prompt} Or press a key to use the keypad menu."
        
        # Gather with both DTMF and speech
        with response_obj.gather(
            input="dtmf speech",
            action=action_url,
            timeout=timeout,
            speech_timeout=speech_timeout,
            speech_model="phone_call",
            enhanced=True,
        ) as g:
            g.say(retry_prompt)
    else:
        # First retry: simple repeat with slight rephrasing
        retry_prompt = f"I didn't catch that. {prompt}"
        
        # Gather with both DTMF and speech
        with response_obj.gather(
            input="dtmf speech",
            action=action_url,
            timeout=timeout,
            speech_timeout=speech_timeout,
            speech_model="phone_call",
            enhanced=True,
        ) as g:
            g.say(retry_prompt)
    
    return response_obj

def get_session_id():
    """
    Create or retrieve a unique session ID for the current conversation.
    
    The session ID provides a way to consistently track a single conversation
    across websocket connections and API calls.
    
    Returns:
        str: A unique session identifier
    """
    if "session_id" not in session:
        # Create a new session ID with timestamp and UUID
        # Format: YYYYMMDD-timestamp-uuid
        time_part = time.strftime("%Y%m%d-%H%M%S")
        unique_id = str(uuid.uuid4())[:8]  # Use first 8 chars of UUID for brevity
        new_id = f"{time_part}-{unique_id}"
        session["session_id"] = new_id
        logger.info(f"Created new session ID: {new_id}")
        return new_id
    
    return session["session_id"]