"""
Streaming response handler for faster perceived response times.
Allows sending partial responses as they're generated.
"""

import asyncio
import logging
from typing import AsyncIterator, Dict, Any, Optional, List
import json

logger = logging.getLogger(__name__)


class StreamingResponseHandler:
    """Handles streaming responses for conversational AI."""
    
    def __init__(self):
        self._response_queue: asyncio.Queue = asyncio.Queue()
        self._is_complete = False
        
    async def stream_openai_response(
        self,
        client,
        messages: List[Dict[str, str]],
        model: str = "gpt-4o-mini",
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream OpenAI responses token by token.
        
        Args:
            client: OpenAI async client
            messages: Conversation messages
            model: Model to use
            **kwargs: Additional parameters for OpenAI
            
        Yields:
            Response tokens as they arrive
        """
        try:
            # Create streaming completion
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                **kwargs
            )
            
            # Collect full response for logging
            full_response = ""
            
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_response += token
                    yield token
            
            logger.debug(f"Streamed response complete: {full_response[:100]}...")
            
        except Exception as e:
            logger.error(f"Error streaming OpenAI response: {e}")
            yield f"I apologize, but I'm having trouble processing your request. Please try again."
    
    async def get_first_sentence(
        self,
        client,
        messages: List[Dict[str, str]],
        model: str = "gpt-4o-mini",
        **kwargs
    ) -> str:
        """
        Get just the first sentence quickly for immediate response.
        
        Args:
            client: OpenAI async client
            messages: Conversation messages
            model: Model to use
            **kwargs: Additional parameters
            
        Returns:
            First sentence of the response
        """
        first_sentence = ""
        sentence_enders = [".", "!", "?", ":", "\n"]
        
        async for token in self.stream_openai_response(client, messages, model, **kwargs):
            first_sentence += token
            
            # Check if we've completed a sentence
            if any(ender in token for ender in sentence_enders):
                # Find the sentence end
                for ender in sentence_enders:
                    if ender in first_sentence:
                        idx = first_sentence.index(ender) + 1
                        return first_sentence[:idx].strip()
        
        # If no sentence ender found, return what we have
        return first_sentence.strip() if first_sentence else "Let me help you with that."


# Global instance
streaming_handler = StreamingResponseHandler()