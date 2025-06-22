"""
AI Intelligence Mixin for Async Agents.

This mixin adds AI capabilities to async agents while maintaining
their async nature and integration with the FSM orchestration.
"""

import json
import logging
import openai
import time
import asyncio
from typing import Dict, Any, List, Optional
from app.config import settings
from app.utils.openai_pool import get_openai_client
from app.utils.ai_cache import ai_cache

logger = logging.getLogger(__name__)

class AIIntelligenceMixin:
    """
    Mixin to add AI intelligence to async agents.
    
    This mixin provides methods to use OpenAI's API for intelligent
    decision-making while maintaining async patterns.
    """
    
    def __init__(self):
        """Initialize the AI client."""
        self._ai_client = None
        self._ai_enabled = True
        self._model = "gpt-4o-mini"  # Fast and intelligent model
        
    async def _get_ai_client(self):
        """Get AI client from connection pool."""
        if self._ai_client is None:
            self._ai_client = await get_openai_client()
        return self._ai_client
    
    async def process_with_ai(
        self, 
        input_text: str, 
        context: Dict[str, Any],
        use_tools: bool = True,
        fast_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Process input using AI for intelligent understanding and response.
        
        Args:
            input_text: The user's input text
            context: Conversation context
            use_tools: Whether to enable tool calling
            
        Returns:
            Response dictionary with text and metadata
        """
        if not self._ai_enabled:
            # Return simple response - no fallback
            return {
                "text": "AI is not enabled.",
                "agent": getattr(self, 'name', 'AI'),
                "handled": True,
                "actions": []
            }
        
        try:
            # Check cache first
            state = context.get("conversation_state", "")
            cached_response = await ai_cache.get(input_text, state, context)
            if cached_response:
                logger.debug(f"Using cached AI response for: {input_text[:30]}...")
                cached_response["agent"] = getattr(self, 'name', 'AI')
                cached_response["handled"] = True
                cached_response["ai_generated"] = True
                cached_response["from_cache"] = True
                return cached_response
            # Build conversation history
            messages = self._build_messages(input_text, context)
            
            # Prepare API call parameters
            params = {
                "model": self._model,
                "messages": messages,
                "temperature": 0.0,  # Zero for fastest, most deterministic responses
                "max_tokens": 50,     # Minimal tokens for speed
                "stream": False       # Ensure not streaming
            }
            
            # Add tools if available and enabled
            if use_tools and hasattr(self, 'tools') and self.tools:
                params["tools"] = self.tools
                params["tool_choice"] = "auto"
            
            # Make AI API call (reduced logging for speed)
            logger.debug(f"AI call: {params['model']}, {len(params['messages'])} msgs")
            
            client = await self._get_ai_client()
            
            # Track timing with timeout
            start_time = time.time()
            try:
                # Add timeout to prevent hanging
                response = await asyncio.wait_for(
                    client.chat.completions.create(**params),
                    timeout=3.0  # 3 second timeout
                )
                duration = time.time() - start_time
                
                if duration > 2.0:
                    logger.warning(f"Slow AI response: {duration:.2f}s for {self.name}")
                else:
                    logger.debug(f"AI response time: {duration:.2f}s")
            except asyncio.TimeoutError:
                logger.error(f"AI request timed out after 3s for {self.name}")
                # Return fast fallback
                return {
                    "text": "I understand. Let me help you with that.",
                    "agent": getattr(self, 'name', 'AI'),
                    "handled": True,
                    "actions": [],
                    "timeout": True
                }
            
            # Process the response
            result = await self._process_ai_response(response, context)
            
            # Cache the result for future use
            if result.get("text") and not result.get("error"):
                await ai_cache.set(input_text, state, context, result)
            
            return result
            
        except Exception as e:
            logger.error(f"AI processing error in {self.name}: {e}", exc_info=True)
            # Return a fallback response instead of trying to call non-existent method
            return {
                "text": f"[{getattr(self, 'name', 'AI')}] Processed: {input_text}",
                "agent": getattr(self, 'name', 'AI'),
                "handled": True,
                "actions": []
            }
    
    def _build_messages(self, input_text: str, context: Dict[str, Any]) -> List[Dict[str, str]]:
        """Build message history for AI context - OPTIMIZED for speed."""
        messages = []
        
        # Combine all system context into ONE message for efficiency
        system_parts = []
        
        # Base instructions
        if hasattr(self, 'instructions'):
            system_parts.append(self.instructions)
        else:
            from app.config import settings
            system_parts.append(f"You are {getattr(self, 'name', 'an AI assistant')} for {settings.RESTAURANT_NAME}. Be concise and natural.")
        
        # Add essential context only
        if context.get("customer_name"):
            system_parts.append(f"Customer: {context['customer_name']}")
        
        if context.get("cart_items"):
            cart_summary = self._summarize_cart(context["cart_items"])
            system_parts.append(f"Cart: {cart_summary}")
        
        # Single system message
        messages.append({"role": "system", "content": "\n".join(system_parts)})
        
        # Add only last 2 messages for context (not 5)
        if context.get("conversation_history"):
            for msg in context["conversation_history"][-2:]:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
        
        # Add the current user input
        messages.append({"role": "user", "content": input_text})
        
        return messages
    
    async def _process_ai_response(
        self, 
        response: Any, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process the AI API response."""
        message = response.choices[0].message
        
        # Log response quietly
        content_preview = message.content[:50] if message.content else "None"
        logger.debug(f"AI response: {content_preview}... Tools: {bool(getattr(message, 'tool_calls', None))}")
        
        # Handle tool calls if present
        if hasattr(message, 'tool_calls') and message.tool_calls:
            tool_results = []
            
            for tool_call in message.tool_calls:
                # Execute the tool
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                logger.critical(f"\n🔧 EXECUTING TOOL: {tool_name}")
                logger.critical(f"   Arguments: {json.dumps(tool_args, indent=2)}")
                
                # Execute tool using the agent's execute_tool method
                if hasattr(self, 'execute_tool'):
                    logger.critical(f"   Calling execute_tool method...")
                    result = await self.execute_tool(tool_name, tool_args)
                    logger.critical(f"   Result: {json.dumps(result, indent=2)}")
                    tool_results.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "result": result
                    })
                else:
                    logger.critical(f"   ✗ ERROR: No execute_tool method found!")
                    logger.warning(f"No execute_tool method found for {tool_name}")
            
            # Get final response after tool execution
            return await self._get_final_response_after_tools(
                message, tool_results, context
            )
        
        # Return direct response if no tools were called
        logger.critical("✗ No tool calls in AI response")
        return {
            "text": message.content,
            "agent": getattr(self, 'name', 'AI'),
            "handled": True,
            "ai_generated": True,
            "actions": []
        }
    
    async def _get_final_response_after_tools(
        self, 
        original_message: Any,
        tool_results: List[Dict[str, Any]], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get final AI response after tool execution."""
        logger.critical(f"=== _get_final_response_after_tools ===")
        logger.critical(f"Tool results: {json.dumps(tool_results, indent=2)}")
        logger.critical(f"Context state: {context.get('conversation_state')}")
        logger.critical(f"Customer name: {context.get('customer_name')}")
        
        # Build follow-up messages including tool results
        messages = self._build_messages("", context)
        
        # Add the assistant's message with tool calls
        messages.append(original_message.model_dump())
        
        # Add tool results
        for i, result in enumerate(tool_results):
            messages.append({
                "role": "tool",
                "tool_call_id": original_message.tool_calls[i].id,
                "content": json.dumps(result["result"])
            })
        
        # Get final response
        logger.critical(f"Getting final AI response after tools...")
        client = await self._get_ai_client()
        final_response = await client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.1,  # Very low for speed
            max_tokens=100   # Even shorter for speed
        )
        
        response_text = final_response.choices[0].message.content
        logger.critical(f"Final AI response text: '{response_text}'")
        
        return {
            "text": response_text,
            "agent": getattr(self, 'name', 'AI'),
            "handled": True,
            "ai_generated": True,
            "tool_results": tool_results,
            "actions": self._extract_actions_from_tools(tool_results),
            "tool_calls": [tool_call.model_dump() for tool_call in original_message.tool_calls]
        }
    
    def _summarize_cart(self, cart_items: List[Dict[str, Any]]) -> str:
        """Summarize cart items for context."""
        if not cart_items:
            return "Empty"
        
        summary_parts = []
        for item in cart_items[:5]:  # Limit to first 5 items
            name = item.get("name", "Unknown item")
            quantity = item.get("quantity", 1)
            summary_parts.append(f"{quantity}x {name}")
        
        if len(cart_items) > 5:
            summary_parts.append(f"... and {len(cart_items) - 5} more items")
        
        return ", ".join(summary_parts)
    
    def _extract_actions_from_tools(
        self, 
        tool_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract actions from tool execution results."""
        actions = []
        
        for result in tool_results:
            tool_name = result["tool"]
            
            # Map tool calls to actions
            if tool_name == "add_to_cart":
                actions.append({
                    "type": "cart_updated",
                    "item": result["args"].get("item_name"),
                    "quantity": result["args"].get("quantity", 1)
                })
            elif tool_name == "update_customer_info":
                if result["args"].get("name"):
                    actions.append({
                        "type": "set_customer_name",
                        "name": result["args"]["name"]
                    })
            elif tool_name == "confirm_order":
                actions.append({
                    "type": "order_confirmed",
                    "confirmed": result["args"].get("confirmed", False)
                })
            elif tool_name == "escalate_to_human":
                actions.append({
                    "type": "escalate_to_human",
                    "reason": result["args"].get("reason")
                })
        
        return actions
    
    async def get_fast_response(self, input_text: str, context: Dict[str, Any]) -> str:
        """
        Get a fast, contextual response without full AI processing.
        Used for immediate feedback while full processing happens.
        
        Args:
            input_text: User input
            context: Current context
            
        Returns:
            Quick response text
        """
        input_lower = input_text.lower()
        state = context.get("conversation_state", "")
        
        # Quick responses based on state and input
        if state == "GREETING":
            # Name patterns
            if len(input_text.split()) == 1 and input_text[0].isupper():
                return f"Nice to meet you! How can I help you today?"
            elif "my name is" in input_lower or "i'm" in input_lower or "i am" in input_lower:
                return "Great to meet you! What can I help you with today?"
        
        elif state == "MAIN_MENU":
            if any(word in input_lower for word in ["order", "food", "hungry"]):
                return "Perfect! What would you like to order today?"
            elif "menu" in input_lower:
                return "I'd be happy to help you with our menu. We have appetizers, sushi rolls, sashimi, and beverages."
        
        elif state == "ORDERING":
            if any(phrase in input_lower for phrase in ["that's all", "done", "finished", "complete"]):
                return "Great! Let me confirm your order for you."
            elif any(word in input_lower for word in ["add", "want", "like", "get"]):
                return "I'll add that to your order."
        
        # Default response
        return "I'm processing your request..."
    
    async def understand_intent(
        self, 
        input_text: str, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use AI to understand user intent from their input.
        
        Returns:
            Dict with intent, entities, and confidence
        """
        try:
            messages = [
                {
                    "role": "system",
                    "content": """You are an intent classifier for a restaurant ordering system.
                    Classify the user's intent into one of these categories:
                    - greeting: User is greeting or introducing themselves
                    - provide_name: User is providing their name
                    - menu_inquiry: User is asking about the menu
                    - place_order: User wants to order something
                    - modify_order: User wants to change their order
                    - confirm_order: User is confirming their order
                    - cancel_order: User wants to cancel
                    - request_human: User wants to speak to a person
                    - general_question: Other questions
                    
                    Also extract any entities like names, menu items, quantities.
                    
                    Respond in JSON format: {"intent": "...", "entities": {...}, "confidence": 0.0-1.0}
                    """
                },
                {"role": "user", "content": input_text}
            ]
            
            client = await self._get_ai_client()
            response = await client.chat.completions.create(
                model="gpt-4o-mini",  # Use consistent model
                messages=messages,
                temperature=0.1,  # Very low temp for deterministic intent detection
                max_tokens=100,   # Intent detection needs less tokens
                response_format={ "type": "json_object" }
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"Intent understanding error: {e}")
            # Return a default intent
            return {
                "intent": "general_question",
                "entities": {},
                "confidence": 0.0
            }