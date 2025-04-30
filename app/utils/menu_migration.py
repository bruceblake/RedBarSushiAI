"""
Menu migration utility for transferring menu data from JSON file to database.
This module provides functions to migrate the menu data from the file-based approach to the database.
"""

import json
import logging
import os
from app.utils.menu_utils import find_menu_file_path, MENU_FILE_PATH
from app.utils.menu_db_store import menu_db_store
from app.utils.deliverect import process_deliverect_menu
from app import db

# Set up logging
logger = logging.getLogger(__name__)

def migrate_menu_to_database(file_path=None, location_id=None, force=False):
    """
    Migrate menu data from the JSON file to the database.
    
    Args:
        file_path: Path to the menu JSON file (optional, will use default if not provided)
        location_id: Optional location ID to associate with the menu data
        force: If True, will override existing database data
        
    Returns:
        dict: Migration statistics
    """
    try:
        # Determine the file path if not provided
        if not file_path:
            file_path = find_menu_file_path()
            if not file_path:
                file_path = MENU_FILE_PATH
                
        logger.info(f"Starting menu migration from file: {file_path}")
        
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"Menu file not found: {file_path}")
            return {"success": False, "error": "Menu file not found"}
        
        # Read the menu data from file
        with open(file_path, 'r') as f:
            menu_data = json.load(f)
            
        # Process Deliverect format if needed
        if "channels" in menu_data or "products" in menu_data:
            logger.info("Found Deliverect-format menu data - processing...")
            menu_data = process_deliverect_menu(menu_data)
        
        # Check if menu data is valid
        if "items" not in menu_data:
            logger.error("Invalid menu data: 'items' key not found")
            return {"success": False, "error": "Invalid menu data"}
            
        # Check if there's already data in the database
        from app.models.menu import MenuItem
        
        existing_count = MenuItem.query.count()
        if existing_count > 0 and not force:
            logger.warning(f"Database already contains {existing_count} menu items. Use force=True to override.")
            return {
                "success": False, 
                "error": f"Database already contains {existing_count} menu items",
                "existing_count": existing_count
            }
            
        # Store the menu data in the database
        result = menu_db_store.store_menu_data(menu_data, location_id)
        
        if result:
            # Count the migrated items
            items_count = len(menu_data.get("items", []))
            modifiers_count = len(menu_data.get("modifiers", []))
            modifier_groups_count = len(menu_data.get("modifierGroups", []))
            
            logger.info(f"Successfully migrated menu data: {items_count} items, {modifiers_count} modifiers, {modifier_groups_count} groups")
            
            return {
                "success": True,
                "items_count": items_count,
                "modifiers_count": modifiers_count,
                "modifier_groups_count": modifier_groups_count,
                "location_id": location_id
            }
        else:
            logger.error("Failed to store menu data in database")
            return {"success": False, "error": "Failed to store menu data in database"}
            
    except Exception as e:
        logger.error(f"Error during menu migration: {str(e)}")
        return {"success": False, "error": str(e)}

def verify_menu_migration(location_id=None):
    """
    Verify that the menu data was correctly migrated to the database.
    
    Args:
        location_id: Optional location ID to check
        
    Returns:
        dict: Verification results
    """
    try:
        # Get menu data from file
        file_path = find_menu_file_path()
        if not file_path:
            file_path = MENU_FILE_PATH
            
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"Menu file not found: {file_path}")
            return {"success": False, "error": "Menu file not found"}
            
        # Read the menu data from file
        with open(file_path, 'r') as f:
            file_menu_data = json.load(f)
            
        # Process Deliverect format if needed
        if "channels" in file_menu_data or "products" in file_menu_data:
            file_menu_data = process_deliverect_menu(file_menu_data)
            
        # Get menu data from database
        db_menu_data = menu_db_store.get_menu_data(location_id=location_id, force_refresh=True)
        
        # Compare item counts
        file_items_count = len(file_menu_data.get("items", []))
        db_items_count = len(db_menu_data.get("items", []))
        
        file_modifiers_count = len(file_menu_data.get("modifiers", []))
        db_modifiers_count = len(db_menu_data.get("modifiers", []))
        
        file_modifier_groups_count = len(file_menu_data.get("modifierGroups", []))
        db_modifier_groups_count = len(db_menu_data.get("modifierGroups", []))
        
        # Check if all items were migrated
        items_match = file_items_count == db_items_count
        modifiers_match = file_modifiers_count == db_modifiers_count
        modifier_groups_match = file_modifier_groups_count == db_modifier_groups_count
        
        # Check if some items were migrated
        items_partial = db_items_count > 0
        modifiers_partial = db_modifiers_count > 0
        modifier_groups_partial = db_modifier_groups_count > 0
        
        # Overall success if everything matches exactly
        success = items_match and modifiers_match and modifier_groups_match
        
        return {
            "success": success,
            "file_items_count": file_items_count,
            "db_items_count": db_items_count,
            "items_match": items_match,
            "items_partial": items_partial,
            
            "file_modifiers_count": file_modifiers_count,
            "db_modifiers_count": db_modifiers_count,
            "modifiers_match": modifiers_match,
            "modifiers_partial": modifiers_partial,
            
            "file_modifier_groups_count": file_modifier_groups_count,
            "db_modifier_groups_count": db_modifier_groups_count,
            "modifier_groups_match": modifier_groups_match,
            "modifier_groups_partial": modifier_groups_partial,
            
            "location_id": location_id
        }
            
    except Exception as e:
        logger.error(f"Error during migration verification: {str(e)}")
        return {"success": False, "error": str(e)}
        
def initialize_database_tables():
    """
    Initialize the database tables required for menu storage.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Import the models
        from app.models.menu import MenuItem, MenuModifier, MenuModifierGroup
        
        # Create all tables
        db.create_all()
        
        logger.info("Database tables created successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error initializing database tables: {str(e)}")
        return False

def export_database_to_file(file_path, location_id=None):
    """
    Export the menu data from the database to a JSON file.
    
    Args:
        file_path: Path to the output JSON file
        location_id: Optional location ID to filter the menu data
        
    Returns:
        bool: True if successful, False otherwise
    """
    return menu_db_store.export_menu_data_to_file(file_path, location_id)