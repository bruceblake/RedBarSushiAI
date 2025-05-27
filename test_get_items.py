import asyncio
from app.db_async import async_session_factory
from app.db.crud_menu_async import get_items

async def test():
    try:
        async with async_session_factory() as db:
            print("Testing get_items function...")
            items = await get_items(db, limit=10)
            print(f"Successfully loaded {len(items)} items:")
            for item in items:
                print(f"  - {item.name}: ${item.price} (PLU: {item.plu})")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())