"""
Database initialization module.
This module ensures the database is properly initialized for menu storage on application startup.
"""

import logging
import os
from flask import current_app
from app import db

logger = logging.getLogger(__name__)

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
        
        # Import models to ensure they're registered
        from app.models.menu import MenuItem, MenuModifier, MenuModifierGroup
        
        # Create tables if they don't exist
        try:
            db.engine.execute("SELECT 1 FROM menu_items LIMIT 1")
            logger.info("Menu tables already exist in database")
        except Exception:
            logger.info("Creating menu tables in database...")
            db.create_all()
            logger.info("Menu tables created successfully")
            
        # Check if we should migrate existing data
        should_migrate = current_app.config.get("MIGRATE_MENU_DATA", True)
        if should_migrate:
            # Only migrate if we don't already have data
            try:
                item_count = MenuItem.query.count()
                if item_count > 0:
                    logger.info(f"Database already contains {item_count} menu items - skipping migration")
                else:
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
                            logger.info(f"Successfully migrated {result.get('items_count')} menu items to database")
                        else:
                            logger.error(f"Failed to migrate menu data: {result.get('error')}")
                    else:
                        logger.warning(f"Menu file not found at {menu_file} - cannot migrate data")
            except Exception as e:
                logger.error(f"Error checking or migrating menu data: {e}", exc_info=True)
                
        # Set configuration to use database
        current_app.config["MENU_BACKEND"] = "database"
        logger.info("Database initialization complete - using database for menu storage")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}", exc_info=True)
        # Don't raise - just log the error since this is called during app initialization