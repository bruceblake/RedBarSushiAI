"""
AI-Enhanced Async Frontline Voice Agent for RedBarSushiAI.

This module provides an AI-powered frontline agent that combines
async operations with intelligent decision-making using OpenAI.
"""

import logging
import json
from typing import Dict, Any, Optional, List

from app.agents.base_async import BaseAsyncAgent
from app.agents.ai_mixin import AIIntelligenceMixin
from app.config import settings

logger = logging.getLogger(__name__)

class AsyncFrontlineVoiceAgentAI(BaseAsyncAgent, AIIntelligenceMixin):
    """
    AI-enhanced frontline agent for handling voice interactions.
    
    This agent uses AI for understanding intent and generating responses
    while maintaining compatibility with the async FSM orchestration.
    """
    
    def __init__(self, agent_id: Optional[str] = None):
        """Initialize the AI-enhanced frontline voice agent."""
        BaseAsyncAgent.__init__(self, agent_id=agent_id, name="FrontlineVoiceAI")
        AIIntelligenceMixin.__init__(self)
        
        self.conversation_state = "GREETING"
        self.greeting_done = False
        
        # Context maintained across the conversation
        self.context = {
            "customer_name": None,
            "order_type": None,
            "order_items": [],
            "current_item": None,
            "conversation_history": []
        }
        
        # Available states
        self.states = [
            "GREETING", "MAIN_MENU", "ORDERING", "VALIDATION", 
            "CONFIRMATION", "FULFILLMENT", "COMPLETION", "FOLLOW_UP",
            "ESCALATION"
        ]
        
        # AI instructions for the agent
        self.instructions = """
You are the friendly voice of Red Bar Sushi restaurant, handling phone calls from customers.
Your name is Sarah, and you're here to help customers with their orders and questions.

PERSONALITY:
- Warm, friendly, and professional
- Conversational but efficient
- Enthusiastic about the food
- Patient with customers

PRIMARY RESPONSIBILITIES:
1. Greet customers warmly and get their name
2. Help with menu questions by using your menu knowledge
3. Take accurate orders and handle modifications
4. Provide order summaries and confirm details
5. Handle pickup/delivery preferences
6. Escalate to human staff when needed

CONVERSATION FLOW:
- Start with a warm greeting and ask for their name
- Once you have their name, ask how you can help
- Guide them through ordering or answer their questions
- Be proactive in suggesting popular items or deals
- Confirm order details before finalizing
- End with clear next steps

IMPORTANT RULES:
- Always be accurate about menu items and prices
- Use the tools available to look up menu information
- Never make up menu items or prices
- If unsure, ask for clarification
- Be helpful with dietary restrictions and preferences
- Keep responses concise but friendly (2-3 sentences)

CURRENT CONTEXT:
- Restaurant: Red Bar Sushi
- Specialties: Fresh sushi, sashimi, and Japanese cuisine
- Order types: Pickup and delivery available
- Business hours: 11 AM - 10 PM daily
"""
        
        # Define tools for AI to use
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "lookup_menu_item",
                    "description": "Look up information about a specific menu item",
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
                    "name": "get_menu_categories",
                    "description": "Get list of available menu categories",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "add_to_cart",
                    "description": "Add an item to the customer's order",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_name": {
                                "type": "string",
                                "description": "The name of the menu item"
                            },
                            "quantity": {
                                "type": "integer",
                                "description": "Number of items to add",
                                "default": 1
                            },
                            "modifiers": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of modifiers (e.g., 'spicy', 'no wasabi')"
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
                    "description": "Update customer information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Customer's name"
                            },
                            "phone": {
                                "type": "string",
                                "description": "Customer's phone number"
                            },
                            "order_type": {
                                "type": "string",
                                "enum": ["pickup", "delivery"],
                                "description": "Type of order"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_cart_summary",
                    "description": "Get a summary of the current order",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "confirm_order",
                    "description": "Confirm the order is complete and ready to submit",
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
                    "description": "Transfer to a human staff member",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {
                                "type": "string",
                                "description": "Reason for escalation"
                            }
                        },
                        "required": ["reason"]
                    }
                }
            }
        ]
    
    async def process_voice_input(
        self, 
        input_text: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process voice input using AI for intelligent responses.
        
        Args:
            input_text: The voice input to process
            context: Optional context information
            
        Returns:
            Dict[str, Any]: The agent's response
        """
        context = context or {}
        self.update_context(context)
        
        # Handle first interaction - generate greeting
        if context.get("first_interaction"):
            greeting_context = {
                "conversation_state": "GREETING",
                "state_guidance": "Generate a warm, friendly greeting for Red Bar Sushi. Introduce yourself as Sarah and ask for the customer's name."
            }
            response = await self.process_with_ai("", greeting_context)
            
            # Initialize conversation history with greeting
            self.context["conversation_history"] = [{
                "role": "assistant",
                "content": response.get("text", "")
            }]
            
            self.conversation_state = "GREETING"
            return response
        
        # Add to conversation history
        if input_text:
            self.context["conversation_history"].append({
                "role": "user",
                "content": input_text
            })
        
        # Add current state to context
        context["conversation_state"] = self.conversation_state
        context["customer_name"] = self.context.get("customer_name")
        context["cart_items"] = self.context.get("order_items", [])
        
        logger.info(f"[{self.name}] Processing in state {self.conversation_state}: {input_text}")
        
        # Route to appropriate handler based on state
        if self.conversation_state == "GREETING":
            return await self._handle_greeting(input_text)
        elif self.conversation_state == "MAIN_MENU":
            return await self._handle_main_menu(input_text)
        elif self.conversation_state == "ORDERING":
            return await self._handle_ordering(input_text)
        elif self.conversation_state == "VALIDATION":
            return await self._handle_validation(input_text)
        elif self.conversation_state == "CONFIRMATION":
            return await self._handle_confirmation(input_text)
        else:
            # For other states, use AI to process
            response = await self.process_with_ai(input_text, context)
            
            # Add response to conversation history
            self.context["conversation_history"].append({
                "role": "assistant",
                "content": response.get("text", "")
            })
            
            # Update state based on actions
            await self._update_state_from_actions(response.get("actions", []))
            
            # Keep conversation history limited
            if len(self.context["conversation_history"]) > 20:
                self.context["conversation_history"] = self.context["conversation_history"][-20:]
            
            return response
    
    async def _update_state_from_actions(self, actions: List[Dict[str, Any]]):
        """Update agent state based on actions from AI response."""
        for action in actions:
            action_type = action.get("type")
            
            if action_type == "set_customer_name":
                self.context["customer_name"] = action.get("name")
                if self.conversation_state == "GREETING":
                    self.conversation_state = "MAIN_MENU"
                    
            elif action_type == "cart_updated":
                if self.conversation_state == "MAIN_MENU":
                    self.conversation_state = "ORDERING"
                    
            elif action_type == "order_confirmed":
                if action.get("confirmed"):
                    self.conversation_state = "FULFILLMENT"
                else:
                    self.conversation_state = "ORDERING"
                    
            elif action_type == "escalate_to_human":
                self.conversation_state = "ESCALATION"
    
    async def _handle_greeting(self, input_text: str) -> Dict[str, Any]:
        """Handle inputs in the greeting state using AI."""
        context = self.context.copy()
        context["state_guidance"] = """
        The customer just responded to your greeting. 
        Listen for their name and acknowledge it warmly.
        Then ask how you can help them today.
        
        Extract the customer's name if they provide it.
        Common patterns: "My name is...", "I'm...", "This is...", "Call me..."
        """
        
        response = await self.process_with_ai(input_text, context)
        
        # Try to extract customer name
        name_indicators = ["my name is", "i'm", "i am", "call me", "this is", "it's"]
        transcript = input_text.lower()
        
        for indicator in name_indicators:
            if indicator in transcript:
                start_idx = transcript.find(indicator) + len(indicator)
                name_part = transcript[start_idx:].strip()
                
                # Extract first word as name
                if name_part:
                    words = name_part.split()
                    if words:
                        # Clean up the name
                        name = words[0].strip(".,!?").capitalize()
                        self.context["customer_name"] = name
                        response["actions"].append({
                            "type": "set_customer_name",
                            "name": name
                        })
                        break
        
        # If we have a name, transition to main menu
        if self.context.get("customer_name"):
            self.conversation_state = "MAIN_MENU"
            response["actions"].append({"type": "state_change", "state": "MAIN_MENU"})
        
        return response
    
    async def _handle_main_menu(self, input_text: str) -> Dict[str, Any]:
        """Handle inputs in the main menu state using AI."""
        context = self.context.copy()
        context["state_guidance"] = """
        The customer is in the main menu. They can:
        1. Place an order
        2. Ask about menu items
        3. Request to speak with staff
        
        Listen for their intent and guide them appropriately.
        If they want to order, transition to ordering state.
        """
        
        response = await self.process_with_ai(input_text, context)
        
        # Check if we should transition to ordering
        if any(action.get("type") == "cart_updated" for action in response.get("actions", [])):
            self.conversation_state = "ORDERING"
            response["actions"].append({"type": "state_change", "state": "ORDERING"})
        
        return response
    
    async def _handle_ordering(self, input_text: str) -> Dict[str, Any]:
        """Handle inputs in the ordering state using AI."""
        context = self.context.copy()
        context["state_guidance"] = """
        The customer is ordering. Help them:
        1. Add items to their cart
        2. Modify quantities or items
        3. Answer questions about menu items
        4. Move to checkout when ready
        """
        
        response = await self.process_with_ai(input_text, context)
        
        # Check if order is complete and ready for validation
        if "ready to checkout" in input_text.lower() or "that's all" in input_text.lower():
            self.conversation_state = "VALIDATION"
            response["actions"].append({"type": "state_change", "state": "VALIDATION"})
        
        return response
    
    async def _handle_validation(self, input_text: str) -> Dict[str, Any]:
        """Handle inputs in the validation state using AI."""
        context = self.context.copy()
        context["state_guidance"] = """
        Validate the order and ensure all details are correct.
        Check for any missing information like:
        - Customer contact info
        - Pickup or delivery preference
        - Payment method
        """
        
        response = await self.process_with_ai(input_text, context)
        
        # If validation is complete, move to confirmation
        if self.context.get("customer_phone") and self.context.get("order_type"):
            self.conversation_state = "CONFIRMATION"
            response["actions"].append({"type": "state_change", "state": "CONFIRMATION"})
        
        return response
    
    async def _handle_confirmation(self, input_text: str) -> Dict[str, Any]:
        """Handle inputs in the confirmation state using AI."""
        context = self.context.copy()
        context["state_guidance"] = """
        The customer needs to confirm their order.
        Summarize the order details and total.
        Ask for final confirmation.
        """
        
        response = await self.process_with_ai(input_text, context)
        
        # Check if order is confirmed
        if any(action.get("type") == "order_confirmed" and action.get("confirmed") 
               for action in response.get("actions", [])):
            self.conversation_state = "FULFILLMENT"
            response["actions"].append({"type": "state_change", "state": "FULFILLMENT"})
        
        return response
    
    async def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool and return results.
        
        Args:
            tool_name: Name of the tool to execute
            args: Arguments for the tool
            
        Returns:
            Tool execution results
        """
        logger.info(f"[{self.name}] Executing tool: {tool_name} with args: {args}")
        
        if tool_name == "lookup_menu_item":
            return await self._lookup_menu_item(args.get("item_name", ""))
            
        elif tool_name == "get_menu_categories":
            return await self._get_menu_categories()
            
        elif tool_name == "add_to_cart":
            return await self._add_to_cart(
                args.get("item_name"),
                args.get("quantity", 1),
                args.get("modifiers", [])
            )
            
        elif tool_name == "update_customer_info":
            return await self._update_customer_info(args)
            
        elif tool_name == "get_cart_summary":
            return await self._get_cart_summary()
            
        elif tool_name == "confirm_order":
            return {"confirmed": args.get("confirmed", False)}
            
        elif tool_name == "escalate_to_human":
            return {"escalated": True, "reason": args.get("reason")}
            
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    
    async def _lookup_menu_item(self, item_name: str) -> Dict[str, Any]:
        """Look up menu item information."""
        # Delegate to menu specialist if available
        if "menu" in self.specialists:
            result = await self.specialists["menu"].execute_tool(
                "lookup_menu_item", 
                {"item_name": item_name}
            )
            return result
        
        # Fallback response
        return {
            "found": False,
            "message": "Menu lookup not available"
        }
    
    async def _get_menu_categories(self) -> Dict[str, Any]:
        """Get menu categories."""
        if "menu" in self.specialists:
            result = await self.specialists["menu"].execute_tool(
                "list_categories", 
                {}
            )
            return result
        
        return {"categories": ["Appetizers", "Sushi Rolls", "Sashimi", "Beverages"]}
    
    async def _add_to_cart(
        self, 
        item_name: str, 
        quantity: int, 
        modifiers: List[str]
    ) -> Dict[str, Any]:
        """Add item to cart."""
        # Delegate to cart specialist if available
        if "cart" in self.specialists:
            result = await self.specialists["cart"].execute_tool(
                "add_item",
                {
                    "item_name": item_name,
                    "quantity": quantity,
                    "modifiers": modifiers
                }
            )
            
            # Update local context
            if result.get("success"):
                self.context["order_items"].append({
                    "name": item_name,
                    "quantity": quantity,
                    "modifiers": modifiers
                })
            
            return result
        
        # Fallback - add to local context
        self.context["order_items"].append({
            "name": item_name,
            "quantity": quantity,
            "modifiers": modifiers
        })
        
        return {"success": True, "message": f"Added {quantity}x {item_name}"}
    
    async def _update_customer_info(self, info: Dict[str, Any]) -> Dict[str, Any]:
        """Update customer information."""
        if info.get("name"):
            self.context["customer_name"] = info["name"]
        if info.get("order_type"):
            self.context["order_type"] = info["order_type"]
        
        return {"success": True, "updated": list(info.keys())}
    
    async def _get_cart_summary(self) -> Dict[str, Any]:
        """Get current cart summary."""
        if "cart" in self.specialists:
            return await self.specialists["cart"].execute_tool(
                "get_summary", 
                {}
            )
        
        # Fallback to local context
        items = self.context.get("order_items", [])
        if not items:
            return {"empty": True, "items": [], "total": 0}
        
        return {
            "empty": False,
            "items": items,
            "count": len(items),
            "total": 0  # Would need pricing info
        }