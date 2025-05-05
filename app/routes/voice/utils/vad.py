"""
Voice Activity Detection (VAD) configuration for RedBarSushiAI.

This module provides context-specific VAD settings for different
conversation phases, optimizing silence detection and timeouts.
"""

import logging

# Set up logger
logger = logging.getLogger(__name__)

def configure_vad_for_context(context="normal"):
    """
    Configure VAD settings optimized for different conversation contexts.
    
    Args:
        context: The context type (greeting, ordering, confirmation, etc.)
    
    Returns:
        Dict with VAD configuration parameters
    """
    # Base configuration - reasonable defaults
    base_config = {
        "mode": "dynamic_threshold",
        "timeout": 2.0,               # Default 2-second timeout
        "interrupt_assistant": True,  # Allow user interruptions
        "create_response": True,      # Auto-create responses on turn change
        "speech_started_delay": 0.3,  # Slight delay for better detection
    }
    
    # Context-specific adjustments
    if context == "greeting":
        # Short timeouts for simple responses
        base_config.update({
            "timeout": 1.5,
            "speech_started_delay": 0.2,
        })
    elif context == "ordering":
        # Longer timeouts for complex responses
        base_config.update({
            "timeout": 3.0,              # Longer silence tolerance
            "speech_started_delay": 0.4, # More delay for menu browsing
        })
    elif context == "confirmation":
        # Quick responses expected
        base_config.update({
            "timeout": 1.2,              # Shorter timeouts for yes/no
            "speech_started_delay": 0.2,
        })
    elif context == "complex_order":
        # Maximum patience for complex orders
        base_config.update({
            "timeout": 4.0,              # Very patient silence detection
            "speech_started_delay": 0.5, # Higher delay for complex thinking
        })
    
    return base_config