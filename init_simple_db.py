#!/usr/bin/env python3
"""Simple script to initialize the database."""

import os
import sys
import time
import psycopg2
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def wait_for_postgres(max_attempts=10, delay=2):
    """Wait for PostgreSQL to be available."""
    host = os.environ.get("DB_HOST", "postgres")
    port = os.environ.get("DB_PORT", "5432")
    dbname = os.environ.get("DB_NAME", "redbarsushi")
    user = os.environ.get("DB_USER", "app_user")
    password = os.environ.get("DB_PASSWORD", "password")
    
    logger.info(f"Waiting for PostgreSQL: {user}@{host}:{port}/{dbname}")
    
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f"Connection attempt {attempt}/{max_attempts}...")
            conn = psycopg2.connect(
                host=host,
                port=port,
                dbname=dbname,
                user=user,
                password=password,
                connect_timeout=5
            )
            conn.close()
            logger.info("✅ PostgreSQL is available")
            return True
        except Exception as e:
            logger.warning(f"PostgreSQL not ready yet: {e}")
            if attempt < max_attempts:
                logger.info(f"Waiting {delay} seconds...")
                time.sleep(delay)
    
    logger.error("❌ Could not connect to PostgreSQL after multiple attempts")
    return False

def create_tables():
    """Create basic tables in the database."""
    host = os.environ.get("DB_HOST", "postgres")
    port = os.environ.get("DB_PORT", "5432")
    dbname = os.environ.get("DB_NAME", "redbarsushi")
    user = os.environ.get("DB_USER", "app_user")
    password = os.environ.get("DB_PASSWORD", "password")
    
    try:
        logger.info("Connecting to PostgreSQL to create tables...")
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            connect_timeout=5
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Create basic tables
        logger.info("Creating menu_items table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS menu_items (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                price NUMERIC(10, 2) NOT NULL,
                plu VARCHAR(50) UNIQUE,
                is_available BOOLEAN DEFAULT TRUE
            )
        """)
        
        # Add some test data
        logger.info("Adding test data...")
        try:
            cursor.execute("""
                INSERT INTO menu_items (name, description, price, plu)
                VALUES 
                    ('California Roll', 'Crab, avocado, and cucumber', 12.99, 'CALROLL'),
                    ('Spicy Tuna Roll', 'Fresh tuna with spicy mayo', 14.99, 'SPICYTUNA')
                ON CONFLICT (plu) DO NOTHING
            """)
        except Exception as e:
            logger.warning(f"Could not insert test data: {e}")
        
        # Close connection
        cursor.close()
        conn.close()
        
        logger.info("✅ Database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")
        return False

if __name__ == "__main__":
    logger.info("=== Database Initialization Script ===")
    
    if wait_for_postgres():
        if create_tables():
            logger.info("✅ Database initialized successfully")
            sys.exit(0)
        else:
            logger.error("❌ Failed to create database tables")
            sys.exit(1)
    else:
        logger.error("❌ Could not connect to PostgreSQL")
        sys.exit(1)
