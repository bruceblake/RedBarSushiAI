#!/usr/bin/env python3
"""Test script for database connection."""

import os
import sys
import time
import psycopg2

def test_connection():
    """Test database connection with retry logic."""
    print("\n===== Testing Database Connection =====")
    
    # Get connection parameters from environment
    host = os.environ.get("DB_HOST", "db")
    port = os.environ.get("DB_PORT", "5432")
    dbname = os.environ.get("DB_NAME", "redbarsushi")
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "postgres")
    
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url:
        print(f"Using DATABASE_URL: {db_url}")
    else:
        print(f"Using connection parameters: {user}@{host}:{port}/{dbname}")
    
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"\nAttempt {attempt}/{max_attempts}...")
            conn = psycopg2.connect(
                host=host,
                port=port,
                dbname=dbname,
                user=user,
                password=password,
                connect_timeout=5
            )
            
            cursor = conn.cursor()
            cursor.execute("SELECT version()")
            version = cursor.fetchone()
            
            print(f"\n✅ Connection successful!")
            print(f"PostgreSQL version: {version[0]}")
            
            cursor.close()
            conn.close()
            return True
        
        except Exception as e:
            print(f"\n❌ Connection failed: {e}")
            if attempt < max_attempts:
                print(f"Retrying in 3 seconds...")
                time.sleep(3)
    
    return False

if __name__ == "__main__":
    if test_connection():
        print("\n✅ DATABASE CONNECTION: SUCCESS")
        sys.exit(0)
    else:
        print("\n❌ DATABASE CONNECTION: FAILED after multiple attempts")
        sys.exit(1)
