import json
import pytest
import time
import re
from datetime import datetime, timedelta

@pytest.mark.e2e
def test_store_closure_impact(api_request, create_test_menu_payload):
    """
    Tests how store closure (busy mode) affects ordering functionality.
    
    This test verifies:
    1. Busy mode/closure notification from Deliverect is properly processed
    2. Voice system correctly informs customers about store closure
    3. The system prevents orders during closure periods
    4. The system resumes normal operation when closure ends
    """
    # Setup: Create a test menu
    menu_payload = create_test_menu_payload(payload_type="direct", num_items=3)
    menu_response = api_request.post("/menu_update", data=menu_payload)
    assert menu_response.status == 200
    
    # Generate a test CallSid
    test_call_sid = f"CA{''.join(['1234567890'[i % 10] for i in range(32)])}"
    
    # First, set the store status to PAUSED (closed)
    busy_mode_payload = {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "status": "PAUSED",  # PAUSED = Closed
        "delay": 0
    }
    
    busy_mode_response = api_request.post(
        "/webhook/deliverect/busy_mode",
        data=json.dumps(busy_mode_payload),
        content_type='application/json'
    )
    assert busy_mode_response.status == 200
    
    # Verify the API returns the correct status
    assert busy_mode_response.json()["status"] == "PAUSED"
    
    # Now test calling the voice system
    voice_response = api_request.post(
        "/webhook/voice", 
        data={
            "CallSid": test_call_sid,
            "AccountSid": "AC12345",
            "From": "+15551234567"
        }
    )
    assert voice_response.status == 200
    
    # Parse the greeting TwiML
    greeting_twiml = voice_response.text
    assert "<Response>" in greeting_twiml
    
    # Since the store is closed, the greeting should mention this
    closure_mentioned = any(phrase in greeting_twiml.lower() for phrase in 
                          ["closed", "not open", "unavailable", "busy", "cannot accept orders"])
    assert closure_mentioned, "Voice system didn't mention store closure"
    
    # Try to place an order via API during closure
    test_order_data = {
        "customer": {
            "name": "Jordan Smith",
            "phone": "+15551234567",
            "email": "jordan@example.com"
        },
        "items": [
            {
                "plu": menu_payload["items"][0]["plu"],
                "name": menu_payload["items"][0]["name"],
                "price": menu_payload["items"][0]["price"],
                "quantity": 1
            }
        ],
        "pickup_time": "2025-05-01T19:30:00Z",
        "order_type": "pickup",
        "payment_method": "card"
    }
    
    # Order should be rejected or flagged
    closed_order_response = api_request.post("/order", data=test_order_data)
    
    # Either the API returns an error code, or it accepts the order but flags it
    if closed_order_response.status != 200:
        assert closed_order_response.status in [400, 403, 503], "Unexpected error status code"
    else:
        # If the API accepts the order, it should be flagged as affected by closure
        order_result = closed_order_response.json()
        assert "store_closed" in order_result or "store_status" in order_result
        if "store_status" in order_result:
            assert order_result["store_status"] == "closed" or order_result["store_status"] == "paused"
    
    # Now change the store status to BUSY (open but with increased prep time)
    busy_payload = {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "status": "BUSY",  # BUSY = Open but with increased preparation time
        "delay": 30  # 30 minutes delay
    }
    
    busy_response = api_request.post(
        "/webhook/deliverect/busy_mode",
        data=json.dumps(busy_payload),
        content_type='application/json'
    )
    assert busy_response.status == 200
    assert busy_response.json()["status"] == "BUSY"
    
    # New call during BUSY mode
    busy_call_sid = f"CA{''.join(['9876543210'[i % 10] for i in range(32)])}"
    
    busy_voice_response = api_request.post(
        "/webhook/voice", 
        data={
            "CallSid": busy_call_sid,
            "AccountSid": "AC12345",
            "From": "+15551234567"
        }
    )
    assert busy_voice_response.status == 200
    
    # Parse the busy greeting TwiML
    busy_greeting_twiml = busy_voice_response.text
    assert "<Response>" in busy_greeting_twiml
    
    # In busy mode, should mention longer wait times
    busy_mentioned = any(phrase in busy_greeting_twiml.lower() for phrase in 
                        ["busy", "wait time", "delay", "longer than usual", "30 minute"])
    assert busy_mentioned, "Voice system didn't mention busy status or increased wait time"
    
    # Finally, set the store back to ONLINE (normal operation)
    online_payload = {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "status": "ONLINE",  # ONLINE = Normal operations
        "delay": 0
    }
    
    online_response = api_request.post(
        "/webhook/deliverect/busy_mode",
        data=json.dumps(online_payload),
        content_type='application/json'
    )
    assert online_response.status == 200
    assert online_response.json()["status"] == "ONLINE"
    
    # Verify normal operation is restored
    normal_order_response = api_request.post("/order", data=test_order_data)
    assert normal_order_response.status == 200
    
    # The order should not be flagged as affected by closure
    order_result = normal_order_response.json()
    if "store_status" in order_result:
        assert order_result["store_status"] == "open" or order_result["store_status"] == "online"

