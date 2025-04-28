import json
import pytest
import time
import re
from urllib.parse import urlparse, parse_qs

@pytest.mark.e2e
def test_dtmf_only_order_flow(api_request, create_test_menu_payload):
    """
    Tests a complete order flow using only DTMF (touch-tone) input.
    
    This test verifies:
    1. The system can handle orders with no speech input
    2. The DTMF fallback mode provides all necessary functionality
    3. Users can complete orders using only number keys
    """
    # Setup: Create a test menu
    menu_payload = create_test_menu_payload(payload_type="direct", num_items=3)
    menu_response = api_request.post("/menu_update", data=menu_payload)
    assert menu_response.status == 200
    
    # Generate a test CallSid
    test_call_sid = f"CA{''.join(['1234567890'[i % 10] for i in range(32)])}"
    
    # Initial call to voice webhook
    voice_response = api_request.post(
        "/webhook/voice", 
        data={
            "CallSid": test_call_sid,
            "AccountSid": "AC12345",
            "From": "+15551234567"
        }
    )
    assert voice_response.status == 200
    
    # Force DTMF-only mode
    dtmf_mode_response = api_request.post(
        "/test/force_dtmf_mode",
        data={
            "CallSid": test_call_sid
        }
    )
    assert dtmf_mode_response.status == 200
    
    # Get the initial DTMF menu
    dtmf_menu_response = api_request.post(
        "/test/get_current_prompt",
        data={
            "CallSid": test_call_sid
        }
    )
    assert dtmf_menu_response.status == 200
    
    # Parse the DTMF menu TwiML
    dtmf_menu_twiml = dtmf_menu_response.text
    assert "<Response>" in dtmf_menu_twiml
    assert "press" in dtmf_menu_twiml.lower()  # Should mention button presses
    
    # Extract the Gather action
    dtmf_action = extract_gather_action(dtmf_menu_twiml)
    assert dtmf_action is not None
    
    # Select to place an order (usually 1)
    order_option_response = api_request.post(
        dtmf_action,
        data={
            "CallSid": test_call_sid,
            "Digits": "1"  # Press 1 for ordering
        }
    )
    assert order_option_response.status == 200
    
    # Parse the ordering menu TwiML
    ordering_twiml = order_option_response.text
    assert "<Response>" in ordering_twiml
    assert "press" in ordering_twiml.lower()
    
    # The system should provide a menu of item categories
    assert "categories" in ordering_twiml.lower() or "menu" in ordering_twiml.lower()
    
    # Extract the category selection action
    category_action = extract_gather_action(ordering_twiml)
    assert category_action is not None
    
    # Select the first category (usually 1)
    category_response = api_request.post(
        category_action,
        data={
            "CallSid": test_call_sid,
            "Digits": "1"  # Select first category
        }
    )
    assert category_response.status == 200
    
    # Parse the item selection TwiML
    items_twiml = category_response.text
    assert "<Response>" in items_twiml
    assert "press" in items_twiml.lower()
    
    # Should list items from the selected category
    assert "item" in items_twiml.lower() or "select" in items_twiml.lower()
    
    # Extract the item selection action
    item_select_action = extract_gather_action(items_twiml)
    assert item_select_action is not None
    
    # Select the first item (usually 1)
    item_select_response = api_request.post(
        item_select_action,
        data={
            "CallSid": test_call_sid,
            "Digits": "1"  # Select first item
        }
    )
    assert item_select_response.status == 200
    
    # Parse the quantity selection TwiML
    quantity_twiml = item_select_response.text
    assert "<Response>" in quantity_twiml
    assert "quantity" in quantity_twiml.lower() or "how many" in quantity_twiml.lower()
    
    # Extract the quantity selection action
    quantity_action = extract_gather_action(quantity_twiml)
    assert quantity_action is not None
    
    # Select quantity of 2
    quantity_response = api_request.post(
        quantity_action,
        data={
            "CallSid": test_call_sid,
            "Digits": "2"  # Order 2 of the item
        }
    )
    assert quantity_response.status == 200
    
    # Parse the confirmation TwiML
    confirm_twiml = quantity_response.text
    assert "<Response>" in confirm_twiml
    
    # Should ask for confirmation
    assert "confirm" in confirm_twiml.lower() or "correct" in confirm_twiml.lower()
    
    # Extract the confirmation action
    confirm_action = extract_gather_action(confirm_twiml)
    assert confirm_action is not None
    
    # Confirm the selection (usually 1 for yes)
    confirm_response = api_request.post(
        confirm_action,
        data={
            "CallSid": test_call_sid,
            "Digits": "1"  # 1 for yes
        }
    )
    assert confirm_response.status == 200
    
    # Parse the "anything else" TwiML
    anything_else_twiml = confirm_response.text
    assert "<Response>" in anything_else_twiml
    
    # Should ask if user wants to order anything else
    assert "anything else" in anything_else_twiml.lower() or "more items" in anything_else_twiml.lower()
    
    # Extract the action
    anything_else_action = extract_gather_action(anything_else_twiml)
    assert anything_else_action is not None
    
    # Select no (usually 2)
    anything_else_response = api_request.post(
        anything_else_action,
        data={
            "CallSid": test_call_sid,
            "Digits": "2"  # 2 for no
        }
    )
    assert anything_else_response.status == 200
    
    # Continue through the order flow (this would normally go through several more steps)
    # The remaining test would follow the same pattern of extracting the action and responding with DTMF
    
    # Fast-forward through order completion for testing purposes
    complete_order_response = api_request.post(
        "/test/complete_order",
        data={
            "CallSid": test_call_sid,
            "customer_name": "DTMF Customer",
            "order_type": "pickup",
            "payment_method": "cash"
        }
    )
    assert complete_order_response.status == 200
    
    # Wait briefly for order processing
    time.sleep(1)
    
    # Get the order to verify it was created correctly
    orders_response = api_request.get("/orders/recent")
    assert orders_response.status == 200
    orders = orders_response.json()
    
    # Find our order by customer name
    our_order = None
    for order in orders:
        if "customer" in order and "name" in order["customer"]:
            if order["customer"]["name"] == "DTMF Customer":
                our_order = order
                break
    
    assert our_order is not None, "Order was not created in the system"
    
    # Verify the order has the correct item and quantity
    assert len(our_order["items"]) > 0
    assert our_order["items"][0]["quantity"] == 2

