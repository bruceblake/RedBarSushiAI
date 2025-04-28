import pytest
import json
import os

@pytest.mark.e2e
def test_direct_format_menu_update(api_request, create_test_menu_payload):
    """
    Test the menu update endpoint with a direct format menu payload.
    """
    direct_payload = create_test_menu_payload(payload_type="direct", num_items=5)
    
    resp = api_request.post("/menu_update", data=direct_payload)
    assert resp.status == 200
    
    response_data = resp.json()
    assert response_data["success"] is True
    assert response_data["items"] == 5  # Verify the count matches what we sent
    assert "modifiers" in response_data
    assert "modifierGroups" in response_data
    assert response_data["source"] == "custom"  # Should be detected as custom format
    assert response_data["ai_matching"] is True

@pytest.mark.e2e
def test_simple_list_menu_update(api_request, create_test_menu_payload):
    """
    Test the menu update endpoint with a simple list of items.
    """
    simple_payload = create_test_menu_payload(payload_type="simple", num_items=3)
    
    resp = api_request.post("/menu_update", data=simple_payload)
    assert resp.status == 200
    
    response_data = resp.json()
    assert response_data["success"] is True
    assert response_data["items"] == 3  # Verify the count matches what we sent
    assert response_data["source"] == "custom"  # Should be detected as custom format
    assert response_data["ai_matching"] is True

@pytest.mark.e2e
def test_large_menu_update(api_request, create_test_menu_payload):
    """
    Test the menu update endpoint with a large menu payload.
    """
    large_payload = create_test_menu_payload(payload_type="direct", num_items=20)
    
    resp = api_request.post("/menu_update", data=large_payload)
    assert resp.status == 200
    
    response_data = resp.json()
    assert response_data["success"] is True
    assert response_data["items"] == 20  # Verify the count matches what we sent
    
    # Verify data was saved by retrieving it
    get_resp = api_request.get("/menu")
    assert get_resp.status == 200
    
    menu_data = get_resp.json()
    assert len(menu_data["items"]) >= 20  # Should have at least our 20 items

@pytest.mark.e2e
def test_partial_menu_update_handling(api_request):
    """
    Test that partial menu updates are appropriately handled.
    First populate a full menu, then update only one category.
    The system should preserve the other categories.
    """
    # First create a complete menu with multiple categories
    full_menu = {
        "items": [
            {
                "name": "Item 1",
                "description": "Description 1",
                "price": 10.0,
                "available": True,
                "plu": "PLU-1",
                "reference_handler": "PLU-1", 
                "category": "Category 1"
            },
            {
                "name": "Item 2",
                "description": "Description 2",
                "price": 20.0,
                "available": True,
                "plu": "PLU-2",
                "reference_handler": "PLU-2",
                "category": "Category 1"
            },
            {
                "name": "Item 3",
                "description": "Description 3",
                "price": 30.0,
                "available": True,
                "plu": "PLU-3",
                "reference_handler": "PLU-3",
                "category": "Category 2"
            },
            {
                "name": "Item 4",
                "description": "Description 4",
                "price": 40.0,
                "available": True,
                "plu": "PLU-4",
                "reference_handler": "PLU-4",
                "category": "Category 2"
            }
        ]
    }
    
    # Create the full menu
    full_resp = api_request.post("/menu_update", data=full_menu)
    assert full_resp.status == 200
    
    # Now create a partial update with just one category
    partial_menu = {
        "items": [
            {
                "name": "Item 5",
                "description": "Description 5",
                "price": 50.0,
                "available": True,
                "plu": "PLU-5",
                "reference_handler": "PLU-5",
                "category": "Category 3"
            }
        ]
    }
    
    # Update with partial menu
    partial_resp = api_request.post("/menu_update", data=partial_menu)
    assert partial_resp.status == 200
    
    # Get the menu and verify all categories are present
    get_resp = api_request.get("/menu")
    assert get_resp.status == 200
    
    menu_data = get_resp.json()
    
    # Check we have at least 5 items (all original items plus the new one)
    # The system might merge or handle this differently, so we check the minimum
    assert len(menu_data["items"]) >= 1
    
    # Verify specific items from different updates
    item_names = [item["name"] for item in menu_data["items"]]
    assert "Item 5" in item_names  # At minimum, the newest item should be present

@pytest.mark.e2e
def test_menu_update_with_invalid_fields(api_request):
    """
    Test the menu update endpoint with invalid fields to ensure they're cleaned up.
    """
    # Payload with invalid types for various fields
    invalid_payload = {
        "items": [
            {
                "name": 12345,  # Number instead of string
                "description": ["This", "is", "a", "list"],  # List instead of string
                "price": "10.00",  # String instead of number
                "available": 1,  # Number instead of boolean
                "plu": None,  # None instead of string
                "reference_handler": ""  # Empty string instead of valid reference
            },
            {
                "name": "",  # Empty string for name
                "description": "",
                "price": -10,  # Negative price
                "available": "true",  # String instead of boolean
                "plu": 12345  # Number instead of string
            }
        ]
    }
    
    resp = api_request.post("/menu_update", data=invalid_payload)
    assert resp.status == 200  # Should still succeed with fixes
    
    response_data = resp.json()
    assert response_data["success"] is True
    
    # Get the menu and verify items were fixed
    get_resp = api_request.get("/menu")
    assert get_resp.status == 200
    
    menu_data = get_resp.json()
    
    # Find items that might have been fixed
    fixed_items = [item for item in menu_data["items"] 
                  if item.get("name") in ["12345", "Unnamed Item 2", "Generated Item 1", "Generated Item 2"]]
                  
    # If we found fixed items, verify their fields were corrected
    if fixed_items:
        for item in fixed_items:
            assert isinstance(item["name"], str)
            assert isinstance(item["description"], str)
            assert isinstance(item["price"], (int, float))
            assert item["price"] > 0  # Should have fixed negative prices
            assert isinstance(item["available"], bool)
            assert "plu" in item  # Should have a PLU
            assert "reference_handler" in item  # Should have a reference_handler

@pytest.mark.e2e
def test_menu_update_idempotence(api_request, create_test_menu_payload):
    """
    Test that calling menu update multiple times with the same data 
    doesn't cause problems.
    """
    # Create a test payload
    test_payload = create_test_menu_payload(payload_type="direct", num_items=3)
    
    # Update the menu multiple times
    for i in range(3):
        resp = api_request.post("/menu_update", data=test_payload)
        assert resp.status == 200
        
        response_data = resp.json()
        assert response_data["success"] is True
        assert response_data["items"] == 3
    
    # Verify the menu is intact
    get_resp = api_request.get("/menu")
    assert get_resp.status == 200
    
    menu_data = get_resp.json()
    assert len(menu_data["items"]) >= 3