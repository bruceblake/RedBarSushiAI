import json
import pytest
import time
import re
from urllib.parse import urlparse, parse_qs


@pytest.mark.e2e
def test_delivery_order_flow(api_request, create_test_menu_payload):
    """
    Tests a complete delivery order flow including address collection.

    This test verifies:
    1. The system correctly handles delivery order type selection
    2. The system collects and validates delivery address
    3. The order is properly processed with delivery information
    4. Delivery fees are correctly applied
    """
    # Setup: Create a test menu
    menu_payload = create_test_menu_payload(payload_type="direct", num_items=3)
    menu_response = api_request.post("/menu_update", data=menu_payload)
    assert menu_response.status == 200

    # Extract a test item to order
    test_item = menu_payload["items"][0]

    # Generate a test CallSid
    test_call_sid = f"CA{''.join(['1234567890'[i % 10] for i in range(32)])}"

    # Initial call to voice webhook
    voice_response = api_request.post(
        "/webhook/voice",
        data={
            "CallSid": test_call_sid,
            "AccountSid": "AC12345",
            "From": "+15551234567",
        },
    )
    assert voice_response.status == 200

    # Complete name collection quickly
    greeting_twiml = voice_response.text
    gather_action = extract_gather_action(greeting_twiml)

    name_response = api_request.post(
        gather_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "Jane Smith",
            "Confidence": "0.9",
        },
    )

    name_confirm_twiml = name_response.text
    confirm_name_action = extract_gather_action(name_confirm_twiml)

    confirm_response = api_request.post(
        confirm_name_action,
        data={"CallSid": test_call_sid, "SpeechResult": "yes", "Confidence": "0.9"},
    )

    # Reach the main menu
    main_menu_twiml = confirm_response.text
    main_menu_action = extract_gather_action(main_menu_twiml)

    # Start ordering
    order_start_response = api_request.post(
        main_menu_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "I'd like to place an order",
            "Confidence": "0.9",
        },
    )
    assert order_start_response.status == 200

    # Order an item
    order_start_twiml = order_start_response.text
    first_item_action = extract_gather_action(order_start_twiml)

    first_item_response = api_request.post(
        first_item_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": f"I want one {test_item['name']}",
            "Confidence": "0.9",
        },
    )
    assert first_item_response.status == 200

    # Confirm the item
    first_item_twiml = first_item_response.text
    confirm_item_action = extract_gather_action(first_item_twiml)

    confirm_item_response = api_request.post(
        confirm_item_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "yes that's correct",
            "Confidence": "0.9",
        },
    )
    assert confirm_item_response.status == 200

    # Finish ordering
    anything_else_twiml = confirm_item_response.text
    anything_else_action = extract_gather_action(anything_else_twiml)

    finish_order_response = api_request.post(
        anything_else_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "no that's all",
            "Confidence": "0.9",
        },
    )
    assert finish_order_response.status == 200

    # Confirm the order summary
    summary_twiml = finish_order_response.text
    summary_confirm_action = extract_gather_action(summary_twiml)

    summary_confirm_response = api_request.post(
        summary_confirm_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "yes that's correct",
            "Confidence": "0.9",
        },
    )
    assert summary_confirm_response.status == 200

    # Get to the order type selection
    order_type_twiml = summary_confirm_response.text
    order_type_action = extract_gather_action(order_type_twiml)

    # Choose delivery
    delivery_response = api_request.post(
        order_type_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "delivery",
            "Confidence": "0.9",
        },
    )
    assert delivery_response.status == 200

    # Verify we're asked for an address
    address_twiml = delivery_response.text
    assert "<Response>" in address_twiml
    assert "address" in address_twiml.lower()

    # Extract address prompt action
    address_action = extract_gather_action(address_twiml)
    assert address_action is not None

    # Provide a delivery address
    address_response = api_request.post(
        address_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "123 Main Street, Apartment 4B, New York, NY 10001",
            "Confidence": "0.9",
        },
    )
    assert address_response.status == 200

    # Verify address confirmation
    address_confirm_twiml = address_response.text
    assert "<Response>" in address_confirm_twiml
    assert "123 Main Street" in address_confirm_twiml

    # Extract confirmation action
    address_confirm_action = extract_gather_action(address_confirm_twiml)
    assert address_confirm_action is not None

    # Confirm the address
    address_confirm_response = api_request.post(
        address_confirm_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "yes that's correct",
            "Confidence": "0.9",
        },
    )
    assert address_confirm_response.status == 200

    # Should proceed to payment
    payment_twiml = address_confirm_response.text
    assert "<Response>" in payment_twiml
    assert "payment" in payment_twiml.lower()

    # Process payment
    payment_action = extract_gather_action(payment_twiml)
    payment_response = api_request.post(
        payment_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "cash on delivery",
            "Confidence": "0.9",
        },
    )
    assert payment_response.status == 200

    # Complete order with final confirmation
    final_twiml = payment_response.text
    final_confirm_action = extract_gather_action(final_twiml)

    final_response = api_request.post(
        final_confirm_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "yes place the order",
            "Confidence": "0.95",
        },
    )
    assert final_response.status == 200

    # Verify order completion message
    completion_twiml = final_response.text
    assert "<Response>" in completion_twiml
    assert "thank you" in completion_twiml.lower()

    # Wait briefly for order processing
    time.sleep(1)

    # Get the order to verify delivery details
    orders_response = api_request.get("/orders/recent")
    assert orders_response.status == 200
    orders = orders_response.json()

    # Find our order by customer name
    our_order = None
    for order in orders:
        if "customer" in order and "name" in order["customer"]:
            if order["customer"]["name"] == "Jane Smith":
                our_order = order
                break

    assert our_order is not None, "Order was not created in the system"

    # Verify delivery details
    assert our_order["order_type"] == "delivery"
    assert "delivery_address" in our_order
    assert "123 Main Street" in our_order["delivery_address"]
    assert "New York" in our_order["delivery_address"]

    # Verify delivery fee was applied
    assert "delivery_fee" in our_order
    assert our_order["delivery_fee"] > 0


