#!/usr/bin/env python3
"""Initialize database for RedBarSushiAI with improved error handling."""

import os
import sys
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def connect_with_retry(max_attempts=3, delay=5):
    """Attempt to connect to PostgreSQL with retries."""
    host = os.environ.get("DB_HOST", "postgres")
    port = os.environ.get("DB_PORT", "5432")
    dbname = os.environ.get("DB_NAME", "redbarsushi")
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "postgres")
    
    logger.info(f"Connecting to PostgreSQL: {user}@{host}:{port}/{dbname}")
    
    try:
        import psycopg2
    except ImportError:
        logger.error("❌ psycopg2 module not found. Please install it with: pip install psycopg2-binary")
        sys.exit(1)
    
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f"Connection attempt {attempt}/{max_attempts}...")
            
            # Connect to PostgreSQL
            conn = psycopg2.connect(
                host=host,
                port=port,
                dbname=dbname,
                user=user,
                password=password,
                connect_timeout=10
            )
            
            # Return the connection if successful
            logger.info("✅ Connected to database successfully")
            return conn
            
        except psycopg2.OperationalError as e:
            logger.error(f"Connection attempt {attempt} failed: {e}")
            
            if attempt < max_attempts:
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                logger.error("❌ All connection attempts failed")
                raise
                
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

def create_tables():
    """Create required database tables if they don't exist."""
    try:
        # Connect to PostgreSQL with retry
        conn = connect_with_retry()
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
            logger.info("Adding sample menu items for testing")
            cursor.execute("""
                INSERT INTO menu_categories (name, description)
                VALUES ('Rolls', 'Sushi rolls')
            """)
            
            # Get the inserted category id
            cursor.execute("SELECT id FROM menu_categories WHERE name='Rolls'")
            category_id = cursor.fetchone()[0]
            
            # Insert several menu items for testing
            menu_items = [
                ('California Roll', 'Crab, avocado, and cucumber', 12.99, 'CALROLL'),
                ('Spicy Tuna Roll', 'Fresh tuna with spicy mayo', 14.99, 'SPICY-TUNA'),
                ('Rainbow Roll', 'California roll topped with assorted sashimi', 16.99, 'RAINBOW')
            ]
            
            for name, desc, price, plu in menu_items:
                cursor.execute("""
                    INSERT INTO menu_items (name, description, price, plu)
                    VALUES (%s, %s, %s, %s)
                """, (name, desc, price, plu))
            
            logger.info(f"Added {len(menu_items)} sample menu items")
        
        # Close cursor and connection
        cursor.close()
        conn.close()
        
        logger.info("✅ Database initialization completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error initializing database: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting database initialization")
    if create_tables():
        logger.info("✅ Database setup successful")
        sys.exit(0)
    else:
        logger.error("❌ Database setup failed")
        sys.exit(1)
