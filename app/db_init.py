"""
Database initialization module.
This module ensures the database is properly initialized for menu storage on application startup.
Includes robust connection handling with retry logic for production environments.
"""

import logging
import os
import time
import random
from flask import current_app
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from app import db

logger = logging.getLogger(__name__)

def verify_connection():
    """Verify database connection is active and working."""
    try:
        with db.session.connection() as conn:
            result = conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        logger.warning(f"Connection verification failed: {e}")
        return False

def check_table_exists(table_name):
    """Check if a table exists in the database."""
    try:
        # Try a direct query approach that works with all SQLAlchemy versions
        with db.session.connection() as conn:
            result = conn.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :table_name)"
            ), {"table_name": table_name})
            return result.scalar()
    except Exception as e:
        logger.warning(f"Error checking if table exists: {e}")
        return False

def create_tables():
    """Create all tables using SQLAlchemy ORM."""
    # Import all models to ensure they're registered with SQLAlchemy
    from app.models.location import Location
    from app.models.menu import MenuItem, MenuModifier, MenuModifierGroup
    
    # Create tables
    db.create_all()
    logger.info("Created all database tables")

def execute_with_retry(func, *args, **kwargs):
    """
    Execute a database function with retry logic and exponential backoff.
    
    Args:
        func: The function to execute
        *args, **kwargs: Arguments to pass to the function
        
    Returns:
        The result of the function call or None if all retries failed
    """
    # Get retry settings from environment or use defaults
    max_retries = int(os.environ.get("DB_MAX_RETRIES", 5))
    initial_delay = float(os.environ.get("DB_INITIAL_RETRY_DELAY", 1.0))
    max_delay = float(os.environ.get("DB_MAX_RETRY_DELAY", 30.0))
    
    # Track attempt number
    attempt = 0
    last_error = None
    
    while attempt < max_retries:
        try:
            # If not first attempt, log retry info
            if attempt > 0:
                logger.info(f"Retry attempt {attempt}/{max_retries} for database operation")
            
            # Verify connection first (for non-first attempts)
            if attempt > 0 and not verify_connection():
                logger.warning("Connection verification failed before retry")
                # Continue to retry with a fresh connection
                
            # Execute the function
            result = func(*args, **kwargs)
            
            # If we got here, it worked! Log success on retry
            if attempt > 0:
                logger.info(f"Database operation succeeded after {attempt} retries")
            
            return result
            
        except (OperationalError, SQLAlchemyError) as e:
            # Specific handling for common database connection errors
            attempt += 1
            last_error = e
            
            # Extract useful info from error for logging
            error_type = type(e).__name__
            
            # Log error details but protect sensitive info
            conn_info = str(e).replace(os.environ.get("DATABASE_URL", ""), "[DB_URL]") if "DATABASE_URL" in os.environ else str(e)
            logger.warning(f"Database operation failed with {error_type}: {conn_info}")
            
            # Check if we have retries left
            if attempt >= max_retries:
                logger.error(f"Maximum retries ({max_retries}) reached, giving up")
                break
                
            # Calculate backoff delay with jitter to prevent thundering herd
            delay = min(initial_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5), max_delay)
            logger.info(f"Waiting {delay:.2f} seconds before retry {attempt+1}/{max_retries}")
            
            # Wait before next retry
            time.sleep(delay)
            
            # Clean up session to ensure fresh connection on retry
            db.session.remove()
        
        except Exception as e:
            # Non-connection errors should not be retried
            logger.error(f"Non-retryable error occurred: {e}", exc_info=True)
            raise
            
    # If we got here, all retries failed
    if last_error:
        logger.error(f"All {max_retries} retry attempts failed for database operation")
        # Return None to indicate failure
        return None
        
    # This shouldn't happen, but just in case
    return None

def init_database():
    """
    Initialize the database for menu storage with robust connection handling.
    This function should be called on application startup.
    """
    # Check if we should initialize the database
    should_init = current_app.config.get("INITIALIZE_MENU_DATABASE", True)
    if not should_init:
        logger.info("Skipping database initialization as configured")
        return
    
    logger.info("Initializing database for menu storage...")
    
    # Function to initialize database tables with proper error handling
    def _init_tables():
        # Check if tables exist by looking for key tables
        tables_exist = check_table_exists('menu_items')
        
        if not tables_exist:
            logger.info("Creating database tables...")
            # Create all tables using SQLAlchemy ORM
            create_tables()
            return True
        else:
            logger.info("Database tables already exist")
            return tables_exist
    
    # Initialize tables with retry logic
    tables_initialized = execute_with_retry(_init_tables)
    
    if tables_initialized is None:
        logger.error("Failed to initialize database tables after multiple retries")
        # Fall back to file-based storage due to initialization failure
        current_app.config["MENU_BACKEND"] = "file"
        logger.info("Falling back to file-based menu storage due to database error")
        return
    
    # Function to migrate menu data if needed
    def _migrate_menu_data_if_needed():
        try:
            # Check if we should migrate existing data
            should_migrate = current_app.config.get("MIGRATE_MENU_DATA", True)
            if not should_migrate:
                logger.info("Skipping menu data migration as configured")
                return True
                
            # Import here to avoid circular imports
            from app.models.menu import MenuItem
            
            # Check if we already have menu data in the database
            with db.session.connection() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM menu_items"))
                item_count = result.scalar()
            
            if item_count == 0:
                # No menu items in database, migrate from file
                logger.info("No menu items found in database, migrating from file...")
                
                try:
                    # Import migration module
                    from app.utils.menu_migration import migrate_menu_to_database
                    
                    # Find menu file
                    from app.utils.menu_utils import find_menu_file_path, MENU_FILE_PATH
                    menu_file = find_menu_file_path() or MENU_FILE_PATH
                    
                    # Check if file exists
                    if os.path.exists(menu_file):
                        logger.info(f"Migrating menu data from {menu_file} to database...")
                        result = migrate_menu_to_database(file_path=menu_file, force=True)
                        
                        if result.get("success"):
                            logger.info(f"Successfully migrated menu data: {result.get('items_count')} items")
                            return True
                        else:
                            logger.error(f"Failed to migrate menu data: {result.get('error')}")
                            return False
                    else:
                        logger.warning(f"Menu file not found at {menu_file} - cannot migrate data")
                        return False
                except Exception as e:
                    logger.error(f"Error migrating menu data: {e}", exc_info=True)
                    return False
            else:
                logger.info(f"Found {item_count} menu items in database, skipping migration")
                return True
        except Exception as e:
            logger.error(f"Error in menu data migration: {e}", exc_info=True)
            return False
    
    # Migrate menu data with retry logic
    migration_result = execute_with_retry(_migrate_menu_data_if_needed)
    
    # Verify final connection state
    connection_valid = execute_with_retry(verify_connection)
    
    if connection_valid:
        # Set configuration to use database
        current_app.config["MENU_BACKEND"] = "database"
        logger.info("Database initialization complete - using database for menu storage")
    else:
        # Don't raise - just log the error since this is called during app initialization
        logger.error("Final database connection verification failed - cannot use database")
        # Fall back to file-based storage
        current_app.config["MENU_BACKEND"] = "file"
        logger.info("Falling back to file-based menu storage due to connection issues")