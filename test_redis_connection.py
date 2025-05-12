#!/usr/bin/env python3
"""Test script to verify Redis connection."""

import os
import redis
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def test_redis_connection():
    """Test if the application can connect to Redis."""
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    
    logger.info(f"Testing Redis connection to: {redis_url}")
    
    try:
        # Create Redis client
        r = redis.from_url(redis_url)
        
        # Test connection with a simple SET/GET operation
        r.set("test_key", "test_value")
        value = r.get("test_key")
        
        if value == b"test_value":
            logger.info("✅ Redis connection successful")
            return True
        else:
            logger.error(f"❌ Redis connection failed: Unexpected value: {value}")
            return False
    except Exception as e:
        logger.error(f"❌ Redis connection error: {e}")
        return False

if __name__ == "__main__":
    print("\n===== Testing Redis Connection =====")
    success = test_redis_connection()
    print(f"\nTest result: {'PASSED' if success else 'FAILED'}")
    print("====================================\n")