@pytest.mark.e2e
def test_menu_updates_during_active_orders(api_request, create_test_menu_payload):
    """
    Tests how menu updates are handled when there are active orders in the system.
    
    This test verifies:
    1. Menu updates during active orders don't affect existing orders
    2. New orders after menu updates reflect the current menu
    3. PLUs are preserved during menu updates to maintain consistency
    """
    # Setup: Create a test menu
    initial_menu_payload = create_test_menu_payload(payload_type="direct", num_items=3)
    initial_menu_response = api_request.post("/menu_update", data=initial_menu_payload)
    assert initial_menu_response.status == 200
    
    # Store original menu items for comparison
    original_items = initial_menu_payload["items"]
    
    # Place an order with the original menu
    original_order_data = {
        "customer": {
            "name": "Pat Johnson",
            "phone": "+15551234567",
            "email": "pat@example.com"
        },
        "items": [
            {
                "plu": original_items[0]["plu"],
                "name": original_items[0]["name"],
                "price": original_items[0]["price"],
                "quantity": 1
            }
        ],
        "pickup_time": "2025-05-01T19:30:00Z",
        "order_type": "pickup",
        "payment_method": "card"
    }
    
    original_order_response = api_request.post("/order", data=original_order_data)
    assert original_order_response.status == 200
    original_order_result = original_order_response.json()
    original_order_id = original_order_result["order_id"]
    
    # Mark the order as accepted to ensure it's active
    update_response = api_request.post(
        f"/order/{original_order_id}/status",
        data={"status": "accepted"}
    )
    assert update_response.status == 200
    
    # Create a modified menu with updated prices and descriptions
    # But keep the same PLUs for consistency
    updated_menu_payload = create_test_menu_payload(payload_type="direct", num_items=3)
    
    # Modify the menu contents while preserving PLUs
    for i, item in enumerate(updated_menu_payload["items"]):
        # Keep the same PLU
        item["plu"] = original_items[i]["plu"]
        # Update price (increase by 10%)
        item["price"] = original_items[i]["price"] * 1.1
        # Update description
        item["description"] = original_items[i]["description"] + " (Updated)"
    
    # Apply the menu update
    updated_menu_response = api_request.post("/menu_update", data=updated_menu_payload)
    assert updated_menu_response.status == 200
    
    # Verify the original order is unchanged
    original_order_status = api_request.get(f"/order/{original_order_id}")
    assert original_order_status.status == 200
    order_data = original_order_status.json()
    
    # The price should reflect the original menu, not the updated one
    assert abs(order_data["items"][0]["price"] - original_items[0]["price"]) < 0.01
    
    # Place a new order after the menu update
    new_order_data = {
        "customer": {
            "name": "Quinn Smith",
            "phone": "+15557654321",
            "email": "quinn@example.com"
        },
        "items": [
            {
                "plu": original_items[0]["plu"],  # Same PLU
                "name": updated_menu_payload["items"][0]["name"],
                "price": updated_menu_payload["items"][0]["price"],
                "quantity": 1
            }
        ],
        "pickup_time": "2025-05-01T20:30:00Z",
        "order_type": "pickup",
        "payment_method": "card"
    }
    
    new_order_response = api_request.post("/order", data=new_order_data)
    assert new_order_response.status == 200
    new_order_result = new_order_response.json()
    new_order_id = new_order_result["order_id"]
    
    # Verify the new order reflects the updated menu
    new_order_status = api_request.get(f"/order/{new_order_id}")
    assert new_order_status.status == 200
    new_order_data = new_order_status.json()
    
    # The price should reflect the updated menu
    assert abs(new_order_data["items"][0]["price"] - updated_menu_payload["items"][0]["price"]) < 0.01

