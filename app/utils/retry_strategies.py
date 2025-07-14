"""
Retry Strategies for RedBarSushiAI.

This module provides sophisticated retry mechanisms including exponential backoff
with jitter for handling rate limiting and temporary failures.
"""

import asyncio
import random
import time
import logging
from typing import Callable, Any, Optional, List, Dict, Union
from dataclasses import dataclass
from enum import Enum

import httpx
import openai
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential, 
    retry_if_exception_type,
    before_sleep_log,
    after_log
)

from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class RetryableErrorType(Enum):
    """Types of retryable errors."""
    RATE_LIMIT = "rate_limit"           # 429 Too Many Requests
    TIMEOUT = "timeout"                 # Request timeout
    CONNECTION = "connection"           # Connection errors
    SERVER_ERROR = "server_error"       # 5xx server errors
    CIRCUIT_BREAKER = "circuit_breaker" # Circuit breaker open


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 5
    base_delay: float = 1.0        # Base delay in seconds
    max_delay: float = 60.0        # Maximum delay in seconds
    exponential_base: float = 2.0   # Exponential backoff base
    jitter_factor: float = 0.1     # Random jitter factor (0.0 to 1.0)
    
    def __post_init__(self):
        """Validate configuration."""
        if self.jitter_factor < 0.0 or self.jitter_factor > 1.0:
            raise ValueError("jitter_factor must be between 0.0 and 1.0")


class RateLimitHandler:
    """Handles rate limiting with exponential backoff and jitter."""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        """
        Initialize rate limit handler.
        
        Args:
            config: Retry configuration (uses defaults if None)
        """
        self.config = config or RetryConfig()
    
    def calculate_delay(self, attempt: int, base_delay: Optional[float] = None) -> float:
        """
        Calculate delay with exponential backoff and jitter.
        
        Args:
            attempt: Current attempt number (1-based)
            base_delay: Override base delay for this calculation
            
        Returns:
            Delay in seconds
        """
        base = base_delay or self.config.base_delay
        
        # Exponential backoff: base * (exponential_base ^ (attempt - 1))
        delay = base * (self.config.exponential_base ** (attempt - 1))
        
        # Apply maximum delay limit
        delay = min(delay, self.config.max_delay)
        
        # Add jitter to prevent thundering herd
        jitter = delay * self.config.jitter_factor * random.random()
        final_delay = delay + jitter
        
        logger.debug(f"Calculated retry delay: {final_delay:.2f}s (attempt {attempt})")
        return final_delay
    
    async def wait_for_retry(self, attempt: int, error_type: RetryableErrorType) -> None:
        """
        Wait appropriate time before retry based on error type and attempt.
        
        Args:
            attempt: Current attempt number (1-based)
            error_type: Type of error that occurred
        """
        # Special handling for rate limits
        if error_type == RetryableErrorType.RATE_LIMIT:
            # Use longer delays for rate limits
            delay = self.calculate_delay(attempt, base_delay=2.0)
        else:
            delay = self.calculate_delay(attempt)
        
        logger.info(f"Waiting {delay:.2f}s before retry (attempt {attempt}, error: {error_type.value})")
        await asyncio.sleep(delay)


class OpenAIRateLimitError(Exception):
    """Custom exception for OpenAI rate limiting."""
    
    def __init__(self, message: str, reset_time: Optional[float] = None, remaining: Optional[int] = None):
        """
        Initialize OpenAI rate limit error.
        
        Args:
            message: Error message
            reset_time: Unix timestamp when rate limit resets
            remaining: Number of requests remaining
        """
        super().__init__(message)
        self.reset_time = reset_time
        self.remaining = remaining


class DeliverectRateLimitError(Exception):
    """Custom exception for Deliverect rate limiting."""
    pass


def is_retryable_openai_error(exception: Exception) -> bool:
    """
    Determine if an OpenAI exception is retryable.
    
    Args:
        exception: Exception to check
        
    Returns:
        True if the exception is retryable
    """
    if isinstance(exception, openai.RateLimitError):
        return True
    elif isinstance(exception, openai.APITimeoutError):
        return True
    elif isinstance(exception, openai.APIConnectionError):
        return True
    elif isinstance(exception, openai.InternalServerError):
        return True
    elif isinstance(exception, OpenAIRateLimitError):
        return True
    
    return False


