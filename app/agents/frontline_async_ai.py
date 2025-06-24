"""
AI-Enhanced Async Frontline Voice Agent for RedBarSushiAI.

This module provides an AI-powered frontline agent that combines
async operations with intelligent decision-making using OpenAI.
"""

import logging
import json
import re
from typing import Dict, Any, Optional, List, Tuple

from app.agents.base_async import BaseAsyncAgent
from app.agents.ai_mixin import AIIntelligenceMixin
from app.config import settings
from app.utils.response_cache import response_cache
from app.utils.ai_cache import ai_cache

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
        
        # Set agent-specific max tokens
        self._default_max_tokens = settings.FRONTEND_AGENT_MAX_TOKENS
        
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
        
        # AI instructions for the agent - DYNAMIC VERSION
        self.base_instructions = f"""
You are {settings.RESTAURANT_GREETING_NAME} from {settings.RESTAURANT_NAME}, taking phone orders. Be warm, friendly, and efficient.

KEY TASKS:
1. Get customer name ONLY when in GREETING state
2. Take orders accurately when in MAIN_MENU or ORDERING states
3. Use tools to lookup menu items and manage cart
4. Keep responses short (1-2 sentences)

REMEMBER: Be conversational, accurate with menu/prices, use tools for everything.
"""
        
        # We'll update instructions dynamically based on state
        self.instructions = self.base_instructions
        
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
        context: Optional[Dict[str, Any]] = None,
        stream_callback: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Process voice input using AI for intelligent responses.
        
        Args:
            input_text: The voice input to process
            context: Optional context information
            stream_callback: Optional callback for streaming responses
            
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
        
        # Check if customer name is in the context from FSM
        if context.get("customer_name") and not self.context.get("customer_name"):
            logger.critical(f"CUSTOMER NAME FROM FSM: '{context['customer_name']}'")
            self.context["customer_name"] = context["customer_name"]
        
        # Check if FSM state transition occurred
        if context.get("state_transition_occurred") and context.get("fsm_state"):
            logger.critical(f"STATE TRANSITION DETECTED: Updating agent state to {context['fsm_state']}")
            self.conversation_state = context["fsm_state"]
            logger.critical(f"Agent conversation state updated to: {self.conversation_state}")
        
        # Handle first interaction - generate greeting WITHOUT AI for speed
        if context.get("first_interaction") and not input_text:
            logger.info("FIRST INTERACTION DETECTED - Generating fast greeting")
            
            # Use dynamic greeting for instant response
            if settings.RESTAURANT_PHONE_GREETING:
                greeting_text = settings.RESTAURANT_PHONE_GREETING
            else:
                greeting_text = f"Hello! Welcome to {settings.RESTAURANT_NAME}. I'm {settings.RESTAURANT_GREETING_NAME}, and I'll be helping you today. What's your name?"
            
            response = {
                "text": greeting_text,
                "agent": self.name,
                "handled": True,
                "ai_generated": False,
                "actions": []
            }
            
            # Initialize conversation history with greeting
            self.context["conversation_history"] = [{
                "role": "assistant",
                "content": greeting_text
            }]
            
            self.conversation_state = "GREETING"
            logger.info(f"Conversation state set to: {self.conversation_state}")
            logger.info(f"Returning fast greeting: {greeting_text}")
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
            return await self._handle_greeting(input_text, stream_callback)
        elif self.conversation_state == "MAIN_MENU":
            logger.critical("→ Calling _handle_main_menu")
            logger.critical(f"Customer name in context: {self.context.get('customer_name')}")
            return await self._handle_main_menu(input_text, stream_callback)
        elif self.conversation_state == "ORDERING":
            logger.info("→ Calling _handle_ordering")
            return await self._handle_ordering(input_text, stream_callback)
        elif self.conversation_state == "VALIDATION":
            logger.info("→ Calling _handle_validation")
            return await self._handle_validation(input_text, stream_callback)
        elif self.conversation_state == "CONFIRMATION":
            logger.info("→ Calling _handle_confirmation")
            return await self._handle_confirmation(input_text, stream_callback)
        else:
            # For other states, use AI to process
            logger.info(f"→ Using AI for state: {self.conversation_state}")
            # Check if streaming is available and no tools are needed
            if stream_callback and not any(word in input_text.lower() for word in ["add", "order", "menu", "cart"]):
                response = await self.process_with_ai_streaming(input_text, context, use_tools=False, callback=stream_callback)
            else:
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
    
    # _extract_name_with_regex method removed - AI is required for name detection

    # _force_name_tool_call method removed - AI is required for name detection

    async def _handle_greeting(self, input_text: str, stream_callback: Optional[Any] = None) -> Dict[str, Any]:
        """Handle inputs in the greeting state using AI."""
        logger.critical("=" * 60)
        logger.critical(f"_handle_greeting called with input: '{input_text}'")
        logger.critical("=" * 60)
        
        # Try fast name detection first
        fast_response = ai_cache.get_fast_response(input_text, "GREETING")
        if fast_response:
            # Extract name from response
            import re
            name_match = re.search(r"Nice to meet you, ([^!]+)!", fast_response)
            if name_match:
                name = name_match.group(1)
                logger.critical(f"FAST NAME DETECTION: '{name}'")
                logger.critical(f"Stream callback available: {stream_callback is not None}")
                
                # Update context and return fast response
                self.context["customer_name"] = name
                self.conversation_state = "MAIN_MENU"
                
                # If we have a stream callback, use it to send the response
                if stream_callback:
                    logger.critical(f"STREAMING fast name response: {fast_response}")
                    await stream_callback(fast_response, True)
                
                return {
                    "text": fast_response,
                    "agent": self.name,
                    "handled": True,
                    "ai_generated": False,
                    "actions": [{"type": "set_customer_name", "name": name}],
                    "tool_calls": [{
                        "function": {
                            "name": "update_customer_info",
                            "arguments": {"name": name}
                        }
                    }]
                }
        
        # No regex extraction - rely on AI only
        # extracted_name = self._extract_name_with_regex(input_text)
        # if extracted_name:
        #     logger.critical(f"🎯 Regex extracted name: '{extracted_name}'")
        
        context = self.context.copy()
        context["state_guidance"] = f"""
        The customer just responded to your greeting.
        
        CRITICAL: Look for their name in their response: "{input_text}"
        
        If you detect a name, you MUST:
        1. IMMEDIATELY call the update_customer_info tool with {{"name": "detected_name"}}
        2. THEN respond with "Nice to meet you, [name]! How can I help you today?"
        
        Common name patterns to look for:
        - Single word like "Bruce" → extract "Bruce" and call update_customer_info({{"name": "Bruce"}})
        - "My name is Sarah" → extract "Sarah" and call update_customer_info({{"name": "Sarah"}})
        - "I'm John" → extract "John" and call update_customer_info({{"name": "John"}})
        - "This is Mike" → extract "Mike" and call update_customer_info({{"name": "Mike"}})
        - "It's David" → extract "David" and call update_customer_info({{"name": "David"}})
        
        IMPORTANT: Even if the input is just a single word that could be a name, treat it as a name and call the tool!
        
        If you cannot detect a name, politely ask for it again.
        """
        
        logger.critical(f"Calling process_with_ai with greeting context...")
        response = await self.process_with_ai(input_text, context)
        logger.critical(f"AI response for greeting: {json.dumps(response, indent=2)}")
        
        # No fallback - AI is required
        if response.get("text", "").startswith("[FrontlineVoiceAI] Processed:"):
            logger.error("AI failed - OpenAI API is required for name detection")
        
        # Check if AI called update_customer_info tool to set the name
        name_set_by_ai = False
        if response.get("tool_calls"):
            logger.critical(f"Tool calls detected: {len(response.get('tool_calls', []))} calls")
            for tool_call in response["tool_calls"]:
                logger.critical(f"Processing tool call: {json.dumps(tool_call, indent=2)}")
                if tool_call.get("function", {}).get("name") == "update_customer_info":
                    args = tool_call.get("function", {}).get("arguments", {})
                    if isinstance(args, str):
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
                        name_set_by_ai = True
        
        # No fallback - rely on AI only
        # if not name_set_by_ai and extracted_name:
        #     logger.critical(f"🔧 AI missed the name, using regex fallback: '{extracted_name}'")
        #     return await self._force_name_tool_call(extracted_name)
        
        # Add conversation history
        self.context["conversation_history"].append({
            "role": "assistant",
            "content": response.get("text", "")
        })
        
        # Update state from actions
        await self._update_state_from_actions(response.get("actions", []))
        
        # Stream the response if we have a callback and response text
        if stream_callback and response.get("text"):
            logger.critical(f"STREAMING greeting response: {response['text']}")
            await stream_callback(response['text'], True)
        
        return response
    
    async def _handle_main_menu(self, input_text: str, stream_callback: Optional[Any] = None) -> Dict[str, Any]:
        """Handle inputs in the main menu state using AI."""
        logger.critical(f"=== _handle_main_menu START ===")
        logger.critical(f"Input: '{input_text}'")
        logger.critical(f"Customer name: {self.context.get('customer_name')}")
        
        # Check cache first for common patterns
        # TEMPORARILY DISABLED FOR DEBUGGING
        # cached_response = response_cache.get_for_pattern(input_text, "MAIN_MENU")
        # if cached_response:
        #     logger.info(f"Using cached response for main menu")
        #     cached_response["agent"] = self.name
        #     cached_response["handled"] = True
        #     
        #     # If we have a stream callback, send the cached response through it
        #     if stream_callback and cached_response.get("text"):
        #         logger.critical(f"STREAMING cached response: {cached_response['text']}")
        #         await stream_callback(cached_response['text'], True)
        #     
        #     return cached_response
        
        context = self.context.copy()
        
        # If we just transitioned from greeting and got a name, acknowledge it
        if self.context.get("customer_name") and context.get("state_transition_occurred") and not self.context.get("name_acknowledged"):
            context["state_guidance"] = f"""
        You just got the customer's name ({self.context['customer_name']}) and transitioned to the main menu.
        Acknowledge their name warmly and ask how you can help them today.
        IMPORTANT: Use their name {self.context['customer_name']} in your response!
        For example: "Nice to meet you, {self.context['customer_name']}! How can I help you today?"
        """
            
            # Mark that we've acknowledged the name
            self.context["name_acknowledged"] = True
            
            # Try with AI first - use streaming for the greeting acknowledgment
            if stream_callback:
                # Send immediate acknowledgment while processing
                immediate_ack = f"Nice to meet you, {self.context.get('customer_name', '')}!"
                await stream_callback(immediate_ack, False)
                
                # Now get the full response
                response = await self.process_with_ai(input_text, context)
                
                # Send the rest of the response
                remaining_text = response.get("text", "").replace(immediate_ack, "").strip()
                if remaining_text:
                    await stream_callback(remaining_text, True)
            else:
                response = await self.process_with_ai(input_text, context)
            
            # If AI failed, provide a fallback response
            if response.get("text", "").startswith("[FrontlineVoiceAI] Processed:"):
                customer_name = self.context.get("customer_name", "friend")
                response = {
                    "text": f"Nice to meet you, {customer_name}! How can I help you today? Would you like to place an order, or do you have questions about our menu?",
                    "agent": self.name,
                    "handled": True,
                    "actions": []
                }
                logger.info(f"Using fallback main menu response for {customer_name}")
        else:
            context["state_guidance"] = f"""
        CRITICAL CONTEXT: You are in the ORDER TAKING phase. The greeting phase is COMPLETE.
        
        Customer name: {self.context.get('customer_name')} (ALREADY CONFIRMED - DO NOT UPDATE)
        Current task: TAKE FOOD ORDER
        
        User input: "{input_text}"
        
        PRIORITY ACTIONS:
        1. If the input contains ANY food item names → Use add_to_cart tool
        2. If the input asks about menu → Use lookup_menu_item or get_menu_categories
        3. If the input requests human help → Use escalate_to_human
        
        FORBIDDEN ACTIONS:
        - DO NOT use update_customer_info tool unless user explicitly says "my name is actually..." or "please call me..."
        - DO NOT ask for the customer's name again
        - DO NOT interpret food items as potential names
        
        Common food items that are NOT names: California, Philadelphia, Boston, Alaska, Texas, Manhattan, Brooklyn, Virginia, Georgia, etc.
        
        If unsure whether something is a food item or name, ASSUME IT IS A FOOD ITEM in this state.
        """
            response = await self.process_with_ai(input_text, context)
            
            # No fallback - AI is required
            if response.get("text", "").startswith("[FrontlineVoiceAI] Processed:"):
                logger.error("AI failed - OpenAI API is required")
                response = {
                    "text": "I apologize, but I'm having technical difficulties. Please try again later.",
                    "agent": self.name,
                    "handled": True,
                    "actions": []
                }
        
        # Stream the response if we have a callback and response text
        if stream_callback and response.get("text"):
            logger.critical(f"STREAMING main menu response: {response['text']}")
            await stream_callback(response['text'], True)
        
        # Check if we should transition to ordering
        if any(action.get("type") == "cart_updated" for action in response.get("actions", [])):
            self.conversation_state = "ORDERING"
            response["actions"].append({"type": "state_change", "state": "ORDERING"})
        
        return response
    
    async def _handle_ordering(self, input_text: str, stream_callback: Optional[Any] = None) -> Dict[str, Any]:
        """Handle inputs in the ordering state using AI."""
        context = self.context.copy()
        context["state_guidance"] = f"""
        CRITICAL CONTEXT: You are in the ACTIVE ORDERING phase.
        
        Customer: {self.context.get('customer_name')} (name already confirmed)
        Current cart: {self.context.get('order_items', [])}
        
        User input: "{input_text}"
        
        EXPECTED ACTIONS:
        1. Food items mentioned → Use add_to_cart tool immediately
        2. Quantity changes → Update cart accordingly
        3. Menu questions → Use lookup_menu_item
        4. "That's all"/"Done"/"Complete" → Move to order confirmation
        
        NEVER:
        - Update customer name (it's already confirmed as {self.context.get('customer_name')})
        - Treat food items as potential names
        - Ask for customer name again
        
        Focus ONLY on order-related actions.
        """
        
        response = await self.process_with_ai(input_text, context)
        
        # If AI failed, provide ordering fallback
        if response.get("text", "").startswith("[FrontlineVoiceAI] Processed:"):
            text_lower = input_text.lower()
            
            # Check if customer is done ordering
            if any(phrase in text_lower for phrase in ["that's all", "done", "ready", "checkout", "complete", "finished"]):
                response = {
                    "text": "Great! Let me confirm your order. You've ordered: (Order details would be shown here). Is this correct?",
                    "agent": self.name,
                    "handled": True,
                    "actions": []
                }
                self.conversation_state = "VALIDATION"
            else:
                # General ordering response
                response = {
                    "text": "I understand you'd like to add that to your order. In our system, we have California rolls, spicy tuna, salmon, and many other options. Please specify which items you'd like.",
                    "agent": self.name,
                    "handled": True,
                    "actions": []
                }
        
        # Check if order is complete and ready for validation
        elif "ready to checkout" in input_text.lower() or "that's all" in input_text.lower():
            self.conversation_state = "VALIDATION"
            response["actions"] = response.get("actions", [])
            response["actions"].append({"type": "state_change", "state": "VALIDATION"})
        
        # Stream the response if we have a callback and response text
        if stream_callback and response.get("text"):
            logger.critical(f"STREAMING ordering response: {response['text']}")
            await stream_callback(response['text'], True)
        
        return response
    
    async def _handle_validation(self, input_text: str, stream_callback: Optional[Any] = None) -> Dict[str, Any]:
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
    
    async def _handle_confirmation(self, input_text: str, stream_callback: Optional[Any] = None) -> Dict[str, Any]:
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
            # First, update the cart specialist's context with our call_sid
            if hasattr(self.specialists["cart"], "update_context"):
                self.specialists["cart"].update_context({"call_sid": self.context.get("call_sid")})
            
            # First, we need to look up the item to get its PLU
            # The cart agent's add_item_to_cart requires a PLU, not item name
            lookup_result = await self.specialists["cart"].execute_tool(
                "lookup_menu_item",
                {"item_name": item_name}
            )
            
            if lookup_result.get("found"):
                # Now add to cart with the PLU
                result = await self.specialists["cart"].execute_tool(
                    "add_item_to_cart",
                    {
                        "plu": lookup_result.get("plu"),
                        "quantity": quantity,
                        "modifiers": modifiers
                    }
                )
            elif lookup_result.get("needs_disambiguation"):
                # Handle disambiguation - for duplicate items, just pick the first
                logger.info(f"Disambiguation needed for '{item_name}', auto-selecting first match")
                
                # Get the first candidate's PLU from the disambiguation result
                candidates = lookup_result.get("candidates", [])
                if candidates and len(candidates) > 0:
                    # Extract PLU from the first candidate
                    # The candidates don't directly have PLU, so we need to look it up differently
                    # For now, let's do another lookup with the menu specialist
                    if "menu" in self.specialists:
                        menu_lookup = await self.specialists["menu"].execute_tool(
                            "lookup_menu_item",
                            {"item_name": item_name}
                        )
                        if menu_lookup.get("found"):
                            plu = menu_lookup.get("plu")
                        else:
                            # Fallback - shouldn't happen
                            plu = "SUSHI001"
                    else:
                        # No menu specialist available, use fallback
                        plu = "SUSHI001"
                    
                    result = await self.specialists["cart"].execute_tool(
                        "add_item_to_cart",
                        {
                            "plu": plu,
                            "quantity": quantity,
                            "modifiers": modifiers
                        }
                    )
                else:
                    result = {
                        "success": False,
                        "message": f"I couldn't find '{item_name}' on our menu. Could you please check the name?"
                    }
            else:
                # Item not found
                result = {
                    "success": False,
                    "message": f"I couldn't find '{item_name}' on our menu. Could you please check the name?"
                }
            
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
    
    # _get_fallback_response method removed - AI is required
    
    async def _generate_confirmation_prompt(self, cart: Dict[str, Any]) -> str:
        """
        Generate a confirmation prompt for the order.
        
        Args:
            cart: The cart dictionary with items and total price
            
        Returns:
            str: The confirmation prompt
        """
        items = cart.get("items", [])
        total_price = cart.get("total_price", 0)
        
        if not items:
            return "I don't see any items in your order. Would you like to add something?"
        
        # Build order summary
        order_summary = "Let me confirm your order: "
        
        for item in items:
            name = item.get("name", "")
            quantity = item.get("quantity", 1)
            
            if quantity > 1:
                order_summary += f"{quantity} {name}s, "
            else:
                order_summary += f"{quantity} {name}, "
        
        # Remove trailing comma and space
        order_summary = order_summary[:-2]
        
        # Add total price
        order_summary += f". Your total is ${total_price:.2f}. Is this correct?"
        
        return order_summary