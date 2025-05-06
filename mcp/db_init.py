#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database initialization script for the MCP server.
This script ensures the database has all required tables and initial data.
"""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def init_database():
    """Initialize the database with required tables and seed data."""
    # Get database connection parameters from environment variables
    db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/redbarsushi")
    
    # Parse database URL
    if "://" in db_url:
        # Format: postgresql://user:password@host:port/database
        url_parts = db_url.split("://")[1]
        auth_parts, host_parts = url_parts.split("@")
        
        if ":" in auth_parts:
            user, password = auth_parts.split(":")
        else:
            user, password = auth_parts, ""
        
        if "/" in host_parts:
            host_port, dbname = host_parts.split("/")
        else:
            host_port, dbname = host_parts, "redbarsushi"
        
        if ":" in host_port:
            host, port = host_port.split(":")
        else:
            host, port = host_port, "5432"
    else:
        # Simple format fallback
        user = "postgres"
        password = "postgres"
        host = "postgres"
        port = "5432"
        dbname = "redbarsushi"
    
    # Connect to PostgreSQL server
    print(f"Connecting to PostgreSQL server at {host}:{port}...")
    conn = psycopg2.connect(
        user=user,
        password=password,
        host=host,
        port=port,
        database=dbname
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    
    try:
        # Create a cursor
        cursor = conn.cursor()
        
        # Apply schema if needed
        print("Checking if schema needs to be applied...")
        cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'menu_items')")
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            print("Schema does not exist. Applying schema...")
            # Read and execute schema file
            schema_file = os.path.join(os.path.dirname(__file__), "db", "init", "01_schema.sql")
            with open(schema_file, "r") as f:
                schema_sql = f.read()
                cursor.execute(schema_sql)
            print("Schema applied successfully.")
        else:
            print("Schema already exists.")
        
        # Apply seed data if needed
        print("Checking if seed data needs to be applied...")
        cursor.execute("SELECT COUNT(*) FROM menu_items")
        item_count = cursor.fetchone()[0]
        
        if item_count == 0:
            print("No seed data found. Applying seed data...")
            # Read and execute seed data file
            seed_file = os.path.join(os.path.dirname(__file__), "db", "init", "02_seed_data.sql")
            with open(seed_file, "r") as f:
                seed_sql = f.read()
                cursor.execute(seed_sql)
            print("Seed data applied successfully.")
        else:
            print(f"Seed data already exists ({item_count} menu items found).")
        
        # Close cursor
        cursor.close()
        
        print("Database initialization completed successfully.")
        return True
    
    except Exception as e:
        print(f"Error initializing database: {str(e)}")
        return False
    
    finally:
        # Close connection
        conn.close()

if __name__ == "__main__":
    init_database()