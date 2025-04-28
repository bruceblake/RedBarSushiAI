import pytest
import json
import os

@pytest.mark.e2e
def test_update_menu(api_request):
    """
    Basic test for the menu update endpoint.
    For more comprehensive tests, see the tests in the menu_update directory.
    """
    # Simple menu payload
    payload = {
        "items": [
            {
                "name": "Test Item",
                "description": "A test item",
                "price": 10.0,
                "available": True,
                "plu": "TEST-01",
                "reference_handler": "TEST-01"
            }
        ]
    }
    
    resp = api_request.post("/menu_update", data=payload)
    assert resp.status == 200
    
    # Verify response
    response_data = resp.json()
    assert response_data["success"] is True
    assert response_data["items"] == 1
    
    # For more detailed tests, see the tests in the menu_update directory