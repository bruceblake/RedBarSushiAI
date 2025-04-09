#!/usr/bin/env python
"""
Migration script to add SMS tracking columns to the Order table.
This script adds the following columns to the Order table:
- sms_sid: Twilio SMS SID
- sms_status: Twilio SMS status
- sms_error_code: Error code if SMS delivery failed
- sms_error_message: Error message if SMS delivery failed
"""

import sys
import logging
import os
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_database_url():
    """Get the database URL from the environment or app config."""
    # First check environment variable
    database_url = os.environ.get('DATABASE_URL')
    
    # If not found, try to get from app config
    if not database_url:
        try:
            from app import create_app
            app = create_app()
            database_url = app.config.get('SQLALCHEMY_DATABASE_URI')
        except Exception as e:
            logger.error(f"Failed to get database URL from app config: {e}")
            sys.exit(1)
    
    if not database_url:
        logger.error("No database URL found. Set DATABASE_URL environment variable or configure SQLALCHEMY_DATABASE_URI in app config.")
        sys.exit(1)
        
    return database_url

def parse_db_url(url):
    """Parse database URL into connection parameters."""
    parsed = urlparse(url)
    return {
        'dbname': parsed.path[1:],
        'user': parsed.username,
        'password': parsed.password,
        'host': parsed.hostname,
        'port': parsed.port or 5432
    }

def run_migration():
    """Add SMS tracking columns to the Order table"""
    database_url = get_database_url()
    
    try:
        # Parse the database URL
        logger.info(f"Connecting to database: {database_url}")
        db_params = parse_db_url(database_url)
        
        # Connect directly using psycopg2 to avoid transaction issues
        conn = psycopg2.connect(
            user=db_params['user'],
            password=db_params['password'],
            host=db_params['host'],
            port=db_params['port'],
            dbname=db_params['dbname']
        )
        
        # Set isolation level to avoid transaction issues
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Define the column additions
        columns_to_add = [
            ('sms_sid', 'VARCHAR(50)'),
            ('sms_status', 'VARCHAR(20)'),
            ('sms_error_code', 'INTEGER'),
            ('sms_error_message', 'VARCHAR(255)')
        ]
        
        try:
            # Check if the order table exists
            logger.info("Checking for 'order' table in the database schema...")
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            tables = [row[0] for row in cursor.fetchall()]
            logger.info(f"Found tables: {tables}")
            
            if 'order' not in tables:
                logger.error("'order' table not found in database!")
                return False
            
            # Check which columns already exist
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'order'")
            existing_columns = [row[0] for row in cursor.fetchall()]
            logger.info(f"Existing columns in 'order' table: {existing_columns}")
            
            # Add each column if it doesn't exist
            for column_name, column_type in columns_to_add:
                if column_name not in existing_columns:
                    logger.info(f"Adding column '{column_name}' to Order table")
                    cursor.execute(f'ALTER TABLE "order" ADD COLUMN {column_name} {column_type}')
                else:
                    logger.info(f"Column '{column_name}' already exists in Order table")
            
            logger.info("Migration completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)