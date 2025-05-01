import json
import pytest
import time
import re
from urllib.parse import urlparse, parse_qs


@pytest.mark.e2e
def test_speech_recognition_error_recovery(api_request):
    """
    Tests the system's ability to recover from speech recognition errors.

    This test verifies:
    1. The system can handle low-confidence speech recognition
    2. The system provides appropriate reprompts
    3. The conversation can recover and continue after recognition issues
    """
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

    # Parse the TwiML response
    greeting_twiml = voice_response.text
    assert "<Response>" in greeting_twiml

    # Extract the Gather action URL
    gather_action = extract_gather_action(greeting_twiml)
    assert gather_action is not None

    # Simulate a low-confidence speech recognition result
    name_response = api_request.post(
        gather_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "John Smith",
            "Confidence": "0.2",  # Very low confidence
        },
    )
    assert name_response.status == 200

    # Parse the response - should detect low confidence and ask for clarification
    name_retry_twiml = name_response.text
    assert "<Response>" in name_retry_twiml

    # Should contain a reprompt message for low confidence
    low_confidence_detected = any(
        phrase in name_retry_twiml.lower()
        for phrase in [
            "didn't catch",
            "didn't understand",
            "could you repeat",
            "say that again",
        ]
    )
    assert (
        low_confidence_detected
    ), "System didn't handle low confidence recognition properly"

    # Extract the new Gather action URL
    retry_gather_action = extract_gather_action(name_retry_twiml)
    assert retry_gather_action is not None

    # Now provide a clearer name with good confidence
    clear_name_response = api_request.post(
        retry_gather_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "John Smith",
            "Confidence": "0.9",
        },
    )
    assert clear_name_response.status == 200

    # Verify we're now at name confirmation
    name_confirm_twiml = clear_name_response.text
    assert "John" in name_confirm_twiml  # Should contain the name

    # Complete the name confirmation
    confirm_name_action = extract_gather_action(name_confirm_twiml)
    confirm_response = api_request.post(
        confirm_name_action,
        data={"CallSid": test_call_sid, "SpeechResult": "yes", "Confidence": "0.9"},
    )

    # Verify we made it past the error recovery to the main menu
    main_menu_twiml = confirm_response.text
    assert "menu" in main_menu_twiml.lower() or "order" in main_menu_twiml.lower()


@pytest.mark.e2e
def test_order_submission_error_recovery(api_request, create_test_menu_payload):
    """
    Tests the system's ability to recover from order submission errors.

    This test verifies:
    1. The system detects API failures when submitting orders
    2. The system informs the user appropriately about technical issues
    3. The system offers alternatives (retry, human assistance, etc.)
    """
    # Setup: First create a test menu
    menu_payload = create_test_menu_payload(payload_type="direct", num_items=3)
    menu_response = api_request.post("/menu_update", data=menu_payload)
    assert menu_response.status == 200

    # Extract a test item to order
    test_item = menu_payload["items"][0]

    # Generate a test CallSid
    test_call_sid = f"CA{''.join(['1234567890'[i % 10] for i in range(32)])}"

    # Simulate a completed order flow up to the final confirmation
    # (This is a simplified version - in a real test we'd go through all the steps)

    # 1. First, get to the order placement point by using API mock calls
    # Set up a session with an order ready to be confirmed
    setup_response = api_request.post(
        "/test/setup_mock_order_session",  # This would be a test endpoint we create
        data={
            "CallSid": test_call_sid,
            "customer_name": "John Smith",
            "phone": "+15551234567",
            "items": [
                {
                    "plu": test_item["plu"],
                    "name": test_item["name"],
                    "price": test_item["price"],
                    "quantity": 1,
                }
            ],
            "order_stage": "final_confirmation",
        },
    )
    assert setup_response.status == 200

    # 2. Force the API to fail on the next order submission
    force_error_response = api_request.post(
        "/test/set_next_order_error",  # Another test endpoint we create
        data={"error_type": "api_timeout"},
    )
    assert force_error_response.status == 200

    # 3. Now attempt to confirm the order - should trigger the error
    confirm_endpoint = (
        "/order/confirm"  # The actual endpoint that handles final confirmation
    )
    error_confirm_response = api_request.post(
        confirm_endpoint,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "yes confirm the order",
            "Confidence": "0.9",
        },
    )
    assert error_confirm_response.status == 200

    # 4. Parse the error response TwiML
    error_twiml = error_confirm_response.text
    assert "<Response>" in error_twiml

    # Should contain an error message
    assert any(
        phrase in error_twiml.lower()
        for phrase in [
            "technical difficulty",
            "system error",
            "problem",
            "issue",
            "try again",
        ]
    )

    # Should offer alternatives (retry, human assistance, etc.)
    recovery_options = any(
        phrase in error_twiml.lower()
        for phrase in ["try again", "speak with", "transfer", "call back"]
    )
    assert recovery_options, "System didn't provide recovery options after order error"

    # Extract the action URL for the recovery choice
    recovery_action = extract_gather_action(error_twiml)
    assert recovery_action is not None

    # Choose to retry the order
    retry_response = api_request.post(
        recovery_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "let's try again",
            "Confidence": "0.9",
        },
    )
    assert retry_response.status == 200

    # Verify we're in the retry flow
    retry_twiml = retry_response.text
    assert "<Response>" in retry_twiml
    assert "retry" in retry_twiml.lower() or "again" in retry_twiml.lower()


