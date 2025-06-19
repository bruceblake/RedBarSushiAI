"""
Twilio TwiML utilities for voice call responses.

Legacy Media Streams support has been removed.
Only ConversationRelay is supported now for improved reliability.
"""

import os


def get_environment_name() -> str:
    """
    Get the environment name for greeting messages.
    
    Returns:
        Environment name string
    """
    env = os.environ.get("FASTAPI_ENV", "development")
    
    if env == "production":
        return ""
    elif env == "staging":
        return "Staging"
    else:
        return "Development"