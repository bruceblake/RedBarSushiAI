import json
import pytest


@pytest.mark.integration
def test_category_preservation(flask_client, deliverect_menu_json):
    """
    Test that categories are correctly preserved when receiving menu updates
    from Deliverect. In Deliverect, categories are defined and items are
    assigned to categories via categoryId.

    This test verifies:
    1. Categories are correctly created from a Deliverect menu update
    2. Items are properly assigned to their categories
    3. Category structure is preserved in the menu data
    """
    # Submit a Deliverect-format menu update
    response = flask_client.post(
        "/menu_update",
        data=json.dumps(deliverect_menu_json),
        content_type="application/json",
    )
    assert response.status_code == 200

    # Get the menu to verify category structure
    menu_response = flask_client.get("/menu")
    assert menu_response.status_code == 200
    menu_data = menu_response.json

    # Verify categories exist
    assert "categories" in menu_data
    assert len(menu_data["categories"]) > 0

    # Create a map of category IDs from the input data for verification
    input_categories = {}
    if "data" in deliverect_menu_json and "categories" in deliverect_menu_json["data"]:
        for category in deliverect_menu_json["data"]["categories"]:
            input_categories[category.get("id")] = category.get("name")
    elif "categories" in deliverect_menu_json:
        for category in deliverect_menu_json["categories"]:
            input_categories[category.get("id")] = category.get("name")

    # Verify that the categories in the menu match what was in the input
    output_categories = {
        cat.get("id"): cat.get("name") for cat in menu_data["categories"]
    }
    for cat_id, cat_name in input_categories.items():
        assert (
            cat_id in output_categories
        ), f"Category ID {cat_id} missing from output menu"
        assert (
            output_categories[cat_id] == cat_name
        ), f"Category name mismatch for ID {cat_id}. Expected {cat_name}, got {output_categories[cat_id]}"

    # Check that items are assigned to the correct categories
    for item in menu_data["items"]:
        if "categoryId" in item:
            assert (
                item["categoryId"] in output_categories
            ), f"Item {item['name']} assigned to non-existent category ID {item['categoryId']}"


@pytest.mark.integration
def test_category_update(flask_client):
    """
    Test that category updates are correctly handled by the API.
    This includes category creation, renaming, and deletion.

    This test verifies:
    1. New categories can be added
    2. Existing categories can be renamed
    3. Categories can be removed (if supported)
    4. Items in deleted categories are handled appropriately
    """
    # Create initial menu with categories
    initial_menu = {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "type": "menu.updated",
        "data": {
            "categories": [
                {"id": "CAT-1", "name": "Appetizers", "description": "Starter dishes"},
                {"id": "CAT-2", "name": "Main Courses", "description": "Main dishes"},
                {"id": "CAT-3", "name": "Desserts", "description": "Sweet treats"},
            ],
            "items": [
                {
                    "plu": "ITEM-1",
                    "name": "Spring Rolls",
                    "price": 699,
                    "categoryId": "CAT-1",
                    "available": True,
                },
                {
                    "plu": "ITEM-2",
                    "name": "Grilled Salmon",
                    "price": 1899,
                    "categoryId": "CAT-2",
                    "available": True,
                },
                {
                    "plu": "ITEM-3",
                    "name": "Chocolate Cake",
                    "price": 799,
                    "categoryId": "CAT-3",
                    "available": True,
                },
            ],
        },
    }

    # Submit the initial menu
    response = flask_client.post(
        "/menu_update", data=json.dumps(initial_menu), content_type="application/json"
    )
    assert response.status_code == 200

    # Update with category changes
    updated_menu = {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "type": "menu.updated",
        "data": {
            "categories": [
                {
                    "id": "CAT-1",
                    "name": "Starters",  # Renamed from "Appetizers"
                    "description": "Starter dishes",
                },
                {"id": "CAT-2", "name": "Main Courses", "description": "Main dishes"},
                {
                    "id": "CAT-4",  # New category
                    "name": "Beverages",
                    "description": "Drinks",
                },
                # CAT-3 (Desserts) is omitted - testing category removal
            ],
            "items": [
                {
                    "plu": "ITEM-1",
                    "name": "Spring Rolls",
                    "price": 699,
                    "categoryId": "CAT-1",
                    "available": True,
                },
                {
                    "plu": "ITEM-2",
                    "name": "Grilled Salmon",
                    "price": 1899,
                    "categoryId": "CAT-2",
                    "available": True,
                },
                {
                    "plu": "ITEM-3",
                    "name": "Chocolate Cake",
                    "price": 799,
                    "categoryId": None,  # Item's category was removed
                    "available": True,
                },
                {
                    "plu": "ITEM-4",
                    "name": "Lemonade",
                    "price": 399,
                    "categoryId": "CAT-4",  # Item in new category
                    "available": True,
                },
            ],
        },
    }

    # Submit the updated menu
    update_response = flask_client.post(
        "/menu_update", data=json.dumps(updated_menu), content_type="application/json"
    )
    assert update_response.status_code == 200

    # Get the updated menu
    menu_response = flask_client.get("/menu")
    assert menu_response.status_code == 200
    updated_data = menu_response.json

    # Verify category changes
    categories = {cat["id"]: cat for cat in updated_data["categories"]}

    # Check category renaming
    assert "CAT-1" in categories
    assert categories["CAT-1"]["name"] == "Starters"

    # Check new category
    assert "CAT-4" in categories
    assert categories["CAT-4"]["name"] == "Beverages"

    # Check category removal (if supported)
    # Note: Some implementations might keep all categories, so this check is conditional
    dessert_category_exists = "CAT-3" in categories

    # Find items by PLU
    items = {item["plu"]: item for item in updated_data["items"]}

    # Check that the dessert item (ITEM-3) has the correct category assignment
    assert "ITEM-3" in items
    if dessert_category_exists:
        # If the category wasn't deleted, the item might still be assigned to it
        pass
    else:
        # If implementation removes categories, the item should have no category
        # or be assigned to a default category
        assert (
            items["ITEM-3"].get("categoryId") is None
            or items["ITEM-3"].get("categoryId") != "CAT-3"
        ), f"Item still assigned to deleted category: {items['ITEM-3'].get('categoryId')}"

    # Check new item is in the new category
    assert "ITEM-4" in items
    assert items["ITEM-4"]["categoryId"] == "CAT-4"


