"""
Guardrail Agent for RedBarSushiAI.
This module provides the policy enforcement agent that validates and sanitizes inputs and outputs.
"""

import os
import json
import logging
import time
from typing import Dict, List, Any, Optional, Union, Callable
from app.utils.agents_sdk import tool
from app.utils.agents_sdk import Tool

from app.agents.base import BaseAgent
from app.utils.agents_sdk import guardrail
from app.utils.menu_cache_sdk import get_menu_item_by_plu, get_menu_item_availability
from app.utils.conversation_store_sdk import agents_conversation_store

logger = logging.getLogger(__name__)

# Constants for validation
MAX_ORDER_PRICE = 30000  # $300.00
MAX_SINGLE_ITEM_QUANTITY = 20
MAX_SPECIAL_INSTRUCTIONS_LENGTH = 256
PROFANITY_WORDS = ["fuck", "shit", "ass", "damn"]  # Basic list, would be more comprehensive in production

class GuardrailAgent(BaseAgent):
    """
    Guardrail Agent that enforces business rules and validates interactions.
    Acts as a central policy enforcement point for all agent interactions.
    """
    
    def __init__(
        self,
        name: str = "Guardrail Agent",
        model: str = "gpt-4.1-mini",
        agent_id: Optional[str] = None
    ):
        """Initialize the Guardrail Agent."""
        
        instructions = """
        You are a policy enforcement agent for Red Bar Sushi restaurant's voice ordering system.
        Your primary responsibilities are:
        
        1. Validate inputs and outputs from other agents
        2. Enforce business rules and constraints
        3. Sanitize user inputs to remove inappropriate content
        4. Prevent order total exceeding limits
        5. Verify menu item availability
        6. Ensure modifier selection is valid
        7. Protect against abuse or exploitation
        
        GUARDRAIL PRINCIPLES:
        - Preventative: Block invalid actions before they occur
        - Informative: Provide clear error messages explaining policy violations
        - Progressive: Use retry logic for recoverable errors, but escalate when needed
        - Consistent: Apply the same rules regardless of context
        - Protective: Shield customers and business from negative experiences
        
        VALIDATION RULES:
        - Order totals cannot exceed $300
        - Individual item quantities cannot exceed 20
        - Menu items marked as unavailable cannot be ordered
        - Modifier selections must respect min/max constraints
        - Special instructions cannot contain profanity
        - Delivery addresses must be valid and within delivery radius
        - Order updates can only be done before final submission
        
        You will primarily be called by other agents to validate their actions.
        You should use your tools to check validity and return clear pass/fail results.
        """
        
        # Define the tools this agent can use
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "validate_menu_item",
                    "description": "Validate that a menu item exists and is available",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "plu": {
                                "type": "string",
                                "description": "The PLU code of the menu item"
                            }
                        },
                        "required": ["plu"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "validate_order_total",
                    "description": "Validate that an order total is within allowed limits",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "total_price_cents": {
                                "type": "integer",
                                "description": "The total price of the order in cents"
                            }
                        },
                        "required": ["total_price_cents"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "validate_item_quantity",
                    "description": "Validate that an item quantity is within allowed limits",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "quantity": {
                                "type": "integer",
                                "description": "The quantity of the menu item"
                            }
                        },
                        "required": ["quantity"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "validate_special_instructions",
                    "description": "Validate that special instructions are appropriate",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "The special instructions text"
                            }
                        },
                        "required": ["text"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "validate_modifier_selection",
                    "description": "Validate that modifier selections satisfy group constraints",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "group_id": {
                                "type": "string",
                                "description": "The ID of the modifier group"
                            },
                            "selected_count": {
                                "type": "integer",
                                "description": "The number of modifiers selected from this group"
                            }
                        },
                        "required": ["group_id", "selected_count"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "validate_delivery_address",
                    "description": "Validate a delivery address is within range",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "address": {
                                "type": "string",
                                "description": "The delivery address"
                            },
                            "city": {
                                "type": "string",
                                "description": "The city"
                            },
                            "zip": {
                                "type": "string",
                                "description": "The ZIP/postal code"
                            }
                        },
                        "required": ["address", "city", "zip"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "validate_cart_update",
                    "description": "Validate that a cart can still be updated",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "call_sid": {
                                "type": "string",
                                "description": "The Twilio call SID"
                            }
                        },
                        "required": ["call_sid"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "validate_phone_number",
                    "description": "Validate that a phone number is properly formatted",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "phone": {
                                "type": "string",
                                "description": "The phone number to validate"
                            }
                        },
                        "required": ["phone"]
                    }
                }
            }
        ]
        
        # Initialize the agent
        super().__init__(
            name=name,
            instructions=instructions,
            model=model,
            description="Policy enforcement agent for Red Bar Sushi",
            tools=tools,
            agent_id=agent_id
        )
    
    @tool
    def validate_menu_item(self, plu: str) -> Dict[str, Any]:
        """
        Validate that a menu item exists and is available.
        
        Args:
            plu: The PLU code of the menu item
            
        Returns:
            Validation result
        """
        logger.info(f"Validating menu item with PLU: {plu}")
        
        try:
            # Get the menu item
            menu_item = get_menu_item_by_plu(plu)
            
            if not menu_item:
                return {
                    "valid": False,
                    "reason": f"Menu item with PLU {plu} not found",
                    "suggestion": "Please check the menu for available items"
                }
            
            # Check if the item is available
            is_available = get_menu_item_availability(plu)
            
            if not is_available:
                return {
                    "valid": False,
                    "reason": f"Menu item {menu_item.get('name', 'Unknown')} is currently unavailable",
                    "suggestion": "Please select another item from the menu"
                }
            
            return {
                "valid": True,
                "item_name": menu_item.get("name", "Unknown"),
                "price_cents": menu_item.get("price", 0)
            }
            
        except Exception as e:
            logger.error(f"Error validating menu item: {str(e)}")
            return {
                "valid": False,
                "reason": "An error occurred while validating the menu item",
                "suggestion": "Please try a different menu item"
            }
    
    @tool
    def validate_order_total(self, total_price_cents: int) -> Dict[str, Any]:
        """
        Validate that an order total is within allowed limits.
        
        Args:
            total_price_cents: The total price of the order in cents
            
        Returns:
            Validation result
        """
        logger.info(f"Validating order total: {total_price_cents} cents")
        
        if not isinstance(total_price_cents, int):
            return {
                "valid": False,
                "reason": "Order total must be a number",
                "suggestion": "Please check the order total"
            }
        
        if total_price_cents <= 0:
            return {
                "valid": False,
                "reason": "Order total must be greater than zero",
                "suggestion": "Please add items to your order"
            }
        
        if total_price_cents > MAX_ORDER_PRICE:
            return {
                "valid": False,
                "reason": f"Order total exceeds the maximum limit of ${MAX_ORDER_PRICE/100:.2f}",
                "suggestion": "Please reduce the quantity or remove items"
            }
        
        return {
            "valid": True,
            "total_price_cents": total_price_cents,
            "formatted_total": f"${total_price_cents/100:.2f}"
        }
    
    @tool
    def validate_item_quantity(self, quantity: int) -> Dict[str, Any]:
        """
        Validate that an item quantity is within allowed limits.
        
        Args:
            quantity: The quantity of the menu item
            
        Returns:
            Validation result
        """
        logger.info(f"Validating item quantity: {quantity}")
        
        if not isinstance(quantity, int):
            return {
                "valid": False,
                "reason": "Quantity must be a number",
                "suggestion": "Please specify a valid quantity"
            }
        
        if quantity <= 0:
            return {
                "valid": False,
                "reason": "Quantity must be greater than zero",
                "suggestion": "Please specify at least 1 item"
            }
        
        if quantity > MAX_SINGLE_ITEM_QUANTITY:
            return {
                "valid": False,
                "reason": f"Quantity exceeds the maximum limit of {MAX_SINGLE_ITEM_QUANTITY}",
                "suggestion": f"Please order no more than {MAX_SINGLE_ITEM_QUANTITY} of this item"
            }
        
        return {
            "valid": True,
            "quantity": quantity
        }
    
    @tool
    def validate_special_instructions(self, text: str) -> Dict[str, Any]:
        """
        Validate that special instructions are appropriate.
        
        Args:
            text: The special instructions text
            
        Returns:
            Validation result
        """
        logger.info(f"Validating special instructions: {text}")
        
        if not text:
            return {
                "valid": True,
                "text": ""
            }
        
        # Check length
        if len(text) > MAX_SPECIAL_INSTRUCTIONS_LENGTH:
            return {
                "valid": False,
                "reason": f"Special instructions exceed the maximum length of {MAX_SPECIAL_INSTRUCTIONS_LENGTH} characters",
                "suggestion": "Please provide shorter instructions"
            }
        
        # Check for profanity (basic implementation - would use a better filter in production)
        text_lower = text.lower()
        for word in PROFANITY_WORDS:
            if word in text_lower:
                return {
                    "valid": False,
                    "reason": "Special instructions contain inappropriate language",
                    "suggestion": "Please use appropriate language for your instructions"
                }
        
        return {
            "valid": True,
            "text": text
        }
    
    @tool
    def validate_modifier_selection(self, group_id: str, selected_count: int) -> Dict[str, Any]:
        """
        Validate that modifier selections satisfy group constraints.
        
        Args:
            group_id: The ID of the modifier group
            selected_count: The number of modifiers selected from this group
            
        Returns:
            Validation result
        """
        logger.info(f"Validating modifier selection for group {group_id}: {selected_count} selected")
        
        # In a real implementation, this would query the database for the modifier group
        # For now, let's use a simple mock
        try:
            # Mock data - in production would query DB
            modifier_groups = {
                "SAUCE": {"name": "Sauce Options", "min": 0, "max": 2},
                "SPICE": {"name": "Spice Level", "min": 0, "max": 1},
                "SIDES": {"name": "Side Options", "min": 0, "max": 3},
                "SIZE": {"name": "Size Options", "min": 1, "max": 1}
            }
            
            # Get the group (or a default if not found)
            group = modifier_groups.get(group_id, {"name": "Unknown Group", "min": 0, "max": 1})
            group_name = group["name"]
            min_selection = group["min"]
            max_selection = group["max"]
            
            # Check minimum requirement
            if selected_count < min_selection:
                return {
                    "valid": False,
                    "reason": f"{group_name} requires at least {min_selection} selection(s)",
                    "suggestion": f"Please select at least {min_selection} option(s)"
                }
            
            # Check maximum constraint
            if selected_count > max_selection:
                return {
                    "valid": False,
                    "reason": f"{group_name} allows at most {max_selection} selection(s)",
                    "suggestion": f"Please select no more than {max_selection} option(s)"
                }
            
            return {
                "valid": True,
                "group_name": group_name,
                "selected_count": selected_count
            }
            
        except Exception as e:
            logger.error(f"Error validating modifier selection: {str(e)}")
            return {
                "valid": False,
                "reason": "An error occurred while validating modifier selection",
                "suggestion": "Please try a different selection"
            }
    
    @tool
    def validate_delivery_address(self, address: str, city: str, zip: str) -> Dict[str, Any]:
        """
        Validate a delivery address is within range.
        
        Args:
            address: The delivery address
            city: The city
            zip: The ZIP/postal code
            
        Returns:
            Validation result
        """
        logger.info(f"Validating delivery address: {address}, {city}, {zip}")
        
        # Check for empty fields
        if not address or not city or not zip:
            return {
                "valid": False,
                "reason": "Address, city, and ZIP code are required for delivery",
                "suggestion": "Please provide complete address information"
            }
        
        # In a real implementation, this would check against a delivery radius or service area
        # For now, let's use a simple mock of accepted ZIP codes
        accepted_zips = ["12345", "12346", "12347", "12348", "12349"]
        delivery_fee_cents = 400  # $4.00
        
        if zip not in accepted_zips:
            return {
                "valid": False,
                "reason": f"We don't deliver to ZIP code {zip}",
                "suggestion": "Please check if pickup is available instead"
            }
        
        # Mock implementation of delivery time estimation
        import random
        delivery_time_minutes = random.randint(35, 60)
        
        return {
            "valid": True,
            "address": address,
            "city": city,
            "zip": zip,
            "delivery_fee_cents": delivery_fee_cents,
            "estimated_delivery_time_minutes": delivery_time_minutes
        }
    
    @tool
    def validate_cart_update(self, call_sid: str) -> Dict[str, Any]:
        """
        Validate that a cart can still be updated.
        
        Args:
            call_sid: The Twilio call SID
            
        Returns:
            Validation result
        """
        logger.info(f"Validating cart update for call {call_sid}")
        
        try:
            # Get the current conversation state
            state = agents_conversation_store.get_state(call_sid)
            
            # Check if the cart is locked (order submitted)
            cart_locked = state.get("cart_locked", False)
            
            if cart_locked:
                return {
                    "valid": False,
                    "reason": "Your order has already been submitted and cannot be modified",
                    "suggestion": "You can place a new order or check your order status"
                }
            
            return {
                "valid": True,
                "state": state.get("state", "unknown")
            }
            
        except Exception as e:
            logger.error(f"Error validating cart update: {str(e)}")
            return {
                "valid": False,
                "reason": "An error occurred while checking your order status",
                "suggestion": "Please try placing a new order"
            }
    
    @tool
    def validate_phone_number(self, phone: str) -> Dict[str, Any]:
        """
        Validate that a phone number is properly formatted.
        
        Args:
            phone: The phone number to validate
            
        Returns:
            Validation result
        """
        logger.info(f"Validating phone number: {phone}")
        
        import re
        
        if not phone:
            return {
                "valid": False,
                "reason": "Phone number is required",
                "suggestion": "Please provide a valid phone number"
            }
        
        # Remove any non-digit characters for consistent formatting
        cleaned_phone = re.sub(r'\D', '', phone)
        
        # Check length (expecting 10 or 11 digits)
        if len(cleaned_phone) < 10:
            return {
                "valid": False,
                "reason": "Phone number is too short",
                "suggestion": "Please provide a complete phone number including area code"
            }
        
        if len(cleaned_phone) > 15:
            return {
                "valid": False,
                "reason": "Phone number is too long",
                "suggestion": "Please provide a standard phone number"
            }
        
        # Format the phone number for display and use
        if len(cleaned_phone) == 10:
            formatted_phone = f"+1{cleaned_phone}"
        elif cleaned_phone.startswith('1') and len(cleaned_phone) == 11:
            formatted_phone = f"+{cleaned_phone}"
        else:
            formatted_phone = f"+{cleaned_phone}"
        
        return {
            "valid": True,
            "original_phone": phone,
            "formatted_phone": formatted_phone
        }
    
    def validate_request(self, call_sid: str, validation_type: str, validation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Central method to validate different types of requests.
        
        Args:
            call_sid: The Twilio call SID
            validation_type: The type of validation to perform
            validation_data: Data to validate
            
        Returns:
            Validation result
        """
        logger.info(f"Validating {validation_type} request for call {call_sid}")
        
        # Store the current call context for tool methods
        self.current_call_sid = call_sid
        
        # Process the validation request based on type
        validation_message = f"Validate this {validation_type}: {json.dumps(validation_data)}"
        
        # Process the message with the agent
        start_time = time.time()
        response_text = self.process_message(call_sid, validation_message)
        duration = time.time() - start_time
        
        logger.info(f"Validation processed in {duration:.2f}s")
        
        # Parse the response
        try:
            # Attempt to parse JSON response
            response = json.loads(response_text)
            return response
        except Exception:
            # If not valid JSON, return the text response with a basic structure
            return {
                "valid": False,
                "reason": "Could not process validation",
                "response": response_text
            }
    
    def apply_guardrails(
        self, 
        func_name: str, 
        check_func: Callable,
        result_processor: Optional[Callable] = None,
        error_message: str = "Validation failed"
    ) -> Callable:
        """
        Create a decorator to apply guardrails to any function.
        
        Args:
            func_name: The name of the function being guarded
            check_func: Function that checks if result is valid
            result_processor: Optional function to process the result
            error_message: Message to return on failure
            
        Returns:
            Decorator function
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                # Call the original function
                result = func(*args, **kwargs)
                
                # Process the result if needed
                processed_result = result
                if result_processor:
                    processed_result = result_processor(result)
                
                # Check if the result is valid
                if check_func(processed_result):
                    return result
                else:
                    logger.warning(f"Guardrail failed for {func_name}: {error_message}")
                    return {
                        "success": False,
                        "message": error_message,
                        "original_result": result
                    }
            
            return wrapper
        
        return decorator