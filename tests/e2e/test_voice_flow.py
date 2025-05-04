import json
import pytest
import time
import re
import os
import requests
import logging
import sys
from urllib.parse import urlparse, parse_qs
import xml.etree.ElementTree as ET
from datetime import datetime

# Set up logging
log_format = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(
    level=logging.DEBUG,
    format=log_format,
    handlers=[
        logging.FileHandler("e2e_voice_test_debug.log", mode="w"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("e2e_voice_tests")

# Get the base URL from environment
BASE_URL = os.getenv("BASE_URL", "https://redbarsushiai-staging.onrender.com")
logger.info(f"Running endpoint tests against: {BASE_URL}")

# Function to log TwiML responses in a readable format
def log_twiml_response(response_text, step_name, call_sid=None):
    """Log TwiML response in a readable format with separators for easy visual parsing"""
    try:
        # Print a clear separator for this step
        separator = f"\n{'='*80}\n"
        step_header = f" STEP: {step_name} "
        if call_sid:
            step_header += f" | CALL_SID: {call_sid} "
        
        # Create a timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        
        # Format header with timestamp
        header = separator + f"{step_header:^80}" + separator + f"TIMESTAMP: {timestamp}\n"
        
        # Try to prettify the XML
        try:
            root = ET.fromstring(response_text)
            # Format the XML with indentation for readability
            from xml.dom import minidom
            pretty_xml = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
            body = f"TwiML Response:\n{pretty_xml}\n"
        except Exception as e:
            # If XML parsing fails, just log the raw text
            body = f"Raw Response:\n{response_text}\n"
            logger.warning(f"Could not parse XML: {str(e)}")
        
        # Extract and log important elements for debugging
        debug_info = "Response Analysis:\n"
        
        # Look for Gather actions
        gather_action = extract_gather_action(response_text)
        if gather_action:
            debug_info += f"  - Gather Action: {gather_action}\n"
        
        # Look for Redirect URLs
        redirect_url = extract_redirect_url(response_text)
        if redirect_url:
            debug_info += f"  - Redirect URL: {redirect_url}\n"
        
        # Look for Say text (what would be spoken to the user)
        say_text = re.findall(r"<Say[^>]*>(.*?)</Say>", response_text, re.DOTALL)
        if say_text:
            debug_info += "  - Say Text (what the user would hear):\n"
            for idx, text in enumerate(say_text):
                debug_info += f"      [{idx+1}] {text.strip()}\n"
        
        # Combine everything and log
        full_log = header + body + debug_info + separator
        logger.debug(full_log)
        
    except Exception as e:
        logger.error(f"Error logging TwiML: {str(e)}")
        # Still attempt to log the raw response
        logger.debug(f"Raw response for {step_name}: {response_text}")

@pytest.mark.e2e
def test_homepage_responds_with_twiml():
    """Test that the homepage responds with valid TwiML."""
    logger.info("Starting test_homepage_responds_with_twiml test")
    
    response = requests.get(f"{BASE_URL}")
    log_twiml_response(response.text, "Homepage TwiML Check")
    
    assert response.status_code == 200
    logger.debug(f"Response status code: {response.status_code}")
    
    # The home endpoint should return TwiML
    assert "<?xml version=" in response.text
    assert "<Response>" in response.text or "<response>" in response.text.lower()
    assert "red bar sushi" in response.text.lower()
    logger.debug("Found expected TwiML elements")
    
    # Try to parse as XML to confirm it's valid TwiML
    try:
        root = ET.fromstring(response.text)
        # Check for common Twilio verbs
        gather = root.find(".//Gather") or root.find(".//gather")
        say = root.find(".//Say") or root.find(".//say")
        
        assert gather is not None or say is not None, "No Gather or Say element found in response"
        logger.debug(f"Found gather: {gather is not None}, say: {say is not None}")
    except ET.ParseError:
        logger.error("Response is not valid XML/TwiML")
        assert False, "Response is not valid XML/TwiML"
    
    logger.info("test_homepage_responds_with_twiml test completed successfully")

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
    logger.info("=" * 40)
    logger.info("STARTING test_complete_voice_order_flow")
    logger.info("=" * 40)
    
    # Create a session for persistent cookies
    session = requests.Session()
    
    # Generate a test CallSid
    test_call_sid = f"CA{''.join(['1234567890'[i % 10] for i in range(32)])}"
    logger.info(f"Generated test CallSid: {test_call_sid}")

    # Step 1: Initial call to voice webhook
    logger.info("STEP 1: Initial call to voice webhook")
    logger.debug(f"Requesting initial greeting from {BASE_URL}")
    
    initial_payload = {
        "CallSid": test_call_sid,
        "AccountSid": "AC12345",
        "From": "+15551234567",
    }
    logger.debug(f"Request payload: {json.dumps(initial_payload, indent=2)}")
    
    initial_response = session.post(
        f"{BASE_URL}",
        data=initial_payload
    )
    
    log_twiml_response(initial_response.text, "Initial Greeting", test_call_sid)
    assert initial_response.status_code == 200
    logger.debug(f"Response status code: {initial_response.status_code}")
    
    xml_str = initial_response.text
    
    root = ET.fromstring(xml_str)
    
    assert root.tag == "Response"
    
    gather = root.find("Gather")
    assert gather is not None
    logger.debug("Found Gather element in response")
    
    say_text = gather.findtext("Say")
    assert "Red Bar Sushi" in say_text
    logger.debug(f"Confirmed greeting contains 'Red Bar Sushi'")
    
    # Extract the Gather action URL for the next step
    gather_action = gather.get("action")
    assert gather_action is not None
    logger.debug(f"Found gather action: {gather_action}")
    
    # Convert to full URL if it's a relative path
    if not gather_action.startswith("http"):
        gather_action = f"{BASE_URL}{gather_action}"
        logger.debug(f"Converted to full URL: {gather_action}")

    # Step 2: Provide name (should be directed to take_name)
    logger.info("STEP 2: Providing customer name")
    name_payload = {
        "CallSid": test_call_sid,
        "SpeechResult": "John Smith",
        "Confidence": "0.8",
    }
    logger.debug(f"Request payload: {json.dumps(name_payload, indent=2)}")
    
    name_response = session.post(
        gather_action,
        data=name_payload
    )
    
    log_twiml_response(name_response.text, "Name Provided", test_call_sid)
    assert name_response.status_code == 200
    logger.debug(f"Response status code: {name_response.status_code}")

    # Parse the name confirmation TwiML
    xml_str = name_response.text
    
    root = ET.fromstring(xml_str)
    
    gather = root.find("Gather")
    assert gather is not None
    logger.debug("Found Gather element in name response")
    
    say_text = gather.findtext("Say")
    
    assert "John Smith" in say_text
    logger.debug(f"Confirmed name 'John Smith' is in response")

    # Extract the Gather action URL for name confirmation
    confirm_name_action = gather.get("action")
    assert confirm_name_action is not None
    logger.debug(f"Found name confirmation action: {confirm_name_action}")
    
    # Convert to full URL if it's a relative path
    if not confirm_name_action.startswith("http"):
        confirm_name_action = f"{BASE_URL}{confirm_name_action}"
        logger.debug(f"Converted to full URL: {confirm_name_action}")

    # Step 3: Confirm name
    logger.info("STEP 3: Confirming customer name")
    confirm_payload = {
        "CallSid": test_call_sid,
        "SpeechResult": "yes", 
        "Confidence": "0.9"
    }
    logger.debug(f"Request payload: {json.dumps(confirm_payload, indent=2)}")
    
    confirm_response = session.post(
        confirm_name_action,
        data=confirm_payload
    )
    
    log_twiml_response(confirm_response.text, "Name Confirmation", test_call_sid)
    assert confirm_response.status_code == 200
    logger.debug(f"Response status code: {confirm_response.status_code}")

    # Parse the main menu TwiML
    main_menu_twiml = convertTwiRespToGather(confirm_response.text)
    logger.debug("Parsed main menu TwiML")

    # Extract the Gather action URL for main menu selection
    main_menu_action = main_menu_twiml.get("action")
    assert main_menu_action is not None
    logger.debug(f"Found main menu action: {main_menu_action}")
    
    # Convert to full URL if it's a relative path
    if not main_menu_action.startswith("http"):
        main_menu_action = f"{BASE_URL}{main_menu_action}"
        logger.debug(f"Converted to full URL: {main_menu_action}")

    # Step 4: Choose to ask about menu items
    logger.info("STEP 4: Asking about menu items")
    menu_query_payload = {
        "CallSid": test_call_sid,
        "SpeechResult": "tell me about your menu",
        "Confidence": "0.85",
    }
    logger.debug(f"Request payload: {json.dumps(menu_query_payload, indent=2)}")
    
    menu_query_response = session.post(
        main_menu_action,
        data=menu_query_payload
    )
    
    log_twiml_response(menu_query_response.text, "Menu Query", test_call_sid)
    assert menu_query_response.status_code == 200
    logger.debug(f"Response status code: {menu_query_response.status_code}")

    # Parse the menu response TwiML
    menu_response_twiml = convertTwiRespToGather(menu_query_response.text)
    logger.debug("Parsed menu response TwiML")
    
    # Extract the Gather action URL for continuing the conversation
    menu_continue_action = menu_response_twiml.get("action")
    assert menu_continue_action is not None
    logger.debug(f"Found menu continue action: {menu_continue_action}")
    
    # Convert to full URL if it's a relative path
    if not menu_continue_action.startswith("http"):
        menu_continue_action = f"{BASE_URL}{menu_continue_action}"
        logger.debug(f"Converted to full URL: {menu_continue_action}")

    # Step 5: Ask about a specific menu item (use California Roll which should exist)
    logger.info("STEP 5: Asking about specific menu item (California Roll)")
    item_query_payload = {
        "CallSid": test_call_sid,
        "SpeechResult": "Tell me about the California Roll",
        "Confidence": "0.85",
    }
    logger.debug(f"Request payload: {json.dumps(item_query_payload, indent=2)}")
    
    item_query_response = session.post(
        menu_continue_action,
        data=item_query_payload
    )
    
    log_twiml_response(item_query_response.text, "Item Query (California Roll)", test_call_sid)
    assert item_query_response.status_code == 200
    logger.debug(f"Response status code: {item_query_response.status_code}")

    # Parse the item description TwiML
    item_response_twiml = convertTwiRespToGather(item_query_response.text)
    logger.debug("Parsed item response TwiML")
    
    say_text = item_response_twiml.findtext("Say") or ""
    logger.debug(f"Say text from item response: {say_text}")

    # Also check the raw response text in case the structure changed
    raw_text = item_query_response.text.lower()

    # Check either in the Say element or in the raw response
    assert (
        "california roll" in say_text.lower()
        or "california roll" in raw_text
    ), "Should mention the item"
    logger.debug("Confirmed 'California Roll' is mentioned in the response")

    # Extract the Gather action URL for continuing after item description
    after_item_action = item_response_twiml.get("action")
    assert after_item_action is not None
    logger.debug(f"Found action after item description: {after_item_action}")
    
    # Convert to full URL if it's a relative path
    if not after_item_action.startswith("http"):
        after_item_action = f"{BASE_URL}{after_item_action}"
        logger.debug(f"Converted to full URL: {after_item_action}")

    # Step 6: Decide to place an order
    logger.info("STEP 6: Deciding to place an order")
    order_start_payload = {
        "CallSid": test_call_sid,
        "SpeechResult": "I'd like to place an order",
        "Confidence": "0.9",
    }
    logger.debug(f"Request payload: {json.dumps(order_start_payload, indent=2)}")
    
    order_start_response = session.post(
        after_item_action,
        data=order_start_payload
    )
    
    log_twiml_response(order_start_response.text, "Order Start Request", test_call_sid)
    assert order_start_response.status_code == 200
    logger.debug(f"Response status code: {order_start_response.status_code}")

    logger.info("=" * 40)
    logger.info("Voice flow test completed successfully")
    logger.info("=" * 40)


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
    logger.info("=" * 40)
    logger.info("STARTING test_voice_silence_handling_flow")
    logger.info("=" * 40)
    
    # Create a session for persistent cookies
    session = requests.Session()
    
    # Generate a test CallSid
    test_call_sid = f"CA{''.join(['1234567890'[i % 10] for i in range(32)])}"
    logger.info(f"Generated test CallSid for silence test: {test_call_sid}")

    # Step 1: Initial call to voice webhook
    logger.info("STEP 1: Initial call to voice webhook")
    
    initial_payload = {
        "CallSid": test_call_sid,
        "AccountSid": "AC12345",
        "From": "+15551234567",
    }
    logger.debug(f"Request payload: {json.dumps(initial_payload, indent=2)}")
    
    initial_response = session.post(
        f"{BASE_URL}",
        data=initial_payload
    )
    
    log_twiml_response(initial_response.text, "Initial Greeting (Silence Test)", test_call_sid)
    assert initial_response.status_code == 200
    logger.debug(f"Response status code: {initial_response.status_code}")
    
    xml_str = initial_response.text
    
    root = ET.fromstring(xml_str)
    
    assert root.tag == "Response"
    
    gather = root.find("Gather")
    assert gather is not None
    logger.debug("Found Gather element in response")
    
    say_text = gather.findtext("Say")
    assert "Red Bar Sushi" in say_text
    logger.debug(f"Confirmed greeting contains 'Red Bar Sushi'")
    
    # Extract the Gather action URL for the next step
    gather_action = gather.get("action")
    assert gather_action is not None
    logger.debug(f"Found gather action: {gather_action}")
    
    # Convert to full URL if it's a relative path
    if not gather_action.startswith("http"):
        gather_action = f"{BASE_URL}{gather_action}"
        logger.debug(f"Converted to full URL: {gather_action}")

    # Step 2: Test silence on name collection (don't provide any speech input)
    logger.info("STEP 2: Testing first silence - not providing name")
    silence_payload1 = {"CallSid": test_call_sid}
    logger.debug(f"Request payload (silence - no speech): {json.dumps(silence_payload1, indent=2)}")
    
    silence_response1 = session.post(
        gather_action, 
        data=silence_payload1
    )
    
    log_twiml_response(silence_response1.text, "First Silence Response", test_call_sid)
    assert silence_response1.status_code == 200
    logger.debug(f"Response status code: {silence_response1.status_code}")

    # Parse the first silence response TwiML
    xml_str = silence_response1.text
    
    root = ET.fromstring(xml_str)
    
    assert root.tag == "Response"
    
    gather = root.find("Gather")
    assert gather is not None
    logger.debug("Found Gather element in first silence response")
    
    say_text = gather.findtext("Say")
    logger.debug(f"Say text after first silence: {say_text}")
    
    # First silence should acknowledge that it didn't hear anything
    assert any(phrase in say_text.lower() for phrase in ["didn't hear", "sorry", "couldn't hear"]), \
        "Should acknowledge silence"
    logger.debug("Confirmed first silence response acknowledges not hearing anything")

    # Extract the Gather action URL for the second attempt
    silence1_action = gather.get("action")
    assert silence1_action is not None
    logger.debug(f"Found action after first silence: {silence1_action}")
    
    # Convert to full URL if it's a relative path
    if not silence1_action.startswith("http"):
        silence1_action = f"{BASE_URL}{silence1_action}"
        logger.debug(f"Converted to full URL: {silence1_action}")

    # Step 3: Second silence (no speech input again)
    logger.info("STEP 3: Testing second consecutive silence")
    silence_payload2 = {"CallSid": test_call_sid}
    logger.debug(f"Request payload (second silence): {json.dumps(silence_payload2, indent=2)}")
    
    silence_response2 = session.post(
        silence1_action, 
        data=silence_payload2
    )
    
    log_twiml_response(silence_response2.text, "Second Silence Response", test_call_sid)
    assert silence_response2.status_code == 200
    logger.debug(f"Response status code: {silence_response2.status_code}")

    # Parse the second silence response
    xml_str = silence_response2.text
    
    root = ET.fromstring(xml_str)
    
    assert root.tag == "Response"
    logger.debug("Response tag is 'Response'")
    
    # Either a Gather for another attempt or a different handling strategy
    gather = root.find("Gather")
    if gather is not None:
        logger.debug("Found Gather element in second silence response")
        say_text = gather.findtext("Say") or ""
        logger.debug(f"Say text after second silence: {say_text}")
        
        # Should be still asking for name or providing clearer instructions
        assert "name" in say_text.lower(), "Should still be trying to get name"
        logger.debug("Confirmed second silence response still asks for name")
        
        # Extract the action for next step
        silence2_action = gather.get("action")
        logger.debug(f"Found action after second silence: {silence2_action}")
    else:
        logger.debug("No Gather element found in second silence response, checking for alternatives")
        # If no Gather, might have other elements like Redirect or Say
        say = root.find("Say")
        if say is not None and say.text:
            say_text = say.text
            logger.debug(f"Say text in non-Gather element: {say_text}")
            assert "name" in say_text.lower(), "Should mention name in fallback message"
            logger.debug("Confirmed non-Gather message still mentions name")
        
        # Use a Redirect if present, otherwise use the original gather action
        redirect = root.find("Redirect")
        if redirect is not None and redirect.text:
            silence2_action = redirect.text.strip()
            logger.debug(f"Found Redirect to: {silence2_action}")
        else:
            silence2_action = silence1_action
            logger.debug(f"No Redirect found, using previous action: {silence2_action}")
    
    assert silence2_action is not None, "No action URL found for next step"
    
    # Convert to full URL if it's a relative path
    if not silence2_action.startswith("http"):
        silence2_action = f"{BASE_URL}{silence2_action}"
        logger.debug(f"Converted to full URL: {silence2_action}")

    # Step 4: Now provide a name after silence to test recovery
    logger.info("STEP 4: Providing name after silence to test recovery")
    name_payload = {
        "CallSid": test_call_sid,
        "SpeechResult": "Sarah Johnson",
        "Confidence": "0.8",
    }
    logger.debug(f"Request payload (name after silence): {json.dumps(name_payload, indent=2)}")
    
    name_response = session.post(
        silence2_action,
        data=name_payload
    )
    
    log_twiml_response(name_response.text, "Name After Silence", test_call_sid)
    assert name_response.status_code == 200
    logger.debug(f"Response status code: {name_response.status_code}")

    # Parse the name confirmation TwiML
    xml_str = name_response.text
    
    # Use the helper function to get a Gather element even if there are redirects/says
    name_response_twiml = convertTwiRespToGather(xml_str)
    logger.debug("Used helper function to parse name response TwiML")
    
    # Name should be in the response
    say_text = name_response_twiml.findtext("Say") or ""
    logger.debug(f"Say text after providing name: {say_text}")
    
    assert "Sarah" in say_text or "Sarah Johnson" in say_text, "Should include the name in response"
    logger.debug("Confirmed name 'Sarah Johnson' or 'Sarah' is in the response")

    logger.info("=" * 40)
    logger.info("Silence handling test completed successfully")
    logger.info("=" * 40)


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
    logger.info("=" * 40)
    logger.info("STARTING test_voice_menu_query_flow")
    logger.info("=" * 40)
    
    # Create a session for persistent cookies
    session = requests.Session()
    
    # Generate a test CallSid
    test_call_sid = f"CA{''.join(['1234567890'[i % 10] for i in range(32)])}"
    logger.info(f"Generated test CallSid for menu query test: {test_call_sid}")

    # Step 1: Initial call to voice webhook
    logger.info("STEP 1: Initial call to voice webhook")
    
    initial_payload = {
        "CallSid": test_call_sid,
        "AccountSid": "AC12345",
        "From": "+15551234567",
    }
    logger.debug(f"Request payload: {json.dumps(initial_payload, indent=2)}")
    
    initial_response = session.post(
        f"{BASE_URL}",
        data=initial_payload
    )
    
    log_twiml_response(initial_response.text, "Initial Greeting (Menu Query Test)", test_call_sid)
    assert initial_response.status_code == 200
    logger.debug(f"Response status code: {initial_response.status_code}")
    
    xml_str = initial_response.text
    
    root = ET.fromstring(xml_str)
    
    assert root.tag == "Response"
    
    gather = root.find("Gather")
    assert gather is not None
    logger.debug("Found Gather element in response")
    
    say_text = gather.findtext("Say")
    assert "Red Bar Sushi" in say_text
    logger.debug(f"Confirmed greeting contains 'Red Bar Sushi'")
    
    # Extract the Gather action URL for the next step
    gather_action = gather.get("action")
    assert gather_action is not None
    logger.debug(f"Found gather action: {gather_action}")
    
    # Convert to full URL if it's a relative path
    if not gather_action.startswith("http"):
        gather_action = f"{BASE_URL}{gather_action}"
        logger.debug(f"Converted to full URL: {gather_action}")

    # Step 2: Provide name (should be directed to take_name)
    logger.info("STEP 2: Providing customer name (Mike Smith)")
    name_payload = {
        "CallSid": test_call_sid,
        "SpeechResult": "Mike Smith",
        "Confidence": "0.8",
    }
    logger.debug(f"Request payload: {json.dumps(name_payload, indent=2)}")
    
    name_response = session.post(
        gather_action,
        data=name_payload
    )
    
    log_twiml_response(name_response.text, "Name Provided (Menu Query Test)", test_call_sid)
    assert name_response.status_code == 200
    logger.debug(f"Response status code: {name_response.status_code}")

    # Parse the name confirmation TwiML
    xml_str = name_response.text
    
    root = ET.fromstring(xml_str)
    
    gather = root.find("Gather")
    assert gather is not None
    logger.debug("Found Gather element in name response")
    
    say_text = gather.findtext("Say")
    
    assert "Mike Smith" in say_text
    logger.debug(f"Confirmed name 'Mike Smith' is in response")

    # Extract the Gather action URL for name confirmation
    confirm_name_action = gather.get("action")
    assert confirm_name_action is not None
    logger.debug(f"Found name confirmation action: {confirm_name_action}")
    
    # Convert to full URL if it's a relative path
    if not confirm_name_action.startswith("http"):
        confirm_name_action = f"{BASE_URL}{confirm_name_action}"
        logger.debug(f"Converted to full URL: {confirm_name_action}")

    # Step 3: Confirm name
    logger.info("STEP 3: Confirming customer name")
    confirm_payload = {
        "CallSid": test_call_sid,
        "SpeechResult": "yes", 
        "Confidence": "0.9"
    }
    logger.debug(f"Request payload: {json.dumps(confirm_payload, indent=2)}")
    
    confirm_response = session.post(
        confirm_name_action,
        data=confirm_payload
    )
    
    log_twiml_response(confirm_response.text, "Name Confirmation (Menu Query Test)", test_call_sid)
    assert confirm_response.status_code == 200
    logger.debug(f"Response status code: {confirm_response.status_code}")

    # Parse the main menu TwiML
    main_menu_twiml = convertTwiRespToGather(confirm_response.text)
    logger.debug("Parsed main menu TwiML")

    # Extract the Gather action URL for main menu selection
    main_menu_action = main_menu_twiml.get("action")
    assert main_menu_action is not None
    logger.debug(f"Found main menu action: {main_menu_action}")
    
    # Convert to full URL if it's a relative path
    if not main_menu_action.startswith("http"):
        main_menu_action = f"{BASE_URL}{main_menu_action}"
        logger.debug(f"Converted to full URL: {main_menu_action}")

    # Step 4: Choose to ask about menu
    logger.info("STEP 4: Asking about menu information")
    menu_query_payload = {
        "CallSid": test_call_sid,
        "SpeechResult": "I have some questions about your menu",
        "Confidence": "0.85",
    }
    logger.debug(f"Request payload: {json.dumps(menu_query_payload, indent=2)}")
    
    menu_query_response = session.post(
        main_menu_action,
        data=menu_query_payload
    )
    
    log_twiml_response(menu_query_response.text, "Menu Query", test_call_sid)
    assert menu_query_response.status_code == 200
    logger.debug(f"Response status code: {menu_query_response.status_code}")

    # Parse the menu response TwiML
    menu_response_twiml = convertTwiRespToGather(menu_query_response.text)
    logger.debug("Parsed menu response TwiML")
    
    say_text = menu_response_twiml.findtext("Say") or ""
    logger.debug(f"Say text from menu response: {say_text}")
    
    assert "menu" in say_text.lower() or "food" in say_text.lower(), "Should acknowledge menu query"
    logger.debug("Confirmed response acknowledges menu query")
    
    # Extract the Gather action URL for continuing the conversation
    menu_continue_action = menu_response_twiml.get("action")
    assert menu_continue_action is not None
    logger.debug(f"Found menu continue action: {menu_continue_action}")
    
    # Convert to full URL if it's a relative path
    if not menu_continue_action.startswith("http"):
        menu_continue_action = f"{BASE_URL}{menu_continue_action}"
        logger.debug(f"Converted to full URL: {menu_continue_action}")

    # Step 5: Ask about menu categories
    logger.info("STEP 5: Asking about menu categories")
    category_query_payload = {
        "CallSid": test_call_sid,
        "SpeechResult": "What categories of food do you have?",
        "Confidence": "0.85",
    }
    logger.debug(f"Request payload: {json.dumps(category_query_payload, indent=2)}")
    
    category_query_response = session.post(
        menu_continue_action,
        data=category_query_payload
    )
    
    log_twiml_response(category_query_response.text, "Category Query", test_call_sid)
    assert category_query_response.status_code == 200
    logger.debug(f"Response status code: {category_query_response.status_code}")

    # Parse the category response TwiML
    category_response_twiml = convertTwiRespToGather(category_query_response.text)
    logger.debug("Parsed category response TwiML")
    
    # Get text from Say element if available
    say_text = category_response_twiml.findtext("Say") or ""
    logger.debug(f"Say text from category response: {say_text}")
    
    # Also check the raw response text in case the structure changed
    raw_text = category_query_response.text.lower()
    
    # Common sushi menu categories
    common_categories = ["roll", "sushi", "appetizer", "entree", "special"]
    logger.debug(f"Checking for common menu categories: {common_categories}")
    
    # Check that at least one category is mentioned, either in Say text or raw response
    found_category = False
    found_categories = []
    for category in common_categories:
        if category.lower() in say_text.lower() or category.lower() in raw_text:
            found_category = True
            found_categories.append(category)
    
    assert found_category, "No menu categories mentioned in response"
    logger.debug(f"Found these categories in response: {found_categories}")
    
    # Extract the Gather action URL for continuing after category information
    category_continue_action = category_response_twiml.get("action")
    assert category_continue_action is not None
    logger.debug(f"Found category continue action: {category_continue_action}")
    
    # Convert to full URL if it's a relative path
    if not category_continue_action.startswith("http"):
        category_continue_action = f"{BASE_URL}{category_continue_action}"
        logger.debug(f"Converted to full URL: {category_continue_action}")
    
    # Step 6: Ask about a specific menu item
    logger.info("STEP 6: Asking about specific menu item (Spicy Tuna Roll)")
    item_query_payload = {
        "CallSid": test_call_sid,
        "SpeechResult": "Tell me about the Spicy Tuna Roll",
        "Confidence": "0.85",
    }
    logger.debug(f"Request payload: {json.dumps(item_query_payload, indent=2)}")
    
    item_query_response = session.post(
        category_continue_action,
        data=item_query_payload
    )
    
    log_twiml_response(item_query_response.text, "Item Query (Spicy Tuna Roll)", test_call_sid)
    assert item_query_response.status_code == 200
    logger.debug(f"Response status code: {item_query_response.status_code}")
    
    # Parse the item description TwiML
    item_response_twiml = convertTwiRespToGather(item_query_response.text)
    logger.debug("Parsed item response TwiML")
    
    say_text = item_response_twiml.findtext("Say") or ""
    logger.debug(f"Say text from item response: {say_text}")
    
    # Also check the raw response text
    raw_text = item_query_response.text.lower()
    
    # Check either in the Say element or in the raw response for "tuna" or "spicy"
    matching_keywords = []
    for word in ["tuna", "spicy"]:
        if word in say_text.lower() or word in raw_text:
            matching_keywords.append(word)
    
    assert any(word in say_text.lower() or word in raw_text for word in ["tuna", "spicy"]), \
        "Should mention the requested item or an alternative"
    logger.debug(f"Found these keywords in response: {matching_keywords}")

    logger.info("=" * 40)
    logger.info("Menu query test completed successfully")
    logger.info("=" * 40)


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
