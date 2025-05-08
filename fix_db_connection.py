#!/usr/bin/env python3
# Database connection fix script for RedBarSushiAI

import os
import sys
import time
import logging
import argparse
import psycopg2
import redis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("db_connection_fix")

def parse_args():
    parser = argparse.ArgumentParser(description="Fix database connections for RedBarSushiAI")
    parser.add_argument("--postgres-host", default="postgres", help="PostgreSQL host")
    parser.add_argument("--postgres-port", default=5432, type=int, help="PostgreSQL port")
    parser.add_argument("--postgres-user", default="postgres", help="PostgreSQL user")
    parser.add_argument("--postgres-password", default="postgres", help="PostgreSQL password")
    parser.add_argument("--postgres-db", default="redbarsushi", help="PostgreSQL database name")
    parser.add_argument("--redis-host", default="redis", help="Redis host")
    parser.add_argument("--redis-port", default=6379, type=int, help="Redis port")
    parser.add_argument("--redis-db", default=0, type=int, help="Redis database number")
    parser.add_argument("--max-retries", default=5, type=int, help="Maximum number of connection retries")
    parser.add_argument("--retry-delay", default=5, type=int, help="Delay between retries in seconds")
    parser.add_argument("--update-env", action="store_true", help="Update environment variables if successful")
    return parser.parse_args()

def test_postgres_connection(host, port, user, password, dbname, max_retries=5, retry_delay=5):
    """Test PostgreSQL connection with retries"""
    logger.info(f"Testing PostgreSQL connection to {host}:{port}/{dbname} as {user}")
    
    for attempt in range(1, max_retries + 1):
        try:
            connection_string = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
            if attempt > 1:
                logger.info(f"Retry attempt {attempt}/{max_retries}...")
            
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                dbname=dbname
            )
            
            # Test the connection
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            cursor.close()
            conn.close()
            
            logger.info(f"Successfully connected to PostgreSQL: {version[0]}")
            return True, connection_string
            
        except psycopg2.OperationalError as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            if attempt < max_retries:
                logger.info(f"Waiting {retry_delay} seconds before retrying...")
                time.sleep(retry_delay)
            else:
                logger.error("Maximum retry attempts reached. Could not connect to PostgreSQL.")
                return False, str(e)
    
    return False, "Maximum retry attempts reached"

def test_redis_connection(host, port, db=0, max_retries=5, retry_delay=5):
    """Test Redis connection with retries"""
    logger.info(f"Testing Redis connection to {host}:{port}/{db}")
    
    for attempt in range(1, max_retries + 1):
        try:
            connection_string = f"redis://{host}:{port}/{db}"
            if attempt > 1:
                logger.info(f"Retry attempt {attempt}/{max_retries}...")
            
            r = redis.Redis(host=host, port=port, db=db)
            r.ping()  # This will raise an exception if the connection fails
            
            logger.info("Successfully connected to Redis")
            return True, connection_string
            
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
            logger.error(f"Failed to connect to Redis: {e}")
            if attempt < max_retries:
                logger.info(f"Waiting {retry_delay} seconds before retrying...")
                time.sleep(retry_delay)
            else:
                logger.error("Maximum retry attempts reached. Could not connect to Redis.")
                return False, str(e)
    
    return False, "Maximum retry attempts reached"

def update_environment_variables(postgres_url, redis_url):
    """Update environment variables with successful connection details"""
    logger.info("Updating environment variables...")
    
    # Find .env file or create one
    env_file = '.env'
    if not os.path.exists(env_file):
        with open(env_file, 'w') as f:
            f.write("# Environment variables for RedBarSushiAI\n\n")
    
    # Read existing .env content
    with open(env_file, 'r') as f:
        env_lines = f.readlines()
    
    # Update or add variables
    def update_var(lines, var_name, var_value):
        for i, line in enumerate(lines):
            if line.startswith(f"{var_name}="):
                lines[i] = f"{var_name}={var_value}\n"
                return lines, True
        
        lines.append(f"{var_name}={var_value}\n")
        return lines, False
    
    env_lines, postgres_updated = update_var(env_lines, "DATABASE_URL", postgres_url)
    env_lines, redis_updated = update_var(env_lines, "REDIS_URL", redis_url)
    
    # Write updated .env file
    with open(env_file, 'w') as f:
        f.writelines(env_lines)
    
    logger.info(f"Environment variables updated: DATABASE_URL " + 
                f"({'updated' if postgres_updated else 'added'}) and REDIS_URL " +
                f"({'updated' if redis_updated else 'added'})")
    
    return True

def main():
    """Main function to test and fix database connections"""
    args = parse_args()
    
    # Test PostgreSQL connection
    pg_success, pg_result = test_postgres_connection(
        args.postgres_host,
        args.postgres_port,
        args.postgres_user,
        args.postgres_password,
        args.postgres_db,
        args.max_retries,
        args.retry_delay
    )
    
    # Test Redis connection
    redis_success, redis_result = test_redis_connection(
        args.redis_host,
        args.redis_port,
        args.redis_db,
        args.max_retries,
        args.retry_delay
    )
    
    # Overall status
    if pg_success and redis_success:
        logger.info("All database connections successful!")
        
        # Update environment variables if requested
        if args.update_env:
            update_environment_variables(pg_result, redis_result)
            logger.info("Environment variables updated successfully.")
        
        return 0
    else:
        logger.error("Database connection test failed!")
        if not pg_success:
            logger.error(f"PostgreSQL error: {pg_result}")
        if not redis_success:
            logger.error(f"Redis error: {redis_result}")
        
        return 1

if __name__ == "__main__":
    sys.exit(main())