"""
Enhanced OpenAI Client with 429 Rate Limiting and Exponential Backoff.

This module provides a wrapper around the OpenAI client that handles
rate limiting gracefully with sophisticated retry strategies.
"""

import asyncio
import time
from typing import Dict, Any, Optional, List, Union
import openai
import httpx

from app.config import settings
from app.utils.enhanced_logging import get_logger
from app.utils.retry_strategies import (
    RetryConfig, 
    retry_with_exponential_backoff,
    OpenAIRateLimitError,
    extract_rate_limit_info,
    retry_on_rate_limit
)

logger = get_logger(__name__)


class EnhancedOpenAIClient:
    """
    Enhanced OpenAI client with advanced rate limiting and retry capabilities.
    
    This client wraps the standard OpenAI client and adds:
    - Sophisticated 429 error handling
    - Exponential backoff with jitter
    - Rate limit header parsing
    - Circuit breaker integration
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
        max_retries: int = None,
        timeout: float = None
    ):
        """
        Initialize enhanced OpenAI client.
        
        Args:
            api_key: OpenAI API key (uses settings if None)
            retry_config: Custom retry configuration
            max_retries: Override for max retries (uses settings if None)
            timeout: Override for timeout (uses settings if None)
        """
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.retry_config = retry_config or RetryConfig(
            max_attempts=5,
            base_delay=1.0,
            max_delay=60.0,
            exponential_base=2.0,
            jitter_factor=0.1
        )
        
        # Create the underlying OpenAI client with minimal retries
        # (we handle retries at a higher level)
        self.client = openai.AsyncOpenAI(
            api_key=self.api_key,
            max_retries=max_retries or 0,  # Disable built-in retries
            timeout=timeout or settings.DEFAULT_LLM_API_TIMEOUT
        )
        
        # Rate limit tracking
        self.rate_limit_info: Dict[str, Any] = {}
        self.last_request_time: float = 0
    
    def _handle_rate_limit_response(self, response: Any) -> None:
        """
        Extract and store rate limit information from response.
        
        Args:
            response: OpenAI API response
        """
        if hasattr(response, '_response') and hasattr(response._response, 'headers'):
            self.rate_limit_info = extract_rate_limit_info(response._response)
            self.last_request_time = time.time()
            
            if self.rate_limit_info:
                logger.debug(f"Updated rate limit info: {self.rate_limit_info}")
    
    def _check_rate_limit_headers(self, exception: Exception) -> OpenAIRateLimitError:
        """
        Check if exception contains rate limit information and create enhanced error.
        
        Args:
            exception: Original exception from OpenAI
            
        Returns:
            Enhanced rate limit error with parsed information
        """
        reset_time = None
        remaining = None
        
        # Try to extract rate limit info from exception
        if hasattr(exception, 'response') and hasattr(exception.response, 'headers'):
            headers = exception.response.headers
            rate_limit_info = extract_rate_limit_info(exception.response)
            
            reset_time = rate_limit_info.get('reset_time')
            remaining = rate_limit_info.get('remaining_requests', 0)
        
        return OpenAIRateLimitError(
            str(exception),
            reset_time=reset_time,
            remaining=remaining
        )
    
    async def _make_request_with_retry(self, request_func, *args, **kwargs) -> Any:
        """
        Make OpenAI request with enhanced retry logic.
        
        Args:
            request_func: The OpenAI API function to call
            *args: Positional arguments for the request
            **kwargs: Keyword arguments for the request
            
        Returns:
            Response from OpenAI API
            
        Raises:
            OpenAIRateLimitError: If rate limited after all retries
            Other OpenAI exceptions: If non-retryable error occurs
        """
        async def execute_request():
            try:
                response = await request_func(*args, **kwargs)
                
                # Store rate limit information from successful response
                self._handle_rate_limit_response(response)
                
                return response
                
            except openai.RateLimitError as e:
                logger.warning(f"OpenAI rate limit hit: {e}")
                # Convert to our enhanced rate limit error
                enhanced_error = self._check_rate_limit_headers(e)
                raise enhanced_error
                
            except openai.APITimeoutError as e:
                logger.warning(f"OpenAI timeout: {e}")
                raise e
                
            except openai.APIConnectionError as e:
                logger.warning(f"OpenAI connection error: {e}")
                raise e
                
            except openai.InternalServerError as e:
                logger.warning(f"OpenAI internal server error: {e}")
                raise e
                
            except Exception as e:
                logger.error(f"Unexpected OpenAI error: {e}")
                raise e
        
        # Use our enhanced retry logic
        return await retry_with_exponential_backoff(
            execute_request,
            config=self.retry_config
        )
    
    @retry_on_rate_limit(max_attempts=5, base_delay=1.0)
    async def chat_completions_create(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Any:
        """
        Create chat completion with enhanced retry logic.
        
        Args:
            model: Model to use for completion
            messages: List of messages for the conversation
            **kwargs: Additional parameters for the completion
            
        Returns:
            Chat completion response
        """
        logger.debug(f"Making chat completion request with model {model}")
        
        return await self._make_request_with_retry(
            self.client.chat.completions.create,
            model=model,
            messages=messages,
            **kwargs
        )
    
    @retry_on_rate_limit(max_attempts=3, base_delay=2.0)
    async def embeddings_create(
        self,
        model: str,
        input: Union[str, List[str]],
        **kwargs
    ) -> Any:
        """
        Create embeddings with enhanced retry logic.
        
        Args:
            model: Model to use for embeddings
            input: Text or list of texts to embed
            **kwargs: Additional parameters for embeddings
            
        Returns:
            Embeddings response
        """
        logger.debug(f"Making embeddings request with model {model}")
        
        return await self._make_request_with_retry(
            self.client.embeddings.create,
            model=model,
            input=input,
            **kwargs
        )
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """
        Get current rate limit status information.
        
        Returns:
            Dictionary with rate limit information
        """
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        return {
            "rate_limit_info": self.rate_limit_info.copy(),
            "last_request_time": self.last_request_time,
            "time_since_last_request": time_since_last_request,
            "client_config": {
                "max_attempts": self.retry_config.max_attempts,
                "base_delay": self.retry_config.base_delay,
                "max_delay": self.retry_config.max_delay
            }
        }
    
    async def close(self):
        """Close the underlying client."""
        await self.client.aclose()


# Global enhanced client instance
_enhanced_client: Optional[EnhancedOpenAIClient] = None


async def get_enhanced_openai_client() -> EnhancedOpenAIClient:
    """
    Get or create the global enhanced OpenAI client.
    
    Returns:
        Enhanced OpenAI client instance
    """
    global _enhanced_client
    
    if _enhanced_client is None:
        _enhanced_client = EnhancedOpenAIClient()
        logger.info("Created enhanced OpenAI client with rate limiting")
    
    return _enhanced_client


async def enhanced_chat_completion(
    model: str,
    messages: List[Dict[str, str]],
    **kwargs
) -> Any:
    """
    Convenience function for chat completions with enhanced error handling.
    
    Args:
        model: Model to use for completion
        messages: List of messages for the conversation
        **kwargs: Additional parameters for the completion
        
    Returns:
        Chat completion response
    """
    client = await get_enhanced_openai_client()
    return await client.chat_completions_create(model=model, messages=messages, **kwargs)


async def enhanced_embeddings(
    model: str,
    input: Union[str, List[str]],
    **kwargs
) -> Any:
    """
    Convenience function for embeddings with enhanced error handling.
    
    Args:
        model: Model to use for embeddings
        input: Text or list of texts to embed
        **kwargs: Additional parameters for embeddings
        
    Returns:
        Embeddings response
    """
    client = await get_enhanced_openai_client()
    return await client.embeddings_create(model=model, input=input, **kwargs)