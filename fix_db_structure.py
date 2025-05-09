#!/usr/bin/env python3
"""
Script to fix database structure issues in the RedBarSushiAI application.
This script adds the missing reference_handler column to the menu_modifiers table.
"""

import os
import sys
import logging
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

try:
    from sqlalchemy import create_engine, text
    logger.info("Successfully imported sqlalchemy")
except ImportError:
    logger.error("SQLAlchemy is required to run this script. Please install it using 'pip install sqlalchemy'")
    sys.exit(1)

def get_database_url():
    """Get the database URL from environment variables or use default for dev."""
    # Try different environment variables depending on deployment
    db_url = os.environ.get('DATABASE_URL')
    
    if not db_url:
        db_url = "postgresql://postgres:postgres@postgres:5432/redbarsushi"
        logger.warning(f"DATABASE_URL not found, using default: {db_url}")
    
    return db_url

def add_missing_column():
    """Add the missing reference_handler column to menu_modifiers table."""
    db_url = get_database_url()
    
    try:
        # Create engine
        logger.info(f"Connecting to database: {db_url}")
        engine = create_engine(db_url)
        
        # Connect to the database
        with engine.connect() as connection:
            # Check if column already exists
            check_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'menu_modifiers' AND column_name = 'reference_handler'
            """)
            
            result = connection.execute(check_query)
            column_exists = result.fetchone() is not None
            
            if column_exists:
                logger.info("Column 'reference_handler' already exists in menu_modifiers table")
            else:
                # Add the missing column
                add_column_query = text("""
                    ALTER TABLE menu_modifiers ADD COLUMN reference_handler TEXT
                """)
                
                logger.info("Adding 'reference_handler' column to menu_modifiers table")
                connection.execute(add_column_query)
                connection.commit()
                logger.info("Column added successfully")
        
        return True
    
    except Exception as e:
        logger.error(f"Error fixing database structure: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting database structure fix script")
    
    # Add missing column to menu_modifiers table
    success = add_missing_column()
    
    if success:
        logger.info("Database structure fix completed successfully")
    else:
        logger.error("Failed to fix database structure. Please check the logs for details.")
        sys.exit(1)