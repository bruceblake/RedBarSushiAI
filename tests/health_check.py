"""
Health check utilities for test services.
Provides functions to verify that all required services are ready before running tests.
"""

import asyncio
import os
import sys
import time
from typing import Dict, Tuple, Optional
import asyncpg
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ServiceHealthChecker:
    """Check health of test services."""
    
    def __init__(self, timeout: int = 60, check_interval: float = 2.0):
        """
        Initialize health checker.
        
        Args:
            timeout: Maximum time to wait for services (seconds)
            check_interval: Time between health checks (seconds)
        """
        self.timeout = timeout
        self.check_interval = check_interval
        self.start_time = time.time()
        
        # Get configuration from environment
        self.postgres_url = os.getenv(
            'DATABASE_URL',
            'postgresql+asyncpg://redbarsushi:redbarsushi@postgres-test:5432/redbarsushi_test'
        )
        self.redis_url = os.getenv('REDIS_URL', 'redis://redis-test:6379/0')
    
    async def check_postgres(self) -> Tuple[bool, str]:
        """
        Check PostgreSQL connectivity and readiness.
        
        Returns:
            Tuple of (is_healthy, message)
        """
        try:
            # Try to connect
            engine = create_async_engine(self.postgres_url, echo=False)
            async with engine.begin() as conn:
                # Check basic connectivity
                result = await conn.execute(text("SELECT 1"))
                result.fetchone()
                
                # Check tables exist
                table_check = await conn.execute(
                    text("""
                        SELECT COUNT(*) 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_type = 'BASE TABLE'
                    """)
                )
                table_count = table_check.scalar()
                
                # Check for test data
                if table_count > 0:
                    try:
                        data_check = await conn.execute(
                            text("SELECT COUNT(*) FROM menu_items")
                        )
                        item_count = data_check.scalar()
                        message = f"PostgreSQL ready with {table_count} tables and {item_count} menu items"
                    except Exception:
                        message = f"PostgreSQL ready with {table_count} tables (no test data yet)"
                else:
                    message = "PostgreSQL ready (no tables yet)"
                
            await engine.dispose()
            return True, message
            
        except Exception as e:
            return False, f"PostgreSQL not ready: {str(e)}"
    
    async def check_redis(self) -> Tuple[bool, str]:
        """
        Check Redis connectivity and readiness.
        
        Returns:
            Tuple of (is_healthy, message)
        """
        try:
            # Parse Redis URL
            redis_client = redis.from_url(self.redis_url, decode_responses=True)
            
            # Check connectivity
            await redis_client.ping()
            
            # Test basic operations
            test_key = "health_check_test"
            await redis_client.set(test_key, "test_value", ex=10)
            value = await redis_client.get(test_key)
            
            if value == "test_value":
                # Get info
                info = await redis_client.info()
                memory_usage = info.get('used_memory_human', 'unknown')
                await redis_client.delete(test_key)
                await redis_client.aclose()
                
                return True, f"Redis ready (memory: {memory_usage})"
            else:
                await redis_client.aclose()
                return False, "Redis read/write test failed"
                
        except Exception as e:
            return False, f"Redis not ready: {str(e)}"
    
    async def wait_for_service(
        self, 
        service_name: str, 
        check_func
    ) -> Tuple[bool, str]:
        """
        Wait for a service to become healthy.
        
        Args:
            service_name: Name of the service
            check_func: Async function to check service health
            
        Returns:
            Tuple of (is_healthy, message)
        """
        logger.info(f"Waiting for {service_name}...")
        
        while True:
            is_healthy, message = await check_func()
            
            if is_healthy:
                elapsed = time.time() - self.start_time
                logger.info(f"✓ {service_name} ready in {elapsed:.1f}s: {message}")
                return True, message
            
            elapsed = time.time() - self.start_time
            if elapsed >= self.timeout:
                logger.error(f"✗ {service_name} failed to become ready within {self.timeout}s")
                return False, message
            
            await asyncio.sleep(self.check_interval)
    
    async def check_all_services(self) -> Dict[str, Tuple[bool, str]]:
        """
        Check all required services.
        
        Returns:
            Dictionary mapping service names to (is_healthy, message) tuples
        """
        results = {}
        
        # Check services in parallel
        postgres_task = asyncio.create_task(
            self.wait_for_service("PostgreSQL", self.check_postgres)
        )
        redis_task = asyncio.create_task(
            self.wait_for_service("Redis", self.check_redis)
        )
        
        # Wait for all checks
        results["postgres"] = await postgres_task
        results["redis"] = await redis_task
        
        return results
    
    async def ensure_healthy(self) -> bool:
        """
        Ensure all services are healthy, raise exception if not.
        
        Returns:
            True if all services are healthy
            
        Raises:
            RuntimeError: If any service is unhealthy
        """
        logger.info("=" * 50)
        logger.info("Test Services Health Check")
        logger.info("=" * 50)
        
        results = await self.check_all_services()
        
        all_healthy = all(healthy for healthy, _ in results.values())
        
        if all_healthy:
            logger.info("✓ All services are healthy!")
            logger.info("=" * 50)
            return True
        else:
            unhealthy = [
                f"{service}: {message}"
                for service, (healthy, message) in results.items()
                if not healthy
            ]
            error_msg = "Some services are not healthy:\n" + "\n".join(unhealthy)
            logger.error(error_msg)
            logger.info("=" * 50)
            raise RuntimeError(error_msg)


async def wait_for_services(timeout: int = 60) -> bool:
    """
    Wait for all test services to be ready.
    
    Args:
        timeout: Maximum time to wait in seconds
        
    Returns:
        True if all services are ready
        
    Raises:
        RuntimeError: If services don't become ready within timeout
    """
    checker = ServiceHealthChecker(timeout=timeout)
    return await checker.ensure_healthy()


def check_services_sync(timeout: int = 60) -> bool:
    """
    Synchronous wrapper for service health check.
    
    Args:
        timeout: Maximum time to wait in seconds
        
    Returns:
        True if all services are ready
    """
    return asyncio.run(wait_for_services(timeout))


if __name__ == "__main__":
    # Allow running as a standalone script
    try:
        timeout = int(sys.argv[1]) if len(sys.argv) > 1 else 60
        check_services_sync(timeout)
        sys.exit(0)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        sys.exit(1)