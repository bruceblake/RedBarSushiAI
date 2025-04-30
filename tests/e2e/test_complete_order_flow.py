import json
import time
import pytest

@pytest.mark.e2e
def test_complete_order_workflow(api_request, create_test_menu_payload):
    """
    Test a complete user workflow from menu creation to order completion.
    
    This test verifies the entire user journey:
    1. Admin updates the menu via Deliverect
    2. Menu is available to customers
    3. Customer can place an order with menu items
    4. Order is processed and confirmed
    5. Menu item availability is updated
    
    This is a true end-to-end test that simulates a complete business process.
    """
    # Step 1: Admin updates the menu via Deliverect
    menu_payload = create_test_menu_payload(payload_type="standard", num_items=5)
    
    # Extract key information for later verification
    items = []
    if "data" in menu_payload and "menu" in menu_payload["data"]:
        for cat in menu_payload["data"]["menu"]["categories"]:
            for item in cat["products"]:
                items.append({
                    "plu": item["plu"],
                    "name": item["name"],
                    "price": item["price"]
                })
    
    # Update the menu using the Deliverect webhook
    menu_response = api_request.post("/menu_update", data=menu_payload)
    assert menu_response.status == 200
    assert menu_response.json()["success"] is True
    
    # Step 2: Verify the menu is available to customers
    # Wait a moment for any async processing to complete
    time.sleep(1)
    
    menu_get_response = api_request.get("/menu")
    assert menu_get_response.status == 200
    retrieved_menu = menu_get_response.json()
    
    # Verify the menu contains the items we added
    assert "items" in retrieved_menu
    assert len(retrieved_menu["items"]) >= len(items)
    
    # Find the test items in the menu by PLU
    retrieved_items = {item["plu"]: item for item in retrieved_menu["items"]}
    
    for test_item in items:
        assert test_item["plu"] in retrieved_items
        assert retrieved_items[test_item["plu"]]["name"] == test_item["name"]
        # Allow for price format conversion (dollars to cents or vice versa)
        if retrieved_items[test_item["plu"]]["price"] > 100:
            # If price in cents, compare with cents
            expected_price = int(test_item["price"] * 100) if test_item["price"] < 100 else test_item["price"]
            assert abs(retrieved_items[test_item["plu"]]["price"] - expected_price) < 1
        else:
            # If price in dollars, compare with dollars
            expected_price = test_item["price"] if test_item["price"] < 100 else test_item["price"] / 100
            assert abs(retrieved_items[test_item["plu"]]["price"] - expected_price) < 0.01
    
    # Step 3: Customer places an order with items from the menu
    # Select two items from our menu for the order
    order_items = []
    for i, item_plu in enumerate(list(retrieved_items.keys())[:2]):
        order_items.append({
            "plu": item_plu,
            "quantity": i + 1,  # Order 1 of first item, 2 of second
            "name": retrieved_items[item_plu]["name"],
            "price": retrieved_items[item_plu]["price"],
            "modifiers": []  # No modifiers for simplicity
        })
    
    order_payload = {
        "customer": {
            "name": "Test Customer",
            "phone": "+15551234567",
            "email": "test@example.com"
        },
        "items": order_items,
        "pickup_time": "2025-04-30T18:30:00Z",
        "order_notes": "E2E test order",
        "payment_method": "card"
    }
    
    # Submit the order
    order_response = api_request.post("/order", data=order_payload)
    assert order_response.status == 200
    order_result = order_response.json()
    
    # Verify the order was created with an ID
    assert "order_id" in order_result
    order_id = order_result["order_id"]
    
    # Step 4: Verify the order was received and is being processed
    order_status_response = api_request.get(f"/order/{order_id}")
    assert order_status_response.status == 200
    order_status = order_status_response.json()
    
    # Verify the order details match what we sent
    assert order_status["customer"]["name"] == "Test Customer"
    assert len(order_status["items"]) == len(order_items)
    
    # Verify the initial status is correct (might be "pending" or "received")
    assert order_status["status"] in ["pending", "received", "processing"]
    
    # Step 5: Restaurant marks the order as "accepted"
    update_payload = {
        "status": "accepted"
    }
    update_response = api_request.post(f"/order/{order_id}/status", data=update_payload)
    assert update_response.status == 200
    
    # Verify the status was updated
    status_response = api_request.get(f"/order/{order_id}")
    assert status_response.status == 200
    updated_status = status_response.json()
    assert updated_status["status"] == "accepted"
    
    # Step 6: Restaurant marks one item as unavailable (snoozed) after running out
    # Use the first ordered item for our test
    snooze_item_plu = order_items[0]["plu"]
    
    snooze_payload = {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "operations": [
            {
                "action": "snooze",
                "data": {
                    "items": [
                        {
                            "plu": snooze_item_plu,
                            "snoozeStart": "2025-04-30T00:00:00.000000Z",
                            "snoozeEnd": "2025-05-01T00:00:00.000000Z"
                        }
                    ]
                }
            }
        ],
        "allSnoozedItems": [
            {
                "plu": snooze_item_plu,
                "snoozeStart": "2025-04-30T00:00:00.000000Z",
                "snoozeEnd": "2025-05-01T00:00:00.000000Z"
            }
        ]
    }
    
    snooze_response = api_request.post("/menu_update", data=snooze_payload)
    assert snooze_response.status == 200
    
    # Verify the item is now snoozed in the menu
    updated_menu_response = api_request.get("/menu")
    assert updated_menu_response.status == 200
    updated_menu = updated_menu_response.json()
    
    # Find our snoozed item
    snoozed_item = next((i for i in updated_menu["items"] if i["plu"] == snooze_item_plu), None)
    assert snoozed_item is not None
    assert snoozed_item.get("snoozed") is True or snoozed_item.get("available") is False
    
    # Step 7: Restaurant marks the order as "completed"
    complete_payload = {
        "status": "completed"
    }
    complete_response = api_request.post(f"/order/{order_id}/status", data=complete_payload)
    assert complete_response.status == 200
    
    # Verify the order is now complete
    final_status_response = api_request.get(f"/order/{order_id}")
    assert final_status_response.status == 200
    final_status = final_status_response.json()
    assert final_status["status"] == "completed"
    
    # Verify we've tested a full round-trip workflow
    # From menu creation to order completion with menu updates
    
    # Cleanup: Restaurant unsnoozes the item
    unsnooze_payload = {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "operations": [
            {
                "action": "unsnooze",
                "data": {
                    "items": [
                        {
                            "plu": snooze_item_plu
                        }
                    ]
                }
            }
        ],
        "allSnoozedItems": []
    }
    
    unsnooze_response = api_request.post("/menu_update", data=unsnooze_payload)
    assert unsnooze_response.status == 200
    
    # Verify the item is available again
    final_menu_response = api_request.get("/menu")
    assert final_menu_response.status == 200
    final_menu = final_menu_response.json()
    
    final_item = next((i for i in final_menu["items"] if i["plu"] == snooze_item_plu), None)
    assert final_item is not None
    assert final_item.get("snoozed") is not True and final_item.get("available") is not False

