"""
Async frontline voice agent for handling voice interactions.

This module provides an asynchronous frontline agent that serves as the main
entry point for voice interactions, delegating to specialist agents as needed.
"""

import logging
import json
import asyncio
from typing import Dict, Any, Optional, List, Tuple, Union, Callable

from app.agents.base_async import BaseAsyncAgent
from app.config import settings

# Set up logging
logger = logging.getLogger(__name__)

class AsyncFrontlineVoiceAgent(BaseAsyncAgent):
    """
    Async frontline agent for handling voice interactions.
    
    This agent is responsible for handling the initial voice interaction,
    understanding the user's intent, and delegating to specialist agents
    as needed.
    """
    
    def __init__(self, agent_id: Optional[str] = None):
        """
        Initialize the frontline voice agent.
        
        Args:
            agent_id: Optional ID for the agent (used with OpenAI Assistants API)
        """
        super().__init__(agent_id=agent_id, name="FrontlineVoice")
        self.conversation_state = "GREETING"  # Initial state
        self.greeting_done = False
        
        # Voice agent specific context
        self.context = {
            "customer_name": None,
            "order_type": None,  # pickup or delivery
            "order_items": [],
            "current_item": None,
            "current_item_modifiers": [],
            "current_stage": "greeting",
            "is_new_customer": True
        }
        
        # Available states
        self.states = [
            "GREETING", "MAIN_MENU", "ORDERING", "VALIDATION", 
            "CONFIRMATION", "FULFILLMENT", "COMPLETION", "FOLLOW_UP",
            "ESCALATION"
        ]
        
        # Define tools
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_menu_item",
                    "description": "Get information about a menu item",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_name": {
                                "type": "string",
                                "description": "The name of the menu item to look up"
                            }
                        },
                        "required": ["item_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
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
                                "description": "The quantity to add (default: 1)"
                            },
                            "modifiers": {
                                "type": "array",
                                "description": "List of modifiers to apply to the item",
                                "items": {
                                    "type": "string"
                                }
                            }
                        },
                        "required": ["item_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "update_customer_info",
                    "description": "Update information about the customer",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "The customer's name"
                            },
                            "phone": {
                                "type": "string",
                                "description": "The customer's phone number"
                            },
                            "order_type": {
                                "type": "string",
                                "description": "The type of order (pickup or delivery)",
                                "enum": ["pickup", "delivery"]
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "confirm_order",
                    "description": "Confirm the current order for processing",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "confirmed": {
                                "type": "boolean",
                                "description": "Whether the order is confirmed"
                            }
                        },
                        "required": ["confirmed"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "escalate_to_human",
                    "description": "Escalate the conversation to a human staff member",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {
                                "type": "string",
                                "description": "The reason for escalation"
                            }
                        },
                        "required": ["reason"]
                    }
                }
            }
        ]
    
    async def process_voice_input(self, input_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a voice input and generate a response.
        
        This method determines the appropriate handling for the input based on
        the current conversation state and delegates to specialist agents as needed.
        
        Args:
            input_text: The voice input to process
            context: Optional context information
            
        Returns:
            Dict[str, Any]: The agent's response
        """
        context = context or {}
        self.update_context(context)
        
        # Log the input and current state
        logger.info(f"[FrontlineVoice] Processing voice input in state {self.conversation_state}: {input_text}")
        
        # Check if this is the first input (greeting)
        if self.conversation_state == "GREETING" and not self.greeting_done:
            # Handle initial greeting
            response = await self._handle_greeting(input_text)
            self.greeting_done = True
            
            # Transition to main menu state
            self.conversation_state = "MAIN_MENU"
            response["actions"].append({"type": "state_change", "state": self.conversation_state})
            
            return response
            
        # Check for state-specific handling
        if self.conversation_state == "MAIN_MENU":
            return await self._handle_main_menu(input_text)
        elif self.conversation_state == "ORDERING":
            return await self._handle_ordering(input_text)
        elif self.conversation_state == "VALIDATION":
            return await self._handle_validation(input_text)
        elif self.conversation_state == "CONFIRMATION":
            return await self._handle_confirmation(input_text)
        elif self.conversation_state == "FULFILLMENT":
            return await self._handle_fulfillment(input_text)
        elif self.conversation_state == "COMPLETION":
            return await self._handle_completion(input_text)
        elif self.conversation_state == "FOLLOW_UP":
            return await self._handle_follow_up(input_text)
        elif self.conversation_state == "ESCALATION":
            return await self._handle_escalation(input_text)
        else:
            # Unknown state - reset to main menu
            self.conversation_state = "MAIN_MENU"
            return await self._handle_main_menu(input_text)
    
    async def _handle_greeting(self, input_text: str) -> Dict[str, Any]:
        """
        Handle the initial greeting.
        
        Args:
            input_text: The voice input to process
            
        Returns:
            Dict[str, Any]: The agent's response
        """
        # If this is the first interaction, provide a warm greeting
        if not input_text or self.context.get("first_interaction"):
            response = {
                "text": "Hello! Welcome to Red Bar Sushi. I'm here to help you place an order or answer any questions about our menu. May I have your name, please?",
                "agent": self.name,
                "handled": True,
                "actions": []
            }
            self.context["first_interaction"] = False
            return response
        
        # Extract customer name if possible
        customer_name = self._extract_name(input_text)
        
        if customer_name:
            self.context["customer_name"] = customer_name
            # Move to main menu after getting name
            self.conversation_state = "MAIN_MENU"
            
            response = {
                "text": f"Thank you, {customer_name}! What can I help you with today? I can take your order, answer questions about our menu, or help you with pickup or delivery options.",
                "agent": self.name,
                "handled": True,
                "actions": [
                    {"type": "set_customer_name", "name": customer_name},
                    {"type": "state_change", "state": self.conversation_state}
                ]
            }
        else:
            # Couldn't extract name, ask again more clearly
            response = {
                "text": "I'm sorry, I didn't catch your name. Could you please tell me your name?",
                "agent": self.name,
                "handled": True,
                "actions": []
            }
        
        return response
    
    async def _handle_main_menu(self, input_text: str) -> Dict[str, Any]:
        """
        Handle inputs in the main menu state.
        
        Args:
            input_text: The voice input to process
            
        Returns:
            Dict[str, Any]: The agent's response
        """
        # Check for intent to order
        if self._has_order_intent(input_text):
            # Transition to ordering state
            self.conversation_state = "ORDERING"
            
            # Delegate to menu agent for suggestions if needed
            if "menu" in self.specialists and self._has_menu_question(input_text):
                response = await self.delegate_to_specialist("menu", input_text, self.context)
                response["actions"].append({"type": "state_change", "state": self.conversation_state})
                return response
            
            # Delegate to cart agent for order processing
            if "cart" in self.specialists:
                response = await self.delegate_to_specialist("cart", input_text, self.context)
                response["actions"].append({"type": "state_change", "state": self.conversation_state})
                return response
            
            # Fallback if no specialists
            return {
                "text": "I'd be happy to take your order. What would you like today?",
                "agent": self.name,
                "handled": True,
                "actions": [
                    {"type": "state_change", "state": self.conversation_state}
                ]
            }
        
        # Check for menu questions
        if self._has_menu_question(input_text) and "menu" in self.specialists:
            return await self.delegate_to_specialist("menu", input_text, self.context)
        
        # Check for escalation
        if self._has_escalation_intent(input_text) and "escalation" in self.specialists:
            self.conversation_state = "ESCALATION"
            response = await self.delegate_to_specialist("escalation", input_text, self.context)
            response["actions"].append({"type": "state_change", "state": self.conversation_state})
            return response
        
        # Default response
        return {
            "text": "I can help you with our menu, take your order, or connect you with a staff member. What would you like to do?",
            "agent": self.name,
            "handled": True,
            "actions": []
        }
    
    async def _handle_ordering(self, input_text: str) -> Dict[str, Any]:
        """
        Handle inputs in the ordering state.
        
        Args:
            input_text: The voice input to process
            
        Returns:
            Dict[str, Any]: The agent's response
        """
        # Delegate to cart agent
        if "cart" in self.specialists:
            response = await self.delegate_to_specialist("cart", input_text, self.context)
            
            # Check if cart agent indicates order is ready for validation
            if response.get("order_ready_for_validation", False):
                self.conversation_state = "VALIDATION"
                response["actions"].append({"type": "state_change", "state": self.conversation_state})
                
                # If guardrail agent is available, delegate to it
                if "guardrail" in self.specialists:
                    validation_response = await self.delegate_to_specialist("guardrail", "validate_order", self.context)
                    response["validation_result"] = validation_response.get("validation_result", {})
            
            return response
        
        # Fallback if no cart agent
        return {
            "text": "I'd be happy to take your order, but I'm having trouble processing it. Could you please try again?",
            "agent": self.name,
            "handled": True,
            "actions": []
        }
    
    async def _handle_validation(self, input_text: str) -> Dict[str, Any]:
        """
        Handle inputs in the validation state.
        
        Args:
            input_text: The voice input to process
            
        Returns:
            Dict[str, Any]: The agent's response
        """
        # Delegate to guardrail agent
        if "guardrail" in self.specialists:
            response = await self.delegate_to_specialist("guardrail", input_text, self.context)
            
            # Check if validation is complete
            if response.get("validation_complete", False):
                if response.get("validation_passed", False):
                    # Transition to confirmation state
                    self.conversation_state = "CONFIRMATION"
                    response["actions"].append({"type": "state_change", "state": self.conversation_state})
                    
                    # Generate confirmation prompt
                    response["text"] = self._generate_confirmation_prompt()
                else:
                    # Stay in validation state, issues need to be resolved
                    response["text"] = "There are some issues with your order that need to be resolved."
            
            return response
        
        # Fallback if no guardrail agent
        self.conversation_state = "CONFIRMATION"
        return {
            "text": self._generate_confirmation_prompt(),
            "agent": self.name,
            "handled": True,
            "actions": [
                {"type": "state_change", "state": self.conversation_state}
            ]
        }
    
    async def _handle_confirmation(self, input_text: str) -> Dict[str, Any]:
        """
        Handle inputs in the confirmation state.
        
        Args:
            input_text: The voice input to process
            
        Returns:
            Dict[str, Any]: The agent's response
        """
        # Check for confirmation or cancellation
        if self._has_confirmation_intent(input_text):
            # Transition to fulfillment state
            self.conversation_state = "FULFILLMENT"
            
            # Delegate to fulfillment agent if available
            if "fulfillment" in self.specialists:
                response = await self.delegate_to_specialist("fulfillment", "process_order", self.context)
                response["actions"].append({"type": "state_change", "state": self.conversation_state})
                
                # Check if fulfillment is complete
                if response.get("fulfillment_complete", False):
                    self.conversation_state = "COMPLETION"
                    response["actions"].append({"type": "state_change", "state": self.conversation_state})
                
                return response
            
            # Fallback if no fulfillment agent
            return {
                "text": "Thank you for your order! We'll have it ready for you shortly.",
                "agent": self.name,
                "handled": True,
                "actions": [
                    {"type": "state_change", "state": self.conversation_state}
                ]
            }
        elif self._has_cancellation_intent(input_text):
            # Return to ordering state
            self.conversation_state = "ORDERING"
            
            return {
                "text": "No problem. Let's make some changes to your order. What would you like to change?",
                "agent": self.name,
                "handled": True,
                "actions": [
                    {"type": "state_change", "state": self.conversation_state}
                ]
            }
        else:
            # Unclear response, ask for confirmation again
            return {
                "text": "I'm sorry, I didn't catch that. Would you like to confirm your order?",
                "agent": self.name,
                "handled": True,
                "actions": []
            }
    
    async def _handle_fulfillment(self, input_text: str) -> Dict[str, Any]:
        """
        Handle inputs in the fulfillment state.
        
        Args:
            input_text: The voice input to process
            
        Returns:
            Dict[str, Any]: The agent's response
        """
        # Delegate to fulfillment agent
        if "fulfillment" in self.specialists:
            response = await self.delegate_to_specialist("fulfillment", input_text, self.context)
            
            # Check if fulfillment is complete
            if response.get("fulfillment_complete", False):
                self.conversation_state = "COMPLETION"
                response["actions"].append({"type": "state_change", "state": self.conversation_state})
            
            return response
        
        # Fallback if no fulfillment agent
        self.conversation_state = "COMPLETION"
        return {
            "text": "Your order has been processed. Thank you for choosing Red Bar Sushi!",
            "agent": self.name,
            "handled": True,
            "actions": [
                {"type": "state_change", "state": self.conversation_state}
            ]
        }
    
    async def _handle_completion(self, input_text: str) -> Dict[str, Any]:
        """
        Handle inputs in the completion state.
        
        Args:
            input_text: The voice input to process
            
        Returns:
            Dict[str, Any]: The agent's response
        """
        # Check if the customer has more questions
        if self._has_follow_up_intent(input_text):
            self.conversation_state = "FOLLOW_UP"
            return await self._handle_follow_up(input_text)
        
        # Default completion response
        return {
            "text": "Thank you for your order! Your food will be ready shortly. Is there anything else I can help you with?",
            "agent": self.name,
            "handled": True,
            "actions": []
        }
    
    async def _handle_follow_up(self, input_text: str) -> Dict[str, Any]:
        """
        Handle inputs in the follow-up state.
        
        Args:
            input_text: The voice input to process
            
        Returns:
            Dict[str, Any]: The agent's response
        """
        # Check for new order intent
        if self._has_order_intent(input_text):
            # Reset order context and transition to ordering state
            self.context["order_items"] = []
            self.context["current_item"] = None
            self.context["current_item_modifiers"] = []
            self.conversation_state = "ORDERING"
            
            return {
                "text": "I'd be happy to take another order. What would you like?",
                "agent": self.name,
                "handled": True,
                "actions": [
                    {"type": "state_change", "state": self.conversation_state},
                    {"type": "reset_order"}
                ]
            }
        
        # Check for end conversation intent
        if self._has_end_conversation_intent(input_text):
            return {
                "text": "Thank you for choosing Red Bar Sushi! Have a great day!",
                "agent": self.name,
                "handled": True,
                "actions": [
                    {"type": "end_conversation"}
                ]
            }
        
        # Check for menu questions
        if self._has_menu_question(input_text) and "menu" in self.specialists:
            return await self.delegate_to_specialist("menu", input_text, self.context)
        
        # Default follow-up response
        return {
            "text": "Is there anything else I can help you with?",
            "agent": self.name,
            "handled": True,
            "actions": []
        }
    
    async def _handle_escalation(self, input_text: str) -> Dict[str, Any]:
        """
        Handle inputs in the escalation state.
        
        Args:
            input_text: The voice input to process
            
        Returns:
            Dict[str, Any]: The agent's response
        """
        # Delegate to escalation agent
        if "escalation" in self.specialists:
            return await self.delegate_to_specialist("escalation", input_text, self.context)
        
        # Fallback if no escalation agent
        return {
            "text": "I'll connect you with a staff member shortly. Please hold.",
            "agent": self.name,
            "handled": True,
            "actions": [
                {"type": "escalate_to_human"}
            ]
        }
    
    def _extract_name(self, text: str) -> Optional[str]:
        """
        Extract customer name from text.
        
        Args:
            text: Text to extract name from
            
        Returns:
            Optional[str]: Extracted name or None
        """
        import re
        
        # Simple name extraction - a more sophisticated approach would be used in production
        name_indicators = [
            r"my name is\s+(\w+)",
            r"i'm\s+(\w+)",
            r"i am\s+(\w+)",
            r"call me\s+(\w+)",
            r"this is\s+(\w+)",
            r"it's\s+(\w+)",
            r"^(\w+)$"  # Single word response
        ]
        
        text_clean = text.strip()
        
        for pattern in name_indicators:
            match = re.search(pattern, text_clean, re.IGNORECASE)
            if match:
                name = match.group(1)
                # Capitalize first letter
                return name.capitalize()
        
        # If text is just 1-2 words and looks like a name, accept it
        words = text_clean.split()
        if 1 <= len(words) <= 2:
            # Check if it's likely a name (starts with capital letter or all letters)
            first_word = words[0]
            if first_word.isalpha() and len(first_word) > 1:
                return first_word.capitalize()
        
        return None
    
    def _has_order_intent(self, text: str) -> bool:
        """
        Check if text has ordering intent.
        
        Args:
            text: Text to check
            
        Returns:
            bool: True if text has ordering intent
        """
        order_keywords = [
            "order", "place an order", "i'll take", "i will take",
            "give me", "can i get", "can i have", "i'd like to order",
            "i want to order", "let me get", "i'll have"
        ]
        
        text_lower = text.lower()
        
        for keyword in order_keywords:
            if keyword in text_lower:
                return True
                
        return False
    
    def _has_menu_question(self, text: str) -> bool:
        """
        Check if text has menu question.
        
        Args:
            text: Text to check
            
        Returns:
            bool: True if text has menu question
        """
        menu_keywords = [
            "menu", "what do you have", "options", "special", "recommend", 
            "popular", "signature", "dish", "roll", "sushi", "what's good", 
            "what is good"
        ]
        
        text_lower = text.lower()
        
        for keyword in menu_keywords:
            if keyword in text_lower:
                return True
                
        return False
    
    def _has_escalation_intent(self, text: str) -> bool:
        """
        Check if text has escalation intent.
        
        Args:
            text: Text to check
            
        Returns:
            bool: True if text has escalation intent
        """
        escalation_keywords = [
            "human", "person", "staff", "manager", "speak to someone", 
            "speak to a person", "talk to someone", "talk to a human"
        ]
        
        text_lower = text.lower()
        
        for keyword in escalation_keywords:
            if keyword in text_lower:
                return True
                
        return False
    
    def _has_confirmation_intent(self, text: str) -> bool:
        """
        Check if text has confirmation intent.
        
        Args:
            text: Text to check
            
        Returns:
            bool: True if text has confirmation intent
        """
        confirmation_keywords = [
            "yes", "yeah", "yep", "confirm", "sounds good", "correct", 
            "that's right", "that is right", "right", "okay", "ok"
        ]
        
        text_lower = text.lower()
        
        for keyword in confirmation_keywords:
            if keyword in text_lower:
                return True
                
        return False
    
    def _has_cancellation_intent(self, text: str) -> bool:
        """
        Check if text has cancellation intent.
        
        Args:
            text: Text to check
            
        Returns:
            bool: True if text has cancellation intent
        """
        cancellation_keywords = [
            "no", "nope", "cancel", "change", "modify", "wrong", "incorrect", 
            "that's not right", "that is not right", "not right"
        ]
        
        text_lower = text.lower()
        
        for keyword in cancellation_keywords:
            if keyword in text_lower:
                return True
                
        return False
    
    def _has_follow_up_intent(self, text: str) -> bool:
        """
        Check if text has follow-up intent.
        
        Args:
            text: Text to check
            
        Returns:
            bool: True if text has follow-up intent
        """
        follow_up_keywords = [
            "more", "another", "question", "also", "what about", "how about", 
            "what else", "one more"
        ]
        
        text_lower = text.lower()
        
        for keyword in follow_up_keywords:
            if keyword in text_lower:
                return True
                
        return False
    
    def _has_end_conversation_intent(self, text: str) -> bool:
        """
        Check if text has end conversation intent.
        
        Args:
            text: Text to check
            
        Returns:
            bool: True if text has end conversation intent
        """
        end_keywords = [
            "goodbye", "bye", "that's all", "that is all", "nothing else", 
            "thank you", "thanks", "done", "finished", "complete"
        ]
        
        text_lower = text.lower()
        
        for keyword in end_keywords:
            if keyword in text_lower:
                return True
                
        return False
    
    def _generate_confirmation_prompt(self) -> str:
        """
        Generate a confirmation prompt for the current order.
        
        Returns:
            str: Confirmation prompt text
        """
        order_items = self.context.get("order_items", [])
        
        if not order_items:
            return "You don't have any items in your order. Would you like to add something?"
        
        # Build confirmation text
        confirmation_text = "Here's your order: "
        
        for item in order_items:
            item_text = f"{item.get('quantity', 1)} {item.get('name', 'Unknown Item')}"
            
            # Add modifiers if any
            modifiers = item.get("modifiers", [])
            if modifiers:
                modifier_text = ", ".join(modifiers)
                item_text += f" with {modifier_text}"
                
            confirmation_text += item_text + ". "
            
        confirmation_text += "Would you like to confirm your order?"
        
        return confirmation_text
    
    async def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool owned by this agent.
        
        Args:
            tool_name: The name of the tool to execute
            args: Arguments for the tool
            
        Returns:
            Dict[str, Any]: The tool's result
        """
        if tool_name == "get_menu_item":
            # Delegate to menu agent if available
            if "menu" in self.specialists:
                return await self.specialists["menu"].execute_tool(tool_name, args)
            else:
                return {"status": "error", "message": "Menu agent not available"}
                
        elif tool_name == "add_to_cart":
            # Delegate to cart agent if available
            if "cart" in self.specialists:
                return await self.specialists["cart"].execute_tool(tool_name, args)
            else:
                return {"status": "error", "message": "Cart agent not available"}
                
        elif tool_name == "update_customer_info":
            # Update customer info in context
            if "name" in args:
                self.context["customer_name"] = args["name"]
                
            if "phone" in args:
                self.context["customer_phone"] = args["phone"]
                
            if "order_type" in args:
                self.context["order_type"] = args["order_type"]
                
            return {
                "status": "success",
                "message": "Customer info updated",
                "updated_fields": list(args.keys())
            }
            
        elif tool_name == "confirm_order":
            # Confirm order and transition to fulfillment
            if args.get("confirmed", False):
                self.conversation_state = "FULFILLMENT"
                
                # Delegate to fulfillment agent if available
                if "fulfillment" in self.specialists:
                    result = await self.specialists["fulfillment"].execute_tool("process_order", {})
                    return {
                        "status": "success",
                        "message": "Order confirmed and processing",
                        "fulfillment_result": result
                    }
                else:
                    return {
                        "status": "success",
                        "message": "Order confirmed",
                        "warning": "Fulfillment agent not available"
                    }
            else:
                return {
                    "status": "error",
                    "message": "Order not confirmed"
                }
                
        elif tool_name == "escalate_to_human":
            # Escalate to human staff
            self.conversation_state = "ESCALATION"
            
            # Delegate to escalation agent if available
            if "escalation" in self.specialists:
                return await self.specialists["escalation"].execute_tool("escalate", args)
            else:
                return {
                    "status": "success",
                    "message": "Escalation requested",
                    "warning": "Escalation agent not available"
                }
                
        else:
            return {
                "status": "error",
                "message": f"Tool '{tool_name}' not implemented"
            }
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get the tools supported by this agent.
        
        Returns:
            List[Dict[str, Any]]: List of tool definitions
        """
        return self.tools