#!/usr/bin/env python
"""
Simple script to test database connection.
Run this from the Render dashboard to debug connection issues.
"""
import os
import sys
import time

def test_db_connection():
    # Print database URL info (without password)
    db_url = os.environ.get('SQLALCHEMY_DATABASE_URI', 'Not set')
    db_url_parts = db_url.split('@')
    
    if len(db_url_parts) > 1:
        # Get username and host without exposing password
        auth_parts = db_url_parts[0].split(':')
        if len(auth_parts) > 1:
            username = auth_parts[-2].split('/')[-1]
            host_info = db_url_parts[1]
            print(f"Database URL user: {username}")
            print(f"Database URL host: {host_info}")
    else:
        print(f"Database URL format unexpected: {db_url[:10]}...")
    
    # Check for Render-specific environment variables
    render_db_url = os.environ.get('RENDER_DATABASE_URL', 'Not set')
    if render_db_url != 'Not set':
        print("RENDER_DATABASE_URL is set")
        # Use this URL instead if available
        os.environ['SQLALCHEMY_DATABASE_URI'] = render_db_url
        print("Using RENDER_DATABASE_URL for connection")
    
    internal_db_url = os.environ.get('INTERNAL_DATABASE_URL', 'Not set') 
    if internal_db_url != 'Not set':
        print("INTERNAL_DATABASE_URL is set")
    
    # Test actual connection
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.exc import SQLAlchemyError
        
        db_url = os.environ.get('SQLALCHEMY_DATABASE_URI')
        if not db_url:
            print("SQLALCHEMY_DATABASE_URI is not set!")
            return False
        
        print(f"Attempting connection to database...")
        
        # Create engine and connect
        start = time.time()
        engine = create_engine(db_url)
        print("Engine created")
        
        connection = engine.connect()
        print("Connected successfully!")
        
        # Test a simple query
        result = connection.execute("SELECT 1").fetchone()
        print(f"Query result: {result}")
        
        # Close connection
        connection.close()
        end = time.time()
        
        print(f"Connection test successful! Time taken: {end-start:.2f} seconds")
        return True
        
    except SQLAlchemyError as e:
        print(f"SQLAlchemy error: {str(e)}")
        return False
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return False

if __name__ == "__main__":
    print("Database Connection Test")
    print("-----------------------")
    result = test_db_connection()
    print("Result:", "SUCCESS" if result else "FAILURE")
    sys.exit(0 if result else 1)