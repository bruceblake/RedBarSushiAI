#!/usr/bin/env python3
"""
Database Menu Integration Script

This script migrates the menu data from JSON files to the PostgreSQL database
and configures the application to use the database for menu data.

Usage:
    python database_menu_integration.py [--force] [--location-id LOCATION_ID]

Options:
    --force          Force migration even if database already has menu data
    --location-id    Optional location ID to associate with the menu data
    --skip-config    Skip the configuration update step
"""

import os
import sys
import argparse
import logging
import shutil
import time
from datetime import datetime

# Setup logging with unique timestamp in filename
log_timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'menu_migration_{log_timestamp}.log')
    ]
)
logger = logging.getLogger(__name__)

def backup_file(file_path, backup_dir=None):
    """
    Create a backup of the specified file.
    
    Args:
        file_path: Path to the file to backup
        backup_dir: Optional directory to store backups
        
    Returns:
        str: Path to the backup file, or None if backup failed
    """
    if not os.path.exists(file_path):
        logger.warning(f"File not found, cannot backup: {file_path}")
        return None
    
    # Generate backup filename with timestamp
    backup_filename = f"{os.path.basename(file_path)}.bak.{int(time.time())}"
    
    # Determine backup path
    if backup_dir:
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, backup_filename)
    else:
        backup_path = os.path.join(os.path.dirname(file_path), backup_filename)
    
    try:
        shutil.copy2(file_path, backup_path)
        logger.info(f"Backed up {file_path} to {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Failed to backup file {file_path}: {e}")
        return None

