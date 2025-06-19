#!/usr/bin/env python3
"""
Simple menu seeding script for testing RedBarSushiAI.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.db_async import get_db
from app.models.menu_async import MenuCategory, MenuItem, MenuNameVariant

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed_sample_menu():
    """Seed database with sample menu items for testing."""
    
    async for db in get_db():
        try:
            # Create sample category
            sushi_category = MenuCategory(
                name="Sushi Rolls",
                description="Fresh sushi rolls made to order",
                order_index=1
            )
            db.add(sushi_category)
            await db.flush()  # Get the ID
            
            # Create sample menu items
            california_roll = MenuItem(
                name="California Roll",
                description="Crab, avocado, cucumber",
                price=12.95,
                plu="SUSHI001",
                category_id=sushi_category.id,
                is_available=True
            )
            
            spicy_tuna_roll = MenuItem(
                name="Spicy Tuna Roll", 
                description="Spicy tuna with cucumber",
                price=14.95,
                plu="SUSHI002",
                category_id=sushi_category.id,
                is_available=True
            )
            
            salmon_roll = MenuItem(
                name="Salmon Avocado Roll",
                description="Fresh salmon with avocado",
                price=13.95,
                plu="SUSHI003", 
                category_id=sushi_category.id,
                is_available=True
            )
            
            db.add_all([california_roll, spicy_tuna_roll, salmon_roll])
            
            # Create name variants for better AI matching
            variants = [
                MenuNameVariant(
                    variant_phrase="california roll",
                    canonical_name="California Roll",
                    target_plu="SUSHI001",
                    score=1.0
                ),
                MenuNameVariant(
                    variant_phrase="cali roll",
                    canonical_name="California Roll", 
                    target_plu="SUSHI001",
                    score=0.9
                ),
                MenuNameVariant(
                    variant_phrase="spicy tuna",
                    canonical_name="Spicy Tuna Roll",
                    target_plu="SUSHI002",
                    score=1.0
                ),
                MenuNameVariant(
                    variant_phrase="salmon roll",
                    canonical_name="Salmon Avocado Roll",
                    target_plu="SUSHI003",
                    score=0.9
                ),
                MenuNameVariant(
                    variant_phrase="salmon avocado",
                    canonical_name="Salmon Avocado Roll",
                    target_plu="SUSHI003",
                    score=1.0
                )
            ]
            
            db.add_all(variants)
            
            # Commit changes
            await db.commit()
            
            logger.info("✅ Sample menu data seeded successfully!")
            logger.info("Created:")
            logger.info("  - 1 category: Sushi Rolls")
            logger.info("  - 3 menu items: California Roll, Spicy Tuna Roll, Salmon Avocado Roll")
            logger.info("  - 5 name variants for AI matching")
            
            return True
            
        except Exception as e:
            logger.error(f"Error seeding menu data: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            await db.rollback()
            return False
        finally:
            break  # Exit the async generator loop


async def main():
    """Main entry point."""
    logger.info("Starting menu seeding...")
    
    try:
        success = await seed_sample_menu()
        
        if success:
            logger.info("\n✅ Menu seeding completed successfully!")
            return 0
        else:
            logger.error("\n❌ Menu seeding failed!")
            return 1
            
    except Exception as e:
        logger.error(f"\n❌ Fatal error: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)