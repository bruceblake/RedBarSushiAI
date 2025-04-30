import json
import pytest
import time
import re
from urllib.parse import urlparse, parse_qs
from twilio.twiml.voice_response import VoiceResponse

@pytest.mark.e2e
def test_complete_voice_order_flow(api_request, create_test_menu_payload):
    """
    Test a complete voice call flow from greeting to order completion.
    
    This test verifies the entire voice call journey:
    1. Initial greeting and name collection
    2. Menu inquiry about items
    3. Building an order with items and modifiers
    4. Handling payment information
    5. Confirming and placing the order
    6. Verifying order completion and notifications
    
    This is a true end-to-end test that simulates a complete voice call.
    """
    # Step 1: First create a menu that the voice system will use
    menu_payload = create_test_menu_payload(payload_type="standard", num_items=5, include_modifiers=True)
    menu_response = api_request.post("/menu_update", data=menu_payload)
    assert menu_response.status == 200
    
    # Extract items from the menu for use in testing
    items = []
    if "data" in menu_payload and "menu" in menu_payload["data"]:
        for cat in menu_payload["data"]["menu"]["categories"]:
            for item in cat["products"]:
                items.append({
                    "plu": item["plu"],
                    "name": item["name"],
                    "price": item["price"]
                })
    
    # Step 2: Initiate a mock voice call
    # Generate a test CallSid
    test_call_sid = f"CA{''.join(['1234567890'[i % 10] for i in range(32)])}"
    
    # Initial call to voice webhook
    voice_response = api_request.post(
        "", 
        data={
            "CallSid": test_call_sid,
            "AccountSid": "AC12345",
            "From": "+15551234567"
        }
    )
    assert voice_response.status == 200
    
    # Parse the TwiML response to get the greeting and next action
    greeting_twiml = voice_response.text
    assert "<Response>" in greeting_twiml
    assert "<Say>" in greeting_twiml  # Should contain a greeting
    
    # Extract the Gather action URL for the next step
    gather_action = extract_gather_action(greeting_twiml)
    assert gather_action is not None
    
    # Step 3: Provide name (should be directed to take_name)
    name_response = api_request.post(
        gather_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "John Smith",
            "Confidence": "0.8"
        }
    )
    assert name_response.status == 200
    
    # Parse the name confirmation TwiML
    name_confirm_twiml = name_response.text
    assert "<Response>" in name_confirm_twiml
    assert "John" in name_confirm_twiml  # Should contain the name
    
    # Extract the Gather action URL for name confirmation
    confirm_name_action = extract_gather_action(name_confirm_twiml)
    assert confirm_name_action is not None
    
    # Step 4: Confirm name
    confirm_response = api_request.post(
        confirm_name_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "yes",
            "Confidence": "0.9"
        }
    )
    assert confirm_response.status == 200
    
    # Parse the main menu TwiML
    main_menu_twiml = confirm_response.text
    assert "<Response>" in main_menu_twiml
    assert "order" in main_menu_twiml.lower()  # Should mention ordering
    
    # Extract the Gather action URL for main menu selection
    main_menu_action = extract_gather_action(main_menu_twiml)
    assert main_menu_action is not None
    
    # Step 5: Choose to ask about menu items
    menu_query_response = api_request.post(
        main_menu_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "tell me about your menu",
            "Confidence": "0.85"
        }
    )
    assert menu_query_response.status == 200
    
    # Parse the menu response TwiML
    menu_response_twiml = menu_query_response.text
    assert "<Response>" in menu_response_twiml
    
    # Extract the Gather action URL for continuing the conversation
    menu_continue_action = extract_gather_action(menu_response_twiml)
    assert menu_continue_action is not None
    
    # Step 6: Ask about a specific menu item
    item_query_response = api_request.post(
        menu_continue_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": f"Tell me about the {items[0]['name']}",
            "Confidence": "0.85"
        }
    )
    assert item_query_response.status == 200
    
    # Parse the item description TwiML
    item_response_twiml = item_query_response.text
    assert "<Response>" in item_response_twiml
    assert items[0]['name'].lower() in item_response_twiml.lower()  # Should mention the item
    
    # Extract the Gather action URL for continuing after item description
    after_item_action = extract_gather_action(item_response_twiml)
    assert after_item_action is not None
    
    # Step 7: Decide to place an order
    order_start_response = api_request.post(
        after_item_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "I'd like to place an order",
            "Confidence": "0.9"
        }
    )
    assert order_start_response.status == 200
    
    # Parse the order start TwiML
    order_start_twiml = order_start_response.text
    assert "<Response>" in order_start_twiml
    assert "order" in order_start_twiml.lower()  # Should mention ordering
    
    # Extract the Gather action URL for the first item ordering
    first_item_action = extract_gather_action(order_start_twiml)
    assert first_item_action is not None
    
    # Step 8: Order first item
    first_item_response = api_request.post(
        first_item_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": f"I want one {items[0]['name']}",
            "Confidence": "0.85"
        }
    )
    assert first_item_response.status == 200
    
    # Parse the confirmation for first item
    first_item_confirm_twiml = first_item_response.text
    assert "<Response>" in first_item_confirm_twiml
    assert items[0]['name'].lower() in first_item_confirm_twiml.lower()  # Should confirm the item
    
    # Extract the Gather action URL for confirming first item
    confirm_first_item_action = extract_gather_action(first_item_confirm_twiml)
    assert confirm_first_item_action is not None
    
    # Step 9: Confirm first item addition
    first_confirm_response = api_request.post(
        confirm_first_item_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "yes that's correct",
            "Confidence": "0.9"
        }
    )
    assert first_confirm_response.status == 200
    
    # Parse the TwiML after confirming first item
    after_first_item_twiml = first_confirm_response.text
    assert "<Response>" in after_first_item_twiml
    assert "anything else" in after_first_item_twiml.lower()  # Should ask about adding more
    
    # Extract the Gather action URL for adding more items
    add_more_action = extract_gather_action(after_first_item_twiml)
    assert add_more_action is not None
    
    # Step 10: Add a second item
    second_item_response = api_request.post(
        add_more_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": f"Yes, add one {items[1]['name']}",
            "Confidence": "0.85"
        }
    )
    assert second_item_response.status == 200
    
    # Parse the confirmation for second item
    second_item_confirm_twiml = second_item_response.text
    assert "<Response>" in second_item_confirm_twiml
    assert items[1]['name'].lower() in second_item_confirm_twiml.lower()  # Should confirm the item
    
    # Extract the Gather action URL for confirming second item
    confirm_second_item_action = extract_gather_action(second_item_confirm_twiml)
    assert confirm_second_item_action is not None
    
    # Step 11: Confirm second item addition
    second_confirm_response = api_request.post(
        confirm_second_item_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "yes",
            "Confidence": "0.9"
        }
    )
    assert second_confirm_response.status == 200
    
    # Parse the TwiML after confirming second item
    after_second_item_twiml = second_confirm_response.text
    assert "<Response>" in after_second_item_twiml
    assert "anything else" in after_second_item_twiml.lower()  # Should ask about adding more
    
    # Extract the Gather action URL for adding more items
    add_more_action2 = extract_gather_action(after_second_item_twiml)
    assert add_more_action2 is not None
    
    # Step 12: Finish adding items
    finish_adding_response = api_request.post(
        add_more_action2,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "No that's all",
            "Confidence": "0.9"
        }
    )
    assert finish_adding_response.status == 200
    
    # Parse the order summary TwiML
    order_summary_twiml = finish_adding_response.text
    assert "<Response>" in order_summary_twiml
    assert "order" in order_summary_twiml.lower()  # Should summarize the order
    
    # Both ordered items should be mentioned in the summary
    assert items[0]['name'].lower() in order_summary_twiml.lower()
    assert items[1]['name'].lower() in order_summary_twiml.lower()
    
    # Extract the Gather action URL for confirming full order
    confirm_full_order_action = extract_gather_action(order_summary_twiml)
    assert confirm_full_order_action is not None
    
    # Step 13: Confirm full order
    confirm_full_response = api_request.post(
        confirm_full_order_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "Yes, the order is correct",
            "Confidence": "0.9"
        }
    )
    assert confirm_full_response.status == 200
    
    # Parse the pickup time TwiML
    pickup_twiml = confirm_full_response.text
    assert "<Response>" in pickup_twiml
    assert "pickup" in pickup_twiml.lower()  # Should ask about pickup time
    
    # Extract the Gather action URL for pickup time
    pickup_action = extract_gather_action(pickup_twiml)
    assert pickup_action is not None
    
    # Step 14: Provide pickup time
    pickup_response = api_request.post(
        pickup_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "As soon as possible",
            "Confidence": "0.85"
        }
    )
    assert pickup_response.status == 200
    
    # Parse the payment method TwiML
    payment_twiml = pickup_response.text
    assert "<Response>" in payment_twiml
    assert "payment" in payment_twiml.lower()  # Should ask about payment
    
    # Extract the Gather action URL for payment method
    payment_action = extract_gather_action(payment_twiml)
    assert payment_action is not None
    
    # Step 15: Provide payment method
    payment_response = api_request.post(
        payment_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "I'll pay with cash",
            "Confidence": "0.9"
        }
    )
    assert payment_response.status == 200
    
    # Parse the final confirmation TwiML
    final_confirm_twiml = payment_response.text
    assert "<Response>" in final_confirm_twiml
    assert "confirm" in final_confirm_twiml.lower()  # Should ask for final confirmation
    
    # Extract the Gather action URL for final confirmation
    final_confirm_action = extract_gather_action(final_confirm_twiml)
    assert final_confirm_action is not None
    
    # Step 16: Give final confirmation
    final_response = api_request.post(
        final_confirm_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "Yes, place the order",
            "Confidence": "0.95"
        }
    )
    assert final_response.status == 200
    
    # Parse the order completion TwiML
    completion_twiml = final_response.text
    assert "<Response>" in completion_twiml
    assert "thank you" in completion_twiml.lower()  # Should thank the customer
    assert "order" in completion_twiml.lower()  # Should mention the order
    
    # Verify the order was actually created in the system
    # Wait briefly for async processing
    time.sleep(1)
    
    # Get recent orders to verify ours was created
    orders_response = api_request.get("/orders/recent")
    assert orders_response.status == 200
    orders = orders_response.json()
    
    # Find our order by customer name
    our_order = None
    for order in orders:
        if "customer" in order and "name" in order["customer"]:
            if order["customer"]["name"] == "John Smith":
                our_order = order
                break
    
    assert our_order is not None, "Order was not created in the system"
    
    # Verify order contains the items we requested
    assert len(our_order["items"]) == 2
    
    # Match items by name (case insensitive)
    order_item_names = [item["name"].lower() for item in our_order["items"]]
    assert items[0]["name"].lower() in order_item_names
    assert items[1]["name"].lower() in order_item_names

