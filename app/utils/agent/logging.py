"""
Logging utilities for OpenAI API calls.
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def log_openai_request(
    model: str, messages: List[Dict[str, Any]], function_name: str = ""
) -> None:
    """Log detailed information about an OpenAI API request"""
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
    """Log detailed information about an OpenAI API response"""
    logger.info(f"[OPENAI-RESPONSE] Function: {function_name}")
    try:
        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "message"):
                content = choice.message.content
                logger.info(
                    f"[OPENAI-CONTENT] {content[:200]}..."
                )  # Log first 200 chars
            elif hasattr(choice, "text"):
                content = choice.text
                logger.info(
                    f"[OPENAI-CONTENT] {content[:200]}..."
                )  # Log first 200 chars
        logger.info(f"[OPENAI-FULL] {str(response)[:500]}...")  # Log first 500 chars
    except Exception as e:
        logger.error(
            f"[OPENAI-RESPONSE-ERROR] Failed to log response: {str(e)}"
        )  # Broad except, but safe for logging
        logger.error(f"[OPENAI-RESPONSE-RAW] {str(response)[:500]}...")