"""
Test script to validate Redis and in-memory cache invalidation improvements in menu_db_store.py
"""

import json
import time
import logging
import sys
from app.utils.menu_db_store import menu_db_store

# Set up logging to console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

# Create a test menu with minimal data
TEST_MENU = {
    "items": [
        {
            "name": "Test Sushi Roll",
            "price": 12.99,
            "description": "A delicious test sushi roll",
            "category": "Sushi Rolls",
            "available": True,
            "reference_handler": "test-sushi-roll",
        },
        {
            "name": "Spicy Tuna",
            "price": 14.99,
            "description": "Spicy tuna roll with special sauce",
            "category": "Sushi Rolls",
            "available": True,
            "reference_handler": "spicy-tuna-roll",
        },
    ],
    "modifiers": [],
    "modifierGroups": [],
}


def verify_redis_cache_state():
    """Check Redis for keys matching our patterns"""
    if not menu_db_store.redis_client:
        print("Redis client not available")
        return {}

    try:
        # Check for menu: keys
        menu_keys = menu_db_store.redis_client.keys("menu:*")
        print(f"Found {len(menu_keys)} menu: keys in Redis: {menu_keys}")

        # Check for menu_item: keys
        menu_item_keys = menu_db_store.redis_client.keys("menu_item:*")
        print(f"Found {len(menu_item_keys)} menu_item: keys in Redis: {menu_item_keys}")

        return {"menu_keys": menu_keys, "menu_item_keys": menu_item_keys}
    except Exception as e:
        print(f"Error checking Redis cache: {e}")
        return {}


def verify_memory_cache_state():
    """Check in-memory cache for menu-related keys"""
    from app.utils.menu_db_store import _memory_cache, _memory_cache_timestamps

    # Count menu-related keys
    menu_keys = [k for k in _memory_cache.keys() if k.startswith("menu:")]
    menu_item_keys = [k for k in _memory_cache.keys() if k.startswith("menu_item:")]

    print(f"Found {len(menu_keys)} menu: keys in memory cache: {menu_keys}")
    print(
        f"Found {len(menu_item_keys)} menu_item: keys in memory cache: {menu_item_keys}"
    )

    return {"menu_keys": menu_keys, "menu_item_keys": menu_item_keys}


def run_test():
    print("\n=== Testing Menu Cache Invalidation ===\n")

    # 1. Store initial menu data
    print("\n--- Step 1: Storing initial menu data ---")
    result = menu_db_store.store_menu_data(TEST_MENU)
    print(f"Menu stored successfully: {result}")

    # 2. Load the data to cache it
    print("\n--- Step 2: Loading menu data to cache it ---")
    for i in range(3):
        # Load multiple times to ensure it's cached
        menu_data = menu_db_store.get_menu_data()
        print(f"Loaded menu with {len(menu_data['items'])} items (iteration {i+1})")

    # 3. Find items to create menu_item: cache entries
    print("\n--- Step 3: Finding menu items to cache them ---")
    for item in TEST_MENU["items"]:
        found_item = menu_db_store.find_menu_item(item["name"])
        print(f"Found item {item['name']}: {found_item is not None}")

    # 4. Check cache state before update
    print("\n--- Step 4: Checking cache state before update ---")
    redis_before = verify_redis_cache_state()
    memory_before = verify_memory_cache_state()

    # 5. Update a menu item which should invalidate caches
    print("\n--- Step 5: Updating a menu item ---")
    updated_item = TEST_MENU["items"][0].copy()
    updated_item["price"] = 15.99
    updated_item["description"] = "Updated description for cache test"

    result = menu_db_store.update_menu_item(updated_item)
    print(f"Menu item updated successfully: {result}")

    # 6. Check cache state after update
    print("\n--- Step 6: Checking cache state after update ---")
    redis_after = verify_redis_cache_state()
    memory_after = verify_memory_cache_state()

    # 7. Verify the caches were invalidated
    print("\n--- Step 7: Verifying cache invalidation ---")

    # Redis invalidation check
    redis_keys_removed = len(redis_before.get("menu_keys", [])) > len(
        redis_after.get("menu_keys", [])
    )
    redis_item_keys_removed = len(redis_before.get("menu_item_keys", [])) > len(
        redis_after.get("menu_item_keys", [])
    )

    # Memory cache invalidation check
    memory_keys_removed = len(memory_before.get("menu_keys", [])) > len(
        memory_after.get("menu_keys", [])
    )
    memory_item_keys_removed = len(memory_before.get("menu_item_keys", [])) > len(
        memory_after.get("menu_item_keys", [])
    )

    print(f"Redis menu: keys invalidated: {redis_keys_removed}")
    print(f"Redis menu_item: keys invalidated: {redis_item_keys_removed}")
    print(f"Memory menu: keys invalidated: {memory_keys_removed}")
    print(f"Memory menu_item: keys invalidated: {memory_item_keys_removed}")

    # 8. Load updated data to verify the update
    print("\n--- Step 8: Loading updated menu data ---")
    updated_menu = menu_db_store.get_menu_data(force_refresh=True)
    updated_item = next(
        (
            item
            for item in updated_menu["items"]
            if item["reference_handler"] == "test-sushi-roll"
        ),
        None,
    )

    if updated_item:
        print(f"Updated item price: {updated_item['price']}")
        print(f"Updated item description: {updated_item['description']}")
    else:
        print("Updated item not found")

    print("\n=== Cache Invalidation Test Complete ===\n")

    # Return success if all validations passed
    return (
        redis_keys_removed
        and redis_item_keys_removed
        and memory_keys_removed
        and memory_item_keys_removed
    )


if __name__ == "__main__":
    from flask import Flask
    from app import db

    # Create a minimal Flask application context
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///test_cache.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Initialize the database
    with app.app_context():
        db.init_app(app)
        db.create_all()

        # Run the test
        success = run_test()

        # Clean up
        db.drop_all()

    # Report final result
    if success:
        print("SUCCESS: Cache invalidation is working correctly!")
    else:
        print("FAILURE: Cache invalidation issues detected.")
        sys.exit(1)
