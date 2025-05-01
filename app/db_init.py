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
        
        # Create the tables using SQLAlchemy engine directly - works with SQLAlchemy 2.0
        try:
            # First check if the tables exist - using connection for SQLAlchemy 2.0 compatibility
            with db.engine.connect() as conn:
                try:
                    conn.execute(db.text("SELECT 1 FROM menu_items LIMIT 1"))
                    logger.info("Menu tables already exist in database")
                    tables_exist = True
                except Exception:
                    logger.info("Tables don't exist yet, creating with SQL...")
                    tables_exist = False
                    
                    # Create tables using direct SQL
                    try:
                        # Create tables with SQL - only if they don't exist
                        # Using PostgreSQL-specific SQL syntax
                        create_tables_sql = """
                        CREATE TABLE IF NOT EXISTS menu_items (
                            id SERIAL PRIMARY KEY,
                            name VARCHAR(255) NOT NULL,
                            reference_handler VARCHAR(255),
                            plu VARCHAR(255),
                            price FLOAT,
                            description TEXT,
                            category VARCHAR(255),
                            parent_id VARCHAR(255),
                            available BOOLEAN DEFAULT TRUE,
                            snoozed BOOLEAN DEFAULT FALSE,
                            is_category BOOLEAN DEFAULT FALSE,
                            is_variant BOOLEAN DEFAULT FALSE,
                            snooze_start TIMESTAMP,
                            snooze_end TIMESTAMP,
                            snooze_until TIMESTAMP,
                            created_at TIMESTAMP DEFAULT NOW(),
                            updated_at TIMESTAMP DEFAULT NOW(),
                            location_id VARCHAR(36),
                            properties JSONB
                        );

                        CREATE TABLE IF NOT EXISTS menu_modifiers (
                            id SERIAL PRIMARY KEY,
                            name VARCHAR(255) NOT NULL,
                            reference_handler VARCHAR(255),
                            price FLOAT DEFAULT 0.0,
                            available BOOLEAN DEFAULT TRUE,
                            created_at TIMESTAMP DEFAULT NOW(),
                            updated_at TIMESTAMP DEFAULT NOW(),
                            location_id VARCHAR(36),
                            properties JSONB
                        );

                        CREATE TABLE IF NOT EXISTS menu_modifier_groups (
                            id SERIAL PRIMARY KEY,
                            name VARCHAR(255) NOT NULL,
                            reference_handler VARCHAR(255),
                            min_allowed INTEGER DEFAULT 0,
                            max_allowed INTEGER,
                            multi_max INTEGER DEFAULT 1,
                            is_variant_group BOOLEAN DEFAULT FALSE,
                            created_at TIMESTAMP DEFAULT NOW(),
                            updated_at TIMESTAMP DEFAULT NOW(),
                            location_id VARCHAR(36),
                            properties JSONB
                        );

                        CREATE TABLE IF NOT EXISTS menu_item_modifiers (
                            menu_item_id INTEGER REFERENCES menu_items(id) ON DELETE CASCADE,
                            menu_modifier_group_id INTEGER REFERENCES menu_modifier_groups(id) ON DELETE CASCADE,
                            PRIMARY KEY (menu_item_id, menu_modifier_group_id)
                        );

                        CREATE TABLE IF NOT EXISTS menu_modifier_group_items (
                            menu_modifier_group_id INTEGER REFERENCES menu_modifier_groups(id) ON DELETE CASCADE,
                            menu_modifier_id INTEGER REFERENCES menu_modifiers(id) ON DELETE CASCADE,
                            PRIMARY KEY (menu_modifier_group_id, menu_modifier_id)
                        );

                        CREATE INDEX IF NOT EXISTS idx_menu_items_reference_handler ON menu_items(reference_handler);
                        CREATE INDEX IF NOT EXISTS idx_menu_items_plu ON menu_items(plu);
                        CREATE INDEX IF NOT EXISTS idx_menu_modifiers_reference_handler ON menu_modifiers(reference_handler);
                        CREATE INDEX IF NOT EXISTS idx_menu_modifier_groups_reference_handler ON menu_modifier_groups(reference_handler);
                        """
                        
                        # Execute the SQL in SQLAlchemy 2.0 compatible way
                        conn.execute(db.text(create_tables_sql))
                        conn.commit()
                        
                        logger.info("Successfully created menu tables with direct SQL")
            except Exception as sql_error:
                logger.error(f"Error creating tables with SQL: {sql_error}")
                # Try with SQLAlchemy as fallback
                try:
                    # Import models here to avoid top-level circular imports
                    from app.models.menu import MenuItem, MenuModifier, MenuModifierGroup
                    db.create_all()
                    logger.info("Created tables using SQLAlchemy ORM")
                except Exception as orm_error:
                    logger.error(f"Failed to create tables with ORM too: {orm_error}")
        
        # Check if we should migrate existing data - only if tables were just created
        if not tables_exist:
            should_migrate = current_app.config.get("MIGRATE_MENU_DATA", True)
            if should_migrate:
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
                            logger.info(f"Successfully migrated {result.get('items_count')} menu items to database")
                        else:
                            logger.error(f"Failed to migrate menu data: {result.get('error')}")
                    else:
                        logger.warning(f"Menu file not found at {menu_file} - cannot migrate data")
                except Exception as e:
                    logger.error(f"Error migrating menu data: {e}", exc_info=True)
                
        # Set configuration to use database
        current_app.config["MENU_BACKEND"] = "database"
        logger.info("Database initialization complete - using database for menu storage")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}", exc_info=True)
        # Don't raise - just log the error since this is called during app initialization