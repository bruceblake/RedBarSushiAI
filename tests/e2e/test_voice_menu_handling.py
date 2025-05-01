import json
import time
import pytest
import logging
import uuid

# Set up logging for the test
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

@pytest.mark.e2e
def test_voice_menu_inquiry_handling(api_request, create_test_menu_payload):
    """
    Test a complete voice order flow with menu inquiries and order modification.
    
    This test verifies:
    1. Menu is properly loaded and cached
    2. Voice system correctly handles menu inquiries
    3. Order modification works with menu items
    4. Cache invalidation works properly when menu changes
    5. The entire order flow works end-to-end
    """
    # Generate a unique session ID for this test run
    session_id = f"test-session-{uuid.uuid4()}"
    logger.info(f"Starting voice menu test with session ID: {session_id}")
    
    # Step 1: Setup a test menu with known items
    menu_payload = create_test_menu_payload(payload_type="standard", num_items=8)
    
    # Extract menu items for verification
    test_items = []
    categories = []
    if "data" in menu_payload and "menu" in menu_payload["data"]:
        for cat in menu_payload["data"]["menu"]["categories"]:
            cat_name = cat["name"]
            categories.append(cat_name)
            for item in cat["products"]:
                test_items.append({
                    "plu": item["plu"],
                    "name": item["name"],
                    "price": item["price"],
                    "category": cat_name
                })
    
    # Log the test items for debugging
    logger.info(f"Test menu contains {len(test_items)} items in {len(categories)} categories")
    for idx, item in enumerate(test_items[:5]):  # Log first 5 items
        logger.info(f"Test item {idx+1}: {item['name']} (PLU: {item['plu']}, Price: {item['price']})")
    
    # Update the menu using the Deliverect webhook
    menu_response = api_request.post("/menu_update", data=menu_payload)
    assert menu_response.status == 200
    assert menu_response.json()["success"] is True
    logger.info("Test menu successfully loaded into system")
    
    # Step 2: Clear the menu cache to ensure we're using the latest data
    cache_response = api_request.get("/clear_menu_cache")
    assert cache_response.status == 200
    logger.info("Menu cache cleared")
    
    # Step 3: Initialize a voice session
    take_name_response = api_request.post("/take_name", data={"CallSid": session_id, "Digits": "1"})
    assert take_name_response.status == 200
    logger.info("Voice session initialized with take_name endpoint")
    
    # Step 4: Confirm the name
    confirm_name_response = api_request.post("/confirm_name", data={"CallSid": session_id, "Digits": "1"})
    assert confirm_name_response.status == 200
    logger.info("Name confirmed in voice session")
    
    # Step 5: Send a general menu inquiry
    menu_inquiry_text = "What items do you have on the menu?"
    menu_inquiry_response = api_request.post("/handle_menu_questions", data={
        "CallSid": session_id,
        "SpeechResult": menu_inquiry_text
    })
    assert menu_inquiry_response.status == 200
    logger.info(f"Sent menu inquiry: '{menu_inquiry_text}'")
    
    # The TwiML response should contain items from our test menu
    response_text = menu_inquiry_response.text
    
    # Check that the response mentions at least one category
    category_mentioned = any(cat.lower() in response_text.lower() for cat in categories)
    assert category_mentioned, "Response should mention at least one menu category"
    logger.info("Response includes menu categories as expected")
    
    # Check that the response mentions at least one test item
    item_mentioned = any(item["name"].lower() in response_text.lower() for item in test_items)
    assert item_mentioned, "Response should mention at least one menu item"
    logger.info("Response includes menu items as expected")
    
    # Step 6: Place an order for an item from our test menu
    # Use the first test item in our order
    test_item = test_items[0]
    order_text = f"I'd like to order the {test_item['name']}"
    
    order_response = api_request.post("/new_order", data={
        "CallSid": session_id,
        "SpeechResult": order_text
    })
    assert order_response.status == 200
    logger.info(f"Placed order for test item: '{test_item['name']}'")
    
    # Step 7: Confirm the order
    confirm_order_response = api_request.post("/confirm_order", data={
        "CallSid": session_id,
        "Digits": "1"  # 1 for confirm
    })
    assert confirm_order_response.status == 200
    logger.info("Order confirmed")
    
    # Step 8: Test order modification
    # Add another item from our test menu
    second_item = test_items[1]
    modify_text = f"I'd like to add a {second_item['name']}"
    
    modify_response = api_request.post("/new_modify_order", data={
        "CallSid": session_id,
        "SpeechResult": modify_text
    })
    assert modify_response.status == 200
    logger.info(f"Requested order modification to add: '{second_item['name']}'")
    
    # Check response text includes the added item
    assert second_item['name'].lower() in modify_response.text.lower(), f"Response should confirm adding {second_item['name']}"
    logger.info("Modification response includes the added item as expected")
    
    # Step 9: Complete the order
    complete_response = api_request.post("/complete_order", data={
        "CallSid": session_id,
        "Digits": "1"  # 1 for complete
    })
    assert complete_response.status == 200
    logger.info("Order completed successfully")
    
    # Step 10: Test cache invalidation by updating a menu item
    # Change the price of the first test item
    original_price = test_items[0]['price']
    test_items[0]['price'] = original_price * 2
    
    # Update just this item
    item_update_response = api_request.post("/update_menu_item", data={
        "item_data": json.dumps(test_items[0])
    })
    assert item_update_response.status == 200
    logger.info(f"Updated price of '{test_items[0]['name']}' from {original_price} to {test_items[0]['price']}")
    
    # Clear cache again
    api_request.get("/clear_menu_cache")
    
    # Step 11: Verify the updated price is reflected in menu inquiry
    new_menu_inquiry = f"How much is the {test_items[0]['name']}?"
    price_inquiry_response = api_request.post("/handle_menu_questions", data={
        "CallSid": session_id,
        "SpeechResult": new_menu_inquiry
    })
    assert price_inquiry_response.status == 200
    
    # Response should show the new price, not the old one
    # Convert both prices to strings with same format for comparison
    old_price_str = f"${original_price:.2f}".replace(".00", "")
    new_price_str = f"${test_items[0]['price']:.2f}".replace(".00", "")
    
    logger.info(f"Checking that response shows new price {new_price_str} instead of old price {old_price_str}")
    
    response_text = price_inquiry_response.text
    assert new_price_str in response_text or str(test_items[0]['price']) in response_text, "Response should include the updated price"
    assert old_price_str not in response_text, "Response should not contain the old price"
    logger.info("Cache invalidation verified - response shows updated price")
    
    logger.info("Voice menu handling test completed successfully!")


