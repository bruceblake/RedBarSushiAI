import json
import requests

# Load the sample menu
with open('sample_deliverect_menu_subset.json', 'r') as f:
    data = json.load(f)

# Extract just the menu data
menu_data = data['data']['menu']

# Send the update
response = requests.post(
    'http://localhost:8080/api/deliverect/menu/update',
    json=menu_data,
    headers={'Content-Type': 'application/json'}
)

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

# Check the database
import asyncio
from app.db_async import async_session_factory
from app.models.menu_async import MenuItem
from sqlalchemy import select

async def check_items():
    async with async_session_factory() as db:
        result = await db.execute(select(MenuItem).where(MenuItem.name.ilike('%roll%') | MenuItem.name.ilike('%sushi%') | MenuItem.name.ilike('%nigiri%')))
        items = result.scalars().all()
        print(f'\nFound {len(items)} sushi items after update:')
        for item in items:
            print(f'  - {item.name}: ${item.price} (PLU: {item.plu})')

asyncio.run(check_items())