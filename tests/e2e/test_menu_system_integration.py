"""
End-to-end tests for menu system with caching and Deliverect integration.
Tests menu updates, cache invalidation, and agent menu lookups.
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.menu_async import MenuItem, MenuCategory
from app.utils.menu_matcher_cache_async import AsyncCachedMenuMatcher, clear_cached_menu_matcher, get_cached_async_menu_matcher
from app.agents.menu_async import AsyncMenuAgent
from app.api.deliverect_menu import handle_menu_update
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def sample_menu_data():
    """Sample menu data from Deliverect."""
    return [{
        "channelLinkId": "test_channel",
        "menuId": "menu_001",
        "categories": [
            {
                "name": "Sushi Rolls",
                "id": "cat_001",
                "description": "Fresh sushi rolls"
            }
        ],
        "products": {
            "item_001": {
                "name": "California Roll",
                "plu": "PLU_CALI_ROLL",
                "price": 1200,  # $12.00
                "description": "Crab, avocado, cucumber",
                "categoryId": "cat_001",
                "isAvailable": True,
                "modifierGroups": ["mg_001"]
            },
            "item_002": {
                "name": "Spicy Tuna Roll",
                "plu": "PLU_SPICY_TUNA",
                "price": 1400,  # $14.00
                "description": "Spicy tuna, cucumber",
                "categoryId": "cat_001",
                "isAvailable": True
            }
        },
        "modifierGroups": {
            "mg_001": {
                "name": "Spice Level",
                "plu": "PLU_SPICE",
                "min": 0,
                "max": 1,
                "modifiers": ["mod_001"]
            }
        },
        "modifiers": {
            "mod_001": {
                "name": "Extra Spicy",
                "plu": "PLU_EXTRA_SPICY",
                "price": 0
            }
        },
        "snoozedProducts": []
    }]


@pytest.mark.asyncio
async def test_menu_update_process(db_session, sample_menu_data):
    """Test complete menu update process from Deliverect."""
    # Clear existing data
    await db_session.execute(delete(MenuItem))
    await db_session.execute(delete(MenuCategory))
    await db_session.commit()
    
    # Process menu update
    background_tasks = MagicMock()
    result = await handle_menu_update(sample_menu_data, background_tasks, db_session)
    
    assert result["status"] == "ONLINE"
    
    # Verify data was saved
    categories = await db_session.execute(select(MenuCategory))
    assert len(categories.scalars().all()) == 1
    
    items = await db_session.execute(select(MenuItem))
    items_list = items.scalars().all()
    assert len(items_list) == 2
    
    # Check specific item
    cali_roll = next(i for i in items_list if i.plu == "PLU_CALI_ROLL")
    assert cali_roll.name == "California Roll"
    assert cali_roll.price == 1200
    assert cali_roll.is_available is True
    
    # Verify background task was scheduled
    background_tasks.add_task.assert_called_once()


@pytest.mark.asyncio
async def test_menu_cache_invalidation(db_session):
    """Test that menu cache is properly invalidated after update."""
    # Create a menu matcher
    matcher = AsyncCachedMenuMatcher(db_session)
    await matcher.initialize()
    
    # Mock Redis cache
    with patch('app.utils.menu_cache.menu_cache') as mock_cache:
        # Clear cache
        await clear_cached_menu_matcher()
        
        # Verify cache operations
        mock_cache.clear_all.assert_called_once()


@pytest.mark.asyncio
async def test_menu_agent_lookup(db_session):
    """Test menu agent looking up items."""
    # Create test menu item
    item = MenuItem(
        name="Rainbow Roll",
        plu="PLU_RAINBOW",
        price=1800,
        description="Assorted sashimi on California roll",
        is_available=True,
        deliverect_item_id="item_003"
    )
    db_session.add(item)
    await db_session.commit()
    
    # Create menu agent
    agent = AsyncMenuAgent(db=db_session)
    
    # Test lookup
    result = await agent._lookup_menu_item("Rainbow Roll")
    
    assert result["found"] is True
    assert result["name"] == "Rainbow Roll"
    assert result["price"] == "$18.00"
    assert result["is_available"] is True


@pytest.mark.asyncio
async def test_menu_agent_unavailable_item(db_session):
    """Test menu agent handling unavailable items."""
    # Create snoozed item
    item = MenuItem(
        name="Dragon Roll",
        plu="PLU_DRAGON",
        price=2000,
        is_available=False,
        snoozed_until=datetime.utcnow() + timedelta(hours=2)
    )
    db_session.add(item)
    await db_session.commit()
    
    agent = AsyncMenuAgent(db=db_session)
    result = await agent._lookup_menu_item("Dragon Roll")
    
    assert result["found"] is True
    assert result["is_available"] is False
    assert "currently unavailable" in result["availability_message"]


@pytest.mark.asyncio
async def test_menu_agent_fuzzy_matching(db_session):
    """Test fuzzy matching for menu items."""
    # Create items
    items = [
        MenuItem(name="Salmon Roll", plu="PLU_SALMON", price=1000),
        MenuItem(name="Spicy Salmon Roll", plu="PLU_SPICY_SALMON", price=1200)
    ]
    db_session.add_all(items)
    await db_session.commit()
    
    agent = AsyncMenuAgent(db=db_session)
    
    # Test fuzzy match
    result = await agent._lookup_menu_item("Salomon Roll")  # Typo
    
    assert result["found"] is True
    assert result["name"] == "Salmon Roll"  # Should find closest match


@pytest.mark.asyncio
async def test_menu_categories_listing(db_session):
    """Test listing menu categories."""
    # Create categories
    categories = [
        MenuCategory(name="Appetizers", deliverect_category_id="cat_app"),
        MenuCategory(name="Sushi", deliverect_category_id="cat_sushi"),
        MenuCategory(name="Drinks", deliverect_category_id="cat_drinks")
    ]
    db_session.add_all(categories)
    await db_session.commit()
    
    agent = AsyncMenuAgent(db=db_session)
    result = await agent._list_categories()
    
    assert len(result["categories"]) == 3
    assert "Appetizers" in result["categories"]
    assert "Sushi" in result["categories"]
    assert "Drinks" in result["categories"]


@pytest.mark.asyncio
async def test_menu_items_by_category(db_session):
    """Test getting items by category."""
    # Create category and items
    category = MenuCategory(name="Rolls", deliverect_category_id="cat_rolls")
    db_session.add(category)
    await db_session.flush()
    
    items = [
        MenuItem(name="Tuna Roll", plu="PLU_TUNA", price=800, category_id=category.id),
        MenuItem(name="Salmon Roll", plu="PLU_SALMON", price=900, category_id=category.id),
        MenuItem(name="Edamame", plu="PLU_EDAMAME", price=500, category_id=None)  # Different category
    ]
    db_session.add_all(items)
    await db_session.commit()
    
    agent = AsyncMenuAgent(db=db_session)
    result = await agent._get_items_by_category("Rolls")
    
    assert len(result["items"]) == 2
    item_names = [i["name"] for i in result["items"]]
    assert "Tuna Roll" in item_names
    assert "Salmon Roll" in item_names
    assert "Edamame" not in item_names


@pytest.mark.asyncio
async def test_snoozed_products_update(db_session, sample_menu_data):
    """Test updating snoozed products."""
    # Create item
    item = MenuItem(
        name="Test Item",
        plu="PLU_TEST",
        price=1000,
        is_available=True
    )
    db_session.add(item)
    await db_session.commit()
    
    # Add snoozed product
    sample_menu_data[0]["snoozedProducts"] = [{
        "plu": "PLU_TEST",
        "snooze_end": (datetime.utcnow() + timedelta(hours=1)).isoformat()
    }]
    
    # Process update
    background_tasks = MagicMock()
    await handle_menu_update(sample_menu_data, background_tasks, db_session)
    
    # Verify item is now unavailable
    updated_item = await db_session.get(MenuItem, item.id)
    assert updated_item.is_available is False
    assert updated_item.snoozed_until is not None


@pytest.mark.asyncio
async def test_menu_cache_force_refresh(db_session):
    """Test force refresh of menu cache."""
    # Create matcher
    matcher1 = await get_cached_async_menu_matcher(db_session)
    matcher2 = await get_cached_async_menu_matcher(db_session, force_refresh=False)
    matcher3 = await get_cached_async_menu_matcher(db_session, force_refresh=True)
    
    # Without force_refresh, should return same instance
    assert matcher1 is matcher2
    # With force_refresh, should create new instance
    assert matcher1 is not matcher3


@pytest.mark.asyncio
async def test_menu_agent_process_question(db_session):
    """Test menu agent processing natural language questions."""
    # Create test data
    category = MenuCategory(name="Sushi", deliverect_category_id="cat_sushi")
    db_session.add(category)
    await db_session.flush()
    
    item = MenuItem(
        name="Salmon Nigiri",
        plu="PLU_SALMON_NIGIRI",
        price=600,
        description="Fresh salmon over rice",
        category_id=category.id
    )
    db_session.add(item)
    await db_session.commit()
    
    agent = AsyncMenuAgent(db=db_session)
    
    # Test menu question
    response = await agent.process_input(
        "Do you have salmon nigiri?",
        {}
    )
    
    assert "Salmon Nigiri" in response["text"]
    assert "$6.00" in response["text"]
    assert "Fresh salmon over rice" in response["text"]


@pytest.mark.asyncio
async def test_menu_agent_category_question(db_session):
    """Test menu agent answering category questions."""
    categories = [
        MenuCategory(name="Appetizers", deliverect_category_id="cat_app"),
        MenuCategory(name="Sushi Rolls", deliverect_category_id="cat_rolls"),
        MenuCategory(name="Beverages", deliverect_category_id="cat_bev")
    ]
    db_session.add_all(categories)
    await db_session.commit()
    
    agent = AsyncMenuAgent(db=db_session)
    response = await agent.process_input(
        "What categories do you have?",
        {}
    )
    
    assert "Appetizers" in response["text"]
    assert "Sushi Rolls" in response["text"]
    assert "Beverages" in response["text"]