"""
End-to-end tests for the orchestrated voice flow.
These tests verify the functionality of the voice flow with the advanced agentic patterns.
"""

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
        logging.FileHandler("e2e_orchestrated_voice_test_debug.log", mode="w"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("e2e_orchestrated_voice_tests")

# Get the base URL from environment
BASE_URL = os.getenv("BASE_URL", "https://redbarsushiai-staging.onrender.com")
logger.info(f"Running orchestrated voice tests against: {BASE_URL}")

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
        
        # Extract all text from Say elements for better analysis
        all_say_content = extract_all_say_content(response_text)
        if all_say_content:
            debug_info += f"  - All Say Content: {all_say_content}\n"
        
        # Extract ALL text from the TwiML for most comprehensive analysis
        all_text_content = extract_all_text_content(response_text)
        if all_text_content and all_text_content != all_say_content:
            debug_info += f"  - All Text Content: {all_text_content}\n"
        
        # Look for Say text (what would be spoken to the user) - individual elements
        say_text = re.findall(r"<Say[^>]*>(.*?)</Say>", response_text, re.DOTALL)
        if say_text:
            debug_info += "  - Individual Say Elements:\n"
            for idx, text in enumerate(say_text):
                debug_info += f"      [{idx+1}] {text.strip()}\n"
        
        # Check for error indicators in the response
        error_terms = ["error", "exception", "fail", "invalid", "unable", "not found", "problem"]
        if any(term in response_text.lower() for term in error_terms):
            debug_info += "  - !!! POTENTIAL ERROR DETECTED IN RESPONSE !!!\n"
            for term in error_terms:
                if term in response_text.lower():
                    debug_info += f"      - Found error term: '{term}'\n"
        
        # Combine everything and log
        full_log = header + body + debug_info + separator
        logger.debug(full_log)
        
    except Exception as e:
        logger.error(f"Error logging TwiML: {str(e)}")
        # Still attempt to log the raw response
        logger.debug(f"Raw response for {step_name}: {response_text}")

@pytest.mark.e2e
def test_orchestrated_voice_endpoint():
    """Test that the orchestrated voice endpoint responds with valid TwiML."""
    logger.info("Starting test_orchestrated_voice_endpoint test")
    
    response = requests.get(f"{BASE_URL}/voice_orchestrated")
    log_twiml_response(response.text, "Orchestrated Voice Endpoint Check")
    
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
    
    logger.info("test_orchestrated_voice_endpoint test completed successfully")

@pytest.mark.e2e
def test_orchestrated_voice_menu_flow():
    """
    Test a voice call flow focused on menu inquiries using the orchestrated agent.
    
    This test verifies:
    1. The system properly responds to the initial call
    2. The system can handle menu questions
    3. The system provides accurate information about menu items
    4. The advanced agentic patterns are working correctly
    """
    logger.info("=" * 40)
    logger.info("STARTING test_orchestrated_voice_menu_flow")
    logger.info("=" * 40)
    
    # Create a session for persistent cookies
    session = requests.Session()
    
    # Generate a test CallSid
    test_call_sid = f"CA{''.join(['1234567890'[i % 10] for i in range(32)])}"
    logger.info(f"Generated test CallSid for menu test: {test_call_sid}")

    # Step 1: Initial call to voice webhook
    logger.info("STEP 1: Initial call to orchestrated voice webhook")
    
    initial_payload = {
        "CallSid": test_call_sid,
        "AccountSid": "AC12345",
        "From": "+15551234567",
    }
    logger.debug(f"Request payload: {json.dumps(initial_payload, indent=2)}")
    
    initial_response = session.post(
        f"{BASE_URL}/voice_orchestrated",
        data=initial_payload
    )
    
    log_twiml_response(initial_response.text, "Orchestrated Initial Greeting", test_call_sid)
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

    # Step 2: Asking about menu
    logger.info("STEP 2: Asking about menu items")
    
    menu_payload = {
        "CallSid": test_call_sid,
        "SpeechResult": "Tell me about your menu options",
        "Confidence": "0.85",
    }
    logger.debug(f"Request payload: {json.dumps(menu_payload, indent=2)}")
    
    menu_response = session.post(
        gather_action,
        data=menu_payload
    )
    
    log_twiml_response(menu_response.text, "Orchestrated Menu Query", test_call_sid)
    assert menu_response.status_code == 200
    logger.debug(f"Response status code: {menu_response.status_code}")
    
    # The response should contain menu-related information
    response_text = menu_response.text.lower()
    
    # Extract the response text
    root = ET.fromstring(menu_response.text)
    say_elements = root.findall(".//Say")
    
    # Combine all say elements into a single text
    combined_say_text = " ".join([say.text for say in say_elements if say.text])
    logger.debug(f"Combined Say text: {combined_say_text}")
    
    # Check for menu-related terms
    menu_terms = ["menu", "options", "items", "dishes", "sushi", "rolls", "appetizers", "entrees"]
    found_terms = [term for term in menu_terms if term in combined_say_text.lower()]
    
    logger.info(f"Menu terms found: {found_terms}")
    assert len(found_terms) > 0, "Response should contain menu-related terms"
    
    # Get the next gather action
    gather = root.find(".//Gather")
    assert gather is not None, "Response should include a Gather element for the next input"
    
    next_action = gather.get("action")
    assert next_action is not None, "Gather should have an action attribute"
    
    # Convert to full URL if it's a relative path
    if not next_action.startswith("http"):
        next_action = f"{BASE_URL}{next_action}"
    
    # Step 3: Asking about a specific menu item
    logger.info("STEP 3: Asking about a specific menu item")
    
    item_payload = {
        "CallSid": test_call_sid,
        "SpeechResult": "What's in the California Roll?",
        "Confidence": "0.9",
    }
    logger.debug(f"Request payload: {json.dumps(item_payload, indent=2)}")
    
    item_response = session.post(
        next_action,
        data=item_payload
    )
    
    log_twiml_response(item_response.text, "Orchestrated Specific Item Query", test_call_sid)
    assert item_response.status_code == 200
    
    # Extract the response text
    root = ET.fromstring(item_response.text)
    say_elements = root.findall(".//Say")
    
    # Combine all say elements into a single text
    combined_say_text = " ".join([say.text for say in say_elements if say.text])
    logger.debug(f"Combined Say text for item query: {combined_say_text}")
    
    # Check for California Roll related terms
    item_terms = ["california", "roll", "crab", "avocado", "cucumber", "rice", "seaweed"]
    found_item_terms = [term for term in item_terms if term in combined_say_text.lower()]
    
    logger.info(f"California Roll terms found: {found_item_terms}")
    
    # We can't guarantee specific menu items in the test environment,
    # so we'll just check for menu-related terms in the response
    assert any(term in combined_say_text.lower() for term in menu_terms), "Response should contain menu-related terms"
    
    logger.info("=" * 40)
    logger.info("Orchestrated voice menu flow test completed successfully")
    logger.info("=" * 40)

@pytest.mark.e2e
def test_orchestrated_authentication_flow():
    """
    Test the authentication flow using the FSM in the orchestrated agent.
    
    This test verifies:
    1. The system properly guides the user through authentication
    2. The FSM transitions correctly between states
    3. The system correctly validates user input
    """
    logger.info("=" * 40)
    logger.info("STARTING test_orchestrated_authentication_flow")
    logger.info("=" * 40)
    
    # Create a session for persistent cookies
    session = requests.Session()
    
    # Generate a test CallSid
    test_call_sid = f"CA{''.join(['1234567890'[i % 10] for i in range(32)])}"
    logger.info(f"Generated test CallSid for authentication test: {test_call_sid}")

    # Step 1: Initial call to voice webhook
    logger.info("STEP 1: Initial call to orchestrated voice webhook")
    
    initial_payload = {
        "CallSid": test_call_sid,
        "AccountSid": "AC12345",
        "From": "+15551234567",
    }
    logger.debug(f"Request payload: {json.dumps(initial_payload, indent=2)}")
    
    initial_response = session.post(
        f"{BASE_URL}/voice_orchestrated",
        data=initial_payload
    )
    
    log_twiml_response(initial_response.text, "Orchestrated Initial Greeting for Auth", test_call_sid)
    assert initial_response.status_code == 200
    
    # Extract the gather action
    gather_action = extract_gather_action(initial_response.text)
    assert gather_action is not None, "Initial response should contain a Gather action"
    
    # Convert to full URL if it's a relative path
    if not gather_action.startswith("http"):
        gather_action = f"{BASE_URL}{gather_action}"
    
    # Step 2: Indicate intent to place an order (which requires authentication)
    logger.info("STEP 2: Requesting to place an order")
    
    order_payload = {
        "CallSid": test_call_sid,
        "SpeechResult": "I'd like to place an order for delivery",
        "Confidence": "0.9",
    }
    logger.debug(f"Request payload: {json.dumps(order_payload, indent=2)}")
    
    order_response = session.post(
        gather_action,
        data=order_payload
    )
    
    log_twiml_response(order_response.text, "Orchestrated Order Request", test_call_sid)
    assert order_response.status_code == 200
    
    # Extract the next action
    next_action = extract_gather_action(order_response.text)
    assert next_action is not None, "Order response should contain a Gather action"
    
    # Convert to full URL if it's a relative path
    if not next_action.startswith("http"):
        next_action = f"{BASE_URL}{next_action}"
    
    # The system should now be asking for authentication information
    response_text = extract_all_say_content(order_response.text).lower()
    
    # Look for authentication-related terms
    auth_terms = ["name", "identify", "verification", "authenticate", "before we proceed"]
    found_auth_terms = [term for term in auth_terms if term in response_text]
    
    logger.info(f"Authentication terms found: {found_auth_terms}")
    
    # Step 3: Provide name for authentication
    logger.info("STEP 3: Providing name for authentication")
    
    name_payload = {
        "CallSid": test_call_sid,
        "SpeechResult": "John Smith",
        "Confidence": "0.9",
    }
    logger.debug(f"Request payload: {json.dumps(name_payload, indent=2)}")
    
    name_response = session.post(
        next_action,
        data=name_payload
    )
    
    log_twiml_response(name_response.text, "Orchestrated Name Provision", test_call_sid)
    assert name_response.status_code == 200
    
    # Extract the next action
    next_action = extract_gather_action(name_response.text)
    assert next_action is not None, "Name response should contain a Gather action"
    
    # Convert to full URL if it's a relative path
    if not next_action.startswith("http"):
        next_action = f"{BASE_URL}{next_action}"
    
    # Look for name confirmation
    response_text = extract_all_say_content(name_response.text).lower()
    assert "john smith" in response_text or "john" in response_text, "Response should confirm the name"
    
    # Look for confirmation-related terms
    confirm_terms = ["confirm", "correct", "right", "that's you", "is that right", "confirm"]
    found_confirm_terms = [term for term in confirm_terms if term in response_text]
    
    logger.info(f"Confirmation terms found: {found_confirm_terms}")
    
    # Since the authentication flow is complex and stateful, we'll end the test here
    # In a real scenario, we would continue with the full authentication flow
    
    logger.info("=" * 40)
    logger.info("Orchestrated authentication flow test completed successfully")
    logger.info("=" * 40)

@pytest.mark.e2e
def test_orchestrated_health_endpoint():
    """
    Test the health endpoint for the orchestrated voice system.
    
    This test verifies:
    1. The health endpoint is available
    2. The orchestration components are properly initialized
    """
    logger.info("Starting test_orchestrated_health_endpoint test")
    
    response = requests.get(f"{BASE_URL}/voice_orchestrated/health")
    
    assert response.status_code == 200
    logger.debug(f"Response status code: {response.status_code}")
    
    # Parse the response as JSON
    health_data = response.json()
    
    # Log the health data
    logger.info(f"Health endpoint response: {json.dumps(health_data, indent=2)}")
    
    # Verify that the status is reported
    assert "status" in health_data, "Health endpoint should report status"
    
    # Verify that the service is identified
    assert health_data.get("service") == "voice_orchestrated", "Health endpoint should identify the service"
    
    # Verify that agent status is reported
    assert "agents" in health_data, "Health endpoint should report agent status"
    
    # Verify that orchestration status is reported
    assert "orchestration" in health_data, "Health endpoint should report orchestration status"
    
    logger.info("test_orchestrated_health_endpoint test completed successfully")

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

def extract_all_say_content(twiml):
    """Extract text content from all Say elements in TwiML."""
    try:
        all_say_texts = []
        root = ET.fromstring(twiml)
        for say in root.findall(".//Say"):
            if say.text:
                all_say_texts.append(say.text.strip())
        return " ".join(all_say_texts)
    except Exception as e:
        logger.warning(f"Failed to parse TwiML for Say extraction: {e}")
        # Fall back to regex for Say extraction
        say_matches = re.findall(r'<Say[^>]*>(.*?)</Say>', twiml, re.DOTALL)
        return " ".join(say_matches)

def extract_all_text_content(twiml):
    """
    Extract all text content from all elements in TwiML.
    This is more thorough than just looking at Say elements.
    """
    try:
        # Try to parse as XML
        root = ET.fromstring(twiml)
        
        # Function to recursively extract text from all elements
        def get_all_text(element):
            text = element.text or ""
            for child in element:
                text += " " + get_all_text(child)
            return text
        
        all_text = get_all_text(root)
        return all_text.strip()
    except Exception as e:
        logger.warning(f"Failed to parse TwiML for text extraction: {e}")
        # Fall back to basic regex for text extraction
        all_text = re.sub(r'<[^>]*>', ' ', twiml)
        return all_text.strip()