@pytest.mark.e2e
def test_order_with_special_requests(api_request, create_test_menu_payload):
    """
    Tests an order with special requests and dietary restrictions.

    This test verifies:
    1. The system can handle special requests for menu items
    2. Dietary restrictions are properly recorded with the order
    3. Special instructions are passed to the kitchen
    """
    # Setup: Create a test menu
    menu_payload = create_test_menu_payload(payload_type="direct", num_items=3)
    menu_response = api_request.post("/menu_update", data=menu_payload)
    assert menu_response.status == 200

    # Extract a test item to order
    test_item = menu_payload["items"][0]

    # Generate a test CallSid
    test_call_sid = f"CA{''.join(['1234567890'[i % 10] for i in range(32)])}"

    # Set up a session at the ordering stage
    # This simplifies the test by skipping the initial greeting and name collection
    setup_response = api_request.post(
        "/test/setup_mock_order_session",
        data={
            "CallSid": test_call_sid,
            "customer_name": "Alex Johnson",
            "phone": "+15551234567",
            "order_stage": "ordering",
        },
    )
    assert setup_response.status == 200

    # Get the current ordering prompt
    ordering_prompt_response = api_request.post(
        "/test/get_current_prompt", data={"CallSid": test_call_sid}
    )
    assert ordering_prompt_response.status == 200

    # Parse the ordering TwiML
    ordering_twiml = ordering_prompt_response.text
    assert "<Response>" in ordering_twiml

    # Extract the action URL for ordering
    ordering_action = extract_gather_action(ordering_twiml)
    assert ordering_action is not None

    # Order item with a special request
    special_order_response = api_request.post(
        ordering_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": f"I want one {test_item['name']} but I have a gluten allergy, can you make it gluten free?",
            "Confidence": "0.9",
        },
    )
    assert special_order_response.status == 200

    # Verify the system acknowledges the special request
    special_twiml = special_order_response.text
    assert "<Response>" in special_twiml

    # Should mention the special request or allergies
    special_request_acknowledged = any(
        phrase in special_twiml.lower()
        for phrase in ["special", "allergy", "gluten", "request", "dietary"]
    )
    assert (
        special_request_acknowledged
    ), "System didn't acknowledge special dietary request"

    # Extract the confirmation action
    special_confirm_action = extract_gather_action(special_twiml)
    assert special_confirm_action is not None

    # Confirm the special request
    special_confirm_response = api_request.post(
        special_confirm_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "yes that's correct",
            "Confidence": "0.9",
        },
    )
    assert special_confirm_response.status == 200

    # Anything else?
    anything_else_twiml = special_confirm_response.text
    anything_else_action = extract_gather_action(anything_else_twiml)

    # No more items
    finish_order_response = api_request.post(
        anything_else_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "no that's all",
            "Confidence": "0.9",
        },
    )
    assert finish_order_response.status == 200

    # Fast-forward through order completion
    # (This would normally go through several more steps)

    # Use a test endpoint to complete the order
    complete_order_response = api_request.post(
        "/test/complete_order",
        data={
            "CallSid": test_call_sid,
            "order_type": "pickup",
            "payment_method": "cash",
        },
    )
    assert complete_order_response.status == 200

    # Wait briefly for order processing
    time.sleep(1)

    # Get the order to verify special request details
    orders_response = api_request.get("/orders/recent")
    assert orders_response.status == 200
    orders = orders_response.json()

    # Find our order by customer name
    our_order = None
    for order in orders:
        if "customer" in order and "name" in order["customer"]:
            if order["customer"]["name"] == "Alex Johnson":
                our_order = order
                break

    assert our_order is not None, "Order was not created in the system"

    # Verify special request and dietary restriction
    assert "special_instructions" in our_order
    assert "gluten" in our_order["special_instructions"].lower()
    assert "allergy" in our_order["special_instructions"].lower()

    # Verify item has the special request flag
    assert len(our_order["items"]) == 1
    assert "special_requests" in our_order["items"][0]
    assert "gluten free" in our_order["items"][0]["special_requests"].lower()


