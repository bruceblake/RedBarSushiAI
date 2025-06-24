"""
HTTP utilities for adding correlation IDs to external API calls.

This module provides utilities for propagating correlation IDs
through HTTP requests to external services.
"""

import logging
from typing import Dict, Any, Optional
import httpx

from app.utils.correlation_id import get_correlation_id
from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


def add_correlation_headers(headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Add correlation ID headers to outgoing HTTP requests.
    
    Args:
        headers: Existing headers dict (will be copied)
        
    Returns:
        New headers dict with correlation ID added
    """
    if headers is None:
        headers = {}
    else:
        # Copy to avoid modifying the original
        headers = headers.copy()
    
    correlation_id = get_correlation_id()
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id
        headers["X-Request-ID"] = correlation_id
        headers["X-Trace-ID"] = correlation_id
    
    return headers


class CorrelatedAsyncClient(httpx.AsyncClient):
    """
    An httpx AsyncClient that automatically adds correlation IDs to requests.
    """
    
    async def request(self, *args, **kwargs):
        """Override request to add correlation headers."""
        # Add correlation headers
        headers = kwargs.get("headers", {})
        kwargs["headers"] = add_correlation_headers(headers)
        
        # Log the request with correlation ID
        method = args[0] if args else kwargs.get("method", "UNKNOWN")
        url = args[1] if len(args) > 1 else kwargs.get("url", "UNKNOWN")
        logger.debug(f"Making {method} request to {url}")
        
        return await super().request(*args, **kwargs)


class CorrelatedClient(httpx.Client):
    """
    An httpx Client that automatically adds correlation IDs to requests.
    """
    
    def request(self, *args, **kwargs):
        """Override request to add correlation headers."""
        # Add correlation headers
        headers = kwargs.get("headers", {})
        kwargs["headers"] = add_correlation_headers(headers)
        
        # Log the request with correlation ID
        method = args[0] if args else kwargs.get("method", "UNKNOWN")
        url = args[1] if len(args) > 1 else kwargs.get("url", "UNKNOWN")
        logger.debug(f"Making {method} request to {url}")
        
        return super().request(*args, **kwargs)