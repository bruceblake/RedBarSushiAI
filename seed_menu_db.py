#!/usr/bin/env python
"""
Menu database seeding script.

This script is a standalone tool for manually seeding the database with menu data
from a JSON file. It is NOT part of the application's normal startup process.

Usage:
    python seed_menu_db.py [--file <json_file_path>] [--location <location_id>] [--force]

Options:
    --file: Path to the menu JSON file (default: menu_data.json)
    --location: Optional location ID to associate with the menu data
    --force: Override existing database data
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from flask import Flask
from sqlalchemy import inspect

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"menu_seed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger("menu_seeder")


def create_app():
    """Create a minimal Flask application for database operations."""
    app = Flask(__name__)
    
    # Import database configuration
    if os.path.exists("app/config.py"):
        from app.config import SQLALCHEMY_DATABASE_URI, SQLALCHEMY_TRACK_MODIFICATIONS
        app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = SQLALCHEMY_TRACK_MODIFICATIONS
    else:
        # Fallback to environment variables
        app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # Initialize the database
    from app import db
    db.init_app(app)
    
    return app


def seed_database(file_path, location_id=None, force=False):
    """Seed the database with menu data from a JSON file."""
    logger.info(f"Starting menu seeding from file: {file_path}")
    
    # Check if file exists
    if not os.path.exists(file_path):
        logger.error(f"Menu file not found: {file_path}")
        return False
    
    try:
        # Read the menu data from file
        with open(file_path, "r") as f:
            menu_data = json.load(f)
        
        # Process Deliverect format if needed
        from app.utils.deliverect import process_deliverect_menu
        if "channels" in menu_data or "products" in menu_data:
            logger.info("Found Deliverect-format menu data - processing...")
            menu_data = process_deliverect_menu(menu_data)
        
        # Validate menu data
        if "items" not in menu_data:
            logger.error("Invalid menu data: 'items' key not found")
            return False
        
        # Check if there's already data in the database
        from app.models.menu import MenuItem
        
        existing_count = MenuItem.query.count()
        if existing_count > 0 and not force:
            logger.warning(
                f"Database already contains {existing_count} menu items. Use --force to override."
            )
            return False
        
        # Store the menu data in the database
        from app.utils.menu_db_store import menu_db_store
        result = menu_db_store.store_menu_data(menu_data, location_id)
        
        if result:
            # Count the seeded items
            items_count = len(menu_data.get("items", []))
            modifiers_count = len(menu_data.get("modifiers", []))
            modifier_groups_count = len(menu_data.get("modifierGroups", []))
            
            logger.info(
                f"Successfully seeded menu data: {items_count} items, {modifiers_count} modifiers, {modifier_groups_count} groups"
            )
            return True
        else:
            logger.error("Failed to store menu data in database")
            return False
    
    except Exception as e:
        logger.error(f"Error during menu seeding: {str(e)}")
        return False


def show_database_info():
    """Show information about the current database state."""
    try:
        from app.models.menu import MenuItem, MenuModifier, MenuModifierGroup
        
        item_count = MenuItem.query.count()
        modifier_count = MenuModifier.query.count()
        group_count = MenuModifierGroup.query.count()
        
        logger.info("Current database state:")
        logger.info(f"  - Items: {item_count}")
        logger.info(f"  - Modifiers: {modifier_count}")
        logger.info(f"  - Modifier Groups: {group_count}")
        
        if item_count > 0:
            # Show sample items
            sample_items = MenuItem.query.limit(5).all()
            logger.info("Sample items:")
            for item in sample_items:
                logger.info(f"  - {item.name} (PLU: {item.plu})")
    
    except Exception as e:
        logger.error(f"Error retrieving database info: {str(e)}")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Seed the database with menu data from a JSON file")
    parser.add_argument(
        "--file", 
        default="menu_data.json", 
        help="Path to the menu JSON file"
    )
    parser.add_argument(
        "--location", 
        help="Optional location ID to associate with the menu data"
    )
    parser.add_argument(
        "--force", 
        action="store_true", 
        help="Override existing database data"
    )
    parser.add_argument(
        "--info", 
        action="store_true", 
        help="Show current database information without seeding"
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Create the Flask app context
    app = create_app()
    
    with app.app_context():
        # Setup database if needed
        from app import db
        if not inspect(db.engine).has_table("menu_items"):
            logger.info("Creating database tables...")
            db.create_all()
        
        # Show database info if requested
        if args.info:
            show_database_info()
            return
        
        # Seed the database
        success = seed_database(args.file, args.location, args.force)
        
        if success:
            logger.info("Menu seeding completed successfully!")
            show_database_info()
        else:
            logger.error("Menu seeding failed!")
            sys.exit(1)


if __name__ == "__main__":
    main()