@pytest.mark.e2e
def test_human_agent_transfer_flow(api_request):
    """
    Tests the flow for transferring a customer to a human agent.
    
    This test verifies:
    1. The system recognizes requests for human assistance
    2. The system correctly initiates the transfer process
    3. The proper transfer protocols are followed
    4. Customer information is preserved during transfer
    """
    # Generate a test CallSid
    test_call_sid = f"CA{''.join(['1234567890'[i % 10] for i in range(32)])}"
    
    # Initial call to voice webhook
    voice_response = api_request.post(
        "/webhook/voice", 
        data={
            "CallSid": test_call_sid,
            "AccountSid": "AC12345",
            "From": "+15551234567"
        }
    )
    assert voice_response.status == 200
    
    # Handle initial greeting and name collection
    greeting_twiml = voice_response.text
    gather_action = extract_gather_action(greeting_twiml)
    
    name_response = api_request.post(
        gather_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "Taylor Wilson",
            "Confidence": "0.9"
        }
    )
    
    name_confirm_twiml = name_response.text
    confirm_name_action = extract_gather_action(name_confirm_twiml)
    
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
    
    # Request to speak to a human agent
    human_request_response = api_request.post(
        main_menu_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "I want to speak to a real person",
            "Confidence": "0.9"
        }
    )
    assert human_request_response.status == 200
    
    # Parse the human transfer TwiML
    transfer_twiml = human_request_response.text
    assert "<Response>" in transfer_twiml
    
    # Should acknowledge the transfer request
    transfer_acknowledgement = any(phrase in transfer_twiml.lower() for phrase in 
                                  ["transfer", "connect", "agent", "representative", "person"])
    assert transfer_acknowledgement, "System didn't acknowledge human transfer request"
    
    # Check for Dial or Redirect tag that would handle the transfer
    has_transfer_action = "<Dial>" in transfer_twiml or "<Redirect>" in transfer_twiml
    assert has_transfer_action, "Transfer TwiML doesn't contain Dial or Redirect tag"
    
    # If using Dial, check for a proper phone number
    if "<Dial>" in transfer_twiml:
        dial_match = re.search(r'<Dial[^>]*>([^<]*)</Dial>', transfer_twiml)
        assert dial_match, "Dial tag doesn't contain a phone number"
        
        phone_number = dial_match.group(1).strip()
        assert re.match(r'^\+?\d{10,15}$', phone_number), f"Invalid phone number format: {phone_number}"
    
    # If using Redirect, check for a proper URL
    if "<Redirect>" in transfer_twiml:
        redirect_url = extract_redirect_url(transfer_twiml)
        assert redirect_url, "Redirect tag doesn't contain a URL"
        assert redirect_url.startswith("/"), f"Invalid redirect URL: {redirect_url}"
    
    # Check for customer info preservation (usually done via URL params or session)
    customer_info_preserved = "Taylor" in transfer_twiml or "+15551234567" in transfer_twiml
    if not customer_info_preserved:
        # Check URL params if using Redirect
        if "<Redirect>" in transfer_twiml:
            redirect_url = extract_redirect_url(transfer_twiml)
            if "?" in redirect_url:
                query_params = parse_qs(urlparse(redirect_url).query)
                customer_info_preserved = any(["name" in query_params, "phone" in query_params, 
                                             "customer" in query_params])
    
    assert customer_info_preserved, "Customer information not preserved in transfer"

