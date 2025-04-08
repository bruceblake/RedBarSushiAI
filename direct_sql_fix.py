#\!/usr/bin/env python
"""
Direct SQL migration script to add SMS tracking columns to the Order table.
This script connects directly to the database using psycopg2.
"""

import os
import sys
import psycopg2
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_direct_migration():
    """Add SMS tracking columns directly to the Order table using psycopg2"""
    # Use DATABASE_URL from environment (Render provides this)
    db_url = os.environ.get('DATABASE_URL') or os.environ.get('RENDER_DATABASE_URL')
    
    if not db_url:
        logger.error("No DATABASE_URL found in environment")
        logger.info("Please set the DATABASE_URL environment variable")
        return False
    
    logger.info(f"Using database URL (credentials hidden)")
    
    try:
        # Connect directly to the database
        connection = psycopg2.connect(db_url)
        connection.autocommit = False
        cursor = connection.cursor()
        
        try:
            # Check which tables exist
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            tables = [row[0] for row in cursor.fetchall()]
            logger.info(f"Found tables: {tables}")
            
            # Check for order table
            if 'order' not in tables:
                logger.error("Could not find 'order' table. This is unexpected.")
                return False
            
            # Get existing columns in order table
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'order'")
            existing_columns = [row[0] for row in cursor.fetchall()]
            logger.info(f"Existing columns in 'order' table: {existing_columns}")
            
            # Define columns to add
            columns_to_add = [
                ('sms_sid', 'VARCHAR(50)'),
                ('sms_status', 'VARCHAR(20)'),
                ('sms_error_code', 'INTEGER'),
                ('sms_error_message', 'VARCHAR(255)')
            ]
            
            # Add missing columns
            for column_name, column_type in columns_to_add:
                if column_name not in existing_columns:
                    logger.info(f"Adding column '{column_name}' to order table")
                    cursor.execute(f'ALTER TABLE "order" ADD COLUMN {column_name} {column_type}')
                else:
                    logger.info(f"Column '{column_name}' already exists")
            
            # Commit changes
            connection.commit()
            logger.info("Migration completed successfully")
            return True
            
        except Exception as e:
            connection.rollback()
            logger.error(f"Error during migration: {e}")
            return False
            
        finally:
            cursor.close()
            connection.close()
            
    except Exception as e:
        logger.error(f"Could not connect to database: {e}")
        return False

if __name__ == "__main__":
    success = run_direct_migration()
    if success:
        logger.info("Migration successful\!")
    else:
        logger.error("Migration failed\!")
    sys.exit(0 if success else 1)