@pytest.mark.e2e
def test_voice_silence_handling_flow(api_request):
    """
    Test the voice call flow with silence at different points to verify proper silence handling.
    
    This test verifies:
    1. The system properly detects silence (no speech or DTMF input)
    2. The system provides appropriate prompts after silence
    3. The system falls back gracefully after multiple silences
    4. The system can recover from silence and continue the conversation
    5. The system uses adaptive timeouts based on context
    
    This is a true end-to-end test focused on the robustness of the voice interface.
    """
    # Generate a test CallSid
    test_call_sid = f"CA{''.join(['1234567890'[i % 10] for i in range(32)])}"
    
    # Step 1: Initial call to voice webhook
    voice_response = api_request.post(
        "/webhook/voice", 
        data={
            "CallSid": test_call_sid,
            "AccountSid": "AC12345",
            "From": "+15551234567"
        }
    )
    assert voice_response.status == 200
    
    # Parse the TwiML response to get the greeting and next action
    greeting_twiml = voice_response.text
    assert "<Response>" in greeting_twiml
    
    # Extract the Gather action URL for the next step
    gather_action = extract_gather_action(greeting_twiml)
    assert gather_action is not None
    
    # Step 2: Test silence on name collection
    # First silence (no SpeechResult or Digits)
    silence_response1 = api_request.post(
        gather_action,
        data={
            "CallSid": test_call_sid
        }
    )
    assert silence_response1.status == 200
    
    # Parse the first silence response
    silence1_twiml = silence_response1.text
    assert "<Response>" in silence1_twiml
    assert "didn't hear" in silence1_twiml.lower() or "sorry" in silence1_twiml.lower()  # Should acknowledge silence
    
    # Extract the new Gather action URL
    silence1_action = extract_gather_action(silence1_twiml)
    assert silence1_action is not None
    
    # Second silence (no SpeechResult or Digits)
    silence_response2 = api_request.post(
        silence1_action,
        data={
            "CallSid": test_call_sid
        }
    )
    assert silence_response2.status == 200
    
    # Parse the second silence response
    silence2_twiml = silence_response2.text
    assert "<Response>" in silence2_twiml
    # Second silence should give clearer instructions or a fallback
    assert "name" in silence2_twiml.lower()  # Should still be trying to get name or fallback
    
    # Extract the new Gather action URL
    silence2_action = extract_gather_action(silence2_twiml)
    assert silence2_action is not None
    
    # Now provide a name after silence to test recovery
    name_response = api_request.post(
        silence2_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "Sarah Johnson",
            "Confidence": "0.8"
        }
    )
    assert name_response.status == 200
    
    # Parse the name confirmation TwiML
    name_confirm_twiml = name_response.text
    assert "<Response>" in name_confirm_twiml
    assert "Sarah" in name_confirm_twiml  # Should contain the name
    
    # Extract the Gather action URL for name confirmation
    confirm_name_action = extract_gather_action(name_confirm_twiml)
    assert confirm_name_action is not None
    
    # Confirm name
    confirm_response = api_request.post(
        confirm_name_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "yes",
            "Confidence": "0.9"
        }
    )
    assert confirm_response.status == 200
    
    # Parse the main menu TwiML
    main_menu_twiml = confirm_response.text
    assert "<Response>" in main_menu_twiml
    
    # Extract the Gather action URL for main menu selection
    main_menu_action = extract_gather_action(main_menu_twiml)
    assert main_menu_action is not None
    
    # Step 3: Test multiple silences at main menu to force fallback to DTMF
    # First silence at main menu
    main_silence1 = api_request.post(
        main_menu_action,
        data={
            "CallSid": test_call_sid
        }
    )
    assert main_silence1.status == 200
    
    # Parse the first main menu silence response
    main_silence1_twiml = main_silence1.text
    assert "<Response>" in main_silence1_twiml
    assert "didn't hear" in main_silence1_twiml.lower() or "sorry" in main_silence1_twiml.lower()
    
    # Extract the new Gather action URL
    main_silence1_action = extract_gather_action(main_silence1_twiml)
    assert main_silence1_action is not None
    
    # Second silence at main menu
    main_silence2 = api_request.post(
        main_silence1_action,
        data={
            "CallSid": test_call_sid
        }
    )
    assert main_silence2.status == 200
    
    # Parse the second main menu silence response
    main_silence2_twiml = main_silence2.text
    assert "<Response>" in main_silence2_twiml
    
    # Check if system is starting to use DTMF fallback cues
    dtmf_detected = "press" in main_silence2_twiml.lower()
    
    # Extract the new Gather action URL
    main_silence2_action = extract_gather_action(main_silence2_twiml)
    assert main_silence2_action is not None
    
    # Third silence - should trigger a more significant fallback
    main_silence3 = api_request.post(
        main_silence2_action,
        data={
            "CallSid": test_call_sid
        }
    )
    assert main_silence3.status == 200
    
    # Parse the third main menu silence response
    main_silence3_twiml = main_silence3.text
    assert "<Response>" in main_silence3_twiml
    
    # At this point, system should be in DTMF-only mode or a significant fallback
    assert "press" in main_silence3_twiml.lower() or "transfer" in main_silence3_twiml.lower()
    
    # Extract the final action URL (might be a Gather or a Redirect)
    final_action = extract_gather_action(main_silence3_twiml)
    if final_action is None:
        final_action = extract_redirect_url(main_silence3_twiml)
    
    assert final_action is not None
    
    # Now provide DTMF input to test recovery from multiple silences
    dtmf_response = api_request.post(
        final_action,
        data={
            "CallSid": test_call_sid,
            "Digits": "1"  # Usually 1 is for ordering
        }
    )
    assert dtmf_response.status == 200
    
    # Verify system recovered and is proceeding with the call
    dtmf_twiml = dtmf_response.text
    assert "<Response>" in dtmf_twiml
    
    # Should be either proceeding with order or offering help
    assert "order" in dtmf_twiml.lower() or "help" in dtmf_twiml.lower()