@pytest.mark.e2e
def test_order_modification_flow(api_request, create_test_menu_payload):
    """
    Tests the ability to modify an order after initial creation.

    This test verifies:
    1. The system allows adding items to an existing order
    2. The system allows removing items from an existing order
    3. The system allows modifying quantities of items
    4. The modified order is correctly processed
    """
    # Setup: Create a test menu
    menu_payload = create_test_menu_payload(payload_type="direct", num_items=3)
    menu_response = api_request.post("/menu_update", data=menu_payload)
    assert menu_response.status == 200

    # Extract test items to order
    test_item1 = menu_payload["items"][0]
    test_item2 = menu_payload["items"][1]

    # Generate a test CallSid
    test_call_sid = f"CA{''.join(['1234567890'[i % 10] for i in range(32)])}"

    # Set up a session with an initial order
    setup_response = api_request.post(
        "/test/setup_mock_order_session",
        data={
            "CallSid": test_call_sid,
            "customer_name": "Morgan Davis",
            "phone": "+15551234567",
            "items": [
                {
                    "plu": test_item1["plu"],
                    "name": test_item1["name"],
                    "price": test_item1["price"],
                    "quantity": 1,
                }
            ],
            "order_stage": "order_summary",
        },
    )
    assert setup_response.status == 200

    # Get the current order summary prompt
    summary_prompt_response = api_request.post(
        "/test/get_current_prompt", data={"CallSid": test_call_sid}
    )
    assert summary_prompt_response.status == 200

    # Parse the summary TwiML
    summary_twiml = summary_prompt_response.text
    assert "<Response>" in summary_twiml
    assert test_item1["name"] in summary_twiml  # Should mention the item

    # Extract the action URL for the order summary
    summary_action = extract_gather_action(summary_twiml)
    assert summary_action is not None

    # Request to modify the order
    modify_request_response = api_request.post(
        summary_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "I want to make some changes to my order",
            "Confidence": "0.9",
        },
    )
    assert modify_request_response.status == 200

    # Verify the system enters the modification flow
    modify_twiml = modify_request_response.text
    assert "<Response>" in modify_twiml
    assert "change" in modify_twiml.lower() or "modify" in modify_twiml.lower()

    # Extract the modification options action
    modify_options_action = extract_gather_action(modify_twiml)
    assert modify_options_action is not None

    # Request to add an item
    add_item_response = api_request.post(
        modify_options_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "I want to add another item",
            "Confidence": "0.9",
        },
    )
    assert add_item_response.status == 200

    # Verify we're in the add item flow
    add_item_twiml = add_item_response.text
    assert "<Response>" in add_item_twiml
    assert "add" in add_item_twiml.lower()

    # Extract the add item action
    add_item_action = extract_gather_action(add_item_twiml)
    assert add_item_action is not None

    # Specify the item to add
    specify_item_response = api_request.post(
        add_item_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": f"I want one {test_item2['name']}",
            "Confidence": "0.9",
        },
    )
    assert specify_item_response.status == 200

    # Verify the new item is understood
    new_item_twiml = specify_item_response.text
    assert "<Response>" in new_item_twiml
    assert test_item2["name"] in new_item_twiml

    # Extract the confirmation action
    new_item_confirm_action = extract_gather_action(new_item_twiml)
    assert new_item_confirm_action is not None

    # Confirm the new item
    new_item_confirm_response = api_request.post(
        new_item_confirm_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "yes that's correct",
            "Confidence": "0.9",
        },
    )
    assert new_item_confirm_response.status == 200

    # Now request to modify an existing item's quantity
    modify_again_twiml = new_item_confirm_response.text
    modify_again_action = extract_gather_action(modify_again_twiml)

    modify_quantity_response = api_request.post(
        modify_again_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "I want to change the quantity of the first item",
            "Confidence": "0.9",
        },
    )
    assert modify_quantity_response.status == 200

    # Verify we're in the quantity modification flow
    quantity_twiml = modify_quantity_response.text
    assert "<Response>" in quantity_twiml
    assert "quantity" in quantity_twiml.lower() or "how many" in quantity_twiml.lower()

    # Extract the quantity action
    quantity_action = extract_gather_action(quantity_twiml)
    assert quantity_action is not None

    # Specify the new quantity
    new_quantity_response = api_request.post(
        quantity_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "make it two please",
            "Confidence": "0.9",
        },
    )
    assert new_quantity_response.status == 200

    # Verify the quantity change is understood
    quantity_confirm_twiml = new_quantity_response.text
    assert "<Response>" in quantity_confirm_twiml
    assert "two" in quantity_confirm_twiml.lower()

    # Extract the confirmation action
    quantity_confirm_action = extract_gather_action(quantity_confirm_twiml)
    assert quantity_confirm_action is not None

    # Confirm the quantity change
    quantity_confirm_response = api_request.post(
        quantity_confirm_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "yes that's correct",
            "Confidence": "0.9",
        },
    )
    assert quantity_confirm_response.status == 200

    # Get the updated order summary
    updated_summary_twiml = quantity_confirm_response.text
    assert "<Response>" in updated_summary_twiml

    # Check that both items are mentioned with correct quantities
    assert test_item1["name"] in updated_summary_twiml
    assert test_item2["name"] in updated_summary_twiml
    assert "two" in updated_summary_twiml.lower()

    # Extract the final confirmation action
    final_confirm_action = extract_gather_action(updated_summary_twiml)
    assert final_confirm_action is not None

    # Confirm the final order
    final_confirm_response = api_request.post(
        final_confirm_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "yes that looks good",
            "Confidence": "0.95",
        },
    )
    assert final_confirm_response.status == 200

    # Fast-forward to complete the order
    complete_order_response = api_request.post(
        "/test/complete_order",
        data={
            "CallSid": test_call_sid,
            "order_type": "pickup",
            "payment_method": "cash",
        },
    )
    assert complete_order_response.status == 200

    # Wait briefly for order processing
    time.sleep(1)

    # Get the order to verify the modifications
    orders_response = api_request.get("/orders/recent")
    assert orders_response.status == 200
    orders = orders_response.json()

    # Find our order by customer name
    our_order = None
    for order in orders:
        if "customer" in order and "name" in order["customer"]:
            if order["customer"]["name"] == "Morgan Davis":
                our_order = order
                break

    assert our_order is not None, "Order was not created in the system"

    # Verify the order contains both items with correct quantities
    assert len(our_order["items"]) == 2

    item1_found = False
    item2_found = False
    for item in our_order["items"]:
        if item["plu"] == test_item1["plu"]:
            item1_found = True
            assert item["quantity"] == 2, "First item quantity not updated to 2"
        elif item["plu"] == test_item2["plu"]:
            item2_found = True
            assert item["quantity"] == 1, "Second item quantity incorrect"

    assert item1_found, "First item not found in final order"
    assert item2_found, "Second item not found in final order"


# Helper functions to parse TwiML
def extract_gather_action(twiml):
    """Extract the 'action' attribute from a <Gather> tag in TwiML."""
    gather_match = re.search(r'<Gather[^>]*action="([^"]*)"', twiml)
    if gather_match:
        return gather_match.group(1)
    return None


def extract_redirect_url(twiml):
    """Extract the URL from a <Redirect> tag in TwiML."""
    redirect_match = re.search(r"<Redirect[^>]*>([^<]*)</Redirect>", twiml)
    if redirect_match:
        return redirect_match.group(1).strip()
    return None