@pytest.mark.e2e
def test_multiple_users_on_call(api_request, create_test_menu_payload):
    """
    Tests the system's handling of multiple users speaking on the same call.
    
    This test verifies:
    1. The system can handle different voices in the same conversation
    2. The order flow works when multiple people participate
    3. The final order correctly captures all inputs
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
    
    # Initial call to voice webhook
    voice_response = api_request.post(
        "/webhook/voice", 
        data={
            "CallSid": test_call_sid,
            "AccountSid": "AC12345",
            "From": "+15551234567"
        }
    )
    assert voice_response.status == 200
    
    # First user provides name
    greeting_twiml = voice_response.text
    gather_action = extract_gather_action(greeting_twiml)
    
    name_response = api_request.post(
        gather_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "Sam and Jordan",  # Multiple names
            "Confidence": "0.9"
        }
    )
    
    name_confirm_twiml = name_response.text
    confirm_name_action = extract_gather_action(name_confirm_twiml)
    
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
    
    # First user starts order
    order_start_response = api_request.post(
        main_menu_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "We would like to place an order",
            "Confidence": "0.9"
        }
    )
    assert order_start_response.status == 200
    
    # First user orders an item
    order_start_twiml = order_start_response.text
    first_item_action = extract_gather_action(order_start_twiml)
    
    first_item_response = api_request.post(
        first_item_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": f"I want one {test_item1['name']}",
            "Confidence": "0.9"
        }
    )
    assert first_item_response.status == 200
    
    # Confirm first item
    first_item_twiml = first_item_response.text
    confirm_item_action = extract_gather_action(first_item_twiml)
    
    confirm_item_response = api_request.post(
        confirm_item_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "yes that's correct",
            "Confidence": "0.9"
        }
    )
    assert confirm_item_response.status == 200
    
    # Ask for more items
    anything_else_twiml = confirm_item_response.text
    anything_else_action = extract_gather_action(anything_else_twiml)
    
    # Second user adds an item (different speech pattern)
    second_user_item_response = api_request.post(
        anything_else_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": f"Yeah, and I'll have the {test_item2['name']}",
            "Confidence": "0.85"  # Slightly different confidence
        }
    )
    assert second_user_item_response.status == 200
    
    # Confirm second item
    second_item_twiml = second_user_item_response.text
    confirm_second_item_action = extract_gather_action(second_item_twiml)
    
    confirm_second_item_response = api_request.post(
        confirm_second_item_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "Yes that's right",
            "Confidence": "0.87"  # Different confidence
        }
    )
    assert confirm_second_item_response.status == 200
    
    # More items?
    more_items_twiml = confirm_second_item_response.text
    more_items_action = extract_gather_action(more_items_twiml)
    
    # Done with ordering
    done_ordering_response = api_request.post(
        more_items_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "No that's all for us",
            "Confidence": "0.9"
        }
    )
    assert done_ordering_response.status == 200
    
    # Confirm the order summary
    summary_twiml = done_ordering_response.text
    summary_action = extract_gather_action(summary_twiml)
    
    # Both users' items should be in the summary
    assert test_item1["name"] in summary_twiml
    assert test_item2["name"] in summary_twiml
    
    # First user confirms the summary
    summary_confirm_response = api_request.post(
        summary_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "Yes that's right",
            "Confidence": "0.9"
        }
    )
    assert summary_confirm_response.status == 200
    
    # Fast-forward through order completion for testing purposes
    complete_order_response = api_request.post(
        "/test/complete_order",
        data={
            "CallSid": test_call_sid,
            "order_type": "pickup",
            "payment_method": "cash"
        }
    )
    assert complete_order_response.status == 200
    
    # Wait briefly for order processing
    time.sleep(1)
    
    # Get the order to verify it includes both users' items
    orders_response = api_request.get("/orders/recent")
    assert orders_response.status == 200
    orders = orders_response.json()
    
    # Find our order by customer name
    our_order = None
    for order in orders:
        if "customer" in order and "name" in order["customer"]:
            if "Sam and Jordan" in order["customer"]["name"]:
                our_order = order
                break
    
    assert our_order is not None, "Order was not created in the system"
    
    # Verify the order contains both users' items
    assert len(our_order["items"]) == 2
    
    order_items = [item["plu"] for item in our_order["items"]]
    assert test_item1["plu"] in order_items, "First user's item missing from order"
    assert test_item2["plu"] in order_items, "Second user's item missing from order"

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