def is_retryable_http_error(exception: Exception) -> bool:
    """
    Determine if an HTTP exception is retryable.
    
    Args:
        exception: Exception to check
        
    Returns:
        True if the exception is retryable
    """
    if isinstance(exception, httpx.TimeoutException):
        return True
    elif isinstance(exception, httpx.ConnectError):
        return True
    elif isinstance(exception, httpx.HTTPStatusError):
        # Retry on 429 (rate limit) and 5xx (server errors)
        if exception.response.status_code == 429:
            return True
        elif 500 <= exception.response.status_code < 600:
            return True
    
    return False


def extract_rate_limit_info(response: Union[httpx.Response, Any]) -> Dict[str, Any]:
    """
    Extract rate limit information from response headers.
    
    Args:
        response: HTTP response object
        
    Returns:
        Dictionary with rate limit information
    """
    rate_limit_info = {}
    
    if hasattr(response, 'headers'):
        headers = response.headers
        
        # OpenAI rate limit headers
        if 'x-ratelimit-remaining-requests' in headers:
            rate_limit_info['remaining_requests'] = int(headers['x-ratelimit-remaining-requests'])
        if 'x-ratelimit-remaining-tokens' in headers:
            rate_limit_info['remaining_tokens'] = int(headers['x-ratelimit-remaining-tokens'])
        if 'x-ratelimit-reset-requests' in headers:
            rate_limit_info['reset_requests'] = headers['x-ratelimit-reset-requests']
        if 'x-ratelimit-reset-tokens' in headers:
            rate_limit_info['reset_tokens'] = headers['x-ratelimit-reset-tokens']
        
        # Standard rate limit headers
        if 'retry-after' in headers:
            rate_limit_info['retry_after'] = int(headers['retry-after'])
        if 'x-ratelimit-reset' in headers:
            rate_limit_info['reset_time'] = int(headers['x-ratelimit-reset'])
    
    return rate_limit_info


async def retry_with_exponential_backoff(
    func: Callable,
    *args,
    config: Optional[RetryConfig] = None,
    **kwargs
) -> Any:
    """
    Execute function with exponential backoff retry logic.
    
    Args:
        func: Async function to execute
        *args: Positional arguments for the function
        config: Retry configuration
        **kwargs: Keyword arguments for the function
        
    Returns:
        Result of the function call
        
    Raises:
        The last exception if all retries fail
    """
    retry_config = config or RetryConfig()
    rate_limit_handler = RateLimitHandler(retry_config)
    
    last_exception = None
    
    for attempt in range(1, retry_config.max_attempts + 1):
        try:
            logger.debug(f"Executing function attempt {attempt}/{retry_config.max_attempts}")
            result = await func(*args, **kwargs)
            
            if attempt > 1:
                logger.info(f"Function succeeded on attempt {attempt}")
            
            return result
            
        except Exception as e:
            last_exception = e
            
            # Determine if this error is retryable
            is_retryable = (
                is_retryable_openai_error(e) or 
                is_retryable_http_error(e)
            )
            
            if not is_retryable:
                logger.error(f"Non-retryable error on attempt {attempt}: {e}")
                raise e
            
            if attempt >= retry_config.max_attempts:
                logger.error(f"All {retry_config.max_attempts} attempts failed")
                break
            
            # Determine error type for appropriate backoff
            if isinstance(e, (openai.RateLimitError, OpenAIRateLimitError, DeliverectRateLimitError)):
                error_type = RetryableErrorType.RATE_LIMIT
            elif isinstance(e, (openai.APITimeoutError, httpx.TimeoutException)):
                error_type = RetryableErrorType.TIMEOUT
            elif isinstance(e, (openai.APIConnectionError, httpx.ConnectError)):
                error_type = RetryableErrorType.CONNECTION
            else:
                error_type = RetryableErrorType.SERVER_ERROR
            
            logger.warning(f"Retryable error on attempt {attempt}: {e}")
            
            # Wait before retry
            await rate_limit_handler.wait_for_retry(attempt, error_type)
    
    # All retries failed
    logger.error(f"Function failed after {retry_config.max_attempts} attempts")
    raise last_exception


# Tenacity-based decorators for common retry patterns
def retry_on_rate_limit(max_attempts: int = 5, base_delay: float = 1.0):
    """
    Decorator for retrying on rate limit errors with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay between retries in seconds
        
    Returns:
        Decorated function with retry logic
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=base_delay, min=base_delay, max=60),
        retry=retry_if_exception_type((
            openai.RateLimitError,
            OpenAIRateLimitError,
            DeliverectRateLimitError,
            httpx.HTTPStatusError
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.INFO)
    )