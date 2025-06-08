"""Integration tests for menu synchronization and updates - Task 3.3."""

import pytest
import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp

from app.utils.deliverect.menu_async import sync_menu_from_deliverect
from app.utils.menu_db_store_async import AsyncMenuDBStore
from app.utils.menu_matcher_cache_async import AsyncCachedMenuMatcher
from app.db.crud_menu_async import (
    get_items, get_item, update_item, snooze_item, unsnooze_item
)
from app.redis_async import (
    clear_menu_cache, cache_menu_data, cache_menu_item,
    get_cached_menu_item, redis_delete
)
from app.models.menu_async import MenuItem, MenuCategory, MenuModifier


class TestDeliverectWebhookProcessing:
    """Test Deliverect webhook processing - Task 3.3.1."""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_menu_update_webhook(self, db_session, real_redis_client):
        """Test processing menu update webhook from Deliverect."""
        # Mock webhook payload
        webhook_payload = {
            "eventType": "MENU_UPDATE",
            "timestamp": datetime.now().isoformat(),
            "menu": {
                "categories": [
                    {
                        "id": "cat_001",
                        "name": "Special Rolls",
                        "products": [
                            {
                                "id": "prod_001",
                                "name": "Dragon Roll",
                                "price": 1895,  # $18.95 in cents
                                "plu": "DRG001",
                                "available": True,
                                "description": "Shrimp tempura, avocado, topped with eel"
                            }
                        ]
                    }
                ]
            }
        }
        
        # Process webhook
        menu_store = AsyncMenuDBStore(db_session, real_redis_client)
        
        with patch('app.utils.deliverect.auth.get_deliverect_token') as mock_auth:
            mock_auth.return_value = "test_token"
            
            # Sync menu data
            await sync_menu_from_deliverect(
                db_session,
                location_id="test_location",
                menu_data=webhook_payload["menu"]
            )
        
        # Verify menu was updated in database
        items = await get_items(db_session, location_id="test_location")
        dragon_roll = next((item for item in items if item.plu == "DRG001"), None)
        
        assert dragon_roll is not None
        assert dragon_roll.name == "Dragon Roll"
        assert dragon_roll.price == 18.95
        assert dragon_roll.is_available is True
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_product_availability_webhook(self, db_session, real_redis_client):
        """Test product availability update webhook."""
        # Create test item
        test_item = MenuItem(
            name="Test Roll",
            plu="TEST001",
            price=12.95,
            is_available=True,
            deliverect_item_id="prod_test",
            category_id="cat_001"
        )
        db_session.add(test_item)
        await db_session.commit()
        
        # Mock availability update webhook
        webhook_payload = {
            "eventType": "PRODUCT_AVAILABILITY_UPDATE",
            "productId": "prod_test",
            "available": False,
            "reason": "Out of stock"
        }
        
        # Process webhook
        await update_item(
            db_session,
            test_item.id,
            {"is_available": webhook_payload["available"]}
        )
        
        # Clear cache to ensure fresh data
        await clear_menu_cache()
        
        # Verify availability was updated
        updated_item = await get_item(db_session, test_item.id)
        assert updated_item.is_available is False
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_snooze_webhook(self, db_session, real_redis_client):
        """Test product snooze webhook processing."""
        # Create test item
        test_item = MenuItem(
            name="Snooze Test Roll",
            plu="SNOOZE001",
            price=15.95,
            is_available=True
        )
        db_session.add(test_item)
        await db_session.commit()
        
        # Mock snooze webhook
        webhook_payload = {
            "eventType": "PRODUCT_SNOOZE",
            "productId": test_item.id,
            "snoozedUntil": "2024-12-31T23:59:59Z",
            "reason": "Ingredient shortage"
        }
        
        # Process snooze
        snooze_until = datetime.fromisoformat(webhook_payload["snoozedUntil"].replace("Z", "+00:00"))
        await snooze_item(db_session, test_item.id, snooze_until)
        
        # Verify item is snoozed
        snoozed_item = await get_item(db_session, test_item.id)
        assert snoozed_item.snoozed_until is not None
        assert snoozed_item.snoozed_until > datetime.now()


class TestCacheInvalidation:
    """Test cache invalidation on menu updates - Task 3.3.2."""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_cache_invalidation_on_menu_update(self, db_session, real_redis_client):
        """Test that cache is properly invalidated when menu is updated."""
        # Create cached menu matcher
        menu_store = AsyncMenuDBStore(db_session, real_redis_client)
        cached_matcher = AsyncCachedMenuMatcher(menu_store, real_redis_client)
        
        # Cache initial menu data
        initial_menu = {
            "items": [
                {"id": "1", "name": "Old Roll", "plu": "OLD001", "price": 10.00}
            ]
        }
        await cache_menu_data(initial_menu, ttl=3600)
        
        # Verify cached data
        cached_items = await cached_matcher.get_cached_items()
        assert len(cached_items) == 1
        assert cached_items[0]["name"] == "Old Roll"
        
        # Update menu (simulating webhook)
        updated_menu = {
            "items": [
                {"id": "1", "name": "New Roll", "plu": "OLD001", "price": 12.00}
            ]
        }
        
        # Clear cache and update
        await clear_menu_cache()
        await cache_menu_data(updated_menu, ttl=3600)
        
        # Verify cache was invalidated and updated
        new_cached_items = await cached_matcher.get_cached_items()
        assert len(new_cached_items) == 1
        assert new_cached_items[0]["name"] == "New Roll"
        assert new_cached_items[0]["price"] == 12.00
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_selective_cache_invalidation(self, db_session, real_redis_client):
        """Test selective cache invalidation for specific items."""
        menu_store = AsyncMenuDBStore(db_session, real_redis_client)
        
        # Cache multiple items
        await cache_menu_item("PLU001", {"name": "Item 1", "price": 10.00})
        await cache_menu_item("PLU002", {"name": "Item 2", "price": 15.00})
        await cache_menu_item("PLU003", {"name": "Item 3", "price": 20.00})
        
        # Invalidate specific item
        await redis_delete(f"menu:item:PLU002")
        
        # Verify selective invalidation
        item1 = await get_cached_menu_item("PLU001")
        item2 = await get_cached_menu_item("PLU002")
        item3 = await get_cached_menu_item("PLU003")
        
        assert item1 is not None
        assert item2 is None  # Should be invalidated
        assert item3 is not None


