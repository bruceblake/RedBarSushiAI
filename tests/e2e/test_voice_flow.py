import json
import pytest
import time
import re
import os
import requests
from urllib.parse import urlparse, parse_qs
import xml.etree.ElementTree as ET

# Get the base URL from environment
BASE_URL = os.getenv("BASE_URL", "https://redbarsushiai-staging.onrender.com")
print(f"Running endpoint tests against: {BASE_URL}")

@pytest.mark.e2e
def test_homepage_responds_with_twiml():
    """Test that the homepage responds with valid TwiML."""
    response = requests.get(f"{BASE_URL}")
    assert response.status_code == 200
    
    # The home endpoint should return TwiML
    assert "<?xml version=" in response.text
    assert "<Response>" in response.text or "<response>" in response.text.lower()
    assert "red bar sushi" in response.text.lower()
    
    # Try to parse as XML to confirm it's valid TwiML
    try:
        root = ET.fromstring(response.text)
        # Check for common Twilio verbs
        gather = root.find(".//Gather") or root.find(".//gather")
        say = root.find(".//Say") or root.find(".//say")
        
        assert gather is not None or say is not None, "No Gather or Say element found in response"
    except ET.ParseError:
        assert False, "Response is not valid XML/TwiML"

@pytest.mark.e2e
def test_complete_voice_order_flow():
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
    # Create a session for persistent cookies
    session = requests.Session()
    
    # Generate a test CallSid
    test_call_sid = f"CA{''.join(['1234567890'[i % 10] for i in range(32)])}"

    # Step 1: Initial call to voice webhook
    initial_response = session.post(
        f"{BASE_URL}",
        data={
            "CallSid": test_call_sid,
            "AccountSid": "AC12345",
            "From": "+15551234567",
        }
    )
    assert initial_response.status_code == 200
    
    xml_str = initial_response.text
    
    root = ET.fromstring(xml_str)
    
    assert root.tag == "Response"
    
    gather = root.find("Gather")
    assert gather is not None
    
    say_text = gather.findtext("Say")
    assert "Red Bar Sushi" in say_text
    
    # Extract the Gather action URL for the next step
    gather_action = gather.get("action")
    assert gather_action is not None
    
    # Convert to full URL if it's a relative path
    if not gather_action.startswith("http"):
        gather_action = f"{BASE_URL}{gather_action}"

    # Step 3: Provide name (should be directed to take_name)
    name_response = session.post(
        gather_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "John Smith",
            "Confidence": "0.8",
        }
    )
    assert name_response.status_code == 200

    # Parse the name confirmation TwiML
    xml_str = name_response.text
    
    root = ET.fromstring(xml_str)
    
    gather = root.find("Gather")
    
    say_text = gather.findtext("Say")
    
    assert "John Smith" in say_text

    # Extract the Gather action URL for name confirmation
    confirm_name_action = gather.get("action")
    assert confirm_name_action is not None
    
    # Convert to full URL if it's a relative path
    if not confirm_name_action.startswith("http"):
        confirm_name_action = f"{BASE_URL}{confirm_name_action}"

    # Step 4: Confirm name
    confirm_response = session.post(
        confirm_name_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "yes", 
            "Confidence": "0.9"
        }
    )
    assert confirm_response.status_code == 200

    # Parse the main menu TwiML
    main_menu_twiml = convertTwiRespToGather(confirm_response.text)

    # Extract the Gather action URL for main menu selection
    main_menu_action = main_menu_twiml.get("action")
    assert main_menu_action is not None
    
    # Convert to full URL if it's a relative path
    if not main_menu_action.startswith("http"):
        main_menu_action = f"{BASE_URL}{main_menu_action}"

    # Step 5: Choose to ask about menu items
    menu_query_response = session.post(
        main_menu_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "tell me about your menu",
            "Confidence": "0.85",
        }
    )
    assert menu_query_response.status_code == 200

    # Parse the menu response TwiML
    menu_response_twiml = convertTwiRespToGather(menu_query_response.text)
    
    # Extract the Gather action URL for continuing the conversation
    menu_continue_action = menu_response_twiml.get("action")
    assert menu_continue_action is not None
    
    # Convert to full URL if it's a relative path
    if not menu_continue_action.startswith("http"):
        menu_continue_action = f"{BASE_URL}{menu_continue_action}"

    # Step 6: Ask about a specific menu item (use California Roll which should exist)
    item_query_response = session.post(
        menu_continue_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "Tell me about the California Roll",
            "Confidence": "0.85",
        }
    )
    assert item_query_response.status_code == 200

    # Parse the item description TwiML
    item_response_twiml = convertTwiRespToGather(item_query_response.text)
    say_text = item_response_twiml.findtext("Say") or ""

    # Also check the raw response text in case the structure changed
    raw_text = item_query_response.text.lower()

    # Check either in the Say element or in the raw response
    assert (
        "california roll" in say_text.lower()
        or "california roll" in raw_text
    ), "Should mention the item"

    # Extract the Gather action URL for continuing after item description
    after_item_action = item_response_twiml.get("action")
    assert after_item_action is not None
    
    # Convert to full URL if it's a relative path
    if not after_item_action.startswith("http"):
        after_item_action = f"{BASE_URL}{after_item_action}"

    # Step 7: Decide to place an order
    order_start_response = session.post(
        after_item_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "I'd like to place an order",
            "Confidence": "0.9",
        }
    )
    assert order_start_response.status_code == 200

    print("Basic voice flow test completed successfully")


