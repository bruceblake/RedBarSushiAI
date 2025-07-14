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
from app.fsm.core import ConversationHSMStates, ConversationHSMEvents
from app.utils.json_utils import safe_json_dumps

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
        
        # AI instructions for the agent - INTELLIGENT VERSION
        self.base_instructions = f"""
You are {settings.RESTAURANT_GREETING_NAME} from {settings.RESTAURANT_NAME}, taking phone orders. Be warm, friendly, and efficient.

CORE INTELLIGENCE PRINCIPLE:
You are an intelligent AI agent. Use your intelligence to understand customer intent and always use the appropriate tools to fulfill their requests. There are NO hardcoded rules or keyword matching - rely on your AI intelligence to determine when and how to use tools.

TOOL USAGE PHILOSOPHY:
- ALWAYS use tools when dealing with menu items, cart operations, or order management
- Use your intelligence to determine customer intent - don't rely on specific phrases
- If a customer wants to know about menu items, use ask_menu_specialist tool
- If a customer wants to order something, use add_to_cart tool (optimized for fast resolution)
- If a customer seems done ordering, use proceed_to_checkout tool
- If a customer asks about their order, use view_cart tool

CRITICAL RULE: ALWAYS complete actions immediately. NEVER say "let me check" or "one moment" - just do it and provide the answer.

INTELLIGENCE PATTERN: When customers ask about food/menu items:
1. Use your intelligence to determine what they want to know
2. Use the appropriate tools to get that information immediately
3. Provide the complete answer in your response - never leave actions incomplete

TOOL USAGE REQUIREMENTS:
1. Use AI intelligence to determine which tool is needed for each request
2. Call tools immediately when information is requested
3. ALWAYS provide the full information in your response - never defer or promise to check later
4. Complete ALL actions in a single response
5. If you need multiple tools, call them all in the same response

FORBIDDEN BEHAVIORS:
- Never say "let me check" or "one moment please" 
- Never promise future actions
- Never provide incomplete responses
- Never defer tool usage to future responses

CONVERSATION FLOW:
1. Get customer name when greeting (GREETING state) - use update_customer_info tool immediately
2. Help with menu questions and ordering (MAIN_MENU/ORDERING states)  
3. Keep responses conversational but efficient (1-2 sentences)
4. Always use tools - never give responses without checking data first
5. Complete all promised actions in the same response

NAME RECOGNITION: When customer provides their name (in any state), immediately call update_customer_info tool with their name.

REMEMBER: You are an intelligent agent, not a rule-following bot. Use your AI capabilities to understand intent and always use appropriate tools to provide accurate, real-time information from our database.
"""
        
        # We'll update instructions dynamically based on state
        self.instructions = self.base_instructions
        
        # Define tools for AI to use
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "ask_menu_specialist",
                    "description": "Ask the menu specialist about menu items, categories, or any menu-related questions",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "The menu question to ask the specialist"
                            }
                        },
                        "required": ["question"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "add_to_cart",
                    "description": "Add an item to the customer's cart using optimized direct menu resolution. This tool efficiently resolves the item name to PLU via Menu Agent, then adds to cart.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_name": {
                                "type": "string",
                                "description": "Name of the item to add"
                            },
                            "quantity": {
                                "type": "integer",
                                "description": "Quantity to add",
                                "default": 1
                            },
                            "modifiers": {
                                "type": "array",
                                "description": "A list of special requests or customizations for the item",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["item_name", "quantity"]
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
                    "name": "proceed_to_checkout",
                    "description": "Proceed to checkout when customer is done ordering",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ready_for_checkout": {
                                "type": "boolean",
                                "description": "Whether the customer is ready for checkout"
                            }
                        },
                        "required": ["ready_for_checkout"]
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
        logger.critical(f"Context received: {safe_json_dumps(context, indent=2)}")
        logger.critical(f"Current agent conversation state: {self.conversation_state}")
        logger.critical("★" * 80)
        
        context = context or {}
        self.update_context(context)
        
        # Check if customer name is in the context from FSM
        if context.get("customer_name") and not self.context.get("customer_name"):
            logger.critical(f"CUSTOMER NAME FROM FSM: '{context['customer_name']}'")
            self.context["customer_name"] = context["customer_name"]
        
        # Check if FSM state transition occurred
        if context.get("state_transition_occurred") and context.get("hsm_state"):
            logger.critical(f"STATE TRANSITION DETECTED: Updating agent state to {context['hsm_state']}")
            self.conversation_state = context["hsm_state"]
            logger.critical(f"Agent conversation state updated to: {self.conversation_state}")
        
        # Handle first interaction - generate greeting WITHOUT AI for speed
        if context.get("first_interaction") and not input_text:
            logger.info("FIRST INTERACTION DETECTED - Generating fast greeting")
            
            # Use dynamic greeting for instant response
            # Use AI to generate personalized greeting based on restaurant config
            greeting_context = {
                "restaurant_name": settings.RESTAURANT_NAME,
                "assistant_name": settings.RESTAURANT_GREETING_NAME,
                "conversation_state": "GREETING",
                "custom_greeting": settings.RESTAURANT_PHONE_GREETING if settings.RESTAURANT_PHONE_GREETING else None
            }
            
            response = await self.process_with_ai("Generate initial greeting", greeting_context)
            response["ai_generated"] = True  # Ensure it's marked as AI-generated
            
            # Get the AI-generated greeting text
            greeting_text = response.get("text", "Hello! Welcome to our restaurant.")
            
            # Initialize conversation history with greeting
            self.context["conversation_history"] = [{
                "role": "assistant",
                "content": greeting_text
            }]
            
            self.conversation_state = "GREETING"
            logger.info(f"Conversation state set to: {self.conversation_state}")
            logger.info(f"Returning AI-generated greeting: {greeting_text}")
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
        logger.info(f"  - Full context: {safe_json_dumps(context, indent=2)}")
        
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
            # ALWAYS use AI with tools - no hardcoded fallbacks
            response = await self.process_with_ai(input_text, context)
            logger.info(f"AI response: {safe_json_dumps(response, indent=2)}")
            
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
            logger.info(f"Processing action: {safe_json_dumps(action, indent=2)}")
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
        2. THEN respond with a personalized AI-generated greeting using the customer's name
        
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
        logger.critical(f"AI response for greeting: {safe_json_dumps(response, indent=2)}")
        
        # No fallback - AI is required
        if response.get("text", "").startswith("[FrontlineVoiceAI] Processed:"):
            logger.error("AI failed - OpenAI API is required for name detection")
        
        # Check if AI called update_customer_info tool to set the name
        name_set_by_ai = False
        if response.get("tool_calls"):
            logger.critical(f"Tool calls detected: {len(response.get('tool_calls', []))} calls")
            for tool_call in response["tool_calls"]:
                logger.critical(f"Processing tool call: {safe_json_dumps(tool_call, indent=2)}")
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
        # Add conversation history to the context for AI processing
        context["conversation_history"] = self.context.get("conversation_history", [])
        
        # Skip the name acknowledgment logic - it's causing cached responses
        # The name acknowledgment should happen in the greeting phase, not main menu
        # Just set the flag to prevent future acknowledgments
        if self.context.get("customer_name") and not self.context.get("name_acknowledged"):
            self.context["name_acknowledged"] = True
        
        # Process all main menu inputs the same way
        context["state_guidance"] = f"""
        You are in the MAIN MENU phase. Use AI intelligence to understand what the customer wants and respond appropriately.
        
        Customer name: {self.context.get('customer_name')}
        
        Use your tools intelligently based on customer requests:
        - For menu questions: Use appropriate menu tools immediately
        - For ordering: Use add_to_cart tool immediately  
        - For customer info updates: Use update_customer_info tool immediately
        - For other requests: Use appropriate tools as needed
        
        ALWAYS complete requested actions immediately with tools - never defer or promise to check later.
        """
        response = await self.process_with_ai(input_text, context)
        
        # No fallback - AI is required
        if response.get("text", "").startswith("[FrontlineVoiceAI] Processed:"):
            logger.error("AI failed - OpenAI API is required")
            raise Exception("AI processing failed - system requires AI intelligence to function")
        
        # Stream the response if we have a callback and response text
        if stream_callback and response.get("text"):
            logger.critical(f"STREAMING main menu response: {response['text']}")
            await stream_callback(response['text'], True)
        
        # Add AI response to conversation history
        if response.get("text"):
            self.context["conversation_history"].append({
                "role": "assistant",
                "content": response.get("text", "")
            })
        
        # Check if we should transition to ordering
        if any(action.get("type") == "cart_updated" for action in response.get("actions", [])):
            self.conversation_state = "ORDERING"
            response["actions"].append({"type": "state_change", "state": "ORDERING"})
        
        return response
    
    async def _handle_ordering(self, input_text: str, stream_callback: Optional[Any] = None) -> Dict[str, Any]:
        """Handle inputs in the ordering state using AI."""
        context = self.context.copy()
        # Use AI to detect if user is indicating order completion - COMPLETELY DYNAMIC
        completion_check_context = {
            "conversation_state": "ORDERING", 
            "customer_name": self.context.get('customer_name'),
            "cart_items": self.context.get('order_items', []),
            "conversation_history": self.context.get("conversation_history", [])
        }
        
        completion_intent = await self.understand_intent(input_text, completion_check_context)
        logger.critical(f"Completion intent check: {completion_intent}")
        
        # Use ONLY AI intelligence to determine completion - no hardcoded phrases
        if completion_intent.get("intent") == "complete_order" and completion_intent.get("confidence", 0) > 0.6:
            # Customer wants to complete their order
            if len(self.context.get('order_items', [])) > 0:
                # The AI's job is to ask for confirmation, NOT to change the state directly.
                # The state will change to CONFIRMATION on the *next* user input (e.g., "yes, that's correct").
                try:
                    # Get cart data from multiple sources for confirmation
                    cart_data = None
                    
                    # Try cart specialist first
                    if "cart" in self.specialists:
                        cart_result = await self.specialists["cart"].execute_tool("get_cart_summary", {})
                        if cart_result.get("success"):
                            cart_data = cart_result
                    
                    # Fallback to context data
                    if not cart_data:
                        cart_items = self.context.get('order_items', [])
                        if cart_items:
                            cart_data = {
                                "success": True,
                                "items": cart_items,
                                "total_price": sum(item.get('price', 0) * item.get('quantity', 1) for item in cart_items)
                            }
                    
                    # Generate cart summary for confirmation
                    if cart_data and cart_data.get("success") and cart_data.get("items"):
                        # Get simple cart summary
                        items = cart_data.get("items", [])
                        total = cart_data.get("total_price", 0)
                        
                        if items:
                            item_list = []
                            for item in items:
                                name = item.get("name", "Unknown item")
                                quantity = item.get("quantity", 1)
                                if quantity > 1:
                                    item_list.append(f"{quantity} {name}")
                                else:
                                    item_list.append(name)
                            
                            cart_summary = ", ".join(item_list)
                            confirmation_text = f"Okay, I have: {cart_summary}. Does that sound right before we finalize everything?"
                        else:
                            confirmation_text = "It looks like there's nothing in your cart yet. What can I get started for you?"
                    else:
                        confirmation_text = "Let me confirm your order. What items did you want to order?"
                        
                except Exception as e:
                    logger.error(f"Error generating confirmation: {e}")
                    confirmation_text = "Let me confirm your order. Does everything sound correct?"

                response = {
                    "text": confirmation_text,
                    "agent": self.name,
                    "handled": True,
                    # No state change action here. We wait for the user's reply.
                    "actions": [] 
                }
            else:
                # This part can remain the same
                response = {
                    "text": "It looks like there's nothing in your cart yet. What can I get started for you?",
                    "agent": self.name,
                    "handled": True,
                    "actions": []
                }
            
            return response
        
        # Check for item modification intent before AI processing
        modification_intent = await self.understand_intent(input_text, context)
        if modification_intent.get("intent") == "modify_order" and modification_intent.get("confidence", 0) > 0.7:
            logger.info("Detected item modification intent")
            self.conversation_state = ConversationHSMStates.ORDERING_ITEM_MODIFICATION
            return await self._handle_item_modification()
        
        # Add conversation history to the context for AI processing
        context["conversation_history"] = self.context.get("conversation_history", [])
        context["state_guidance"] = f"""
        ORDERING MODE - Customer: {self.context.get('customer_name')}

        Current cart: {len(self.context.get('order_items', []))} items
        Last input: "{input_text}"

        MANDATORY TOOL USAGE FOR ORDERS:
        - If customer mentions ANY food item for ordering, you MUST use add_to_cart tool
        - ALWAYS use exact item names and quantities from customer's request
        - NEVER respond with "I've added..." without actually using the add_to_cart tool
        - Every order item REQUIRES a tool call

        CRITICAL ORDER COMPLETION DETECTION:
        When in ORDERING state with items in cart, be extremely sensitive to completion signals.
        Users may indicate completion in many ways - your job is to intelligently detect when
        they want to STOP ADDING and move to checkout/confirmation.

        PRIORITY ANALYSIS:
        1. Order completion signals (e.g., "that's all", "done", "finished", "that's it for me")
        2. Additional item requests (e.g., "I also want a Coke") → USE add_to_cart TOOL
        3. Menu questions (asking about available items or categories)
        4. Order modifications (e.g., "remove the fries")

        CAUTION: Phrases like 'one moment', 'hang on', or questions about the menu are NOT completion signals. When in doubt, ask a clarifying question like, "Will there be anything else for you?" before assuming the order is complete.

        Use AI intelligence to determine TRUE intent, but ALWAYS use tools for adding items.
        """
        
        response = await self.process_with_ai(input_text, context)
        
        # --- PHASE 2 ENHANCEMENT: Check for state transitions based on tool results ---
        # Analyze tool results from the AI response for state transitions
        if response.get('tool_results'):
            for tool_result in response['tool_results']:
                tool_name = tool_result.get('tool', '')
                result_data = tool_result.get('result', {})
                
                # Check for out-of-stock items from menu lookup
                if tool_name == 'lookup_menu_item' and result_data.get('found'):
                    item_data = result_data.get('item', {})
                    
                    # Check if item is snoozed/unavailable
                    if item_data.get('snoozed') or not item_data.get('available', True):
                        logger.info(f"Detected out-of-stock item: {item_data.get('name')}")
                        self.context['item_out_of_stock'] = item_data
                        self.conversation_state = ConversationHSMStates.ORDERING_OUT_OF_STOCK
                        return await self._handle_out_of_stock()
                    
                    # Check for required customizations
                    modifier_groups = result_data.get('modifier_groups', [])
                    required_groups = [g for g in modifier_groups if g.get('required', False)]
                    
                    if required_groups:
                        logger.info(f"Detected required customization for: {item_data.get('name')}")
                        self.context['item_pending_customization'] = {
                            'item': item_data,
                            'modifier_groups': modifier_groups,
                            'required_groups': required_groups
                        }
                        self.conversation_state = ConversationHSMStates.ORDERING_ITEM_CUSTOMIZATION
                        return await self._handle_item_customization()
                
                # Check for successful cart additions that might trigger upselling
                elif tool_name == 'add_to_cart' and result_data.get('success'):
                    if self._should_trigger_upsell():
                        logger.info("Triggering upsell suggestion")
                        self.context['recent_cart_addition'] = result_data
                        self.conversation_state = ConversationHSMStates.ORDERING_UPSELL_SUGGESTION
                        return await self._handle_upsell_suggestion()
        
        # NO FALLBACK LOGIC - AI is required for all processing
        # If AI fails, we should handle it gracefully but not with hardcoded patterns
        if response.get("text", "").startswith("[FrontlineVoiceAI] Processed:"):
            # AI failure - return error instead of hardcoded fallback
            response = {
                "text": "I'm having trouble understanding. Could you please rephrase your request?",
                "agent": self.name,
                "handled": False,
                "actions": [],
                "error": "AI processing failed - no hardcoded fallbacks allowed"
            }
        
        # Note: Order completion is now handled at the beginning of this function
        
        # Add AI response to conversation history
        if response.get("text"):
            self.context["conversation_history"].append({
                "role": "assistant",
                "content": response.get("text", "")
            })
        
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
        """Handle inputs in the confirmation state using AI with validation."""
        
        # --- PHASE 3 ENHANCEMENT: Validate order before confirmation ---
        try:
            if "validation" in self.specialists:
                logger.info("Running order validation before confirmation")
                
                # Get current cart for validation
                cart_data = await self._get_cart_summary()
                
                # Validate the complete order
                validation_result = await self.specialists["validation"].execute_tool(
                    "validate_order_for_checkout",
                    {"cart": cart_data}
                )
                
                logger.info(f"Validation result: {validation_result}")
                
                # Check if order is invalid
                if not validation_result.get("is_valid", True):
                    issues = validation_result.get("issues", [])
                    
                    if issues:
                        # Order is INVALID - address the first critical issue
                        first_issue = issues[0]
                        issue_type = first_issue.get("issue_type")
                        
                        logger.warning(f"Order validation failed: {issue_type}")
                        
                        # Handle different types of validation issues
                        if issue_type == "MISSING_REQUIRED_MODIFIER":
                            # Transition to customization to fix the missing modifier
                            self.conversation_state = ConversationHSMStates.ORDERING_ITEM_CUSTOMIZATION
                            
                            # Store context for the customization handler
                            item_plu = first_issue['context']['item_plu']
                            group_plu = first_issue['context']['group_plu']
                            
                            # Get detailed item info for customization
                            if "menu" in self.specialists:
                                item_details = await self.specialists["menu"].execute_tool(
                                    "get_item_details", 
                                    {"item_plu": item_plu}
                                )
                                
                                if item_details.get("found"):
                                    self.context['item_pending_customization'] = {
                                        'item': item_details['item'],
                                        'modifier_groups': item_details['item']['modifier_groups'],
                                        'required_groups': [g for g in item_details['item']['modifier_groups'] if g.get('required', False)]
                                    }
                            
                            # Return the specific remediation prompt
                            return {
                                "text": first_issue.get('remediation_prompt', 'Please complete your order selection.'),
                                "agent": self.name,
                                "handled": True,
                                "actions": [{"type": "state_change", "state": "ORDERING_ITEM_CUSTOMIZATION"}],
                                "validation_issue": first_issue
                            }
                        
                        elif issue_type == "ITEM_UNAVAILABLE":
                            # Transition to out-of-stock handling
                            self.conversation_state = ConversationHSMStates.ORDERING_OUT_OF_STOCK
                            self.context['item_out_of_stock'] = {
                                'name': first_issue.get('item_name'),
                                'plu': first_issue['context']['item_plu']
                            }
                            
                            return await self._handle_out_of_stock()
                        
                        elif issue_type == "TOO_MANY_MODIFIERS":
                            # Handle over-selection
                            return {
                                "text": first_issue.get('remediation_prompt', 'Please adjust your selections.'),
                                "agent": self.name,
                                "handled": True,
                                "actions": [{"type": "state_change", "state": "ORDERING"}],
                                "validation_issue": first_issue
                            }
                        
                        elif issue_type == "EMPTY_CART":
                            # Cart is empty
                            self.conversation_state = ConversationHSMStates.ORDERING
                            return {
                                "text": "It looks like your cart is empty. What would you like to order?",
                                "agent": self.name,
                                "handled": True,
                                "actions": [{"type": "state_change", "state": "ORDERING"}]
                            }
                        
                        else:
                            # Generic validation failure
                            return {
                                "text": first_issue.get('remediation_prompt', 'There seems to be an issue with your order. Let me help you fix it.'),
                                "agent": self.name,
                                "handled": True,
                                "validation_issue": first_issue
                            }
                
                logger.info("Order validation passed - proceeding with confirmation")
            
        except Exception as e:
            logger.error(f"Error during order validation: {e}")
            # Continue with confirmation despite validation error
        
        # --- ORIGINAL CONFIRMATION LOGIC ---
        # If validation passes, proceed with normal confirmation flow
        context = self.context.copy()
        context["state_guidance"] = """
        CONFIRMATION STATE - Final order review and confirmation.
        
        The order has passed validation and is ready for final confirmation.
        
        YOUR TASKS:
        1. Summarize the order details clearly
        2. Include total price if available
        3. Ask for final confirmation ("Is this correct?" or "Shall I place this order?")
        4. Be ready to process their confirmation or handle any last-minute changes
        
        Keep it concise but complete. This is the final checkpoint before order placement.
        """
        
        response = await self.process_with_ai(input_text, context)
        
        # Check if order is confirmed
        if any(action.get("type") == "order_confirmed" and action.get("confirmed") 
               for action in response.get("actions", [])):
            self.conversation_state = ConversationHSMStates.FULFILLMENT
            response["actions"].append({"type": "state_change", "state": "FULFILLMENT"})
            logger.info("Order confirmed and moving to fulfillment")
        
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
        logger.critical(f"Arguments: {safe_json_dumps(args, indent=2)}")
        logger.critical("=" * 60)
        
        if tool_name == "ask_menu_specialist":
            return await self._ask_menu_specialist(args.get("question", ""))
            
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
            
        elif tool_name == "proceed_to_checkout":
            return await self._proceed_to_checkout(args)
            
        elif tool_name == "confirm_order":
            return {"confirmed": args.get("confirmed", False)}
            
        elif tool_name == "escalate_to_human":
            return {"escalated": True, "reason": args.get("reason")}
            
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    
    async def _ask_menu_specialist(self, question: str) -> Dict[str, Any]:
        """Delegate menu questions to the Menu Agent."""
        try:
            # Import menu agent factory here to avoid circular imports
            from app.agents.factory_async import async_agent_factory
            
            # Get a fresh menu agent instance with database session
            menu_agent = await async_agent_factory.get_agent("menu", db=getattr(self, '_db_session', None))
            
            # Let the menu agent handle the question intelligently
            response = await menu_agent.process_with_ai(
                question,
                {"request_type": "menu_inquiry"},
                use_tools=True
            )
            
            # Return the response from the menu specialist
            return {
                "success": True,
                "response": response.get("text", ""),
                "tool_results": response.get("tool_results", [])
            }
            
        except Exception as e:
            logger.error(f"Error asking menu specialist: {e}")
            return {
                "success": False,
                "error": f"Menu specialist unavailable: {str(e)}"
            }
    
    async def _add_to_cart(
        self, 
        item_name: str, 
        quantity: int, 
        modifiers: List[str]
    ) -> Dict[str, Any]:
        """
        Add item to cart using optimized resolve-then-add pattern.
        
        This optimization eliminates the Frontline -> Cart -> Menu delegation chain
        by having Frontline directly resolve the item with Menu Agent first,
        then calling Cart Agent with the validated PLU.
        """
        # Get call_sid from context for cart operations
        call_sid = self.context.get("call_sid")
        
        # OPTIMIZATION: Direct Menu Agent resolution to get PLU
        # This eliminates the Cart -> Menu delegation hop
        if "menu" not in self.specialists:
            return {
                "success": False,
                "error": "Menu specialist not available",
                "item_name": item_name
            }
        
        try:
            # Step 1: Resolve item name to PLU using Menu Agent directly
            logger.debug(f"[{call_sid}] OPTIMIZED: Resolving '{item_name}' directly via Menu Agent")
            
            # Set context for menu agent
            if hasattr(self.specialists["menu"], "set_current_call"):
                self.specialists["menu"].set_current_call(call_sid)
            
            menu_lookup_result = await self.specialists["menu"].execute_tool(
                "lookup_menu_item",
                {"item_name": item_name}
            )
            
            if not menu_lookup_result.get("found", False):
                return {
                    "success": False,
                    "error": f"Item '{item_name}' not found on menu",
                    "item_name": item_name,
                    "suggestion": menu_lookup_result.get("suggestion", "Please try a different item")
                }
            
            # Extract PLU and item details from menu response
            item_data = menu_lookup_result.get("item", {})
            item_plu = item_data.get("plu")
            
            if not item_plu:
                return {
                    "success": False,
                    "error": f"No PLU found for item '{item_name}'",
                    "item_name": item_name
                }
            
            logger.debug(f"[{call_sid}] OPTIMIZED: Resolved '{item_name}' to PLU '{item_plu}'")
            
            # Step 2: Add to cart using validated PLU (direct Cart Agent call)
            if "cart" not in self.specialists:
                return {
                    "success": False,
                    "error": "Cart specialist not available",
                    "item_name": item_name
                }
            
            # Set context for cart agent
            if hasattr(self.specialists["cart"], "set_current_call"):
                self.specialists["cart"].set_current_call(call_sid)
            
            cart_result = await self.specialists["cart"].execute_tool(
                "add_item_to_cart",
                {
                    "plu": item_plu,
                    "quantity": quantity,
                    "modifiers": modifiers,
                    "special_instructions": ""
                }
            )
            
            logger.debug(f"[{call_sid}] OPTIMIZED: Added item to cart - {cart_result}")
            
            return {
                "success": True,
                "item_added": item_data.get("name", item_name),
                "quantity": quantity,
                "plu": item_plu,
                "cart_total": cart_result.get("cart_total", "unknown"),
                "optimization": "direct_resolution"  # Flag to track optimization usage
            }
            
        except Exception as e:
            logger.error(f"[{call_sid}] OPTIMIZED add_to_cart failed: {e}")
            return {
                "success": False,
                "error": f"Failed to add item: {str(e)}",
                "item_name": item_name
            }
    
    async def _update_customer_info(self, info: Dict[str, Any]) -> Dict[str, Any]:
        """Update customer information."""
        logger.critical(f"_update_customer_info called with: {safe_json_dumps(info, indent=2)}")
        
        if info.get("name"):
            self.context["customer_name"] = info["name"]
            logger.critical(f"✓ Customer name updated to: {info['name']}")
            logger.critical(f"Current context after name update: {safe_json_dumps(self.context, indent=2)}")
        if info.get("order_type"):
            self.context["order_type"] = info["order_type"]
            logger.critical(f"✓ Order type updated to: {info['order_type']}")
        
        result = {"success": True, "updated": list(info.keys())}
        logger.critical(f"Update result: {safe_json_dumps(result, indent=2)}")
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
    
    async def _proceed_to_checkout(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Proceed to checkout when customer is done ordering."""
        ready_for_checkout = args.get("ready_for_checkout", False)
        logger.critical(f"_proceed_to_checkout called with ready_for_checkout: {ready_for_checkout}")
        
        if ready_for_checkout:
            # Transition to validation/confirmation state
            self.conversation_state = "VALIDATION"
            logger.critical(f"✓ State changed from {self.conversation_state} to VALIDATION")
            
            return {
                "success": True,
                "message": "Proceeding to checkout",
                "next_state": "VALIDATION",
                "action": "proceed_to_checkout"
            }
        
        return {
            "success": False,
            "message": "Customer not ready for checkout"
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
    
    # ============================================================================
    # PHASE 2 ENHANCEMENT: New State Handler Methods
    # ============================================================================
    
    async def _handle_out_of_stock(self) -> Dict[str, Any]:
        """Handle the conversation when a requested item is unavailable."""
        item = self.context.get('item_out_of_stock', {})
        item_name = item.get('name', 'that item')
        
        logger.info(f"Handling out-of-stock state for: {item_name}")
        
        # Get alternatives from the menu agent
        alternatives = []
        try:
            if "menu" in self.specialists:
                # Get popular items as alternatives
                alternatives_result = await self.specialists["menu"].execute_tool(
                    "get_popular_items", 
                    {"max_results": 3}
                )
                if alternatives_result.get("items"):
                    alternatives = alternatives_result["items"][:2]  # Limit to 2 suggestions
        except Exception as e:
            logger.error(f"Error getting alternatives: {e}")
        
        context = self.context.copy()
        context["state_guidance"] = f"""
        CRITICAL: You are in the OUT_OF_STOCK state.
        The user asked for '{item_name}', which is currently unavailable.
        
        YOUR TASKS:
        1. Politely inform them it's not available right now
        2. Suggest alternatives if available: {[alt.get('name') for alt in alternatives]}
        3. Ask what they would like to do instead
        4. Be empathetic and helpful
        
        Keep it conversational and focus on recovering the conversation smoothly.
        """
        
        # Create input that triggers appropriate response
        ai_input = f"The customer requested {item_name} but it's unavailable. Suggest alternatives and help them choose something else."
        response = await self.process_with_ai(ai_input, context)
        
        # Transition back to ORDERING state
        self.conversation_state = ConversationHSMStates.ORDERING
        self.context.pop('item_out_of_stock', None)  # Clean up context
        
        return response
    
    async def _handle_item_customization(self) -> Dict[str, Any]:
        """Guide the user through selecting required modifiers."""
        pending_item_data = self.context.get('item_pending_customization', {})
        item = pending_item_data.get('item', {})
        required_groups = pending_item_data.get('required_groups', [])
        
        item_name = item.get('name', 'this item')
        
        logger.info(f"Handling item customization for: {item_name}")
        
        if not required_groups:
            # No required customization, proceed normally
            self.conversation_state = ConversationHSMStates.ORDERING
            self.context.pop('item_pending_customization', None)
            return {"text": f"Got it, I'll add {item_name} to your order.", "agent": self.name, "handled": True}
        
        # Get the first required modifier group
        first_group = required_groups[0]
        group_name = first_group.get('name', 'options')
        min_selection = first_group.get('min_selection', 1)
        max_selection = first_group.get('max_selection', 1)
        
        # Get the available modifiers for this group
        modifiers = first_group.get('modifiers', [])
        modifier_names = [mod.get('name') for mod in modifiers if mod.get('available', True)]
        
        context = self.context.copy()
        context["state_guidance"] = f"""
        CRITICAL: You are in the ITEM_CUSTOMIZATION state.
        The user wants to order '{item_name}' but it requires customization.
        
        REQUIRED SELECTION:
        - Group: {group_name}
        - Available options: {modifier_names}
        - Must select: {min_selection} to {max_selection} option(s)
        
        YOUR TASK:
        Ask the user to choose from the available options. Make it clear what they need to select.
        Be friendly and helpful. Example: "For the {item_name}, how would you like your {group_name}? You can choose from {', '.join(modifier_names[:3])}."
        """
        
        ai_input = f"Ask the user to customize {item_name} by selecting {group_name} options."
        response = await self.process_with_ai(ai_input, context)
        
        # Note: We stay in CUSTOMIZATION state until user responds with their choice
        # The transition back will happen when we process their selection
        
        return response
    
    async def _handle_upsell_suggestion(self) -> Dict[str, Any]:
        """Handle proactive upselling opportunities."""
        recent_addition = self.context.get('recent_cart_addition', {})
        
        logger.info("Handling upsell suggestion")
        
        # Get upselling suggestions based on recent addition
        upsell_items = []
        try:
            if "menu" in self.specialists:
                # Get categories to find upsell candidates
                categories_result = await self.specialists["menu"].execute_tool("get_menu_categories", {})
                categories = categories_result.get("categories", [])
                
                # Use AI to intelligently select appropriate upsell category
                if categories:
                    # For now, get popular items from any category as upsell candidates
                    upsell_result = await self.specialists["menu"].execute_tool(
                        "get_popular_items",
                        {"max_results": 2}  # Let AI decide appropriate upsells
                    )
                if upsell_result.get("items"):
                    upsell_items = upsell_result["items"]
        except Exception as e:
            logger.error(f"Error getting upsell items: {e}")
        
        context = self.context.copy()
        context["state_guidance"] = f"""
        CRITICAL: You are in the UPSELL_SUGGESTION state.
        The user just added an item to their cart successfully.
        
        YOUR TASK:
        Make a friendly, natural upselling suggestion. Options:
        - Suggest a complementary item: {[item.get('name') for item in upsell_items]}
        - Offer a combo or meal deal
        - Suggest a popular addition
        
        Keep it brief and natural. Don't be pushy. Use your intelligence to suggest appropriate complementary items based on what's available in our menu.
        """
        
        ai_input = "Make a friendly upselling suggestion based on their recent order."
        response = await self.process_with_ai(ai_input, context)
        
        # Transition back to ORDERING state after the suggestion
        self.conversation_state = ConversationHSMStates.ORDERING
        self.context.pop('recent_cart_addition', None)
        
        return response
    
    async def _handle_item_modification(self) -> Dict[str, Any]:
        """Handle requests to modify items already in the cart."""
        logger.info("Handling item modification request")
        
        # Get current cart summary
        cart_summary = await self._get_cart_summary()
        
        context = self.context.copy()
        context["state_guidance"] = f"""
        CRITICAL: You are in the ITEM_MODIFICATION state.
        The user wants to change something in their existing order.
        
        CURRENT CART: {cart_summary.get('items', [])}
        
        YOUR TASKS:
        1. Understand exactly what they want to change
        2. Use tools to modify the cart as requested
        3. Confirm the change with the user
        4. Ask if there's anything else they need
        
        Be helpful and make sure you understand their request clearly before making changes.
        """
        
        # The AI will process their modification request and potentially call cart tools
        response = await self.process_with_ai("Process the user's order modification request.", context)
        
        # Transition back to ORDERING state
        self.conversation_state = ConversationHSMStates.ORDERING
        
        return response
    
    def _should_trigger_upsell(self) -> bool:
        """
        Determine if an upselling opportunity should be triggered.
        This could be based on business logic, cart contents, or random chance.
        """
        # Simple logic: trigger upsell 30% of the time, but not if cart is already large
        import random
        
        cart_items = self.context.get('order_items', [])
        
        # Don't upsell if cart already has many items
        if len(cart_items) >= 3:
            return False
        
        # Don't upsell too frequently (store in context to track)
        recent_upsells = self.context.get('recent_upsells', 0)
        if recent_upsells >= 1:
            return False
        
        # 30% chance to trigger upsell
        should_upsell = random.random() < 0.3
        
        if should_upsell:
            self.context['recent_upsells'] = recent_upsells + 1
        
        return should_upsell