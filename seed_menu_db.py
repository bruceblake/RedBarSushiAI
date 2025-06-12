#!/usr/bin/env python3
"""
Menu seeding script for RedBarSushiAI.
Loads sample menu data into the database.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from datetime import datetime

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

# Import models
from app.models.menu_async import MenuCategory, MenuItem, MenuModifier, MenuModifierGroup, MenuNameVariant
from app.models.location_async import Location

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed_menu_data(session: AsyncSession):
    """Load sample menu data into the database."""
    
    try:
        # Get the default location
        result = await session.execute(
            select(Location).where(Location.name == "Red Bar Sushi - Main")
        )
        location = result.scalar_one_or_none()
        
        if not location:
            logger.error("Default location not found! Run init_db.py first.")
            return False
        
        logger.info(f"Using location: {location.name} (ID: {location.id})")
        
        # Create categories
        logger.info("Creating menu categories...")
        categories = {}
        
        category_data = [
            ("Appetizers", "Start your meal with our delicious appetizers"),
            ("Sushi Rolls", "Fresh hand-rolled sushi made to order"),
            ("Nigiri", "Traditional sushi pieces"),
            ("Sashimi", "Fresh sliced fish"),
            ("Beverages", "Drinks and refreshments"),
            ("Desserts", "Sweet endings to your meal")
        ]
        
        for name, description in category_data:
            category = MenuCategory(
                name=name,
                description=description,
                display_order=len(categories) + 1,
                is_active=True,
                location_id=location.id
            )
            session.add(category)
            categories[name] = category
        
        await session.flush()  # Get IDs for categories
        
        # Create menu items
        logger.info("Creating menu items...")
        items = {}
        
        menu_items_data = [
            # Appetizers
            ("Appetizers", "EDAMAME_001", "Edamame", "Steamed soybeans with sea salt", 595),
            ("Appetizers", "GYOZA_001", "Gyoza", "Pan-fried pork dumplings (6 pieces)", 795),
            ("Appetizers", "MISO_SOUP_001", "Miso Soup", "Traditional soybean soup with tofu and seaweed", 395),
            
            # Sushi Rolls
            ("Sushi Rolls", "CALI_ROLL_001", "California Roll", "Crab, avocado, and cucumber", 1295),
            ("Sushi Rolls", "SPICY_TUNA_001", "Spicy Tuna Roll", "Fresh tuna with spicy mayo and cucumber", 1495),
            ("Sushi Rolls", "SALMON_ROLL_001", "Salmon Roll", "Fresh salmon and avocado", 1395),
            ("Sushi Rolls", "RAINBOW_ROLL_001", "Rainbow Roll", "California roll topped with assorted sashimi", 1895),
            ("Sushi Rolls", "DRAGON_ROLL_001", "Dragon Roll", "Shrimp tempura and cucumber topped with eel and avocado", 1795),
            
            # Nigiri
            ("Nigiri", "SALMON_NIGIRI_001", "Salmon Nigiri", "Fresh salmon over rice (2 pieces)", 795),
            ("Nigiri", "TUNA_NIGIRI_001", "Tuna Nigiri", "Fresh tuna over rice (2 pieces)", 895),
            ("Nigiri", "YELLOWTAIL_NIGIRI_001", "Yellowtail Nigiri", "Fresh yellowtail over rice (2 pieces)", 895),
            
            # Beverages
            ("Beverages", "GREEN_TEA_001", "Green Tea", "Hot green tea", 295),
            ("Beverages", "SODA_001", "Soft Drink", "Coke, Sprite, or Orange", 395),
            ("Beverages", "SAKE_001", "Hot Sake", "Traditional Japanese rice wine", 895),
        ]
        
        for category_name, plu, name, description, price in menu_items_data:
            item = MenuItem(
                category_id=categories[category_name].id,
                plu=plu,
                name=name,
                description=description,
                price=price,
                is_available=True,
                location_id=location.id,
                deliverect_item_id=f"DEL_{plu}"
            )
            session.add(item)
            items[plu] = item
        
        await session.flush()
        
        # Create modifier groups
        logger.info("Creating modifier groups...")
        modifier_groups = {}
        
        modifier_group_data = [
            ("Extra Ingredients", 0, 5, 1),
            ("Spice Level", 0, 1, 2),
            ("Special Preparation", 0, 3, 3),
            ("Drink Options", 1, 1, 4)
        ]
        
        for name, min_sel, max_sel, display_order in modifier_group_data:
            group = MenuModifierGroup(
                name=name,
                min_selections=min_sel,
                max_selections=max_sel,
                display_order=display_order,
                location_id=location.id
            )
            session.add(group)
            modifier_groups[name] = group
        
        await session.flush()
        
        # Create modifiers
        logger.info("Creating modifiers...")
        modifiers_data = [
            # Extra Ingredients
            ("Extra Ingredients", "EXTRA_AVO_001", "Extra Avocado", 200),
            ("Extra Ingredients", "EXTRA_CRAB_001", "Extra Crab", 300),
            ("Extra Ingredients", "EXTRA_SPICY_MAYO_001", "Extra Spicy Mayo", 100),
            ("Extra Ingredients", "NO_WASABI_001", "No Wasabi", 0),
            ("Extra Ingredients", "EXTRA_GINGER_001", "Extra Ginger", 0),
            
            # Spice Level
            ("Spice Level", "MILD_001", "Mild", 0),
            ("Spice Level", "MEDIUM_001", "Medium", 0),
            ("Spice Level", "HOT_001", "Hot", 0),
            ("Spice Level", "EXTRA_HOT_001", "Extra Hot", 0),
            
            # Special Preparation
            ("Special Preparation", "SOY_PAPER_001", "Soy Paper (instead of seaweed)", 200),
            ("Special Preparation", "NO_RICE_001", "No Rice", 0),
            ("Special Preparation", "BROWN_RICE_001", "Brown Rice", 150),
            
            # Drink Options
            ("Drink Options", "ICE_001", "With Ice", 0),
            ("Drink Options", "NO_ICE_001", "No Ice", 0),
            ("Drink Options", "LEMON_001", "With Lemon", 0),
        ]
        
        for group_name, plu, name, price_change in modifiers_data:
            modifier = MenuModifier(
                plu=plu,
                name=name,
                price_change=price_change,
                is_available=True,
                location_id=location.id
            )
            session.add(modifier)
            
            # Link to modifier group
            await session.flush()
            modifier_groups[group_name].modifiers.append(modifier)
        
        # Link modifier groups to items
        logger.info("Linking modifier groups to items...")
        
        # All rolls can have extra ingredients and special preparation
        for roll_plu in ["CALI_ROLL_001", "SPICY_TUNA_001", "SALMON_ROLL_001", 
                         "RAINBOW_ROLL_001", "DRAGON_ROLL_001"]:
            items[roll_plu].modifier_groups.append(modifier_groups["Extra Ingredients"])
            items[roll_plu].modifier_groups.append(modifier_groups["Special Preparation"])
        
        # Spicy tuna can have spice level
        items["SPICY_TUNA_001"].modifier_groups.append(modifier_groups["Spice Level"])
        
        # Drinks have drink options
        items["SODA_001"].modifier_groups.append(modifier_groups["Drink Options"])
        
        # Create name variants for better matching
        logger.info("Creating name variants...")
        variants_data = [
            ("cali roll", "California Roll", "CALI_ROLL_001"),
            ("california", "California Roll", "CALI_ROLL_001"),
            ("spicy tuna", "Spicy Tuna Roll", "SPICY_TUNA_001"),
            ("tuna roll", "Spicy Tuna Roll", "SPICY_TUNA_001"),
            ("salmon", "Salmon Roll", "SALMON_ROLL_001"),
            ("sake roll", "Salmon Roll", "SALMON_ROLL_001"),
            ("rainbow", "Rainbow Roll", "RAINBOW_ROLL_001"),
            ("dragon", "Dragon Roll", "DRAGON_ROLL_001"),
            ("coke", "Soft Drink", "SODA_001"),
            ("coca cola", "Soft Drink", "SODA_001"),
            ("sprite", "Soft Drink", "SODA_001"),
            ("soda", "Soft Drink", "SODA_001"),
        ]
        
        for variant_phrase, canonical_name, target_plu in variants_data:
            variant = MenuNameVariant(
                variant_phrase=variant_phrase,
                canonical_name=canonical_name,
                target_plu=target_plu,
                location_id=location.id
            )
            session.add(variant)
        
        # Commit all changes
        await session.commit()
        logger.info("Menu data seeded successfully!")
        
        # Print summary
        result = await session.execute(select(MenuCategory))
        categories_count = len(result.scalars().all())
        
        result = await session.execute(select(MenuItem))
        items_count = len(result.scalars().all())
        
        result = await session.execute(select(MenuModifier))
        modifiers_count = len(result.scalars().all())
        
        logger.info(f"\nSummary:")
        logger.info(f"  Categories: {categories_count}")
        logger.info(f"  Items: {items_count}")
        logger.info(f"  Modifiers: {modifiers_count}")
        logger.info(f"  Name Variants: {len(variants_data)}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error seeding menu data: {e}")
        await session.rollback()
        return False


async def main():
    """Main entry point."""
    # Get database URL
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/redbarsushi"
    )
    
    # Ensure it's using asyncpg
    if "postgresql://" in database_url and "+asyncpg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    
    logger.info("Starting menu data seeding...")
    
    # Create engine and session
    engine = create_async_engine(database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as session:
            # Check if menu data already exists
            result = await session.execute(select(MenuItem))
            existing_items = result.scalars().all()
            
            if existing_items and "--force" not in sys.argv:
                logger.warning(f"Menu data already exists ({len(existing_items)} items). Use --force to overwrite.")
                return 1
            
            if existing_items and "--force" in sys.argv:
                logger.warning("Clearing existing menu data...")
                # Delete in reverse order of dependencies
                await session.execute(MenuNameVariant.__table__.delete())
                await session.execute(MenuItem.__table__.delete())
                await session.execute(MenuModifier.__table__.delete())
                await session.execute(MenuModifierGroup.__table__.delete())
                await session.execute(MenuCategory.__table__.delete())
                await session.commit()
            
            # Seed the data
            success = await seed_menu_data(session)
            
            if success:
                logger.info("\n✅ Menu data seeded successfully!")
                logger.info("\nThe system is now ready to run!")
                logger.info("Start the application with: uvicorn app.main:app --reload")
                return 0
            else:
                logger.error("\n❌ Menu seeding failed!")
                return 1
                
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    if "--help" in sys.argv:
        print("Usage: python seed_menu_db.py [--force]")
        print("  --force: Clear existing menu data before seeding")
        sys.exit(0)
    
    exit_code = asyncio.run(main())
    sys.exit(exit_code)