"""
Agent package for AI-powered functionality.
This package contains components for OpenAI agent integration.
"""

import os
import logging

logger = logging.getLogger(__name__)

# Direct imports with no fallbacks
from app.utils.agent.config import OPENAI_API_KEY, AGENT_API_AVAILABLE
from app.utils.agent.logging import log_openai_request, log_openai_response
from app.utils.agent.menu_tool import SushiMenuTool
from app.utils.agent.functions import analyze_user_input, get_order_modifications
from app.utils.agent.order_agent import OrderParsingAgent

# Validate that the AI agent components are available
if not AGENT_API_AVAILABLE or not OPENAI_API_KEY:
    # Critical components are missing, log error and raise exception
    error_msg = "AI agent components are not available! Missing "
    if not OPENAI_API_KEY:
        error_msg += "OpenAI API key"
    if not AGENT_API_AVAILABLE:
        error_msg += " and Agent API support" if not OPENAI_API_KEY else "Agent API support"
    logger.error(error_msg)
    raise ImportError(error_msg + ". System cannot proceed without AI components.")
else:
    logger.info("Loaded all AI agent components - no fallbacks allowed")

# Export the public API
__all__ = [
    'OPENAI_API_KEY', 
    'AGENT_API_AVAILABLE',
    'log_openai_request', 
    'log_openai_response',
    'SushiMenuTool',
    'OrderParsingAgent', 
    'analyze_user_input', 
    'get_order_modifications'
]