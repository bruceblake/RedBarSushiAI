#!/usr/bin/env python
"""
Migration script to add SMS tracking columns to the Order table on Render.
This is a specialized version of the script that works directly with the render_database_url.
This script adds the following columns to the Order table:
- sms_sid: Twilio SMS SID
- sms_status: Twilio SMS status
- sms_error_code: Error code if SMS delivery failed
- sms_error_message: Error message if SMS delivery failed

USAGE: RENDER_DATABASE_URL="your-render-postgres-url" python migrate_sms_tracking_render.py
"""

import sys
import os
import logging
import psycopg2
from sqlalchemy import text, create_engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_migration_direct_psycopg2():
    """Add SMS tracking columns to the Order table using direct psycopg2 connection"""
    # Get database URL from environment
    db_url = os.environ.get('RENDER_DATABASE_URL')
    if not db_url:
        logger.error("RENDER_DATABASE_URL not set in environment")
        return False
    
    logger.info(f"Using database URL: {db_url.split('@')[1] if '@' in db_url else 'DB URL (credentials hidden)'}")
    
    try:
        # Connect to the database directly with psycopg2
        connection = psycopg2.connect(db_url)
        connection.autocommit = False
        cursor = connection.cursor()
        
        # Define the column additions
        columns_to_add = [
            ('sms_sid', 'VARCHAR(50)'),
            ('sms_status', 'VARCHAR(20)'),
            ('sms_error_code', 'INTEGER'),
            ('sms_error_message', 'VARCHAR(255)')
        ]
        
        try:
            # Check if table exists
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            tables = [row[0] for row in cursor.fetchall()]
            logger.info(f"Found tables: {tables}")
            
            if 'order' not in tables:
                logger.error("'order' table not found. Please check database schema.")
                return False
            
            # Get existing columns
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'order'")
            existing_columns = [row[0] for row in cursor.fetchall()]
            logger.info(f"Existing columns in 'order' table: {existing_columns}")
            
            # Add each column if it doesn't exist
            for column_name, column_type in columns_to_add:
                if column_name not in existing_columns:
                    logger.info(f"Adding column '{column_name}' to Order table")
                    cursor.execute(f'ALTER TABLE "order" ADD COLUMN {column_name} {column_type}')
                    logger.info(f"Column '{column_name}' added successfully")
                else:
                    logger.info(f"Column '{column_name}' already exists in Order table")
            
            # Commit transaction
            connection.commit()
            logger.info("All columns added successfully")
            return True
            
        except Exception as e:
            connection.rollback()
            logger.error(f"Database error: {e}")
            return False
        finally:
            cursor.close()
            connection.close()
    except Exception as e:
        logger.error(f"Connection error: {e}")
        return False

def run_migration():
    
    # Define the column additions
    columns_to_add = [
        ('sms_sid', 'VARCHAR(50)'),
        ('sms_status', 'VARCHAR(20)'),
        ('sms_error_code', 'INTEGER'),
        ('sms_error_message', 'VARCHAR(255)')
    ]
    
    # Create an engine to connect to the database
    engine = create_engine(db_url)
    
    try:
        # Get a connection
        with engine.connect() as connection:
            # Start transaction
            with connection.begin():
                # Log the table name for better debugging
                logger.info("Checking for 'order' table in the database schema...")
                schema_query = text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
                tables_result = connection.execute(schema_query)
                tables = [row[0] for row in tables_result]
                logger.info(f"Found tables: {tables}")
                
                # Now check for columns
                result = connection.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'order'"))
                existing_columns = [row[0] for row in result]
                logger.info(f"Existing columns in 'order' table: {existing_columns}")
                
                # Check if the 'order' table exists
                if 'order' not in tables:
                    logger.error("'order' table not found in database - please check table name")
                    return False
                
                # Add each column if it doesn't exist
                for column_name, column_type in columns_to_add:
                    if column_name not in existing_columns:
                        logger.info(f"Adding column '{column_name}' to Order table")
                        sql = text(f'ALTER TABLE "order" ADD COLUMN {column_name} {column_type}')
                        connection.execute(sql)
                        logger.info(f"Successfully added column '{column_name}'")
                    else:
                        logger.info(f"Column '{column_name}' already exists in Order table")
            
            logger.info("Migration completed successfully")
            return True
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False

if __name__ == "__main__":
    # Try both methods, starting with direct psycopg2
    logger.info("Attempting migration with direct psycopg2 connection...")
    success = run_migration_direct_psycopg2()
    
    if not success:
        logger.info("Direct psycopg2 approach failed, trying SQLAlchemy approach...")
        success = run_migration()
    
    if success:
        logger.info("Migration completed successfully!")
    else:
        logger.error("All migration attempts failed.")
    
    sys.exit(0 if success else 1)