@pytest.mark.e2e
def test_menu_matcher_error_recovery(api_request, create_test_menu_payload):
    """
    Test the system's ability to recover from errors in menu matching.
    
    This test verifies:
    1. System handles non-existent menu items gracefully
    2. Error recovery with menu questions works
    3. Fallback mechanisms are functioning
    """
    # Generate a unique session ID for this test run
    session_id = f"test-session-{uuid.uuid4()}"
    logger.info(f"Starting menu matcher error recovery test with session ID: {session_id}")
    
    # Step 1: Setup a test menu
    menu_payload = create_test_menu_payload(payload_type="standard", num_items=5)
    menu_response = api_request.post("/menu_update", data=menu_payload)
    assert menu_response.status == 200
    logger.info("Test menu loaded")
    
    # Clear cache to ensure we're using the latest data
    api_request.get("/clear_menu_cache")
    
    # Step 2: Initialize a voice session
    take_name_response = api_request.post("/take_name", data={"CallSid": session_id, "Digits": "1"})
    assert take_name_response.status == 200
    
    confirm_name_response = api_request.post("/confirm_name", data={"CallSid": session_id, "Digits": "1"})
    assert confirm_name_response.status == 200
    logger.info("Voice session initialized")
    
    # Step 3: Ask for a non-existent menu item
    nonexistent_item = "Supercalifragilisticexpialidocious Burger with Quantum Sauce"
    invalid_order_response = api_request.post("/new_order", data={
        "CallSid": session_id,
        "SpeechResult": f"I want to order a {nonexistent_item}"
    })
    assert invalid_order_response.status == 200
    logger.info(f"Requested non-existent menu item: '{nonexistent_item}'")
    
    # Response should indicate the item wasn't found and ask for clarification
    response_text = invalid_order_response.text
    assert "not" in response_text.lower() or "don't" in response_text.lower() or "can't" in response_text.lower(), "Response should indicate the item wasn't found"
    logger.info("System correctly indicated non-existent item")
    
    # Step 4: Now try ordering a valid item after the error
    # Extract a real menu item
    test_items = []
    if "data" in menu_payload and "menu" in menu_payload["data"]:
        for cat in menu_payload["data"]["menu"]["categories"]:
            for item in cat["products"]:
                test_items.append({
                    "name": item["name"],
                })
    
    valid_item = test_items[0]["name"]
    valid_order_response = api_request.post("/new_order", data={
        "CallSid": session_id,
        "SpeechResult": f"I'd like to order the {valid_item}"
    })
    assert valid_order_response.status == 200
    logger.info(f"Ordered valid menu item after error: '{valid_item}'")
    
    # Response should now recognize the valid item
    response_text = valid_order_response.text
    assert valid_item.lower() in response_text.lower(), f"Response should include the valid item {valid_item}"
    logger.info("System successfully recovered from error and processed valid order")
    
    # Step 5: Complete the order
    confirm_order_response = api_request.post("/confirm_order", data={
        "CallSid": session_id,
        "Digits": "1"  # 1 for confirm
    })
    assert confirm_order_response.status == 200
    
    complete_response = api_request.post("/complete_order", data={
        "CallSid": session_id,
        "Digits": "1"  # 1 for complete
    })
    assert complete_response.status == 200
    logger.info("Order completed successfully after error recovery")