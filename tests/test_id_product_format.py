"""
Tests for handling the Deliverect format with string product IDs
"""

from app.utils.menu_utils import process_deliverect_menu


def test_deliverect_id_product_format():
    """Test handling Deliverect format where products are ID strings"""
    # Create test data
    test_data = [
        {
            "categories": [
                {"name": "Steak & Burgers", "products": ["prod1", "prod2", "prod3"]},
                {"name": "Pizza", "products": ["prod4", "prod5"]},
            ],
            "products": {
                "prod1": {"name": "Cheeseburger", "price": 1295, "plu": "CHEESE-BURG"},
                "prod2": {"name": "Hamburger", "price": 1195, "plu": "HAM-BURG"},
                "prod3": {"name": "Ribeye Steak", "price": 2995, "plu": "RIBEYE"},
                "prod4": {"name": "Pepperoni Pizza", "price": 1595, "plu": "PEPP-PIZ"},
                "prod5": {"name": "Vegetarian Pizza", "price": 1495, "plu": "VEG-PIZ"},
            },
        }
    ]

    # Process the test data
    result = process_deliverect_menu(test_data)

    # Verify the result - should create proper items with real names
    assert isinstance(result, dict)
    assert "items" in result
    assert len(result["items"]) == 5

    # Check that item names come from the product objects, not synthetic category names
    item_names = [item["name"] for item in result["items"]]
    assert "Cheeseburger" in item_names
    assert "Hamburger" in item_names
    assert "Ribeye Steak" in item_names
    assert "Pepperoni Pizza" in item_names
    assert "Vegetarian Pizza" in item_names

    # Verify no synthetic names like "Steak & Burgers Item" were created
    assert not any("Item" in name for name in item_names)

    # Verify PLU values were properly extracted as reference handlers
    item_refs = [item["reference_handler"] for item in result["items"]]
    assert "CHEESE-BURG" in item_refs
    assert "HAM-BURG" in item_refs
    assert "RIBEYE" in item_refs
    assert "PEPP-PIZ" in item_refs
    assert "VEG-PIZ" in item_refs
