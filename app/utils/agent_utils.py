"""
Agent utility functions for handling OpenAI Agents integration.
This module provides the core functionality for our AI agents.

Note: This file has been refactored into smaller modules in the agent/ package.
This file now serves as a compatibility layer to maintain backward compatibility.
"""

import logging
import os
logger = logging.getLogger(__name__)
logger.info("Loading agent_utils compatibility layer")

# Direct imports to avoid circular dependencies
from app.utils.agent.config import OPENAI_API_KEY, AGENT_API_AVAILABLE
from app.utils.agent.logging import log_openai_request, log_openai_response
from app.utils.agent.menu_tool import SushiMenuTool
from app.utils.agent.order_agent import OrderParsingAgent
from app.utils.agent.functions import analyze_user_input, get_order_modifications

# Export everything that was previously available
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