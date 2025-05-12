#!/usr/bin/env python3
"""Enhanced script to check database connection with detailed diagnostics."""

import os
import sys
import time
import socket
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def check_network():
    """Check network connectivity to the PostgreSQL server."""
    host = os.environ.get("DB_HOST", "postgres")
    port = int(os.environ.get("DB_PORT", "5432"))
    
    logger.info(f"Testing TCP connection to {host}:{port}...")
    try:
        # Simple socket connection test
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            logger.info(f"✅ TCP connection to {host}:{port} successful")
            return True
        else:
            logger.error(f"❌ Could not connect to {host}:{port} - error code: {result}")
            return False
    except Exception as e:
        logger.error(f"❌ Network error: {e}")
        return False

def check_environment_variables():
    """Check if necessary environment variables are set."""
    variables = [
        "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD",
        "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "DATABASE_URL"
    ]
    
    logger.info("Checking environment variables...")
    all_set = True
    
    for var in variables:
        value = os.environ.get(var)
        if value:
            logger.info(f"✅ {var} is set: {value}")
        else:
            logger.error(f"❌ {var} is NOT set!")
            all_set = False
    
    return all_set

def check_db_connection():
    """Check if database connection works with detailed error handling."""
    logger.info("\nDatabase Connection Diagnostics:")
    logger.info("-" * 40)
    
    # Check environment variables first
    if not check_environment_variables():
        logger.error("❌ Some required environment variables are missing")
    
    # Check network connectivity
    if not check_network():
        logger.error("❌ Network connection to database server failed")
        return False
    
    # Get connection parameters from environment
    host = os.environ.get("DB_HOST", "postgres")
    port = os.environ.get("DB_PORT", "5432")
    dbname = os.environ.get("DB_NAME", "redbarsushi")
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "postgres")
    
    try:
        import psycopg2
        # Try connection
        logger.info("Attempting database connection...")
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            connect_timeout=10
        )
        
        # Check connection
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()
        
        logger.info("\n✅ Connection successful!")
        logger.info(f"PostgreSQL version: {version[0]}")
        
        # Check if tables exist
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        tables = cursor.fetchall()
        if tables:
            logger.info("\nExisting tables:")
            for table in tables:
                logger.info(f"- {table[0]}")
        else:
            logger.warning("\n⚠️ No tables found in the database.")
        
        cursor.close()
        conn.close()
        
        return True
    except ImportError:
        logger.error("❌ psycopg2 module not found. Please install it with: pip install psycopg2-binary")
        return False
    except psycopg2.OperationalError as e:
        if "password authentication" in str(e):
            logger.error(f"\n❌ Password authentication failed: {e}")
            logger.error("\nDetailed troubleshooting:")
            logger.error(f"1. Using username: '{user}'")
            logger.error(f"2. Using password: '{'*' * len(password)}'")
            logger.error(f"3. Database name: '{dbname}'")
            logger.error(f"4. Host: '{host}'")
            logger.error(f"5. Port: '{port}'")
            logger.error("\nPossible solutions:")
            logger.error("- Ensure PostgreSQL environment variables are correctly set")
            logger.error("- Try running 'docker exec -it redbarsushi-postgres-dev psql -U postgres' to test login")
            logger.error("- Check if database initialization scripts ran successfully")
        elif "could not connect" in str(e) or "could not translate" in str(e):
            logger.error(f"\n❌ Connection error: {e}")
            logger.error("🔌 Ensure the postgres container is running and healthy")
            logger.error("🔌 Check network connectivity between containers")
        else:
            logger.error(f"\n❌ Database error: {e}")
        return False
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}")
        return False

def retry_check_db(max_attempts=3, delay=5):
    """Retry the database connection check multiple times with delay."""
    for attempt in range(1, max_attempts + 1):
        logger.info(f"\nConnection attempt {attempt}/{max_attempts}...")
        
        if check_db_connection():
            logger.info(f"\n✅ Connection successful on attempt {attempt}")
            return True
            
        if attempt < max_attempts:
            logger.info(f"\n⏱️ Waiting {delay} seconds before next attempt...")
            time.sleep(delay)
            
    logger.error(f"\n❌ All {max_attempts} connection attempts failed")
    return False

if __name__ == "__main__":
    logger.info("Starting enhanced database connection check...")
    if retry_check_db():
        logger.info("\n✅ DATABASE CONNECTION CHECK: SUCCESS")
        sys.exit(0)
    else:
        logger.error("\n❌ DATABASE CONNECTION CHECK: FAILED")
        sys.exit(1)
