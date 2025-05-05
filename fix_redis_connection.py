#!/usr/bin/env python
"""
Fix Redis connection issues in RedBarSushiAI by updating environment variables
and modifying Redis connection logic to handle Docker and staging environment.
"""

import os
import sys
import re
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger("redis_fix")

def detect_environment():
    """Detect the current environment."""
    if os.environ.get("RENDER_SERVICE_ID"):
        return "render"
    elif os.environ.get("DOCKER"):
        return "docker"
    else:
        return "local"

def fix_redis_url(redis_url, environment):
    """Fix a Redis URL for the given environment."""
    if not redis_url:
        if environment == "render":
            return "redis://red-ceqpb6rf1sgc739ut8e0:6379/0"
        elif environment == "docker":
            return "redis://redis:6379/0"
        else:
            return "redis://localhost:6379/0"
    
    # Ensure URL has redis:// prefix
    if not redis_url.startswith("redis://"):
        if ":" in redis_url and "/" in redis_url:
            # Format appears to be hostname:port/db
            host_port, db = redis_url.rsplit("/", 1)
            host, port = host_port.split(":")
            # Make sure we have a valid DB number
            try:
                db_num = int(db)
            except ValueError:
                db_num = 0
            # Reconstruct proper Redis URL
            redis_url = f"redis://{host}:{port}/{db_num}"
        else:
            # Just prefix with redis://
            redis_url = f"redis://{redis_url}"
    
    # For Render, we may need to use a specific Redis host
    if environment == "render":
        # Extract the host from the URL
        pattern = r'redis://([^:]+):'
        match = re.search(pattern, redis_url)
        if match:
            host = match.group(1)
            # If it's localhost, replace with Render Redis service
            if host == "localhost":
                redis_url = redis_url.replace("localhost", "red-ceqpb6rf1sgc739ut8e0")
    
    # For Docker, we should use the service name
    elif environment == "docker":
        # Extract the host from the URL
        pattern = r'redis://([^:]+):'
        match = re.search(pattern, redis_url)
        if match:
            host = match.group(1)
            # If it's localhost, replace with Docker service name
            if host == "localhost":
                redis_url = redis_url.replace("localhost", "redis")
    
    return redis_url

def update_env_variables():
    """Update environment variables for Redis connections."""
    environment = detect_environment()
    logger.info(f"Detected environment: {environment}")
    
    # Get current environment variables
    redis_url = os.environ.get("REDIS_URL")
    celery_broker_url = os.environ.get("CELERY_BROKER_URL")
    celery_result_backend = os.environ.get("CELERY_RESULT_BACKEND")
    
    # Fix URLs
    fixed_redis_url = fix_redis_url(redis_url, environment)
    fixed_celery_broker_url = fix_redis_url(celery_broker_url or redis_url, environment)
    fixed_celery_result_backend = fix_redis_url(celery_result_backend or redis_url, environment)
    
    # Update environment variables
    os.environ["REDIS_URL"] = fixed_redis_url
    os.environ["CELERY_BROKER_URL"] = fixed_celery_broker_url
    os.environ["CELERY_RESULT_BACKEND"] = fixed_celery_result_backend
    
    logger.info(f"Updated REDIS_URL: {fixed_redis_url}")
    logger.info(f"Updated CELERY_BROKER_URL: {fixed_celery_broker_url}")
    logger.info(f"Updated CELERY_RESULT_BACKEND: {fixed_celery_result_backend}")
    
    # Return the updated URLs
    return {
        "REDIS_URL": fixed_redis_url,
        "CELERY_BROKER_URL": fixed_celery_broker_url,
        "CELERY_RESULT_BACKEND": fixed_celery_result_backend
    }

def test_redis_connection(redis_url):
    """Test connection to Redis using the provided URL."""
    try:
        import redis
        client = redis.from_url(redis_url, socket_timeout=2.0)
        client.ping()
        logger.info(f"Successfully connected to Redis at {redis_url}")
        return True
    except ImportError:
        logger.error("Redis module not installed")
        return False
    except Exception as e:
        logger.error(f"Failed to connect to Redis at {redis_url}: {e}")
        return False

def fix_redis_code_files():
    """Update Redis connection code in application files."""
    files_to_update = [
        "/home/proxyie/MySoftware/RedBarSushiAI/app/utils/conversation_store.py",
        "/home/proxyie/MySoftware/RedBarSushiAI/app/utils/menu_db_store.py",
        "/home/proxyie/MySoftware/RedBarSushiAI/app/utils/menu_cache_sdk.py"
    ]
    
    # Update each file to handle Redis connection issues gracefully
    for file_path in files_to_update:
        try:
            if not os.path.exists(file_path):
                logger.warning(f"File not found: {file_path}")
                continue
            
            # Read file content
            with open(file_path, 'r') as file:
                content = file.read()
            
            # Make Redis connection more robust
            if "redis_url = os.environ.get" in content and "redis://localhost" in content:
                # Replace default localhost Redis URL with more robust logic
                pattern = r'redis_url = os.environ.get\([\'"]([^\'"]*)[\'"](, [\'"]redis://localhost:6379/\d+[\'"]\))'
                replacement = r'redis_url = os.environ.get(\1, "")\n            if not redis_url:\n                # Try alternative environment variables\n                redis_url = os.environ.get("REDIS_URL") or os.environ.get("CELERY_BROKER_URL") or "redis://localhost:6379/0"\n            \n            # For Docker environment\n            if os.environ.get("DOCKER") and "localhost" in redis_url:\n                redis_url = redis_url.replace("localhost", "redis")\n            \n            # For Render environment\n            if os.environ.get("RENDER_SERVICE_ID") and "localhost" in redis_url:\n                redis_url = redis_url.replace("localhost", "red-ceqpb6rf1sgc739ut8e0")'
                updated_content = re.sub(pattern, replacement, content)
                
                # Write updated content back to file
                with open(file_path, 'w') as file:
                    file.write(updated_content)
                
                logger.info(f"Updated Redis connection logic in {file_path}")
            else:
                logger.info(f"No Redis connection pattern to update in {file_path}")
        
        except Exception as e:
            logger.error(f"Error updating {file_path}: {e}")

if __name__ == "__main__":
    logger.info("Starting Redis connection fix")
    
    # Update environment variables
    updated_urls = update_env_variables()
    
    # Test Redis connection
    test_redis_connection(updated_urls["REDIS_URL"])
    
    # Update code files
    fix_redis_code_files()
    
    logger.info("Redis connection fix completed")