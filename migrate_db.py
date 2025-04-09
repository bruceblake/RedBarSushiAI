#!/usr/bin/env python
"""
Database migration script to add new columns to the Order table.
Run this script to update your database schema without losing existing data.
"""
import os
import sys
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

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

def parse_db_url(url):
    """Parse a database URL into its components."""
    # Remove postgresql:// prefix
    if url.startswith('postgresql://'):
        url = url[len('postgresql://'):]
    
    # Split user:password@host:port/dbname
    auth, rest = url.split('@', 1)
    host_port, dbname = rest.split('/', 1)
    
    # Handle user:password
    if ':' in auth:
        user, password = auth.split(':', 1)
    else:
        user = auth
        password = ''
    
    # Handle host:port
    if ':' in host_port:
        host, port = host_port.split(':', 1)
        port = int(port)
    else:
        host = host_port
        port = 5432
    
    return {
        'user': user,
        'password': password,
        'host': host,
        'port': port,
        'dbname': dbname
    }

def check_column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table."""
    try:
        cursor.execute(f"SELECT {column_name} FROM {table_name} LIMIT 0")
        return True  # Column exists
    except psycopg2.Error:
        return False  # Column doesn't exist

def add_column_if_not_exists(cursor, table_name, column_name, column_type, nullable=True):
    """Add a column to a table if it doesn't exist."""
    if check_column_exists(cursor, table_name, column_name):
        logger.info(f"Column {column_name} already exists in {table_name}.")
        return False  # Column exists
    
    # Column doesn't exist, add it
    null_str = "NULL" if nullable else "NOT NULL"
    try:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} {null_str}")
        logger.info(f"Added column {column_name} to {table_name}.")
        return True  # Column added
    except psycopg2.Error as e:
        logger.error(f"Error adding column {column_name}: {e}")
        return False  # Failed to add column

def run_migration():
    """Run the database migration."""
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
        
        # Create a cursor
        with conn.cursor() as cursor:
            # Add necessary columns to order table
            added_any = False
            
            # Deliverect status tracking columns
            added_any |= add_column_if_not_exists(cursor, '"order"', 'status_code', 'INTEGER')
            added_any |= add_column_if_not_exists(cursor, '"order"', 'status_updated_at', 'TIMESTAMP')
            
            # Delivery tracking columns
            added_any |= add_column_if_not_exists(cursor, '"order"', 'delivery_status', 'VARCHAR(30)')
            added_any |= add_column_if_not_exists(cursor, '"order"', 'delivery_status_code', 'INTEGER')
            added_any |= add_column_if_not_exists(cursor, '"order"', 'courier_name', 'VARCHAR(50)')
            added_any |= add_column_if_not_exists(cursor, '"order"', 'courier_phone', 'VARCHAR(20)')
            added_any |= add_column_if_not_exists(cursor, '"order"', 'estimated_delivery_time', 'TIMESTAMP')
            
            if added_any:
                logger.info("Migration completed successfully!")
            else:
                logger.info("No migration needed - all columns already exist.")
            
            return True
    except Exception as e:
        logger.error(f"Error during migration: {e}")
        return False
    finally:
        if 'conn' in locals() and conn is not None:
            conn.close()

if __name__ == "__main__":
    logger.info("Starting database migration")
    success = run_migration()
    if success:
        logger.info("Migration completed successfully")
        sys.exit(0)
    else:
        logger.error("Migration failed")
        sys.exit(1)