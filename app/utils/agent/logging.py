"""
Logging utilities for OpenAI API calls.
"""

import logging
import json
from typing import Dict, List, Any

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def log_openai_request(
    model: str, messages: List[Dict[str, Any]], function_name: str = ""
) -> None:
    """Log OpenAI API requests"""
    try:
        # Log basic info about the request
        logger.info(f"[OPENAI-REQUEST] Function: {function_name}, Model: {model}")
        logger.debug(f"[OPENAI-REQUEST-DETAIL] Messages: {json.dumps(messages)}")
    except Exception as e:
        logger.error(f"Error logging OpenAI request: {str(e)}")


def log_openai_response(response: Any, function_name: str = "") -> None:
    """Log OpenAI API responses"""
    try:
        # Log basic info about the response
        if hasattr(response, 'model'):
            model = response.model
        else:
            model = 'unknown'
            
        logger.info(f"[OPENAI-RESPONSE] Function: {function_name}, Model: {model}")
        
        # Include detailed response in debug logs
        if hasattr(response, 'to_dict'):
            logger.debug(f"[OPENAI-RESPONSE-DETAIL] {json.dumps(response.to_dict())}")
        else:
            logger.debug(f"[OPENAI-RESPONSE-DETAIL] {response}")
    except Exception as e:
        logger.error(f"Error logging OpenAI response: {str(e)}")