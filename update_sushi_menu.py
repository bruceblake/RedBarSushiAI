import json
import requests
import asyncio
from app.db_async import async_session_factory
from app.models.menu_async import MenuItem
from sqlalchemy import select

# Load the sushi menu
with open('sushi_menu.json', 'r') as f:
    menu_data = json.load(f)

# Send as a list (API expects array)
response = requests.post(
    'http://localhost:8080/api/deliverect/menu/update',
    json=[menu_data],
    headers={'Content-Type': 'application/json'}
)

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

# Check the database
async def check_items():
    async with async_session_factory() as db:
        result = await db.execute(select(MenuItem).order_by(MenuItem.name))
        items = result.scalars().all()
        print(f'\nTotal items in database: {len(items)}')
        for item in items:
            print(f'  - {item.name}: ${item.price} (PLU: {item.plu})')

asyncio.run(check_items())