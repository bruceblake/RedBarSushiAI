import asyncio
from app.db_async import async_session_factory
from app.models.menu_async import MenuItem
from sqlalchemy import select

async def test():
    async with async_session_factory() as db:
        result = await db.execute(select(MenuItem).limit(5))
        items = result.scalars().all()
        print(f'Found {len(items)} items in database:')
        for item in items:
            print(f'  - {item.name}: ${item.price}')

if __name__ == "__main__":
    asyncio.run(test())