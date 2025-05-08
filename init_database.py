#!/usr/bin/env python
"""
Initialize the database for RedBarSushiAI.
This script creates all tables and loads sample menu data.
"""

import os
import json
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger("init_database")

def init_db():
    """Initialize the database with all required tables."""
    try:
        # Import app context
        from app import create_app, db
        
        # Create app and context
        app = create_app()
        with app.app_context():
            # Create all tables
            logger.info("Creating database tables...")
            db.create_all()
            logger.info("Database tables created successfully")
            
            # Check if menu items already exist
            from app.models.menu import MenuItem
            item_count = MenuItem.query.count()
            
            if item_count == 0:
                # Load sample menu data if available
                logger.info("No menu items found. Loading sample data...")
                load_sample_menu_data(app, db)
            else:
                logger.info(f"Found {item_count} existing menu items. Skipping sample data load.")
                
            # Verify tables were created
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            logger.info(f"Database tables: {tables}")
            
            return True
            
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False

def load_sample_menu_data(app, db):
    """Load sample menu data from menu_data.json if available."""
    try:
        # Check if sample data file exists
        if os.path.exists("menu_data.json"):
            with open("menu_data.json", "r") as f:
                menu_data = json.load(f)
                
            logger.info(f"Loading menu data with {len(menu_data.get('products', {}))} products...")
            
            # Import menu models
            from app.models.menu import (
                MenuCategory, 
                MenuItem, 
                MenuModifier, 
                MenuModifierGroup,
                ItemModifierGroup,
                GroupModifier,
                MenuNameVariant
            )
            
            # Create categories
            for category_id, category_data in menu_data.get("categories", {}).items():
                category = MenuCategory(
                    deliverect_category_id=category_id,
                    name=category_data.get("name", ""),
                    description=category_data.get("description", "")
                )
                db.session.add(category)
            
            # Commit categories first
            db.session.commit()
            logger.info("Categories created successfully")
            
            # Create modifier groups first
            for group_id, group_data in menu_data.get("modifierGroups", {}).items():
                modifier_group = MenuModifierGroup(
                    deliverect_group_id=group_id,
                    name=group_data.get("name", ""),
                    min_selection=group_data.get("min", 0),
                    max_selection=group_data.get("max", 0),
                    multi_max=group_data.get("multiMax", 1),
                    plu=group_data.get("plu", ""),
                    is_variant_group=group_data.get("isVariantGroup", False)
                )
                db.session.add(modifier_group)
            
            # Commit modifier groups
            db.session.commit()
            logger.info("Modifier groups created successfully")
            
            # Create menu items
            for product_id, product_data in menu_data.get("products", {}).items():
                # Find category if specified
                category = None
                if product_data.get("categoryId"):
                    category = MenuCategory.query.filter_by(
                        deliverect_category_id=product_data.get("categoryId")
                    ).first()
                
                menu_item = MenuItem(
                    category_id=category.id if category else None,
                    name=product_data.get("name", ""),
                    description=product_data.get("description", ""),
                    price=product_data.get("price", 0),
                    plu=product_data.get("plu", ""),
                    deliverect_item_id=product_id,
                    is_available=True,
                    is_combo=product_data.get("isCombo", False),
                    is_variant=product_data.get("isVariant", False),
                    image_url=product_data.get("imageUrl", "")
                )
                db.session.add(menu_item)
            
            # Commit menu items
            db.session.commit()
            logger.info("Menu items created successfully")
            
            # Create modifiers
            for modifier_id, modifier_data in menu_data.get("modifiers", {}).items():
                # Find modifier group if specified
                modifier_group = None
                if modifier_data.get("parentId"):
                    modifier_group = MenuModifierGroup.query.filter_by(
                        deliverect_group_id=modifier_data.get("parentId")
                    ).first()
                
                modifier = MenuModifier(
                    modifier_group_id=modifier_group.id if modifier_group else None,
                    name=modifier_data.get("name", ""),
                    price_change=modifier_data.get("price", 0),
                    plu=modifier_data.get("plu", ""),
                    deliverect_modifier_id=modifier_id,
                    is_available=True
                )
                db.session.add(modifier)
            
            # Commit modifiers
            db.session.commit()
            logger.info("Modifiers created successfully")
            
            # Create item-modifier group relationships
            for product_id, product_data in menu_data.get("products", {}).items():
                menu_item = MenuItem.query.filter_by(deliverect_item_id=product_id).first()
                if menu_item and product_data.get("subProducts"):
                    for group_id in product_data.get("subProducts", []):
                        modifier_group = MenuModifierGroup.query.filter_by(deliverect_group_id=group_id).first()
                        if menu_item and modifier_group:
                            item_group = ItemModifierGroup(
                                menu_item_id=menu_item.id,
                                modifier_group_id=modifier_group.id
                            )
                            db.session.add(item_group)
            
            # Commit item-modifier group relationships
            db.session.commit()
            logger.info("Item-modifier group relationships created successfully")
            
            # Create name variants
            logger.info("Creating name variants...")
            items = MenuItem.query.all()
            variant_count = 0
            
            for item in items:
                # Create basic variants for each item
                name_parts = item.name.split()
                for part in name_parts:
                    if len(part) > 3:  # Skip very short words
                        variant = MenuNameVariant(
                            variant_phrase=part.lower(),
                            canonical_name=item.name,
                            target_plu=item.plu
                        )
                        db.session.add(variant)
                        variant_count += 1
            
            # Commit name variants
            db.session.commit()
            logger.info(f"Created {variant_count} name variants")
            
            logger.info("Sample menu data loaded successfully")
            return True
        else:
            logger.warning("No menu_data.json file found. Skipping sample data load.")
            return False
            
    except Exception as e:
        logger.error(f"Error loading sample menu data: {e}")
        return False

if __name__ == "__main__":
    success = init_db()
    if success:
        logger.info("Database initialization complete")
    else:
        logger.error("Database initialization failed")