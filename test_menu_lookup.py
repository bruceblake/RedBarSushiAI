"""
Test menu lookup directly to debug California roll issue.
"""

import asyncio
import logging
from app.utils.menu_matcher_db_async import AsyncMenuMatcher
from app.db_async import get_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_menu_lookup():
    """Test looking up California roll in the menu."""
    
    print("🔍 Testing menu lookup for California roll")
    print("-" * 50)
    
    # Get database session
    async for db in get_db():
        # Create menu matcher
        matcher = AsyncMenuMatcher(db)
        
        # Initialize it
        await matcher.initialize()
        print(f"Loaded {len(matcher.menu_items)} menu items")
        
        # Test lookup
        search_terms = ["California roll", "california roll", "California Roll", "CALIFORNIA ROLL"]
        
        for term in search_terms:
            print(f"\n📋 Searching for: '{term}'")
            
            # Find all matches
            matches = await matcher.find_all_matching_items(term, threshold=0.5)
            print(f"   Found {len(matches)} matches")
            
            for match in matches[:3]:  # Show first 3 matches
                print(f"   - {match['name']} (PLU: {match['plu']}, confidence: {match['confidence']:.2f})")
            
            # Find best match (using first match as best)
            if matches:
                best = matches[0]
                print(f"   ✅ Best match: {best['name']} (PLU: {best['plu']})")
            else:
                print(f"   ❌ No match found")
        
        break
    
    print("\n" + "-" * 50)
    print("✅ Menu lookup test complete")


if __name__ == "__main__":
    print("🚀 Running Menu Lookup Test")
    asyncio.run(test_menu_lookup())