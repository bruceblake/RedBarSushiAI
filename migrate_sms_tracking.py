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
from app import create_app, db
from sqlalchemy import Column, String, Integer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_migration():
    """Add SMS tracking columns to the Order table"""
    # Create app context
    app = create_app()
    
    with app.app_context():
        # Get a connection
        connection = db.engine.connect()
        
        # Define the column additions
        columns_to_add = [
            ('sms_sid', 'VARCHAR(50)'),
            ('sms_status', 'VARCHAR(20)'),
            ('sms_error_code', 'INTEGER'),
            ('sms_error_message', 'VARCHAR(255)')
        ]
        
        # Start transaction
        trans = connection.begin()
        
        try:
            # Check which columns already exist
            # PostgreSQL way to check existing columns
            from sqlalchemy import text
            result = connection.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'order'"))
            existing_columns = [row[0] for row in result]
            
            # Add each column if it doesn't exist
            for column_name, column_type in columns_to_add:
                if column_name not in existing_columns:
                    logger.info(f"Adding column '{column_name}' to Order table")
                    sql = text(f'ALTER TABLE "order" ADD COLUMN {column_name} {column_type}')
                    connection.execute(sql)
                else:
                    logger.info(f"Column '{column_name}' already exists in Order table")
            
            # Commit the transaction
            trans.commit()
            logger.info("Migration completed successfully")
            return True
            
        except Exception as e:
            # Roll back on error
            trans.rollback()
            logger.error(f"Migration failed: {e}")
            return False
        finally:
            # Close the connection
            connection.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)