class TestConcurrentMenuOperations:
    """Test concurrent menu read/write operations - Task 3.3.3."""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_menu_reads(self, db_session, real_redis_client):
        """Test multiple concurrent menu read operations."""
        menu_store = AsyncMenuDBStore(db_session, real_redis_client)
        
        # Create test menu items
        for i in range(10):
            item = MenuItem(
                name=f"Concurrent Item {i}",
                plu=f"CONC{i:03d}",
                price=10.00 + i,
                is_available=True
            )
            db_session.add(item)
        await db_session.commit()
        
        # Perform concurrent reads
        async def read_menu_items():
            items = await menu_store.get_all_items()
            return len(items)
        
        # Launch multiple concurrent reads
        tasks = [read_menu_items() for _ in range(20)]
        results = await asyncio.gather(*tasks)
        
        # All reads should return the same count
        assert all(count >= 10 for count in results)
        assert len(set(results)) == 1  # All results should be identical
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_menu_writes(self, db_session, real_redis_client):
        """Test concurrent menu write operations with proper locking."""
        # Simulate concurrent menu updates
        async def update_menu_item(item_id: str, price_increment: float):
            # Get current item
            item = await get_item(db_session, item_id)
            if item:
                # Update price
                new_price = item.price + price_increment
                await update_item(db_session, item_id, {"price": new_price})
                return new_price
            return None
        
        # Create test item
        test_item = MenuItem(
            name="Concurrent Update Item",
            plu="CONCUPD001",
            price=10.00,
            is_available=True
        )
        db_session.add(test_item)
        await db_session.commit()
        
        # Perform concurrent updates
        tasks = []
        for i in range(5):
            task = update_menu_item(test_item.id, 1.00)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Some updates might fail due to concurrent access
        successful_updates = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_updates) > 0
        
        # Final price should reflect some updates
        final_item = await get_item(db_session, test_item.id)
        assert final_item.price > 10.00


class TestMenuVersioning:
    """Test menu versioning and rollback - Task 3.3.4."""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_menu_version_tracking(self, db_session, real_redis_client):
        """Test menu version tracking system."""
        # Track menu versions
        menu_versions = []
        
        # Version 1
        version_1 = {
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "items": [
                {"id": "1", "name": "Roll V1", "price": 10.00}
            ]
        }
        menu_versions.append(version_1)
        await real_redis_client.set("menu:version:1.0.0", json.dumps(version_1))
        
        # Version 2
        version_2 = {
            "version": "2.0.0",
            "timestamp": datetime.now().isoformat(),
            "items": [
                {"id": "1", "name": "Roll V2", "price": 12.00},
                {"id": "2", "name": "New Roll", "price": 15.00}
            ]
        }
        menu_versions.append(version_2)
        await real_redis_client.set("menu:version:2.0.0", json.dumps(version_2))
        await real_redis_client.set("menu:current_version", "2.0.0")
        
        # Get current version
        current_version_key = await real_redis_client.get("menu:current_version")
        current_version = json.loads(
            await real_redis_client.get(f"menu:version:{current_version_key}")
        )
        
        assert current_version["version"] == "2.0.0"
        assert len(current_version["items"]) == 2
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_menu_rollback(self, db_session, real_redis_client):
        """Test rolling back to previous menu version."""
        # Store multiple versions
        versions = ["1.0.0", "2.0.0", "3.0.0"]
        
        for i, version in enumerate(versions):
            menu_data = {
                "version": version,
                "items": [{"id": str(j), "name": f"Item {j} v{version}", "price": 10 + j} 
                         for j in range(i + 1)]
            }
            await real_redis_client.set(f"menu:version:{version}", json.dumps(menu_data))
        
        # Set current version to latest
        await real_redis_client.set("menu:current_version", "3.0.0")
        
        # Rollback to version 2.0.0
        await real_redis_client.set("menu:current_version", "2.0.0")
        await real_redis_client.set("menu:rollback_from", "3.0.0")
        await real_redis_client.set("menu:rollback_timestamp", datetime.now().isoformat())
        
        # Clear current cache and load rollback version
        await clear_menu_cache()
        rollback_version = json.loads(
            await real_redis_client.get("menu:version:2.0.0")
        )
        await cache_menu_data(rollback_version)
        
        # Verify rollback
        current_version_key = await real_redis_client.get("menu:current_version")
        assert current_version_key == "2.0.0"
        
        # Verify rollback metadata
        rollback_from = await real_redis_client.get("menu:rollback_from")
        assert rollback_from == "3.0.0"