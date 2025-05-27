#!/usr/bin/env python3
"""
Seed the database with Red Bar Sushi menu data.
This script populates the database with menu items for testing.
"""

import asyncio
import os
import sys
from datetime import datetime

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db_async import get_db
from app.models.menu_async import MenuCategory, MenuItem, MenuModifier, MenuModifierGroup
from app.db.crud_menu_async import create_category, create_item, create_modifier, create_modifier_group
from app.schemas.menu import MenuCategoryCreate, MenuItemCreate, MenuModifierCreate, MenuModifierGroupCreate
from sqlalchemy import delete
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def clear_menu_data(db):
    """Clear existing menu data."""
    await db.execute(delete(MenuItem))
    await db.execute(delete(MenuModifier))
    await db.execute(delete(MenuModifierGroup))
    await db.execute(delete(MenuCategory))
    await db.commit()
    logger.info("Cleared existing menu data")

async def seed_menu():
    """Seed the database with menu data."""
    async for db in get_db():
        try:
            # Clear existing data
            await clear_menu_data(db)
            
            # Create categories
            categories = {}
            
            # Appetizers
            appetizers = await create_category(db, MenuCategoryCreate(
                name="Appetizers",
                description="Start your meal with our delicious appetizers"
            ))
            categories['appetizers'] = appetizers.id
            
            # Sushi Rolls
            sushi = await create_category(db, MenuCategoryCreate(
                name="Sushi Rolls",
                description="Fresh sushi rolls made to order"
            ))
            categories['sushi'] = sushi.id
            
            # Sashimi
            sashimi = await create_category(db, MenuCategoryCreate(
                name="Sashimi",
                description="Fresh sliced raw fish"
            ))
            categories['sashimi'] = sashimi.id
            
            # Beverages
            beverages = await create_category(db, MenuCategoryCreate(
                name="Beverages",
                description="Refreshing drinks"
            ))
            categories['beverages'] = beverages.id
            
            logger.info(f"Created {len(categories)} categories")
            
            # Create modifier groups
            modifier_groups = {}
            
            # Spice Level
            spice_group = await create_modifier_group(db, MenuModifierGroupCreate(
                name="Spice Level",
                min_selection=0,
                max_selection=1,
                plu="MG-SPICE"
            ))
            modifier_groups['spice'] = spice_group.id
            
            # Add spice modifiers
            await create_modifier(db, MenuModifierCreate(
                name="Mild",
                modifier_group_id=spice_group.id,
                price_change=0,
                plu="MOD-MILD"
            ))
            await create_modifier(db, MenuModifierCreate(
                name="Medium",
                modifier_group_id=spice_group.id,
                price_change=0,
                plu="MOD-MEDIUM"
            ))
            await create_modifier(db, MenuModifierCreate(
                name="Spicy",
                modifier_group_id=spice_group.id,
                price_change=0,
                plu="MOD-SPICY"
            ))
            
            # Roll Size
            size_group = await create_modifier_group(db, MenuModifierGroupCreate(
                name="Size",
                min_selection=1,
                max_selection=1,
                plu="MG-SIZE"
            ))
            modifier_groups['size'] = size_group.id
            
            await create_modifier(db, MenuModifierCreate(
                name="Regular (8 pieces)",
                modifier_group_id=size_group.id,
                price_change=0,
                plu="MOD-REG"
            ))
            await create_modifier(db, MenuModifierCreate(
                name="Large (12 pieces)",
                modifier_group_id=size_group.id,
                price_change=400,  # $4.00
                plu="MOD-LARGE"
            ))
            
            # Extra Toppings
            extras_group = await create_modifier_group(db, MenuModifierGroupCreate(
                name="Extra Toppings",
                min_selection=0,
                max_selection=3,
                plu="MG-EXTRAS"
            ))
            modifier_groups['extras'] = extras_group.id
            
            await create_modifier(db, MenuModifierCreate(
                name="Extra Avocado",
                modifier_group_id=extras_group.id,
                price_change=200,  # $2.00
                plu="MOD-AVOCADO"
            ))
            await create_modifier(db, MenuModifierCreate(
                name="Spicy Mayo",
                modifier_group_id=extras_group.id,
                price_change=100,  # $1.00
                plu="MOD-SPICYMAYO"
            ))
            await create_modifier(db, MenuModifierCreate(
                name="Tempura Flakes",
                modifier_group_id=extras_group.id,
                price_change=150,  # $1.50
                plu="MOD-TEMPURA"
            ))
            
            logger.info(f"Created {len(modifier_groups)} modifier groups")
            
            # Create menu items
            items_created = 0
            
            # Appetizers
            edamame = await create_item(db, MenuItemCreate(
                name="Edamame",
                category_id=categories['appetizers'],
                price=600,  # $6.00
                description="Steamed soybeans with sea salt",
                plu="APP-001",
                is_available=True
            ))
            items_created += 1
            
            miso_soup = await create_item(db, MenuItemCreate(
                name="Miso Soup",
                category_id=categories['appetizers'],
                price=500,  # $5.00
                description="Traditional Japanese soybean soup",
                plu="APP-002",
                is_available=True
            ))
            items_created += 1
            
            gyoza = await create_item(db, MenuItemCreate(
                name="Gyoza",
                category_id=categories['appetizers'],
                price=800,  # $8.00
                description="Pan-fried pork dumplings (6 pieces)",
                plu="APP-003",
                is_available=True
            ))
            items_created += 1
            
            # Sushi Rolls
            california = await create_item(db, MenuItemCreate(
                name="California Roll",
                category_id=categories['sushi'],
                price=1200,  # $12.00
                description="Crab, avocado, and cucumber",
                plu="ROLL-001",
                is_available=True
            ))
            # Link modifiers to California roll
            from sqlalchemy import select
            stmt = select(MenuItem).where(MenuItem.id == california.id)
            result = await db.execute(stmt)
            california_item = result.scalar_one()
            
            size_group_obj = await db.get(MenuModifierGroup, modifier_groups['size'])
            extras_group_obj = await db.get(MenuModifierGroup, modifier_groups['extras'])
            
            california_item.modifier_groups.append(size_group_obj)
            california_item.modifier_groups.append(extras_group_obj)
            items_created += 1
            
            spicy_tuna = await create_item(db, MenuItemCreate(
                name="Spicy Tuna Roll",
                category_id=categories['sushi'],
                price=1400,  # $14.00
                description="Fresh tuna with spicy mayo",
                plu="ROLL-002",
                is_available=True
            ))
            # Link modifiers
            stmt = select(MenuItem).where(MenuItem.id == spicy_tuna.id)
            result = await db.execute(stmt)
            spicy_tuna_item = result.scalar_one()
            spicy_tuna_item.modifier_groups.append(size_group_obj)
            spicy_tuna_item.modifier_groups.append(extras_group_obj)
            spicy_tuna_item.modifier_groups.append(await db.get(MenuModifierGroup, modifier_groups['spice']))
            items_created += 1
            
            salmon_roll = await create_item(db, MenuItemCreate(
                name="Salmon Roll",
                category_id=categories['sushi'],
                price=1300,  # $13.00
                description="Fresh salmon and cucumber",
                plu="ROLL-003",
                is_available=True
            ))
            items_created += 1
            
            rainbow_roll = await create_item(db, MenuItemCreate(
                name="Rainbow Roll",
                category_id=categories['sushi'],
                price=1800,  # $18.00
                description="California roll topped with assorted sashimi",
                plu="ROLL-004",
                is_available=True
            ))
            items_created += 1
            
            # Sashimi
            salmon_sashimi = await create_item(db, MenuItemCreate(
                name="Salmon Sashimi",
                category_id=categories['sashimi'],
                price=1500,  # $15.00
                description="Fresh salmon (6 pieces)",
                plu="SASH-001",
                is_available=True
            ))
            items_created += 1
            
            tuna_sashimi = await create_item(db, MenuItemCreate(
                name="Tuna Sashimi",
                category_id=categories['sashimi'],
                price=1800,  # $18.00
                description="Fresh tuna (6 pieces)",
                plu="SASH-002",
                is_available=True
            ))
            items_created += 1
            
            # Beverages
            green_tea = await create_item(db, MenuItemCreate(
                name="Green Tea",
                category_id=categories['beverages'],
                price=300,  # $3.00
                description="Hot Japanese green tea",
                plu="BEV-001",
                is_available=True
            ))
            items_created += 1
            
            sake = await create_item(db, MenuItemCreate(
                name="Sake",
                category_id=categories['beverages'],
                price=800,  # $8.00
                description="Premium Japanese rice wine",
                plu="BEV-002",
                is_available=True
            ))
            items_created += 1
            
            coke = await create_item(db, MenuItemCreate(
                name="Coca Cola",
                category_id=categories['beverages'],
                price=400,  # $4.00
                description="Classic Coca Cola",
                plu="BEV-003",
                is_available=True
            ))
            items_created += 1
            
            await db.commit()
            logger.info(f"Created {items_created} menu items")
            
            # Invalidate cache
            from app.utils.menu_cache_sdk import menu_cache
            try:
                menu_cache.clear_cache()
                logger.info("Cleared menu cache")
            except:
                logger.warning("Could not clear menu cache")
            
            logger.info("Menu seeding completed successfully!")
            
        except Exception as e:
            logger.error(f"Error seeding menu: {str(e)}")
            await db.rollback()
            raise
        finally:
            await db.close()

if __name__ == "__main__":
    asyncio.run(seed_menu())