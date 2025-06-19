#!/usr/bin/env python3
"""
Direct test of menu insertion without async generator.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.db_async import engine
from app.models.menu_async import MenuCategory, MenuItem, MenuNameVariant
from sqlalchemy.ext.asyncio import AsyncSession

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_direct_insert():
    """Test direct database insertion."""
    
    async with AsyncSession(engine) as session:
        try:
            # Create sample category
            sushi_category = MenuCategory(
                name="Sushi Rolls",
                description="Fresh sushi rolls made to order",
                order_index=1
            )
            session.add(sushi_category)
            await session.flush()  # Get the ID
            logger.info(f"Created category with ID: {sushi_category.id}")
            
            # Create sample menu item
            california_roll = MenuItem(
                name="California Roll",
                description="Crab, avocado, cucumber",
                price=12.95,
                plu="SUSHI001",
                category_id=sushi_category.id,
                is_available=True
            )
            session.add(california_roll)
            
            # Create name variant
            variant = MenuNameVariant(
                variant_phrase="california roll",
                canonical_name="California Roll",
                target_plu="SUSHI001",
                score=1.0
            )
            session.add(variant)
            
            # Commit changes
            await session.commit()
            
            logger.info("✅ Direct menu insert successful!")
            return True
            
        except Exception as e:
            logger.error(f"Error in direct insert: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            await session.rollback()
            return False


async def main():
    """Main entry point."""
    logger.info("Testing direct menu insertion...")
    
    try:
        success = await test_direct_insert()
        
        if success:
            logger.info("\n✅ Menu test completed successfully!")
            return 0
        else:
            logger.error("\n❌ Menu test failed!")
            return 1
            
    except Exception as e:
        logger.error(f"\n❌ Fatal error: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)