import asyncio
from app.db_async import async_session_factory
from app.models.menu_async import MenuItem
from sqlalchemy import select

async def test():
    async with async_session_factory() as db:
        result = await db.execute(select(MenuItem).where(MenuItem.name.ilike('%roll%') | MenuItem.name.ilike('%sushi%') | MenuItem.name.ilike('%nigiri%')))
        items = result.scalars().all()
        print(f'Found {len(items)} sushi items in database:')
        for item in items:
            print(f'  - {item.name}: ${item.price} (PLU: {item.plu})')
            
        # Also check all items
        all_result = await db.execute(select(MenuItem))
        all_items = all_result.scalars().all()
        print(f'\nTotal items in database: {len(all_items)}')

if __name__ == "__main__":
    asyncio.run(test())