#!/usr/bin/env python3
"""Initialize database for RedBarSushiAI."""

import os
import sys
import psycopg2
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def create_tables():
    """Create required database tables if they don't exist."""
    # Get connection parameters from environment
    host = os.environ.get("DB_HOST", "postgres")
    port = os.environ.get("DB_PORT", "5432")
    dbname = os.environ.get("DB_NAME", "redbarsushi")
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "postgres")
    
    logger.info(f"Connecting to PostgreSQL: {user}@{host}:{port}/{dbname}")
    
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Create basic tables if they don't exist
        logger.info("Creating menu_items table if it doesn't exist")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS menu_items (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                price NUMERIC(10, 2) NOT NULL,
                plu VARCHAR(50) UNIQUE,
                deliverect_item_id VARCHAR(100),
                is_available BOOLEAN DEFAULT TRUE,
                is_combo BOOLEAN DEFAULT FALSE,
                is_variant BOOLEAN DEFAULT FALSE,
                image_url TEXT,
                snoozed_until TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        logger.info("Creating menu_categories table if it doesn't exist")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS menu_categories (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                deliverect_category_id VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        logger.info("Creating menu_modifiers table if it doesn't exist")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS menu_modifiers (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                price_change NUMERIC(10, 2) DEFAULT 0,
                plu VARCHAR(50) UNIQUE,
                deliverect_modifier_id VARCHAR(100),
                is_available BOOLEAN DEFAULT TRUE,
                snoozed_until TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Add a simple menu item for testing if none exists
        cursor.execute("SELECT COUNT(*) FROM menu_items")
        count = cursor.fetchone()[0]
        
        if count == 0:
            logger.info("Adding sample menu item for testing")
            cursor.execute("""
                INSERT INTO menu_items (name, description, price, plu)
                VALUES ('California Roll', 'Crab, avocado, and cucumber', 12.99, 'CALROLL')
            """)
            
            cursor.execute("""
                INSERT INTO menu_categories (name, description)
                VALUES ('Rolls', 'Sushi rolls')
            """)
        
        # Close cursor and connection
        cursor.close()
        conn.close()
        
        logger.info("Database initialization completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting database initialization")
    if create_tables():
        logger.info("Database setup successful")
        sys.exit(0)
    else:
        logger.error("Database setup failed")
        sys.exit(1)