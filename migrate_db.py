#!/usr/bin/env python
"""
Database migration script to add new columns to the Order table.
Run this script to update your database schema without losing existing data.
"""
import os
import sys
import logging
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime
from sqlalchemy.sql import text

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_database_url():
    """Get the database URL from environment or use a default for development."""
    # Try to get from environment variable
    database_url = os.environ.get('DATABASE_URL')
    
    # If not available, use a default for local development
    if not database_url:
        database_url = 'postgresql://postgres:postgres@localhost:5432/redbar'
        logger.warning(f"No DATABASE_URL found in environment, using default: {database_url}")
    
    # Fix common issue with postgres:// vs postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
    return database_url

def add_column_if_not_exists(conn, table_name, column_name, column_type, nullable=True):
    """Add a column to a table if it doesn't exist."""
    # Check if the column exists
    try:
        result = conn.execute(text(f"SELECT {column_name} FROM {table_name} LIMIT 0"))
        logger.info(f"Column {column_name} already exists in {table_name}.")
        return False  # Column exists
    except Exception:
        # Column doesn't exist, add it
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} {'NULL' if nullable else 'NOT NULL'}"))
        logger.info(f"Added column {column_name} to {table_name}.")
        return True  # Column added

def run_migration():
    """Run the database migration."""
    database_url = get_database_url()
    
    try:
        # Connect to the database
        logger.info(f"Connecting to database: {database_url}")
        engine = create_engine(database_url)
        
        # Start a connection
        with engine.connect() as conn:
            # Add necessary columns to order table
            added_any = False
            
            # Deliverect status tracking columns
            added_any |= add_column_if_not_exists(conn, '"order"', 'status_code', 'INTEGER')
            added_any |= add_column_if_not_exists(conn, '"order"', 'status_updated_at', 'TIMESTAMP')
            
            # Delivery tracking columns
            added_any |= add_column_if_not_exists(conn, '"order"', 'delivery_status', 'VARCHAR(30)')
            added_any |= add_column_if_not_exists(conn, '"order"', 'delivery_status_code', 'INTEGER')
            added_any |= add_column_if_not_exists(conn, '"order"', 'courier_name', 'VARCHAR(50)')
            added_any |= add_column_if_not_exists(conn, '"order"', 'courier_phone', 'VARCHAR(20)')
            added_any |= add_column_if_not_exists(conn, '"order"', 'estimated_delivery_time', 'TIMESTAMP')
            
            # Commit the transaction
            conn.execute(text("COMMIT"))
            
            if added_any:
                logger.info("Migration completed successfully!")
            else:
                logger.info("No migration needed - all columns already exist.")
            
            return True
    except Exception as e:
        logger.error(f"Error during migration: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting database migration")
    success = run_migration()
    if success:
        logger.info("Migration completed successfully")
        sys.exit(0)
    else:
        logger.error("Migration failed")
        sys.exit(1)