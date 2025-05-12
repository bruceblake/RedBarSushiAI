#!/usr/bin/env python3
"""Database and service connectivity checker."""

import os
import sys
import socket
import time
import asyncio
import asyncpg

def print_header(text):
    print(f"\n{'=' * 50}")
    print(f"  {text}")
    print(f"{'=' * 50}")

def check_environment():
    """Check for essential environment variables."""
    print_header("Environment Variables Check")
    
    essential_vars = [
        "DATABASE_URL", 
        "REDIS_URL", 
        "OPENAI_API_KEY", 
        "TWILIO_ACCOUNT_SID",
        "SECRET_KEY"
    ]
    
    all_present = True
    for var in essential_vars:
        value = os.environ.get(var)
        if value:
            masked_value = value[:5] + '...' + value[-5:] if len(value) > 10 else '[SHORT]'
            print(f"✅ {var} = {masked_value}")
        else:
            print(f"❌ {var} missing")
            all_present = False
    
    return all_present

def test_socket_connection(host, port, service_name, max_retries=5, retry_delay=2):
    """Test socket connectivity to a host:port."""
    print(f"Testing connection to {service_name} at {host}:{port}...")
    
    for attempt in range(1, max_retries + 1):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                print(f"✅ Successfully connected to {service_name} ({host}:{port})")
                return True
            else:
                print(f"❌ Attempt {attempt}/{max_retries}: Failed to connect to {service_name} ({host}:{port}): Error code {result}")
                
                if attempt < max_retries:
                    print(f"   Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
        except socket.error as e:
            print(f"❌ Attempt {attempt}/{max_retries}: Socket error connecting to {service_name} ({host}:{port}): {e}")
            
            if attempt < max_retries:
                print(f"   Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
    
    return False

async def test_db_connection(db_url, max_retries=5, retry_delay=2):
    """Test PostgreSQL connectivity using asyncpg."""
    print(f"Testing database connection to {db_url.split('@')[1] if '@' in db_url else 'database'}...")
    
    for attempt in range(1, max_retries + 1):
        try:
            conn = await asyncpg.connect(db_url)
            version = await conn.fetchval("SELECT version()")
            await conn.close()
            print(f"✅ Successfully connected to PostgreSQL database!")
            print(f"   Server version: {version}")
            return True
        except Exception as e:
            print(f"❌ Attempt {attempt}/{max_retries}: Database connection failed: {e}")
            
            if attempt < max_retries:
                print(f"   Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
    
    return False

async def main():
    # Check environment variables
    env_status = check_environment()
    
    # Extract service information from environment variables
    print_header("Network Connectivity Tests")
    
    db_url = os.environ.get("DATABASE_URL", "")
    redis_url = os.environ.get("REDIS_URL", "")
    
    # Test postgres connectivity
    postgres_status = False
    if db_url and "@" in db_url:
        try:
            # Extract host and port from DATABASE_URL
            # Format: postgresql://user:password@host:port/dbname
            host_part = db_url.split("@")[1].split("/")[0]
            host = host_part.split(":")[0]
            port = int(host_part.split(":")[1]) if ":" in host_part else 5432
            
            # Test socket connection
            postgres_status = test_socket_connection(host, port, "PostgreSQL")
        except Exception as e:
            print(f"❌ Error extracting database connection info: {e}")
    else:
        print("❌ DATABASE_URL not found or improperly formatted")
    
    # Test Redis connectivity
    redis_status = False
    if redis_url and "//" in redis_url:
        try:
            # Extract host and port from REDIS_URL
            # Format: redis://host:port/dbnum
            host_part = redis_url.split("//")[1].split("/")[0]
            host = host_part.split(":")[0]
            port = int(host_part.split(":")[1]) if ":" in host_part else 6379
            
            # Test socket connection
            redis_status = test_socket_connection(host, port, "Redis")
        except Exception as e:
            print(f"❌ Error extracting Redis connection info: {e}")
    else:
        print("❌ REDIS_URL not found or improperly formatted")
    
    # Test actual database connection
    print_header("Database Query Test")
    db_query_status = False
    if db_url:
        try:
            db_query_status = await test_db_connection(db_url)
        except Exception as e:
            print(f"❌ Error testing database connection: {e}")
    
    # Print summary
    print_header("Test Results Summary")
    print(f"Environment variables: {'✅' if env_status else '❌'}")
    print(f"PostgreSQL connectivity: {'✅' if postgres_status else '❌'}")
    print(f"Redis connectivity: {'✅' if redis_status else '❌'}")
    print(f"Database query: {'✅' if db_query_status else '❌'}")
    
    # Final status
    if env_status and postgres_status and redis_status and db_query_status:
        print("\n✅ All tests passed successfully!")
        return 0
    else:
        print("\n❌ Some tests failed. See details above.")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