@pytest.mark.integration
def test_nested_categories(flask_client):
    """
    Test that nested category structures are correctly handled.
    Deliverect supports parent-child relationships between categories.

    This test verifies:
    1. Parent-child relationships between categories are preserved
    2. Items can be assigned to subcategories
    3. Category hierarchy is maintained after updates
    """
    # Create a menu with nested categories
    nested_categories_menu = {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "type": "menu.updated",
        "data": {
            "categories": [
                {"id": "PARENT-1", "name": "Beverages", "description": "All drinks"},
                {
                    "id": "CHILD-1",
                    "name": "Hot Drinks",
                    "description": "Warm beverages",
                    "parentId": "PARENT-1",
                },
                {
                    "id": "CHILD-2",
                    "name": "Cold Drinks",
                    "description": "Chilled beverages",
                    "parentId": "PARENT-1",
                },
                {"id": "PARENT-2", "name": "Food", "description": "All food items"},
                {
                    "id": "CHILD-3",
                    "name": "Appetizers",
                    "description": "Starters",
                    "parentId": "PARENT-2",
                },
                {
                    "id": "GRANDCHILD-1",
                    "name": "Soups",
                    "description": "Hot soups",
                    "parentId": "CHILD-3",
                },
            ],
            "items": [
                {
                    "plu": "DRINK-1",
                    "name": "Coffee",
                    "price": 399,
                    "categoryId": "CHILD-1",
                    "available": True,
                },
                {
                    "plu": "DRINK-2",
                    "name": "Iced Tea",
                    "price": 349,
                    "categoryId": "CHILD-2",
                    "available": True,
                },
                {
                    "plu": "FOOD-1",
                    "name": "Miso Soup",
                    "price": 499,
                    "categoryId": "GRANDCHILD-1",
                    "available": True,
                },
            ],
        },
    }

    # Submit the nested categories menu
    response = flask_client.post(
        "/menu_update",
        data=json.dumps(nested_categories_menu),
        content_type="application/json",
    )
    assert response.status_code == 200

    # Get the menu to verify category structure
    menu_response = flask_client.get("/menu")
    assert menu_response.status_code == 200
    menu_data = menu_response.json

    # Check that categories exist
    categories = {cat["id"]: cat for cat in menu_data["categories"]}

    # Verify parent-child relationships
    assert "PARENT-1" in categories
    assert "CHILD-1" in categories

    # Check that child categories have the correct parentId
    assert categories["CHILD-1"].get("parentId") == "PARENT-1"
    assert categories["CHILD-2"].get("parentId") == "PARENT-1"
    assert categories["CHILD-3"].get("parentId") == "PARENT-2"
    assert categories["GRANDCHILD-1"].get("parentId") == "CHILD-3"

    # Verify items are in the correct categories
    items = {item["plu"]: item for item in menu_data["items"]}

    assert items["DRINK-1"]["categoryId"] == "CHILD-1"
    assert items["DRINK-2"]["categoryId"] == "CHILD-2"
    assert items["FOOD-1"]["categoryId"] == "GRANDCHILD-1"

    # Update to test category hierarchy changes
    updated_nested_menu = {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "type": "menu.updated",
        "data": {
            "categories": [
                {"id": "PARENT-1", "name": "Beverages", "description": "All drinks"},
                {
                    "id": "CHILD-1",
                    "name": "Hot Drinks",
                    "description": "Warm beverages",
                    "parentId": "PARENT-1",
                },
                {
                    "id": "CHILD-2",
                    "name": "Cold Drinks",
                    "description": "Chilled beverages",
                    "parentId": "PARENT-1",
                },
                {"id": "PARENT-2", "name": "Food", "description": "All food items"},
                {
                    "id": "CHILD-3",
                    "name": "Appetizers",
                    "description": "Starters",
                    "parentId": "PARENT-2",
                },
                {
                    "id": "GRANDCHILD-1",
                    "name": "Soups",
                    "description": "Hot soups",
                    # Changed parent from CHILD-3 to PARENT-2
                    "parentId": "PARENT-2",
                },
            ]
        },
    }

    # Submit the updated nested categories menu
    update_response = flask_client.post(
        "/menu_update",
        data=json.dumps(updated_nested_menu),
        content_type="application/json",
    )
    assert update_response.status_code == 200

    # Get the updated menu
    updated_menu_response = flask_client.get("/menu")
    assert updated_menu_response.status_code == 200
    updated_menu_data = updated_menu_response.json

    # Check that the hierarchy was updated correctly
    updated_categories = {cat["id"]: cat for cat in updated_menu_data["categories"]}

    # Verify the changed parentId
    assert (
        updated_categories["GRANDCHILD-1"].get("parentId") == "PARENT-2"
    ), f"Category GRANDCHILD-1 parent not updated. Expected PARENT-2, got {updated_categories['GRANDCHILD-1'].get('parentId')}"