@pytest.mark.e2e
def test_time_based_availability(api_request, create_test_menu_payload):
    """
    Tests time-based availability for menu items and ordering.
    
    This test verifies:
    1. Items with time-based availability are properly handled
    2. Ordering respects time-based restrictions
    3. Menu displays correctly reflect time-based availability
    """
    # Setup: Create a base menu
    base_menu_payload = create_test_menu_payload(payload_type="direct", num_items=3)
    base_menu_response = api_request.post("/menu_update", data=base_menu_payload)
    assert base_menu_response.status == 200
    
    # Get the current time for time-based testing
    current_time = datetime.utcnow()
    
    # Create a time-based menu with specific availability windows
    # One item available now, one available in the future, one available only in the past
    time_menu_items = [
        {
            # Item available now
            "name": "Currently Available Item",
            "description": "This item is available now",
            "price": 12.99,
            "plu": "TIME-1",
            "available": True,
            "availableFrom": (current_time - timedelta(hours=1)).isoformat(),
            "availableUntil": (current_time + timedelta(hours=1)).isoformat()
        },
        {
            # Item available in the future
            "name": "Future Available Item",
            "description": "This item will be available later",
            "price": 14.99,
            "plu": "TIME-2",
            "available": True,
            "availableFrom": (current_time + timedelta(hours=1)).isoformat(),
            "availableUntil": (current_time + timedelta(hours=3)).isoformat()
        },
        {
            # Item available only in the past
            "name": "Past Available Item",
            "description": "This item was available earlier",
            "price": 9.99,
            "plu": "TIME-3",
            "available": True,
            "availableFrom": (current_time - timedelta(hours=3)).isoformat(),
            "availableUntil": (current_time - timedelta(hours=1)).isoformat()
        }
    ]
    
    time_menu_payload = {
        "items": time_menu_items,
        "modifiers": [],
        "modifierGroups": []
    }
    
    time_menu_response = api_request.post("/menu_update", data=time_menu_payload)
    assert time_menu_response.status == 200
    
    # Get the current menu
    menu_response = api_request.get("/menu")
    assert menu_response.status == 200
    menu_data = menu_response.json()
    
    # Check that time-based availability is correctly reflected
    time_items = {item["plu"]: item for item in menu_data["items"] if item["plu"].startswith("TIME-")}
    
    # The currently available item should be available
    assert "TIME-1" in time_items
    assert time_items["TIME-1"]["available"] is True
    
    # The future item might be in the menu but marked as unavailable
    if "TIME-2" in time_items:
        # Some implementations might include future items but mark them unavailable
        assert time_items["TIME-2"]["available"] is False
    
    # The past item might be excluded or marked unavailable
    if "TIME-3" in time_items:
        # If included, it should be marked unavailable
        assert time_items["TIME-3"]["available"] is False
    
    # Try to order the currently available item
    available_order_data = {
        "customer": {
            "name": "Riley Adams",
            "phone": "+15551234567",
            "email": "riley@example.com"
        },
        "items": [
            {
                "plu": "TIME-1",
                "name": "Currently Available Item",
                "price": 12.99,
                "quantity": 1
            }
        ],
        "pickup_time": "2025-05-01T19:30:00Z",
        "order_type": "pickup",
        "payment_method": "card"
    }
    
    available_order_response = api_request.post("/order", data=available_order_data)
    assert available_order_response.status == 200
    
    # Try to order the future item (should be rejected or flagged)
    future_order_data = {
        "customer": {
            "name": "Riley Adams",
            "phone": "+15551234567",
            "email": "riley@example.com"
        },
        "items": [
            {
                "plu": "TIME-2",
                "name": "Future Available Item",
                "price": 14.99,
                "quantity": 1
            }
        ],
        "pickup_time": "2025-05-01T19:30:00Z",
        "order_type": "pickup",
        "payment_method": "card"
    }
    
    future_order_response = api_request.post("/order", data=future_order_data)
    
    # Either the API rejects the order or it flags the item as unavailable
    if future_order_response.status != 200:
        assert future_order_response.status in [400, 409, 422], "Unexpected error code for unavailable item"
    else:
        # If order is accepted, response should indicate unavailability
        future_order_result = future_order_response.json()
        assert "unavailable_items" in future_order_result or "warnings" in future_order_result

# Helper functions for tests
def extract_gather_action(twiml):
    """Extract the 'action' attribute from a <Gather> tag in TwiML."""
    gather_match = re.search(r'<Gather[^>]*action="([^"]*)"', twiml)
    if gather_match:
        return gather_match.group(1)
    return None