import asyncio
from app.db_async import async_session_factory
from app.utils.menu_utils_db_async import load_menu_data

async def test():
    print("Testing menu loading as agent would...")
    
    # Test 1: Direct session usage
    try:
        async with async_session_factory() as db:
            print("\nTest 1: Loading with direct session")
            menu_data = await load_menu_data(db)
            print(f"Success! Loaded {len(menu_data['items'])} items")
            for item in menu_data['items'][:3]:
                print(f"  - {item['name']}: ${item['price']}")
    except Exception as e:
        print(f"Error in test 1: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 2: Session passed as variable (like in agents)
    try:
        print("\nTest 2: Loading with passed session")
        db = async_session_factory()
        async with db:
            menu_data = await load_menu_data(db)
            print(f"Success! Loaded {len(menu_data['items'])} items")
    except Exception as e:
        print(f"Error in test 2: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 3: Session without context manager
    try:
        print("\nTest 3: Loading without context manager")
        db = async_session_factory()
        menu_data = await load_menu_data(db)
        print(f"Success! Loaded {len(menu_data['items'])} items")
        await db.close()
    except Exception as e:
        print(f"Error in test 3: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())