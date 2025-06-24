"""
Centralized HTTP connection pool management.

This module provides shared HTTP clients with optimized connection pooling
for all external API calls, reducing connection overhead and improving performance.
"""

import logging
from typing import Optional, Dict, Any
import httpx
from contextlib import asynccontextmanager

from app.config import settings
from app.utils.enhanced_logging import get_logger
from app.utils.correlation_id import get_correlation_id

logger = get_logger(__name__)


class HTTPConnectionPool:
    """Manages shared HTTP clients with connection pooling."""
    
    def __init__(self):
        """Initialize HTTP connection pools."""
        # Define connection limits for different services
        self.default_limits = httpx.Limits(
            max_keepalive_connections=getattr(settings, 'HTTP_POOL_KEEPALIVE', 10),
            max_connections=getattr(settings, 'HTTP_POOL_MAX_CONNECTIONS', 100),
            keepalive_expiry=getattr(settings, 'HTTP_POOL_KEEPALIVE_EXPIRY', 30.0)
        )
        
        # Default timeout configuration
        self.default_timeout = httpx.Timeout(
            timeout=getattr(settings, 'HTTP_TIMEOUT', 30.0),
            connect=getattr(settings, 'HTTP_CONNECT_TIMEOUT', 5.0),
            read=getattr(settings, 'HTTP_READ_TIMEOUT', 30.0),
            write=getattr(settings, 'HTTP_WRITE_TIMEOUT', 10.0)
        )
        
        # Create shared clients
        self._clients: Dict[str, httpx.AsyncClient] = {}
        self._sync_clients: Dict[str, httpx.Client] = {}
        
        # Initialize default clients
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize default HTTP clients."""
        # Default async client with correlation ID support
        self._clients['default'] = httpx.AsyncClient(
            limits=self.default_limits,
            timeout=self.default_timeout,
            http2=False,  # Disable HTTP/2 to avoid h2 dependency
            follow_redirects=True,
            event_hooks={
                'request': [self._inject_correlation_id],
                'response': [self._log_response]
            }
        )
        
        # Deliverect-specific client with custom timeout
        self._clients['deliverect'] = httpx.AsyncClient(
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=50,
                keepalive_expiry=60.0
            ),
            timeout=httpx.Timeout(
                timeout=60.0,  # Longer timeout for order submission
                connect=10.0
            ),
            http2=False,  # Disable HTTP/2 to avoid h2 dependency
            follow_redirects=True,
            event_hooks={
                'request': [self._inject_correlation_id],
                'response': [self._log_response]
            }
        )
        
        # External API client (for web fetch, etc.)
        self._clients['external'] = httpx.AsyncClient(
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=20,
                keepalive_expiry=15.0
            ),
            timeout=httpx.Timeout(
                timeout=15.0,
                connect=5.0
            ),
            http2=False,  # Disable HTTP/2 to avoid h2 dependency
            follow_redirects=True,
            event_hooks={
                'request': [self._inject_correlation_id],
                'response': [self._log_response]
            }
        )
        
        logger.info("HTTP connection pools initialized")
    
    async def _inject_correlation_id(self, request: httpx.Request):
        """Inject correlation ID into outgoing requests."""
        correlation_id = get_correlation_id()
        if correlation_id:
            request.headers['X-Correlation-ID'] = correlation_id
    
    async def _log_response(self, response: httpx.Response):
        """Log response details for monitoring."""
        logger.debug(
            f"HTTP Response",
            method=response.request.method,
            url=str(response.request.url),
            status=response.status_code,
            duration_ms=response.elapsed.total_seconds() * 1000,
            correlation_id=response.request.headers.get('X-Correlation-ID')
        )
    
    def get_client(self, service: str = 'default') -> httpx.AsyncClient:
        """
        Get an async HTTP client for a specific service.
        
        Args:
            service: Service name ('default', 'deliverect', 'external')
            
        Returns:
            httpx.AsyncClient: Shared HTTP client
        """
        return self._clients.get(service, self._clients['default'])
    
    def get_sync_client(self, service: str = 'default') -> httpx.Client:
        """
        Get a sync HTTP client for a specific service.
        
        Args:
            service: Service name
            
        Returns:
            httpx.Client: Shared sync HTTP client
        """
        if service not in self._sync_clients:
            # Create sync client with same config as async
            if service == 'deliverect':
                limits = httpx.Limits(
                    max_keepalive_connections=5,
                    max_connections=50,
                    keepalive_expiry=60.0
                )
                timeout = httpx.Timeout(timeout=60.0, connect=10.0)
            elif service == 'external':
                limits = httpx.Limits(
                    max_keepalive_connections=5,
                    max_connections=20,
                    keepalive_expiry=15.0
                )
                timeout = httpx.Timeout(timeout=15.0, connect=5.0)
            else:
                limits = self.default_limits
                timeout = self.default_timeout
            
            self._sync_clients[service] = httpx.Client(
                limits=limits,
                timeout=timeout,
                http2=False,  # Disable HTTP/2 to avoid h2 dependency
                follow_redirects=True
            )
        
        return self._sync_clients[service]
    
    @asynccontextmanager
    async def get_client_context(self, service: str = 'default'):
        """
        Get an HTTP client as a context manager.
        
        Usage:
            async with http_pool.get_client_context('deliverect') as client:
                response = await client.post(...)
        """
        client = self.get_client(service)
        try:
            yield client
        except Exception as e:
            logger.error(f"Error in HTTP client context: {e}", service=service)
            raise
    
    async def close_all(self):
        """Close all HTTP clients."""
        for name, client in self._clients.items():
            try:
                await client.aclose()
                logger.info(f"Closed async HTTP client: {name}")
            except Exception as e:
                logger.error(f"Error closing async client {name}: {e}")
        
        for name, client in self._sync_clients.items():
            try:
                client.close()
                logger.info(f"Closed sync HTTP client: {name}")
            except Exception as e:
                logger.error(f"Error closing sync client {name}: {e}")
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get statistics for all connection pools."""
        stats = {}
        
        for name, client in self._clients.items():
            # httpx doesn't expose direct pool stats, but we can infer some info
            stats[f"async_{name}"] = {
                "max_connections": client._limits.max_connections,
                "max_keepalive": client._limits.max_keepalive_connections,
                "keepalive_expiry": client._limits.keepalive_expiry,
                "timeout": client._timeout.timeout
            }
        
        for name, client in self._sync_clients.items():
            stats[f"sync_{name}"] = {
                "max_connections": client._limits.max_connections,
                "max_keepalive": client._limits.max_keepalive_connections,
                "keepalive_expiry": client._limits.keepalive_expiry,
                "timeout": client._timeout.timeout
            }
        
        return stats


# Global HTTP connection pool instance
http_pool = HTTPConnectionPool()


# Convenience functions
def get_http_client(service: str = 'default') -> httpx.AsyncClient:
    """Get shared HTTP client for a service."""
    return http_pool.get_client(service)


def get_sync_http_client(service: str = 'default') -> httpx.Client:
    """Get shared sync HTTP client for a service."""
    return http_pool.get_sync_client(service)


async def close_http_pools():
    """Close all HTTP connection pools."""
    await http_pool.close_all()