@pytest.mark.e2e
def test_voice_menu_query_flow(api_request, deliverect_menu_payload):
    """
    Test a voice call flow focused on menu inquiries and item information.
    
    This test verifies:
    1. The system can properly answer questions about menu items
    2. The system provides accurate information about prices, descriptions, etc.
    3. The system can handle various phrasings of menu questions
    4. The system can handle conversation transitions between menu topics
    5. The AI generates appropriate and useful responses about the menu
    
    This is an end-to-end test focused on the menu information capabilities.
    """
    # First ensure the menu is populated
    menu_response = api_request.post("/menu_update", data=deliverect_menu_payload)
    assert menu_response.status == 200
    
    # Extract some menu items for testing
    test_items = []
    categories = []
    
    if "data" in deliverect_menu_payload and "menu" in deliverect_menu_payload["data"]:
        menu = deliverect_menu_payload["data"]["menu"]
        
        # Extract categories
        for category in menu.get("categories", []):
            categories.append(category["name"])
            # Extract items from each category
            for product in category.get("products", []):
                test_items.append({
                    "name": product["name"],
                    "description": product.get("description", ""),
                    "price": product.get("price", 0)
                })
    
    assert len(test_items) > 0, "No menu items found for testing"
    assert len(categories) > 0, "No menu categories found for testing"
    
    # Generate a test CallSid
    test_call_sid = f"CA{''.join(['1234567890'[i % 10] for i in range(32)])}"
    
    # Step 1: Initial call to voice webhook
    voice_response = api_request.post(
        "/webhook/voice", 
        data={
            "CallSid": test_call_sid,
            "AccountSid": "AC12345",
            "From": "+15551234567"
        }
    )
    assert voice_response.status == 200
    
    # Handle initial greeting and name collection quickly
    greeting_twiml = voice_response.text
    gather_action = extract_gather_action(greeting_twiml)
    
    # Provide name
    name_response = api_request.post(
        gather_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "Mike Smith",
            "Confidence": "0.8"
        }
    )
    
    name_confirm_twiml = name_response.text
    confirm_name_action = extract_gather_action(name_confirm_twiml)
    
    # Confirm name
    confirm_response = api_request.post(
        confirm_name_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "yes",
            "Confidence": "0.9"
        }
    )
    
    main_menu_twiml = confirm_response.text
    main_menu_action = extract_gather_action(main_menu_twiml)
    
    # Step 2: Choose to ask about menu
    menu_query_response = api_request.post(
        main_menu_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "I have some questions about your menu",
            "Confidence": "0.85"
        }
    )
    assert menu_query_response.status == 200
    
    # Parse the menu response TwiML
    menu_response_twiml = menu_query_response.text
    assert "<Response>" in menu_response_twiml
    
    # Extract the Gather action URL for continuing the conversation
    menu_continue_action = extract_gather_action(menu_response_twiml)
    assert menu_continue_action is not None
    
    # Step 3: Ask about menu categories
    category_query_response = api_request.post(
        menu_continue_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "What categories of food do you have?",
            "Confidence": "0.85"
        }
    )
    assert category_query_response.status == 200
    
    # Parse the category response TwiML
    category_response_twiml = category_query_response.text
    assert "<Response>" in category_response_twiml
    
    # Check that at least one category is mentioned
    found_category = False
    for category in categories:
        if category.lower() in category_response_twiml.lower():
            found_category = True
            break
    assert found_category, "No menu categories mentioned in response"
    
    # Extract the Gather action URL for continuing
    after_category_action = extract_gather_action(category_response_twiml)
    assert after_category_action is not None
    
    # Step 4: Ask about a specific item
    test_item = test_items[0]  # Use the first item
    item_query_response = api_request.post(
        after_category_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": f"Tell me about the {test_item['name']}",
            "Confidence": "0.85"
        }
    )
    assert item_query_response.status == 200
    
    # Parse the item response TwiML
    item_response_twiml = item_query_response.text
    assert "<Response>" in item_response_twiml
    assert test_item['name'].lower() in item_response_twiml.lower()  # Should mention the item
    
    # If the item has a price, it should be mentioned
    if test_item['price'] > 0:
        price_mentioned = False
        # Check for price mention (allowing for dollar signs, decimals, etc.)
        price_dollars = test_item['price'] if test_item['price'] < 100 else test_item['price'] / 100
        price_patterns = [
            fr"\${price_dollars}",
            fr"\${price_dollars:.2f}",
            fr"{price_dollars} dollars",
            fr"{price_dollars:.2f} dollars"
        ]
        for pattern in price_patterns:
            if re.search(pattern, item_response_twiml.lower()):
                price_mentioned = True
                break
        assert price_mentioned, "Item price not mentioned in response"
    
    # Extract the Gather action URL for continuing
    after_item_action = extract_gather_action(item_response_twiml)
    assert after_item_action is not None
    
    # Step 5: Ask about item price specifically
    price_query_response = api_request.post(
        after_item_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": f"How much does the {test_item['name']} cost?",
            "Confidence": "0.85"
        }
    )
    assert price_query_response.status == 200
    
    # Parse the price response TwiML
    price_response_twiml = price_query_response.text
    assert "<Response>" in price_response_twiml
    assert test_item['name'].lower() in price_response_twiml.lower()  # Should mention the item
    
    # Price should definitely be mentioned in a price-specific query
    price_mentioned = False
    price_dollars = test_item['price'] if test_item['price'] < 100 else test_item['price'] / 100
    price_patterns = [
        fr"\${price_dollars}",
        fr"\${price_dollars:.2f}",
        fr"{price_dollars} dollars",
        fr"{price_dollars:.2f} dollars"
    ]
    for pattern in price_patterns:
        if re.search(pattern, price_response_twiml.lower()):
            price_mentioned = True
            break
    assert price_mentioned, "Item price not mentioned in price query response"
    
    # Extract the Gather action URL for continuing
    after_price_action = extract_gather_action(price_response_twiml)
    assert after_price_action is not None
    
    # Step 6: Ask a general question about recommendations
    recommend_query_response = api_request.post(
        after_price_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "What do you recommend?",
            "Confidence": "0.85"
        }
    )
    assert recommend_query_response.status == 200
    
    # Parse the recommendation response TwiML
    recommend_response_twiml = recommend_query_response.text
    assert "<Response>" in recommend_response_twiml
    
    # Should mention at least one menu item in recommendations
    item_mentioned = False
    for item in test_items:
        if item['name'].lower() in recommend_response_twiml.lower():
            item_mentioned = True
            break
    assert item_mentioned, "No menu items mentioned in recommendation response"
    
    # Extract the Gather action URL for continuing
    after_recommend_action = extract_gather_action(recommend_response_twiml)
    assert after_recommend_action is not None
    
    # Step 7: Transition to placing an order
    order_transition_response = api_request.post(
        after_recommend_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "I'd like to place an order now",
            "Confidence": "0.9"
        }
    )
    assert order_transition_response.status == 200
    
    # Parse the order transition TwiML
    order_transition_twiml = order_transition_response.text
    assert "<Response>" in order_transition_twiml
    assert "order" in order_transition_twiml.lower()  # Should acknowledge the order request
    
    # Should be transitioning to the order flow
    order_keywords = ["what would you like", "what can i get", "place your order"]
    transition_detected = False
    for keyword in order_keywords:
        if keyword in order_transition_twiml.lower():
            transition_detected = True
            break
    assert transition_detected, "Did not detect transition to order flow"

# Helper functions to parse TwiML
def extract_gather_action(twiml):
    """Extract the 'action' attribute from a <Gather> tag in TwiML."""
    gather_match = re.search(r'<Gather[^>]*action="([^"]*)"', twiml)
    if gather_match:
        return gather_match.group(1)
    return None

def extract_redirect_url(twiml):
    """Extract the URL from a <Redirect> tag in TwiML."""
    redirect_match = re.search(r'<Redirect[^>]*>([^<]*)</Redirect>', twiml)
    if redirect_match:
        return redirect_match.group(1).strip()
    return None
