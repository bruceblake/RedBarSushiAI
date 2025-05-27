import asyncio
from app.db_async import async_session_factory
from app.models.menu_async import MenuItem
from sqlalchemy import select

async def check_items():
    async with async_session_factory() as db:
        result = await db.execute(select(MenuItem).order_by(MenuItem.name))
        items = result.scalars().all()
        print(f'Total items in database: {len(items)}')
        print('\nAll items:')
        for item in items:
            print(f'  - {item.name}: ${item.price} (PLU: {item.plu}, Available: {item.is_available})')

asyncio.run(check_items())