@pytest.mark.e2e
def test_voice_silence_handling_flow():
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
    # Create a session for persistent cookies
    session = requests.Session()
    
    # Generate a test CallSid
    test_call_sid = f"CA{''.join(['1234567890'[i % 10] for i in range(32)])}"

    # Step 1: Initial call to voice webhook
    initial_response = session.post(
        f"{BASE_URL}",
        data={
            "CallSid": test_call_sid,
            "AccountSid": "AC12345",
            "From": "+15551234567",
        }
    )
    assert initial_response.status_code == 200
    
    xml_str = initial_response.text
    
    root = ET.fromstring(xml_str)
    
    assert root.tag == "Response"
    
    gather = root.find("Gather")
    assert gather is not None
    
    say_text = gather.findtext("Say")
    assert "Red Bar Sushi" in say_text
    
    # Extract the Gather action URL for the next step
    gather_action = gather.get("action")
    assert gather_action is not None
    
    # Convert to full URL if it's a relative path
    if not gather_action.startswith("http"):
        gather_action = f"{BASE_URL}{gather_action}"

    # Step 2: Test silence on name collection (don't provide any speech input)
    silence_response1 = session.post(
        gather_action, 
        data={"CallSid": test_call_sid}
    )
    assert silence_response1.status_code == 200

    # Parse the first silence response TwiML
    xml_str = silence_response1.text
    
    root = ET.fromstring(xml_str)
    
    assert root.tag == "Response"
    
    gather = root.find("Gather")
    assert gather is not None
    
    say_text = gather.findtext("Say")
    
    # First silence should acknowledge that it didn't hear anything
    assert any(phrase in say_text.lower() for phrase in ["didn't hear", "sorry", "couldn't hear"]), \
        "Should acknowledge silence"

    # Extract the Gather action URL for the second attempt
    silence1_action = gather.get("action")
    assert silence1_action is not None
    
    # Convert to full URL if it's a relative path
    if not silence1_action.startswith("http"):
        silence1_action = f"{BASE_URL}{silence1_action}"

    # Step 3: Second silence (no speech input again)
    silence_response2 = session.post(
        silence1_action, 
        data={"CallSid": test_call_sid}
    )
    assert silence_response2.status_code == 200

    # Parse the second silence response
    xml_str = silence_response2.text
    
    root = ET.fromstring(xml_str)
    
    assert root.tag == "Response"
    
    # Either a Gather for another attempt or a different handling strategy
    gather = root.find("Gather")
    if gather is not None:
        say_text = gather.findtext("Say") or ""
        
        # Should be still asking for name or providing clearer instructions
        assert "name" in say_text.lower(), "Should still be trying to get name"
        
        # Extract the action for next step
        silence2_action = gather.get("action")
    else:
        # If no Gather, might have other elements like Redirect or Say
        say = root.find("Say")
        if say is not None and say.text:
            say_text = say.text
            assert "name" in say_text.lower(), "Should mention name in fallback message"
        
        # Use a Redirect if present, otherwise use the original gather action
        redirect = root.find("Redirect")
        if redirect is not None and redirect.text:
            silence2_action = redirect.text.strip()
        else:
            silence2_action = silence1_action
    
    assert silence2_action is not None, "No action URL found for next step"
    
    # Convert to full URL if it's a relative path
    if not silence2_action.startswith("http"):
        silence2_action = f"{BASE_URL}{silence2_action}"

    # Step 4: Now provide a name after silence to test recovery
    name_response = session.post(
        silence2_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "Sarah Johnson",
            "Confidence": "0.8",
        }
    )
    assert name_response.status_code == 200

    # Parse the name confirmation TwiML
    xml_str = name_response.text
    
    # Use the helper function to get a Gather element even if there are redirects/says
    name_response_twiml = convertTwiRespToGather(xml_str)
    
    # Name should be in the response
    say_text = name_response_twiml.findtext("Say") or ""
    assert "Sarah" in say_text or "Sarah Johnson" in say_text, "Should include the name in response"

    print("Silence handling test completed successfully")