@pytest.mark.e2e
def test_menu_update_and_retrieval_workflow(api_request, deliverect_menu_payload, async_menu_payload):
    """
    Test the complete workflow for menu management.
    
    This test verifies:
    1. Menu can be updated with standard Deliverect format
    2. Updated menu can be retrieved
    3. Menu can be updated with async format
    4. Menu can be updated with partial updates
    5. Menu cache can be cleared 
    
    This tests the complete menu management workflow.
    """
    # Step 1: Update menu with standard Deliverect format
    standard_response = api_request.post("/menu_update", data=deliverect_menu_payload)
    assert standard_response.status == 200
    assert standard_response.json()["success"] is True
    
    # Extract items from the payload for verification
    standard_items = []
    for category in deliverect_menu_payload["data"]["menu"]["categories"]:
        for item in category["products"]:
            standard_items.append({
                "plu": item["plu"],
                "name": item["name"]
            })
    
    # Step 2: Retrieve the menu and verify it contains the items
    menu_response = api_request.get("/menu")
    assert menu_response.status == 200
    menu_data = menu_response.json()
    
    # Verify each item from our payload exists in the menu
    menu_items = {item["plu"]: item for item in menu_data["items"]}
    for expected_item in standard_items:
        assert expected_item["plu"] in menu_items
        assert menu_items[expected_item["plu"]]["name"] == expected_item["name"]
    
    # Step 3: Update menu with async format
    async_response = api_request.post("/menu_update", data=async_menu_payload)
    assert async_response.status == 200
    assert async_response.json()["success"] is True
    
    # Verify menu was updated correctly with async format
    updated_menu_response = api_request.get("/menu")
    assert updated_menu_response.status == 200
    updated_menu = updated_menu_response.json()
    
    # Should still contain all items
    for expected_item in standard_items:
        assert any(item["plu"] == expected_item["plu"] for item in updated_menu["items"])
    
    # Step 4: Update a single item price
    single_item_update = {
        "items": [
            {
                "plu": standard_items[0]["plu"],
                "name": standard_items[0]["name"],
                "price": 999  # New price
            }
        ]
    }
    
    partial_update_response = api_request.post("/menu_update", data=single_item_update)
    assert partial_update_response.status == 200
    
    # Verify the price was updated
    partial_menu_response = api_request.get("/menu")
    assert partial_menu_response.status == 200
    partial_menu = partial_menu_response.json()
    
    updated_item = next((i for i in partial_menu["items"] if i["plu"] == standard_items[0]["plu"]), None)
    assert updated_item is not None
    # Check price was updated, accounting for dollar/cent conversion
    if updated_item["price"] > 100:
        assert abs(updated_item["price"] - 999) < 1
    else:
        assert abs(updated_item["price"] - 9.99) < 0.01
    
    # Step 5: Clear the menu cache
    cache_response = api_request.post("/menu/clear_cache")
    assert cache_response.status == 200
    
    # Verify we can still get the menu after cache clear
    final_menu_response = api_request.get("/menu")
    assert final_menu_response.status == 200
    final_menu = final_menu_response.json()
    
    # Menu should still contain the updated item
    final_item = next((i for i in final_menu["items"] if i["plu"] == standard_items[0]["plu"]), None)
    assert final_item is not None
    # Price should still reflect our update
    if final_item["price"] > 100:
        assert abs(final_item["price"] - 999) < 1
    else:
        assert abs(final_item["price"] - 9.99) < 0.01
