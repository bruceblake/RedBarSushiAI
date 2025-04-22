"""
Agent package for AI-powered functionality.
This package contains components for OpenAI agent integration.
This package is designed to work with any menu structure, using AI to dynamically 
analyze menu items and suggest appropriate modifiers without hardcoded values.
"""

import os
import logging

logger = logging.getLogger(__name__)

# Get OpenAI API key from environment
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "dummy_key")

# Set these to always be True to avoid breaking changes
AGENT_API_AVAILABLE = True
AI_COMPONENTS_AVAILABLE = True

logger.info("Loading agent components - AI components will be used for menu analysis")

# Import functions - no fallbacks, require all AI components
from .config import OPENAI_API_KEY, AGENT_API_AVAILABLE
from .logging import log_openai_request, log_openai_response
from .menu_tool import SushiMenuTool
from .order_agent import OrderParsingAgent
from .functions import analyze_user_input, get_order_modifications

logger.info("Successfully imported all agent components")

# Export the public API
__all__ = [
    'OPENAI_API_KEY', 
    'AGENT_API_AVAILABLE',
    'AI_COMPONENTS_AVAILABLE',
    'log_openai_request', 
    'log_openai_response',
    'SushiMenuTool',
    'OrderParsingAgent', 
    'analyze_user_input', 
    'get_order_modifications'
]