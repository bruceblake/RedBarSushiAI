"""
OpenAI request and response logging utilities.
These functions help with debugging OpenAI API interactions.
"""

import logging
from typing import Dict, List, Any

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def log_openai_request(
    model: str, messages: List[Dict[str, Any]], function_name: str = ""
) -> None:
    """
    Log detailed information about an OpenAI API request.
    
    Args:
        model: The OpenAI model being used
        messages: The messages being sent to the API
        function_name: The name of the function making the request
    """
    logger.info(f"[OPENAI-REQUEST] Function: {function_name}, Model: {model}")
    try:
        msg_summary = []
        for msg in messages:
            content = msg.get("content", "")
            if content and isinstance(content, str):
                truncated = content[:100] + "..." if len(content) > 100 else content
                msg_summary.append(f"{msg.get('role')}: {truncated}")
        logger.info(f"[OPENAI-MESSAGES] {'; '.join(msg_summary)}")
    except Exception as e:
        logger.error(
            f"[OPENAI-REQUEST-ERROR] Failed to log messages: {str(e)}"
        )  # Broad except, but safe for logging


def log_openai_response(response: Any, function_name: str = "") -> None:
    """
    Log detailed information about an OpenAI API response.
    
    Args:
        response: The response from the OpenAI API
        function_name: The name of the function that made the request
    """
    logger.info(f"[OPENAI-RESPONSE] Function: {function_name}")
    try:
        if hasattr(response, "choices") and response.choices:
            content = response.choices[0].message.content if hasattr(response.choices[0], "message") else "No content"
            truncated = content[:100] + "..." if len(content) > 100 else content
            logger.info(f"[OPENAI-RESPONSE-CONTENT] {truncated}")
        else:
            logger.info("[OPENAI-RESPONSE-CONTENT] No choices in response or unexpected format")
    except Exception as e:
        logger.error(
            f"[OPENAI-RESPONSE-ERROR] Failed to log response: {str(e)}"
        )  # Broad except, but safe for logging