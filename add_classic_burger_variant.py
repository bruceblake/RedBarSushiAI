#!/usr/bin/env python3
"""
Add classic burger variant manually to test the fix.
"""

import asyncio
import sys
import os

# Add the app directory to the path so we can import models
sys.path.append('/app')

from app.db_async import async_session_factory
from app.models.menu_async import MenuNameVariant
from sqlalchemy import select

async def add_classic_burger_variant():
    """Add name variant mapping classic burger to cheeseburger."""
    
    async with async_session_factory() as db:
        try:
            # Check if variant already exists
            result = await db.execute(
                select(MenuNameVariant).filter(
                    MenuNameVariant.variant_phrase == "classic burger"
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                print(f"✅ Variant already exists: {existing.variant_phrase} → {existing.canonical_name}")
                return
            
            # Create new variant
            variant = MenuNameVariant(
                variant_phrase="classic burger",
                canonical_name="Cheeseburger",
                target_plu="P-BURG-CHE",
                score=0.9
            )
            
            db.add(variant)
            await db.commit()
            
            print(f"✅ Added variant: classic burger → Cheeseburger")
            
            # Verify it was added
            result = await db.execute(
                select(MenuNameVariant).filter(
                    MenuNameVariant.variant_phrase == "classic burger"
                )
            )
            created = result.scalar_one_or_none()
            
            if created:
                print(f"✅ Verification successful: {created.variant_phrase} → {created.canonical_name}")
            else:
                print(f"❌ Verification failed: variant not found after creation")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(add_classic_burger_variant())