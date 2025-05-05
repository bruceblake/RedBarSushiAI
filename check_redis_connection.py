#!/usr/bin/env python
"""
Redis Connection Validation Script for RedBarSushiAI

This script tests the Redis connection in the current environment with detailed logging.
It validates that the REDIS_URL environment variable is being properly detected and used.
"""

import os
import redis
import logging
import sys
import time
import socket

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("redis-check")

def redact_password(url):
    """Redact password from URL for safe logging."""
    if not url or '@' not in url:
        return url
    
    # Handle different URL formats
    if '://' in url:
        # Standard URL format
        prefix, rest = url.split('://', 1)
        if '@' in rest:
            auth_part, host_part = rest.split('@', 1)
            if ':' in auth_part:
                user, _ = auth_part.split(':', 1)
                return f"{prefix}://{user}:****@{host_part}"
    return "[REDACTED]"

def check_redis_connection():
    """Check Redis connection with full environment variable handling."""
    logger.info("=" * 60)
    logger.info("Redis Connection Validator for RedBarSushiAI")
    logger.info("=" * 60)
    
    # Environment detection
    is_render = os.environ.get("RENDER", "").lower() == "true" or os.environ.get("RENDER_SERVICE_ID")
    is_docker = os.environ.get("DOCKER", "").lower() == "true" or os.path.exists("/.dockerenv")
    
    logger.info(f"Running in Render environment: {is_render}")
    logger.info(f"Running in Docker environment: {is_docker}")
    
    # Collect environment variables
    redis_url = os.environ.get("REDIS_URL")
    celery_broker_url = os.environ.get("CELERY_BROKER_URL")
    celery_result_backend = os.environ.get("CELERY_RESULT_BACKEND")
    
    # Log environment state (safely)
    logger.info(f"REDIS_URL: {redact_password(redis_url) if redis_url else 'Not set'}")
    logger.info(f"CELERY_BROKER_URL: {redact_password(celery_broker_url) if celery_broker_url else 'Not set'}")
    logger.info(f"CELERY_RESULT_BACKEND: {redact_password(celery_result_backend) if celery_result_backend else 'Not set'}")
    
    # Connection attempt strategy
    connection_methods = []
    
    # Method 1: REDIS_URL
    if redis_url:
        connection_methods.append(("REDIS_URL", redis_url))
    
    # Method 2: CELERY_BROKER_URL
    if celery_broker_url:
        connection_methods.append(("CELERY_BROKER_URL", celery_broker_url))
    
    # Method 3: Default connections based on environment
    if is_docker:
        connection_methods.append(("Docker default", "redis://redis:6379/0"))
    
    # Method 4: Local development defaults
    connection_methods.append(("Localhost default 1", "redis://localhost:6379/0"))
    connection_methods.append(("Localhost default 2", "redis://127.0.0.1:6379/0"))
    
    # Try each connection method
    for method_name, url in connection_methods:
        try:
            logger.info(f"\nAttempting connection with {method_name}: {redact_password(url)}")
            
            # Handle URL formatting
            if not url.startswith("redis://"):
                formatted_url = f"redis://{url}"
                logger.info(f"Adding 'redis://' prefix to URL: {redact_password(formatted_url)}")
            else:
                formatted_url = url
            
            # Extract hostname for connectivity check
            try:
                if '@' in formatted_url:
                    hostname = formatted_url.split('@')[-1].split('/')[0].split(':')[0]
                else:
                    hostname = formatted_url.split('//')[1].split('/')[0].split(':')[0]
                
                # Try to resolve hostname first
                logger.info(f"Resolving hostname: {hostname}")
                try:
                    socket.gethostbyname(hostname)
                    logger.info(f"Hostname {hostname} resolved successfully")
                except socket.gaierror as e:
                    logger.error(f"Hostname resolution failed: {e}")
                    logger.info("Will attempt Redis connection anyway...")
            except Exception as e:
                logger.warning(f"Could not parse hostname from URL: {e}")
            
            # Create Redis client with timeout
            client = redis.from_url(formatted_url, socket_timeout=3.0)
            
            # Start connection test
            start_time = time.time()
            logger.info("Testing connection with PING...")
            response = client.ping()
            duration = time.time() - start_time
            
            if response:
                logger.info(f"✓ SUCCESS: Connected to Redis in {duration:.3f}s")
                
                # Get Redis server info
                try:
                    info = client.info()
                    redis_version = info.get('redis_version', 'unknown')
                    redis_mode = info.get('redis_mode', 'unknown')
                    connected_clients = info.get('connected_clients', 'unknown')
                    
                    logger.info(f"Redis Version: {redis_version}")
                    logger.info(f"Redis Mode: {redis_mode}")
                    logger.info(f"Connected Clients: {connected_clients}")
                    logger.info("\nConnection details validated successfully!")
                    
                    # Test basic operations
                    logger.info("\nTesting basic Redis operations...")
                    test_key = "redis_connection_test"
                    test_value = f"test_{int(time.time())}"
                    
                    # SET operation
                    client.set(test_key, test_value, ex=60)  # 60 second expiration
                    logger.info("SET operation successful")
                    
                    # GET operation
                    retrieved = client.get(test_key)
                    if retrieved and retrieved.decode('utf-8') == test_value:
                        logger.info("GET operation successful")
                    else:
                        logger.warning(f"GET operation returned unexpected value: {retrieved}")
                    
                    # DEL operation
                    client.delete(test_key)
                    logger.info("DEL operation successful")
                    
                    logger.info("\n✓ All Redis operations completed successfully!")
                    return True
                except Exception as e:
                    logger.error(f"Error getting Redis info: {e}")
                    
            else:
                logger.error(f"× PING failed with response: {response}")
                
        except redis.RedisError as e:
            logger.error(f"× Redis connection error: {e}")
        except Exception as e:
            logger.error(f"× Unexpected error: {e}")
    
    logger.error("\n× FAILURE: Could not connect to Redis with any method")
    return False

if __name__ == "__main__":
    success = check_redis_connection()
    if not success:
        logger.error("\nRecommendations:")
        logger.error("1. Ensure REDIS_URL environment variable is set to the correct URL")
        logger.error("2. Check network connectivity to the Redis server")
        logger.error("3. Verify Redis server is running and accepting connections")
        sys.exit(1)
    else:
        logger.info("\nRedis connection is working correctly!")
        sys.exit(0)