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
    """Stub for logging OpenAI API requests"""
    # Simple logging for testing
    logger.info(f"[OPENAI-REQUEST-STUB] Function: {function_name}")


def log_openai_response(response: Any, function_name: str = "") -> None:
    """Stub for logging OpenAI API responses"""
    # Simple logging for testing
    logger.info(f"[OPENAI-RESPONSE-STUB] Function: {function_name}")