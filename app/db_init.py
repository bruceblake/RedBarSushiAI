"""
Database initialization module.
This module ensures the database is properly initialized for menu storage on application startup.
"""

import logging
import os
import time
from flask import current_app
from sqlalchemy import inspect, text
from app import db

logger = logging.getLogger(__name__)

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

def init_database():
    """
    Initialize the database for menu storage.
    This function should be called on application startup.
    """
    try:
        # Check if we should initialize the database
        should_init = current_app.config.get("INITIALIZE_MENU_DATABASE", True)
        if not should_init:
            logger.info("Skipping database initialization as configured")
            return
        
        logger.info("Initializing database for menu storage...")
        
        # Check if tables exist by looking for key tables
        tables_exist = check_table_exists('menu_items')
        
        if not tables_exist:
            logger.info("Creating database tables...")
            # Create all tables using SQLAlchemy ORM
            create_tables()
            tables_exist = True
        else:
            logger.info("Database tables already exist")
        
        # Check if we should migrate existing data
        should_migrate = current_app.config.get("MIGRATE_MENU_DATA", True)
        if should_migrate:
            # Import here to avoid circular imports
            from app.models.menu import MenuItem
            
            # Check if we already have menu data in the database
            try:
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
                            else:
                                logger.error(f"Failed to migrate menu data: {result.get('error')}")
                        else:
                            logger.warning(f"Menu file not found at {menu_file} - cannot migrate data")
                    except Exception as e:
                        logger.error(f"Error migrating menu data: {e}", exc_info=True)
                else:
                    logger.info(f"Found {item_count} menu items in database, skipping migration")
            except Exception as e:
                logger.error(f"Error checking menu items: {e}", exc_info=True)
        
        # Set configuration to use database
        current_app.config["MENU_BACKEND"] = "database"
        logger.info("Database initialization complete - using database for menu storage")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}", exc_info=True)
        # Don't raise - just log the error since this is called during app initialization
        # Try to continue anyway by using file-based storage as fallback
        current_app.config["MENU_BACKEND"] = "file"
        logger.info("Falling back to file-based menu storage due to database error")