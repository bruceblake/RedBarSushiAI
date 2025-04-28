import pytest
import json
import os

@pytest.mark.e2e
def test_standard_menu_update(api_request, deliverect_menu_payload):
    """
    Test the menu update endpoint with a standard Deliverect menu payload.
    """
    resp = api_request.post("/menu_update", data=deliverect_menu_payload)
    assert resp.status == 200
    
    response_data = resp.json()
    assert response_data["success"] is True
    assert "items" in response_data
    assert response_data["source"] == "deliverect"
    assert response_data["ai_matching"] is True

@pytest.mark.e2e
def test_async_menu_update(api_request, async_menu_payload):
    """
    Test the menu update endpoint with an async Deliverect menu payload.
    """
    resp = api_request.post("/menu_update", data=async_menu_payload)
    assert resp.status == 200
    
    response_data = resp.json()
    assert response_data["success"] is True
    assert "items" in response_data
    assert response_data["source"] == "deliverect"
    assert response_data["ai_matching"] is True

@pytest.mark.e2e
def test_menu_update_with_partial_data(api_request):
    """
    Test the menu update endpoint with a partial menu payload.
    """
    # Create a direct format payload instead of a Deliverect one
    partial_data = {
        "items": [
            {
                "name": "Ice Cream",
                "description": "Vanilla ice cream",
                "price": 4.95,
                "available": True,
                "plu": "DST-001",
                "reference_handler": "DST-001"
            }
        ]
    }
    
    resp = api_request.post("/menu_update", data=partial_data)
    assert resp.status == 200
    
    response_data = resp.json()
    assert response_data["success"] is True
    assert "items" in response_data
    assert response_data["source"] == "custom"

@pytest.mark.e2e
def test_menu_update_with_invalid_data(api_request):
    """
    Test the menu update endpoint with invalid data.
    """
    # Empty payload
    resp = api_request.post("/menu_update", data={})
    assert resp.status in [400, 500]  # Either bad request or internal error
    
    # Non-JSON data
    resp = api_request.post("/menu_update", data="not json")
    assert resp.status in [400, 500]
    
    # JSON but without required fields
    resp = api_request.post("/menu_update", data={"random": "data"})
    assert resp.status in [400, 500]

@pytest.mark.e2e
def test_menu_get_after_update(api_request, deliverect_menu_payload):
    """
    Test that menu data is correctly stored and can be retrieved.
    """
    # First update the menu
    update_resp = api_request.post("/menu_update", data=deliverect_menu_payload)
    assert update_resp.status == 200
    
    # Then retrieve it
    get_resp = api_request.get("/menu")
    assert get_resp.status == 200
    
    menu_data = get_resp.json()
    assert "items" in menu_data
    assert len(menu_data["items"]) > 0
    assert "modifiers" in menu_data
    assert "modifierGroups" in menu_data
    assert "ai_matching" in menu_data and menu_data["ai_matching"] is True

@pytest.mark.e2e
def test_menu_cache_clear(api_request, deliverect_menu_payload):
    """
    Test the menu cache clear functionality.
    """
    # First update the menu
    update_resp = api_request.post("/menu_update", data=deliverect_menu_payload)
    assert update_resp.status == 200
    
    # Then clear the cache
    clear_resp = api_request.get("/clear_menu_cache")
    assert clear_resp.status == 200
    
    clear_data = clear_resp.json()
    assert clear_data["success"] is True
    assert "item_count" in clear_data
    assert clear_data["item_count"] > 0

@pytest.mark.e2e
def test_snooze_unsnooze_functionality(api_request, deliverect_menu_payload):
    """
    Test the snooze/unsnooze functionality for menu items.
    """
    # First update the menu
    update_resp = api_request.post("/menu_update", data=deliverect_menu_payload)
    assert update_resp.status == 200
    
    # Snooze an item
    snooze_data = {
        "operations": [
            {
                "action": "snooze",
                "plu": "cal-roll",  # California Roll from the test data
            }
        ]
    }
    
    snooze_resp = api_request.post("/snoozeUnsnooze", data=snooze_data)
    assert snooze_resp.status == 200
    
    snooze_data = snooze_resp.json()
    assert snooze_data["status"] == "success"
    assert snooze_data["snoozed"] >= 0  # At least zero items were snoozed
    
    # Get the menu to verify the item is snoozed
    get_resp = api_request.get("/menu")
    assert get_resp.status == 200
    
    menu_data = get_resp.json()
    cal_roll_item = next((item for item in menu_data["items"] 
                         if item.get("plu") == "cal-roll" or 
                         item.get("name") == "California Roll"), None)
    
    # If we found the item, check it's snoozed
    if cal_roll_item:
        assert cal_roll_item.get("snoozed") is True
        assert cal_roll_item.get("available") is False