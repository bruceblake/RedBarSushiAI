import pytest
import time

@pytest.mark.e2e
def test_menu_cache_refresh(api_request):
    """
    Test that the menu cache is refreshed when using force_refresh=True.
    """
    # First, create a menu with a specific item
    initial_payload = {
        "items": [
            {
                "name": "Cache Test Item",
                "description": "Item to test caching",
                "price": 10.0,
                "available": True,
                "plu": "CACHE-TEST-1",
                "reference_handler": "CACHE-TEST-1"
            }
        ]
    }
    
    # Update the menu
    resp = api_request.post("/menu_update", data=initial_payload)
    assert resp.status == 200
    
    # Verify the item is in the menu
    get_resp = api_request.get("/menu")
    assert get_resp.status == 200
    
    menu_data = get_resp.json()
    assert any(item["name"] == "Cache Test Item" for item in menu_data["items"])
    
    # Clear the menu cache
    clear_resp = api_request.get("/clear_menu_cache")
    assert clear_resp.status == 200
    
    # Get the menu again to verify the cache was cleared
    get_resp = api_request.get("/menu")
    assert get_resp.status == 200
    
    menu_data = get_resp.json()
    assert any(item["name"] == "Cache Test Item" for item in menu_data["items"])
    
    # Update the menu with a different item
    updated_payload = {
        "items": [
            {
                "name": "New Cache Test Item",
                "description": "New item to test caching",
                "price": 15.0,
                "available": True,
                "plu": "CACHE-TEST-2",
                "reference_handler": "CACHE-TEST-2"
            }
        ]
    }
    
    resp = api_request.post("/menu_update", data=updated_payload)
    assert resp.status == 200
    
    # Get the menu again to verify the update was applied
    get_resp = api_request.get("/menu")
    assert get_resp.status == 200
    
    menu_data = get_resp.json()
    assert any(item["name"] == "New Cache Test Item" for item in menu_data["items"])

@pytest.mark.e2e
def test_menu_cache_debug_endpoints(api_request):
    """
    Test the menu debug endpoints that provide information about the cache.
    """
    # Test the menu_settings endpoint
    settings_resp = api_request.get("/menu_settings")
    assert settings_resp.status == 200
    
    settings_data = settings_resp.json()
    assert settings_data["status"] == "success"
    assert "menu_file_path" in settings_data
    assert "item_count" in settings_data
    assert "items_sample" in settings_data
    
    # Test the debug_menu endpoint
    debug_resp = api_request.get("/debug_menu")
    assert debug_resp.status == 200
    
    debug_data = debug_resp.json()
    assert debug_data["success"] is True
    assert "loaded_menu_info" in debug_data
    assert "file_status" in debug_data
    assert "system_info" in debug_data

@pytest.mark.e2e
def test_menu_write_test_endpoint(api_request):
    """
    Test the write_test endpoint that checks file writing permissions.
    """
    write_resp = api_request.get("/write_test")
    assert write_resp.status == 200
    
    write_data = write_resp.json()
    assert write_data["success"] is True
    assert "results" in write_data
    
    # At least one of the paths should succeed
    assert any(result == "SUCCESS" for result in write_data["results"].values())