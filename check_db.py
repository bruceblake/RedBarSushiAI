#!/usr/bin/env python3
"""Simple script to check database connection."""

import os
import sys
import psycopg2

def check_db_connection():
    """Check if database connection works."""
    print("Database Connection Diagnostics:")
    print("-" * 40)
    
    # Get connection parameters from environment
    host = os.environ.get("DB_HOST", "postgres")
    port = os.environ.get("DB_PORT", "5432")
    dbname = os.environ.get("DB_NAME", "redbarsushi")
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "postgres")
    
    # Display connection info
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Database: {dbname}")
    print(f"User: {user}")
    print(f"Password: {'*' * len(password)}")
    
    # Try PostgreSQL URL format
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url:
        print(f"DATABASE_URL: {db_url.split('@')[0].split('://')[-1]}:****@{db_url.split('@')[-1]}")
    
    # Try connection
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password
        )
        
        # Check connection
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()
        
        print("\nConnection successful!")
        print(f"PostgreSQL version: {version[0]}")
        
        # Check if tables exist
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        tables = cursor.fetchall()
        if tables:
            print("\nExisting tables:")
            for table in tables:
                print(f"- {table[0]}")
        else:
            print("\nNo tables found in the database.")
        
        cursor.close()
        conn.close()
        
        return True
    except Exception as e:
        print(f"\nConnection failed: {e}")
        return False

if __name__ == "__main__":
    if check_db_connection():
        print("\nDatabase connection check: SUCCESS")
        sys.exit(0)
    else:
        print("\nDatabase connection check: FAILED")
        sys.exit(1)