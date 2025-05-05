"""
Tool registry for Realtime API voice integration.

This module provides a registry for tools that can be called by OpenAI's Realtime API,
mapping tool calls to agent methods.
"""

import logging

# Set up logger
logger = logging.getLogger(__name__)

class ToolRegistry:
    """
    Registry for tools that can be called by OpenAI's Realtime API.
    Maps tool calls to agent methods.
    """
    
    def __init__(self):
        """Initialize the tool registry."""
        self.tools = {}
    
    def register_tool(self, name, function, description=None, schema=None):
        """Register a new tool with the registry."""
        self.tools[name] = {
            "function": function,
            "description": description or function.__doc__ or "",
            "schema": schema or {}
        }
    
    def get_tool_definitions(self):
        """Get tool definitions in OpenAI's format."""
        definitions = []
        for name, tool in self.tools.items():
            definitions.append({
                "type": "function",
                "name": name,
                "description": tool["description"],
                "parameters": tool["schema"]
            })
        return definitions
    
    def execute_tool(self, name, args, session_id=None):
        """Execute a registered tool."""
        if name not in self.tools:
            raise ValueError(f"Tool '{name}' not registered")
        
        tool = self.tools[name]
        if session_id:
            return tool["function"](session_id=session_id, **args)
        else:
            return tool["function"](**args)


def register_default_tools(registry):
    """Register default tools with the registry."""
    
    # Get the frontline agent from global components
    from app.routes.voice import get_global_component
    frontline_agent = get_global_component('frontline_agent')
    
    # Lookup menu item
    registry.register_tool(
        name="lookup_menu_item",
        function=frontline_agent.lookup_menu_item if hasattr(frontline_agent, 'lookup_menu_item') else lambda **kwargs: {"error": "Function not available"},
        description="Look up a menu item by name to get its details",
        schema={
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "The name of the menu item to look up"
                }
            },
            "required": ["item_name"]
        }
    )
    
    # Add item to cart
    registry.register_tool(
        name="add_item_to_cart",
        function=frontline_agent.add_to_cart if hasattr(frontline_agent, 'add_to_cart') else lambda **kwargs: {"error": "Function not available"},
        description="Add an item to the customer's cart",
        schema={
            "type": "object",
            "properties": {
                "item_plu": {
                    "type": "string",
                    "description": "The PLU of the menu item"
                },
                "quantity": {
                    "type": "integer",
                    "description": "The quantity to add"
                },
                "modifiers": {
                    "type": "array",
                    "description": "List of modifiers to apply",
                    "items": {
                        "type": "object",
                        "properties": {
                            "modifier_plu": {"type": "string"},
                            "quantity": {"type": "integer"}
                        }
                    }
                }
            },
            "required": ["item_plu", "quantity"]
        }
    )
    
    # Get cart contents
    registry.register_tool(
        name="get_cart",
        function=frontline_agent.get_cart if hasattr(frontline_agent, 'get_cart') else lambda **kwargs: {"error": "Function not available"},
        description="Get the current contents of the customer's cart",
        schema={
            "type": "object",
            "properties": {}
        }
    )
    
    # Complete order
    registry.register_tool(
        name="complete_order",
        function=frontline_agent.complete_order if hasattr(frontline_agent, 'complete_order') else lambda **kwargs: {"error": "Function not available"},
        description="Complete the customer's order and submit it",
        schema={
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Customer's name"
                },
                "phone_number": {
                    "type": "string",
                    "description": "Customer's phone number"
                },
                "order_type": {
                    "type": "integer",
                    "description": "1 for pickup, 2 for delivery"
                },
                "delivery_address": {
                    "type": "string",
                    "description": "Delivery address (required for delivery orders)"
                }
            },
            "required": ["customer_name", "phone_number", "order_type"]
        }
    )