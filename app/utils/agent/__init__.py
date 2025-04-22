"""
Agent package for AI-powered functionality.
This package contains components for OpenAI agent integration.
"""

import os
import logging
import importlib.util

logger = logging.getLogger(__name__)

# Set default values in case imports fail
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
AGENT_API_AVAILABLE = False

# Define function stubs that will be replaced by actual imports if available
def log_openai_request(model=None, messages=None, function_name=None):
    logger.warning("log_openai_request function not properly loaded")
    return None

def log_openai_response(response=None, function_name=None):
    logger.warning("log_openai_response function not properly loaded")
    return None

def analyze_user_input(input_text=None):
    logger.warning("analyze_user_input function not properly loaded")
    return {"error": "Function not available"}

def get_order_modifications(order=None, modification_text=None):
    logger.warning("get_order_modifications function not properly loaded")
    return None, "Function not available"

# Define stub classes
class SushiMenuTool:
    def __init__(self):
        logger.warning("SushiMenuTool class not properly loaded")

class OrderParsingAgent:
    def __init__(self):
        logger.warning("OrderParsingAgent class not properly loaded")
    
    def parse_order(self, order_text):
        return {"items": []}

# Try to import actual components
try:
    # Import config
    from app.utils.agent.config import OPENAI_API_KEY, AGENT_API_AVAILABLE
    
    # Import logging
    from app.utils.agent.logging import log_openai_request, log_openai_response
    
    # Import remaining components if config is available
    try:
        from app.utils.agent.menu_tool import SushiMenuTool
        from app.utils.agent.functions import analyze_user_input, get_order_modifications
        from app.utils.agent.order_agent import OrderParsingAgent
        logger.info("Successfully loaded all agent components")
    except ImportError as e:
        logger.warning(f"Error importing some agent components: {e}")
        
except ImportError as e:
    logger.warning(f"Error importing agent config: {e}")
    logger.warning("AI agent functionality will be limited or unavailable")

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