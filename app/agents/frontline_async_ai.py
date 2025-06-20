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

CRITICAL: TOOL USAGE FOR NAMES
- When a customer provides their name in ANY format (like "My name is John", "I'm Sarah", "John", "This is Mike"), 
  you MUST immediately call the update_customer_info tool with {"name": "their_name"}
- Do not proceed without calling this tool when you detect a name
- After calling the tool, acknowledge their name warmly and transition to helping them

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
        logger.critical("★" * 80)
        logger.critical(f"FRONTLINE AGENT: process_voice_input called")
        logger.critical(f"Input text: '{input_text}'")
        logger.critical(f"Input length: {len(input_text)} chars")
        logger.critical(f"Context received: {json.dumps(context, indent=2)}")
        logger.critical(f"Current agent conversation state: {self.conversation_state}")
        logger.critical("★" * 80)
        
        context = context or {}
        self.update_context(context)
        
        # Check if FSM state transition occurred
        if context.get("state_transition_occurred") and context.get("fsm_state"):
            logger.critical(f"STATE TRANSITION DETECTED: Updating agent state to {context['fsm_state']}")
            self.conversation_state = context["fsm_state"]
            logger.critical(f"Agent conversation state updated to: {self.conversation_state}")
        
        # Handle first interaction - generate greeting
        if context.get("first_interaction"):
            logger.info("FIRST INTERACTION DETECTED - Generating greeting")
            greeting_context = {
                "conversation_state": "GREETING",
                "state_guidance": "Generate a warm, friendly greeting for Red Bar Sushi. Introduce yourself as Sarah and ask for the customer's name."
            }
            logger.info(f"Greeting context: {json.dumps(greeting_context, indent=2)}")
            
            logger.info("Calling process_with_ai for greeting...")
            response = await self.process_with_ai("", greeting_context)
            logger.info(f"AI greeting response: {json.dumps(response, indent=2)}")
            
            # Initialize conversation history with greeting
            self.context["conversation_history"] = [{
                "role": "assistant",
                "content": response.get("text", "")
            }]
            
            self.conversation_state = "GREETING"
            logger.info(f"Conversation state set to: {self.conversation_state}")
            logger.info(f"Returning greeting response: {response.get('text', '')}")
            return response
        
        # Add to conversation history
        if input_text:
            logger.info(f"Adding user input to conversation history: '{input_text}'")
            self.context["conversation_history"].append({
                "role": "user",
                "content": input_text
            })
            logger.info(f"Conversation history length: {len(self.context['conversation_history'])} messages")
        
        # Add current state to context
        context["conversation_state"] = self.conversation_state
        context["customer_name"] = self.context.get("customer_name")
        context["cart_items"] = self.context.get("order_items", [])
        
        logger.info(f"Updated context for processing:")
        logger.info(f"  - Conversation state: {self.conversation_state}")
        logger.info(f"  - Customer name: {context['customer_name']}")
        logger.info(f"  - Cart items: {context['cart_items']}")
        logger.info(f"  - Full context: {json.dumps(context, indent=2)}")
        
        # Route to appropriate handler based on state
        logger.critical(f"Routing to handler for state: {self.conversation_state}")
        if self.conversation_state == "GREETING":
            logger.critical("→ Calling _handle_greeting")
            return await self._handle_greeting(input_text)
        elif self.conversation_state == "MAIN_MENU":
            logger.critical("→ Calling _handle_main_menu")
            logger.critical(f"Customer name in context: {self.context.get('customer_name')}")
            return await self._handle_main_menu(input_text)
        elif self.conversation_state == "ORDERING":
            logger.info("→ Calling _handle_ordering")
            return await self._handle_ordering(input_text)
        elif self.conversation_state == "VALIDATION":
            logger.info("→ Calling _handle_validation")
            return await self._handle_validation(input_text)
        elif self.conversation_state == "CONFIRMATION":
            logger.info("→ Calling _handle_confirmation")
            return await self._handle_confirmation(input_text)
        else:
            # For other states, use AI to process
            logger.info(f"→ Using AI for state: {self.conversation_state}")
            response = await self.process_with_ai(input_text, context)
            logger.info(f"AI response: {json.dumps(response, indent=2)}")
            
            # Add response to conversation history
            self.context["conversation_history"].append({
                "role": "assistant",
                "content": response.get("text", "")
            })
            logger.info(f"Added AI response to conversation history")
            
            # Update state based on actions
            logger.info(f"Updating state based on actions: {response.get('actions', [])}")
            await self._update_state_from_actions(response.get("actions", []))
            
            # Keep conversation history limited
            if len(self.context["conversation_history"]) > 20:
                logger.info(f"Trimming conversation history from {len(self.context['conversation_history'])} to 20 messages")
                self.context["conversation_history"] = self.context["conversation_history"][-20:]
            
            logger.info(f"Final response text: '{response.get('text', '')}'")
            return response
    
    async def _update_state_from_actions(self, actions: List[Dict[str, Any]]):
        """Update agent state based on actions from AI response."""
        logger.info(f"_update_state_from_actions called with {len(actions)} actions")
        for action in actions:
            logger.info(f"Processing action: {json.dumps(action, indent=2)}")
            action_type = action.get("type")
            
            if action_type == "set_customer_name":
                self.context["customer_name"] = action.get("name")
                logger.info(f"Customer name set to: {self.context['customer_name']}")
                if self.conversation_state == "GREETING":
                    self.conversation_state = "MAIN_MENU"
                    logger.info(f"State changed from GREETING to MAIN_MENU")
                    
            elif action_type == "cart_updated":
                logger.info(f"Cart updated action received")
                if self.conversation_state == "MAIN_MENU":
                    self.conversation_state = "ORDERING"
                    logger.info(f"State changed from MAIN_MENU to ORDERING")
                    
            elif action_type == "order_confirmed":
                confirmed = action.get("confirmed")
                logger.info(f"Order confirmed action: confirmed={confirmed}")
                if confirmed:
                    self.conversation_state = "FULFILLMENT"
                    logger.info(f"State changed to FULFILLMENT")
                else:
                    self.conversation_state = "ORDERING"
                    logger.info(f"State changed back to ORDERING")
                    
            elif action_type == "escalate_to_human":
                self.conversation_state = "ESCALATION"
                logger.info(f"State changed to ESCALATION")
    
    async def _handle_greeting(self, input_text: str) -> Dict[str, Any]:
        """Handle inputs in the greeting state using AI."""
        logger.critical("=" * 60)
        logger.critical(f"_handle_greeting called with input: '{input_text}'")
        logger.critical("=" * 60)
        
        context = self.context.copy()
        context["state_guidance"] = """
        The customer just responded to your greeting. 
        
        IMPORTANT: If the customer provides their name in ANY way (like "My name is John", "I'm Sarah", "John", "This is Mike", etc.), 
        you MUST call the update_customer_info tool with their name immediately.
        
        After getting their name, acknowledge it warmly and ask how you can help them today.
        If they don't provide a name, politely ask for it again.
        """
        
        logger.critical(f"Calling process_with_ai with greeting context...")
        response = await self.process_with_ai(input_text, context)
        logger.critical(f"AI response for greeting: {json.dumps(response, indent=2)}")
        
        # Check if AI called update_customer_info tool to set the name
        if response.get("tool_calls"):
            logger.critical(f"Tool calls detected: {len(response.get('tool_calls', []))} calls")
            for tool_call in response["tool_calls"]:
                logger.critical(f"Processing tool call: {json.dumps(tool_call, indent=2)}")
                if tool_call.get("function", {}).get("name") == "update_customer_info":
                    args = tool_call.get("function", {}).get("arguments", {})
                    if isinstance(args, str):
                        import json
                        args = json.loads(args)
                    
                    if args.get("name"):
                        self.context["customer_name"] = args["name"]
                        self.conversation_state = "MAIN_MENU"
                        logger.critical(f"✓ Customer name successfully set to: {args['name']}")
                        logger.critical(f"State changed from GREETING to MAIN_MENU")
                        response["actions"] = response.get("actions", [])
                        response["actions"].append({
                            "type": "set_customer_name", 
                            "name": args["name"]
                        })
                        logger.critical(f"Added set_customer_name action to response")
        
        return response
    
    async def _handle_main_menu(self, input_text: str) -> Dict[str, Any]:
        """Handle inputs in the main menu state using AI."""
        logger.critical(f"=== _handle_main_menu START ===")
        logger.critical(f"Input: '{input_text}'")
        logger.critical(f"Customer name: {self.context.get('customer_name')}")
        
        context = self.context.copy()
        
        # If we just transitioned from greeting and got a name, acknowledge it
        if self.context.get("customer_name") and not input_text:
            context["state_guidance"] = f"""
        You just got the customer's name ({self.context['customer_name']}) and transitioned to the main menu.
        Acknowledge their name warmly and ask how you can help them today.
        For example: "Nice to meet you, {self.context['customer_name']}! How can I help you today?"
        """
        else:
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
        logger.critical("=" * 60)
        logger.critical(f"EXECUTE TOOL: {tool_name}")
        logger.critical(f"Arguments: {json.dumps(args, indent=2)}")
        logger.critical("=" * 60)
        
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
        logger.critical(f"_update_customer_info called with: {json.dumps(info, indent=2)}")
        
        if info.get("name"):
            self.context["customer_name"] = info["name"]
            logger.critical(f"✓ Customer name updated to: {info['name']}")
            logger.critical(f"Current context after name update: {json.dumps(self.context, indent=2)}")
        if info.get("order_type"):
            self.context["order_type"] = info["order_type"]
            logger.critical(f"✓ Order type updated to: {info['order_type']}")
        
        result = {"success": True, "updated": list(info.keys())}
        logger.critical(f"Update result: {json.dumps(result, indent=2)}")
        return result
    
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