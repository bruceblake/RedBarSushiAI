"""
Agent package for AI-powered functionality.
This package contains components for OpenAI agent integration.
"""

# Import the components that should be accessible from the package
from app.utils.agent.config import OPENAI_API_KEY, AGENT_API_AVAILABLE
from app.utils.agent.logging import log_openai_request, log_openai_response
from app.utils.agent.menu_tool import SushiMenuTool
from app.utils.agent.functions import analyze_user_input, get_order_modifications
from app.utils.agent.order_agent import OrderParsingAgent

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