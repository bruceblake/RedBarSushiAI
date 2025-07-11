#!/usr/bin/env python3
"""
Check what's currently in the menu database.
"""

import asyncio
import sys
sys.path.insert(0, '/app')

from app.db_async import get_db
from app.db.crud_menu_async import get_all_menu_items

async def check_current_menu():
    """Check current menu contents."""
    
    async for db in get_db():
        try:
            print("🔍 CURRENT MENU DATABASE CONTENTS")
            print("=" * 60)
            
            # Get all menu items
            items = await get_all_menu_items(db)
            
            print(f"\n📊 Total items in database: {len(items)}")
            print("\n🍽️ MENU ITEMS:")
            print("-" * 40)
            
            for item in items:
                name = item.get('name', 'Unknown')
                plu = item.get('plu', 'No PLU')
                price = item.get('price', 0)
                category = item.get('category_name', 'No Category')
                available = not item.get('snoozed', False)
                
                status = "✅ Available" if available else "❌ Snoozed"
                
                print(f"• {name}")
                print(f"  PLU: {plu}")
                print(f"  Price: ${price:.2f}")
                print(f"  Category: {category}")
                print(f"  Status: {status}")
                print()
                
        finally:
            break
            
    print("🎉 MENU CHECK COMPLETE")

if __name__ == "__main__":
    asyncio.run(check_current_menu())