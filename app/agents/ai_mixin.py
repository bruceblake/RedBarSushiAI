"""
AI Intelligence Mixin for Async Agents.

This mixin adds AI capabilities to async agents while maintaining
their async nature and integration with the FSM orchestration.
"""

import json
import logging
import openai
from typing import Dict, Any, List
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
        self, input_text: str, context: Dict[str, Any], use_tools: bool = True
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
                "max_tokens": 500,
            }

            # Add tools if available and enabled
            if use_tools and hasattr(self, "tools") and self.tools:
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

    def _build_messages(
        self, input_text: str, context: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Build message history for AI context."""
        messages = []

        # Add system instructions
        if hasattr(self, "instructions"):
            messages.append({"role": "system", "content": self.instructions})
        else:
            messages.append(
                {
                    "role": "system",
                    "content": f"You are {getattr(self, 'name', 'an AI assistant')} for Red Bar Sushi restaurant.",
                }
            )

        # Add conversation history if available
        if context.get("conversation_history"):
            # Include last 5 messages for context
            for msg in context["conversation_history"][-5:]:
                messages.append(
                    {"role": msg.get("role", "user"), "content": msg.get("content", "")}
                )

        # Add current state context
        if context.get("conversation_state"):
            messages.append(
                {
                    "role": "system",
                    "content": f"Current conversation state: {context['conversation_state']}",
                }
            )

        # Add customer context if available
        if context.get("customer_name"):
            messages.append(
                {
                    "role": "system",
                    "content": f"Customer name: {context['customer_name']}",
                }
            )

        # Add cart context if in ordering state
        if context.get("cart_items"):
            cart_summary = self._summarize_cart(context["cart_items"])
            messages.append(
                {"role": "system", "content": f"Current cart: {cart_summary}"}
            )

        # Add the current user input
        messages.append({"role": "user", "content": input_text})

        return messages

    async def _process_ai_response(
        self, response: Any, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process the AI API response."""
        message = response.choices[0].message

        # Handle tool calls if present
        if hasattr(message, "tool_calls") and message.tool_calls:
            tool_results = []

            for tool_call in message.tool_calls:
                # Execute the tool
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                logger.info(f"AI calling tool: {tool_name} with args: {tool_args}")

                # Execute tool using the agent's execute_tool method
                if hasattr(self, "execute_tool"):
                    result = await self.execute_tool(tool_name, tool_args)
                    tool_results.append(
                        {"tool": tool_name, "args": tool_args, "result": result}
                    )
                else:
                    logger.warning(f"No execute_tool method found for {tool_name}")

            # Get final response after tool execution
            return await self._get_final_response_after_tools(
                message, tool_results, context
            )

        # Return direct response if no tools were called
        return {
            "text": message.content,
            "agent": getattr(self, "name", "AI"),
            "handled": True,
            "ai_generated": True,
            "actions": [],
        }

    async def _get_final_response_after_tools(
        self,
        original_message: Any,
        tool_results: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Get final AI response after tool execution."""
        # Build follow-up messages including tool results
        messages = self._build_messages("", context)

        # Add the assistant's message with tool calls
        messages.append(original_message.model_dump())

        # Add tool results
        for i, result in enumerate(tool_results):
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": original_message.tool_calls[i].id,
                    "content": json.dumps(result["result"]),
                }
            )

        # Get final response
        final_response = await self.ai_client.chat.completions.create(
            model=self._model, messages=messages, temperature=0.7, max_tokens=500
        )

        return {
            "text": final_response.choices[0].message.content,
            "agent": getattr(self, "name", "AI"),
            "handled": True,
            "ai_generated": True,
            "tool_results": tool_results,
            "actions": self._extract_actions_from_tools(tool_results),
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
        self, tool_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract actions from tool execution results."""
        actions = []

        for result in tool_results:
            tool_name = result["tool"]

            # Map tool calls to actions
            if tool_name == "add_to_cart":
                actions.append(
                    {
                        "type": "cart_updated",
                        "item": result["args"].get("item_name"),
                        "quantity": result["args"].get("quantity", 1),
                    }
                )
            elif tool_name == "update_customer_info":
                if result["args"].get("name"):
                    actions.append(
                        {"type": "set_customer_name", "name": result["args"]["name"]}
                    )
            elif tool_name == "confirm_order":
                actions.append(
                    {
                        "type": "order_confirmed",
                        "confirmed": result["args"].get("confirmed", False),
                    }
                )
            elif tool_name == "escalate_to_human":
                actions.append(
                    {
                        "type": "escalate_to_human",
                        "reason": result["args"].get("reason"),
                    }
                )

        return actions
