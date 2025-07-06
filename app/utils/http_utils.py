"""
HTTP utilities for making correlated async requests.

This module provides HTTP client utilities with correlation IDs and logging.
"""

import logging
import uuid
from typing import Any, Dict, Optional, Union
import httpx
from httpx import AsyncClient, Response

logger = logging.getLogger(__name__)


class CorrelatedAsyncClient:
    """Async HTTP client with correlation ID tracking."""
    
    def __init__(self, base_url: Optional[str] = None, timeout: float = 30.0):
        """
        Initialize the correlated async client.
        
        Args:
            base_url: Base URL for requests
            timeout: Request timeout in seconds
        """
        self.base_url = base_url
        self.timeout = timeout
        self._client: Optional[AsyncClient] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._client = AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
    
    def _get_correlation_id(self, headers: Optional[Dict[str, str]] = None) -> str:
        """Get or generate correlation ID."""
        if headers and 'X-Correlation-ID' in headers:
            return headers['X-Correlation-ID']
        return str(uuid.uuid4())
    
    def _prepare_headers(self, headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Prepare headers with correlation ID."""
        prepared_headers = headers or {}
        if 'X-Correlation-ID' not in prepared_headers:
            prepared_headers['X-Correlation-ID'] = self._get_correlation_id()
        return prepared_headers
    
    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Response:
        """Make GET request with correlation ID."""
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")
        
        prepared_headers = self._prepare_headers(headers)
        correlation_id = prepared_headers['X-Correlation-ID']
        
        logger.info(f"GET {url} [correlation_id={correlation_id}]")
        
        try:
            response = await self._client.get(
                url, params=params, headers=prepared_headers, **kwargs
            )
            logger.info(f"GET {url} -> {response.status_code} [correlation_id={correlation_id}]")
            return response
        except Exception as e:
            logger.error(f"GET {url} failed: {e} [correlation_id={correlation_id}]")
            raise
    
    async def post(
        self,
        url: str,
        data: Optional[Union[Dict[str, Any], str]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Response:
        """Make POST request with correlation ID."""
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")
        
        prepared_headers = self._prepare_headers(headers)
        correlation_id = prepared_headers['X-Correlation-ID']
        
        logger.info(f"POST {url} [correlation_id={correlation_id}]")
        
        try:
            response = await self._client.post(
                url, data=data, json=json, headers=prepared_headers, **kwargs
            )
            logger.info(f"POST {url} -> {response.status_code} [correlation_id={correlation_id}]")
            return response
        except Exception as e:
            logger.error(f"POST {url} failed: {e} [correlation_id={correlation_id}]")
            raise
    
    async def put(
        self,
        url: str,
        data: Optional[Union[Dict[str, Any], str]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Response:
        """Make PUT request with correlation ID."""
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")
        
        prepared_headers = self._prepare_headers(headers)
        correlation_id = prepared_headers['X-Correlation-ID']
        
        logger.info(f"PUT {url} [correlation_id={correlation_id}]")
        
        try:
            response = await self._client.put(
                url, data=data, json=json, headers=prepared_headers, **kwargs
            )
            logger.info(f"PUT {url} -> {response.status_code} [correlation_id={correlation_id}]")
            return response
        except Exception as e:
            logger.error(f"PUT {url} failed: {e} [correlation_id={correlation_id}]")
            raise
    
    async def delete(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Response:
        """Make DELETE request with correlation ID."""
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")
        
        prepared_headers = self._prepare_headers(headers)
        correlation_id = prepared_headers['X-Correlation-ID']
        
        logger.info(f"DELETE {url} [correlation_id={correlation_id}]")
        
        try:
            response = await self._client.delete(
                url, headers=prepared_headers, **kwargs
            )
            logger.info(f"DELETE {url} -> {response.status_code} [correlation_id={correlation_id}]")
            return response
        except Exception as e:
            logger.error(f"DELETE {url} failed: {e} [correlation_id={correlation_id}]")
            raise


async def make_correlated_request(
    method: str,
    url: str,
    base_url: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    **kwargs
) -> Response:
    """
    Make a single correlated HTTP request.
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        url: Request URL
        base_url: Optional base URL
        headers: Optional headers
        **kwargs: Additional arguments for the request
        
    Returns:
        Response object
    """
    async with CorrelatedAsyncClient(base_url=base_url) as client:
        method = method.upper()
        if method == 'GET':
            return await client.get(url, headers=headers, **kwargs)
        elif method == 'POST':
            return await client.post(url, headers=headers, **kwargs)
        elif method == 'PUT':
            return await client.put(url, headers=headers, **kwargs)
        elif method == 'DELETE':
            return await client.delete(url, headers=headers, **kwargs)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")