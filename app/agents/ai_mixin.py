"""
AI Intelligence Mixin for Async Agents.

This mixin adds AI capabilities to async agents while maintaining
their async nature and integration with the FSM orchestration.
"""

import json
import logging
import openai
from typing import Dict, Any, List, Optional
from app.config import settings

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
        self._model = "gpt-4-turbo-preview"
        
    @property
    def ai_client(self):
        """Lazy initialization of OpenAI async client."""
        if self._ai_client is None:
            self._ai_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return self._ai_client
    
    async def process_with_ai(
        self, 
        input_text: str, 
        context: Dict[str, Any],
        use_tools: bool = True
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
            # Fall back to non-AI processing
            return await self.process_input(input_text, context)
        
        try:
            # Build conversation history
            messages = self._build_messages(input_text, context)
            
            # Prepare API call parameters
            params = {
                "model": self._model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 500
            }
            
            # Add tools if available and enabled
            if use_tools and hasattr(self, 'tools') and self.tools:
                params["tools"] = self.tools
                params["tool_choice"] = "auto"
            
            # Make AI API call
            response = await self.ai_client.chat.completions.create(**params)
            
            # Process the response
            return await self._process_ai_response(response, context)
            
        except Exception as e:
            logger.error(f"AI processing error in {self.name}: {e}")
            # Fall back to non-AI processing
            self._ai_enabled = False
            return await self.process_input(input_text, context)
    
    def _build_messages(self, input_text: str, context: Dict[str, Any]) -> List[Dict[str, str]]:
        """Build message history for AI context."""
        messages = []
        
        # Add system instructions
        if hasattr(self, 'instructions'):
            messages.append({"role": "system", "content": self.instructions})
        else:
            messages.append({
                "role": "system", 
                "content": f"You are {getattr(self, 'name', 'an AI assistant')} for Red Bar Sushi restaurant."
            })
        
        # Add conversation history if available
        if context.get("conversation_history"):
            # Include last 5 messages for context
            for msg in context["conversation_history"][-5:]:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
        
        # Add current state context
        if context.get("conversation_state"):
            messages.append({
                "role": "system",
                "content": f"Current conversation state: {context['conversation_state']}"
            })
        
        # Add state guidance if provided
        if context.get("state_guidance"):
            messages.append({
                "role": "system",
                "content": context["state_guidance"]
            })
        
        # Add customer context if available
        if context.get("customer_name"):
            messages.append({
                "role": "system",
                "content": f"Customer name: {context['customer_name']}"
            })
        
        # Add cart context if in ordering state
        if context.get("cart_items"):
            cart_summary = self._summarize_cart(context["cart_items"])
            messages.append({
                "role": "system",
                "content": f"Current cart: {cart_summary}"
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
        
        # Handle tool calls if present
        if hasattr(message, 'tool_calls') and message.tool_calls:
            tool_results = []
            
            for tool_call in message.tool_calls:
                # Execute the tool
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                logger.critical(f"AI calling tool: {tool_name} with args: {tool_args}")
                
                # Execute tool using the agent's execute_tool method
                if hasattr(self, 'execute_tool'):
                    result = await self.execute_tool(tool_name, tool_args)
                    tool_results.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "result": result
                    })
                else:
                    logger.warning(f"No execute_tool method found for {tool_name}")
            
            # Get final response after tool execution
            return await self._get_final_response_after_tools(
                message, tool_results, context
            )
        
        # Return direct response if no tools were called
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
        final_response = await self.ai_client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.7,
            max_tokens=500
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
            
            response = await self.ai_client.chat.completions.create(
                model="gpt-3.5-turbo",  # Use faster model for intent
                messages=messages,
                temperature=0.3,
                max_tokens=200,
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