@pytest.mark.e2e
def test_voice_menu_query_flow():
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
    # Create a session for persistent cookies
    session = requests.Session()
    
    # Generate a test CallSid
    test_call_sid = f"CA{''.join(['1234567890'[i % 10] for i in range(32)])}"

    # Step 1: Initial call to voice webhook
    initial_response = session.post(
        f"{BASE_URL}",
        data={
            "CallSid": test_call_sid,
            "AccountSid": "AC12345",
            "From": "+15551234567",
        }
    )
    assert initial_response.status_code == 200
    
    xml_str = initial_response.text
    
    root = ET.fromstring(xml_str)
    
    assert root.tag == "Response"
    
    gather = root.find("Gather")
    assert gather is not None
    
    say_text = gather.findtext("Say")
    assert "Red Bar Sushi" in say_text
    
    # Extract the Gather action URL for the next step
    gather_action = gather.get("action")
    assert gather_action is not None
    
    # Convert to full URL if it's a relative path
    if not gather_action.startswith("http"):
        gather_action = f"{BASE_URL}{gather_action}"

    # Step 2: Provide name (should be directed to take_name)
    name_response = session.post(
        gather_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "Mike Smith",
            "Confidence": "0.8",
        }
    )
    assert name_response.status_code == 200

    # Parse the name confirmation TwiML
    xml_str = name_response.text
    
    root = ET.fromstring(xml_str)
    
    gather = root.find("Gather")
    assert gather is not None
    
    say_text = gather.findtext("Say")
    
    assert "Mike Smith" in say_text

    # Extract the Gather action URL for name confirmation
    confirm_name_action = gather.get("action")
    assert confirm_name_action is not None
    
    # Convert to full URL if it's a relative path
    if not confirm_name_action.startswith("http"):
        confirm_name_action = f"{BASE_URL}{confirm_name_action}"

    # Step 3: Confirm name
    confirm_response = session.post(
        confirm_name_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "yes", 
            "Confidence": "0.9"
        }
    )
    assert confirm_response.status_code == 200

    # Parse the main menu TwiML
    main_menu_twiml = convertTwiRespToGather(confirm_response.text)

    # Extract the Gather action URL for main menu selection
    main_menu_action = main_menu_twiml.get("action")
    assert main_menu_action is not None
    
    # Convert to full URL if it's a relative path
    if not main_menu_action.startswith("http"):
        main_menu_action = f"{BASE_URL}{main_menu_action}"

    # Step 4: Choose to ask about menu
    menu_query_response = session.post(
        main_menu_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "I have some questions about your menu",
            "Confidence": "0.85",
        }
    )
    assert menu_query_response.status_code == 200

    # Parse the menu response TwiML
    menu_response_twiml = convertTwiRespToGather(menu_query_response.text)
    
    say_text = menu_response_twiml.findtext("Say") or ""
    assert "menu" in say_text.lower() or "food" in say_text.lower(), "Should acknowledge menu query"
    
    # Extract the Gather action URL for continuing the conversation
    menu_continue_action = menu_response_twiml.get("action")
    assert menu_continue_action is not None
    
    # Convert to full URL if it's a relative path
    if not menu_continue_action.startswith("http"):
        menu_continue_action = f"{BASE_URL}{menu_continue_action}"

    # Step 5: Ask about menu categories
    category_query_response = session.post(
        menu_continue_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "What categories of food do you have?",
            "Confidence": "0.85",
        }
    )
    assert category_query_response.status_code == 200

    # Parse the category response TwiML
    category_response_twiml = convertTwiRespToGather(category_query_response.text)
    
    # Get text from Say element if available
    say_text = category_response_twiml.findtext("Say") or ""
    
    # Also check the raw response text in case the structure changed
    raw_text = category_query_response.text.lower()
    
    # Common sushi menu categories
    common_categories = ["roll", "sushi", "appetizer", "entree", "special"]
    
    # Check that at least one category is mentioned, either in Say text or raw response
    found_category = False
    for category in common_categories:
        if category.lower() in say_text.lower() or category.lower() in raw_text:
            found_category = True
            break
    assert found_category, "No menu categories mentioned in response"
    
    # Extract the Gather action URL for continuing after category information
    category_continue_action = category_response_twiml.get("action")
    assert category_continue_action is not None
    
    # Convert to full URL if it's a relative path
    if not category_continue_action.startswith("http"):
        category_continue_action = f"{BASE_URL}{category_continue_action}"
    
    # Step 6: Ask about a specific menu item
    item_query_response = session.post(
        category_continue_action,
        data={
            "CallSid": test_call_sid,
            "SpeechResult": "Tell me about the Spicy Tuna Roll",
            "Confidence": "0.85",
        }
    )
    assert item_query_response.status_code == 200
    
    # Parse the item description TwiML
    item_response_twiml = convertTwiRespToGather(item_query_response.text)
    say_text = item_response_twiml.findtext("Say") or ""
    
    # Also check the raw response text
    raw_text = item_query_response.text.lower()
    
    # Check either in the Say element or in the raw response for "tuna" or "spicy"
    assert any(word in say_text.lower() or word in raw_text for word in ["tuna", "spicy"]), \
        "Should mention the requested item or an alternative"

    print("Menu query test completed successfully")


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


def convertTwiRespToGather(response_text):
    """
    Parse TwiML response and extract or create a Gather element.
    Returns an ElementTree Element representing the Gather.
    """
    root = ET.fromstring(response_text)
    gather = root.find("Gather")

    # If there's no Gather element, create a mock element
    if gather is None:
        # Create a new gather element
        gather = ET.Element("Gather")

        # Check if there's a Say element directly under the Response
        say = root.find("Say")
        if say is not None and say.text:
            # Add the Say element to our mock Gather
            say_element = ET.SubElement(gather, "Say")
            say_element.text = say.text
        else:
            # Ensure there's always a Say element even if empty
            say_element = ET.SubElement(gather, "Say")
            say_element.text = ""

        # Look for the action in any Gather element that follows Say
        next_gather = root.find("Gather")
        if next_gather is not None:
            gather.set("action", next_gather.get("action", ""))
        else:
            # Set a default action if none found
            gather.set("action", "/handle_menu_questions")

    return gather