@pytest.mark.e2e
def test_payment_processing_error_recovery(api_request, create_test_menu_payload):
    """
    Tests the system's ability to recover from payment processing errors.

    This test verifies:
    1. The system can handle payment processing failures
    2. The system provides alternative payment options
    3. The order can be completed after a payment issue is resolved
    """
    # Setup: First create a test menu
    menu_payload = create_test_menu_payload(payload_type="direct", num_items=3)
    menu_response = api_request.post("/menu_update", data=menu_payload)
    assert menu_response.status == 200

    # Extract a test item to order
    test_item = menu_payload["items"][0]

    # Generate a test CallSid
    test_call_sid = f"CA{''.join(['1234567890'[i % 10] for i in range(32)])}"

    # Set up a session with an order at the payment stage
    setup_response = api_request.post(
        "/test/setup_mock_order_session",  # Test endpoint
        data={
            "CallSid": test_call_sid,
            "customer_name": "John Smith",
            "phone": "+15551234567",
            "items": [
                {
                    "plu": test_item["plu"],
                    "name": test_item["name"],
                    "price": test_item["price"],
                    "quantity": 1,
                }
            ],
            "order_stage": "payment_method",
        },
    )
    assert setup_response.status == 200

    # Get the current payment selection prompt
    payment_prompt_response = api_request.post(
        "/order/get_payment_prompt",  # Test endpoint to get the current prompt
        data={"CallSid": test_call_sid},
    )
    assert payment_prompt_response.status == 200

    # Parse the payment TwiML
    payment_twiml = payment_prompt_response.text
    assert "<Response>" in payment_twiml
    assert "payment" in payment_twiml.lower()

    # Extract the Gather action URL for payment method
    payment_action = extract_gather_action(payment_twiml)
    assert payment_action is not None

    # Force the next payment processing to fail
    force_payment_error = api_request.post(
        "/test/set_next_payment_error",  # Test endpoint
        data={"error_type": "payment_declined"},
    )
    assert force_payment_error.status == 200

    # Choose credit card payment - this should trigger the error
    card_payment_response = api_request.post(
        payment_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "I'll pay with credit card",
            "Confidence": "0.9",
        },
    )
    assert card_payment_response.status == 200

    # Parse the error response TwiML
    error_twiml = card_payment_response.text
    assert "<Response>" in error_twiml

    # Should indicate a payment issue
    payment_error_detected = any(
        phrase in error_twiml.lower()
        for phrase in ["payment", "card", "declined", "issue", "problem"]
    )
    assert payment_error_detected, "System didn't indicate payment processing error"

    # Should offer alternatives
    alternatives_offered = any(
        phrase in error_twiml.lower()
        for phrase in ["alternative", "cash", "different method", "try again"]
    )
    assert alternatives_offered, "System didn't offer payment alternatives"

    # Extract the action URL for alternative payment
    alt_payment_action = extract_gather_action(error_twiml)
    assert alt_payment_action is not None

    # Choose cash payment instead
    cash_payment_response = api_request.post(
        alt_payment_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "I'll pay with cash",
            "Confidence": "0.9",
        },
    )
    assert cash_payment_response.status == 200

    # Verify we can now proceed with the order
    final_twiml = cash_payment_response.text
    assert "<Response>" in final_twiml
    assert "cash" in final_twiml.lower()

    # Ensure the order can be finalized
    order_can_finalize = any(
        phrase in final_twiml.lower()
        for phrase in ["finalize", "place", "confirm", "complete"]
    )
    assert order_can_finalize, "System couldn't proceed after payment method change"


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
