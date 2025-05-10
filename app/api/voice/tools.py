"""
Tool call handling for voice interactions.

This module contains functions for handling tool calls from the OpenAI Realtime API,
including processing and returning results.
"""

import json
import logging
import traceback
from typing import Dict, Any, Optional

from app.utils.agent_orchestration_async import async_agent_orchestrator

# Set up logging
logger = logging.getLogger(__name__)

async def process_tool_call(
    call_sid: str,
    tool_name: str,
    tool_args: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Process a tool call from the OpenAI Realtime API.
    
    Args:
        call_sid: The Twilio call SID
        tool_name: The name of the tool to execute
        tool_args: The arguments for the tool
        
    Returns:
        The result of the tool execution
    """
    logger.info(f"[{call_sid}] Processing tool call: {tool_name}")
    logger.debug(f"[{call_sid}] Tool arguments: {tool_args}")
    
    try:
        # Process the tool call with the agent orchestrator
        result = await async_agent_orchestrator.process_tool_call(
            call_sid, tool_name, tool_args
        )
        
        logger.info(f"[{call_sid}] Tool call result: {result.get('status', 'unknown')}")
        return result
    except Exception as e:
        logger.error(f"[{call_sid}] Error processing tool call: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "error": str(e),
            "result": {},
            "message": f"Failed to execute tool {tool_name}: {str(e)}"
        }

async def register_available_tools(openai_client: Any) -> None:
    """
    Register available tools with the OpenAI Realtime client.
    
    Args:
        openai_client: The OpenAI Realtime client
    """
    # Define available tools for the OpenAI client
    tools = [
        {
            "name": "check_menu_item",
            "description": "Check if a menu item is available and get details",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_name": {
                        "type": "string",
                        "description": "The name of the menu item to check"
                    }
                },
                "required": ["item_name"]
            }
        },
        {
            "name": "add_to_cart",
            "description": "Add an item to the customer's cart",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_name": {
                        "type": "string",
                        "description": "The name of the menu item to add"
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "The quantity to add, defaults to 1"
                    },
                    "modifications": {
                        "type": "array",
                        "description": "List of modifications to apply to the item",
                        "items": {
                            "type": "string"
                        }
                    }
                },
                "required": ["item_name"]
            }
        },
        {
            "name": "get_cart",
            "description": "Get the contents of the customer's cart",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "clear_cart",
            "description": "Clear the customer's cart",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "submit_order",
            "description": "Submit the customer's order",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "The customer's name"
                    },
                    "phone_number": {
                        "type": "string",
                        "description": "The customer's phone number"
                    },
                    "order_type": {
                        "type": "string",
                        "description": "The order type (pickup or delivery)",
                        "enum": ["pickup", "delivery"]
                    }
                },
                "required": ["customer_name", "phone_number", "order_type"]
            }
        }
    ]
    
    # Register the tools with the OpenAI client
    await openai_client.register_tools(tools)
    logger.info(f"Registered {len(tools)} tools with OpenAI client")

async def return_tool_result(
    openai_client: Any,
    tool_call_id: str,
    result: Dict[str, Any]
) -> None:
    """
    Return a tool call result to the OpenAI Realtime API.
    
    Args:
        openai_client: The OpenAI Realtime client
        tool_call_id: The ID of the tool call
        result: The result of the tool execution
    """
    try:
        # Ensure the result is serializable
        result_json = json.dumps(result)
        
        # Return the result to OpenAI
        await openai_client.return_tool_result(tool_call_id, result)
        logger.debug(f"Returned tool result for call ID {tool_call_id}")
    except Exception as e:
        logger.error(f"Error returning tool result: {str(e)}")
        logger.error(traceback.format_exc())