def update_configuration(skip_config=False):
    """
    Update the application configuration to use the database for menu data.
    
    Args:
        skip_config: If True, skip the configuration update
        
    Returns:
        bool: True if successful or skipped, False otherwise
    """
    if skip_config:
        logger.info("Skipping configuration update as requested")
        return True
    
    try:
        # Define paths
        menu_utils_path = os.path.join("app", "utils", "menu_utils.py")
        menu_utils_db_path = os.path.join("app", "utils", "menu_utils_db.py")
        
        # Check if files exist
        if not os.path.exists(menu_utils_path):
            logger.error(f"Original menu_utils.py not found at {menu_utils_path}")
            return False
            
        if not os.path.exists(menu_utils_db_path):
            logger.error(f"Database-backed menu_utils_db.py not found at {menu_utils_db_path}")
            return False
        
        # Create backup of original file
        backup_path = backup_file(menu_utils_path)
        if not backup_path:
            logger.warning("Failed to create backup, but continuing with configuration update")
        
        # Create symlink on Unix or copy file on Windows
        if os.name == 'posix':  # Unix/Linux/Mac
            try:
                # First remove the original file if it exists
                if os.path.exists(menu_utils_path):
                    os.remove(menu_utils_path)
                
                # Create a symlink using absolute paths to avoid relative path issues
                os.symlink(
                    os.path.abspath(menu_utils_db_path),
                    os.path.abspath(menu_utils_path)
                )
                logger.info(f"Created symlink from {menu_utils_db_path} to {menu_utils_path}")
            except Exception as e:
                logger.error(f"Failed to create symlink: {e}")
                # Fallback to copy
                shutil.copy(menu_utils_db_path, menu_utils_path)
                logger.info(f"Copied {menu_utils_db_path} to {menu_utils_path} as fallback")
        else:  # Windows
            # Remove the original file if it exists
            if os.path.exists(menu_utils_path):
                os.remove(menu_utils_path)
                
            # Copy the file
            shutil.copy(menu_utils_db_path, menu_utils_path)
            logger.info(f"Copied {menu_utils_db_path} to {menu_utils_path}")
        
        return True
    except Exception as e:
        logger.error(f"Failed to update configuration: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Main function to execute the menu integration."""
    parser = argparse.ArgumentParser(description='Database Menu Integration Script')
    parser.add_argument('--force', action='store_true', 
                        help='Force migration even if database already has data')
    parser.add_argument('--location-id', type=str, default=None,
                        help='Optional location ID to associate with the menu data')
    parser.add_argument('--skip-config', action='store_true',
                        help='Skip the configuration update step')
    args = parser.parse_args()
    
    logger.info("Starting database menu integration")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Command-line arguments: force={args.force}, location_id={args.location_id}, skip_config={args.skip_config}")
    
    # Import the necessary modules
    try:
        # First make sure app context is available
        from app import create_app, db
        
        # Create app context
        app = create_app()
        with app.app_context():
            # Import migration utility
            from app.utils.menu_migration import migrate_menu_to_database, verify_menu_migration
            from app.utils.menu_migration import initialize_database_tables
            
            # First check database connection
            try:
                engine = db.engine
                connection = engine.connect()
                connection.close()
                logger.info("Successfully connected to the database")
            except Exception as e:
                logger.error(f"Failed to connect to the database: {e}")
                return 1
            
            # Initialize database tables if needed
            logger.info("Initializing database tables...")
            if initialize_database_tables():
                logger.info("Database tables initialized successfully")
            else:
                logger.error("Failed to initialize database tables")
                return 1
            
            # Migrate menu data to database
            logger.info(f"Migrating menu data to database for location_id: {args.location_id or 'default'}...")
            result = migrate_menu_to_database(location_id=args.location_id, force=args.force)
            
            if result.get("success"):
                logger.info(f"Migration successful: {result.get('items_count', 0)} items, "
                           f"{result.get('modifiers_count', 0)} modifiers, "
                           f"{result.get('modifier_groups_count', 0)} modifier groups")
                
                # Verify migration
                logger.info("Verifying migration...")
                verify_result = verify_menu_migration(location_id=args.location_id)
                
                if verify_result.get("success"):
                    logger.info("Migration verification passed")
                    
                    # Create backup of original menu file
                    try:
                        from app.utils.menu_utils import find_menu_file_path, MENU_FILE_PATH
                        menu_file_path = find_menu_file_path()
                        if menu_file_path and os.path.exists(menu_file_path):
                            backup_file(menu_file_path)
                        elif os.path.exists("menu_data.json"):
                            backup_file("menu_data.json")
                    except Exception as e:
                        logger.warning(f"Failed to create backup of original menu file: {e}")
                    
                    # Update configuration to use database
                    if update_configuration(args.skip_config):
                        logger.info("Application configuration updated to use database-backed implementation")
                    else:
                        logger.warning("Failed to update application configuration")
                        logger.warning("You may need to manually update the configuration")
                    
                    logger.info("Migration and integration completed successfully")
                    logger.info("The application is now using the PostgreSQL database for menu data")
                    return 0
                else:
                    # Migration verification failed, but data was still migrated
                    # Check if at least some data was migrated
                    if verify_result.get('db_items_count', 0) > 0:
                        logger.warning("Migration verification showed discrepancies, but continuing")
                        logger.warning(f"File items: {verify_result.get('file_items_count', 0)}, "
                                     f"Database items: {verify_result.get('db_items_count', 0)}")
                        
                        # Still update configuration if requested
                        if update_configuration(args.skip_config):
                            logger.info("Application configuration updated to use database-backed implementation")
                            logger.info("Migration and integration completed with warnings")
                            return 0
                        else:
                            logger.warning("Failed to update application configuration")
                            return 1
                    else:
                        logger.error(f"Migration verification failed: {verify_result.get('error', 'Unknown error')}")
                        logger.error(f"File items: {verify_result.get('file_items_count', 0)}, "
                                   f"Database items: {verify_result.get('db_items_count', 0)}")
                        return 1
            elif 'existing_count' in result and not args.force:
                # Database already has data but we're not forcing
                logger.warning(f"Database already contains {result.get('existing_count', 0)} menu items")
                logger.warning("Use --force to override existing data")
                
                # We can still update the configuration if there's existing data
                if args.skip_config:
                    logger.info("Skipping configuration update as requested")
                    return 0
                    
                logger.info("Updating configuration to use existing database data...")
                if update_configuration(args.skip_config):
                    logger.info("Application configuration updated to use database-backed implementation")
                    logger.info("Integration completed with existing database data")
                    return 0
                else:
                    logger.warning("Failed to update application configuration")
                    return 1
            else:
                logger.error(f"Migration failed: {result.get('error', 'Unknown error')}")
                return 1
    
    except ImportError as e:
        logger.error(f"Import error: {e}")
        logger.error("Make sure you're running this script from the project root directory")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main())