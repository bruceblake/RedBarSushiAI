"""
Agent utility functions for handling OpenAI Agents integration.
This module provides the core functionality for our AI agents.
"""

# Import components from submodules
from app.utils.agent_utils.logging import log_openai_request, log_openai_response
from app.utils.agent_utils.menu import find_menu_item_by_name, get_menu_items, SushiMenuTool
from app.utils.agent_utils.order import analyze_user_input, get_order_modifications
from app.utils.agent_utils.parsing import OrderParsingAgent
from app.utils.agent_utils.modification import OrderModificationAgent
from app.utils.agent_utils.tools import (
    find_menu_item_tool, 
    menu_search_tool,
    handle_conversational_question,
    extract_modifiers_from_item,
    check_modifier_constraints
)

# Export all components
__all__ = [
    # Logging utilities
    'log_openai_request',
    'log_openai_response',
    
    # Menu utilities
    'find_menu_item_by_name',
    'get_menu_items',
    'SushiMenuTool',
    
    # Order utilities
    'analyze_user_input',
    'get_order_modifications',
    
    # Agent classes
    'OrderParsingAgent',
    'OrderModificationAgent',
    
    # Tool functions
    'find_menu_item_tool',
    'menu_search_tool',
    'handle_conversational_question',
    'extract_modifiers_from_item',
    'check_modifier_constraints'
]