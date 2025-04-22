"""
Voice call flow module. This module contains main call flow routes 
for receiving calls, taking names, confirming names, and presenting the main menu.
"""

import logging
import json
import time
from flask import request, session, Response
from twilio.twiml.voice_response import VoiceResponse

# Import blueprint
from . import voice_bp

# Import helpers
from .voice_core import (
    setup_gather_params, 
    get_adaptive_timeouts, 
    handle_silence
)

# Import agent utilities
from app.utils.agent_utils import OrderParsingAgent

# Set up logger
logger = logging.getLogger(__name__)

def extract_name_with_agent(input_text):
    """
    Extract a name from user input using the OrderParsingAgent.
    
    Handles various ways users might state their name, including:
    - "My name is John"
    - "This is John"
    - "John speaking"
    - Just "John"
    
    Args:
        input_text: User's spoken response
        
    Returns:
        str: Extracted name, or empty string if no name found
    """
    if not input_text:
        return ""
    
    logger.info(f"Extracting name from: {input_text}")
    
    # Direct extraction for simple cases first for efficiency
    if input_text.lower().startswith("my name is "):
        return input_text[11:].strip()
    
    if input_text.lower().startswith("this is "):
        return input_text[8:].strip()
    
    if input_text.lower().startswith("i am ") or input_text.lower().startswith("i'm "):
        name_part = input_text[5:] if input_text.lower().startswith("i am ") else input_text[4:]
        return name_part.strip()
    
    # For simple statements with just the name
    if len(input_text.split()) <= 2:
        # Likely just stating their name directly
        return input_text.strip()
    
    # Use AI to extract more complex name situations
    try:
        agent = OrderParsingAgent()
        result = agent.extract_name(input_text)
        
        if result and "name" in result and result["name"]:
            logger.info(f"Successfully extracted name with AI agent: {result['name']}")
            return result["name"]
    except Exception as e:
        logger.error(f"Error extracting name with agent: {str(e)}")
        # Fall back to basic extraction if AI fails
        
    # For anything else, just return the input as the name
    # (assuming they just stated their name directly)
    return input_text.strip()

@voice_bp.route("/", methods=["POST"])
def receive_call():
    """
    Entry point for the voice application. Handles incoming calls.
    
    This route:
    1. Sets up a new session
    2. Greets the caller
    3. Asks for their name
    4. Redirects to the name collection route
    """
    # Initialize the TwiML response
    response = VoiceResponse()
    
    # Get call details from Twilio
    caller_phone = request.form.get("From", "")
    call_sid = request.form.get("CallSid", "")
    call_status = request.form.get("CallStatus", "")
    
    # Log call details
    logger.info(f"New call received: {call_sid} from {caller_phone}, status: {call_status}")
    
    # Store caller data in session
    session["call_sid"] = call_sid
    session["sender"] = caller_phone
    session["call_start_time"] = time.time()
    session.permanent = True
    
    # Add a greeting
    greeting = (
        "Thank you for calling Red Bar Sushi. "
        "This is the AI assistant. How can I help you today?"
    )
    response.say(greeting)
    
    # Ask for the caller's name
    name_prompt = "May I have your name please?"
    
    # Set up the name gathering parameters with slightly longer timeouts
    gather_params = setup_gather_params(
        timeout=7,  # Longer timeout for initial interaction
        speech_timeout=3,  # Allow more thinking time
        input_type="dtmf speech"
    )
    
    # Create a gather for the name
    with response.gather(
        action="/take_name",
        **gather_params
    ) as g:
        g.say(name_prompt)
    
    # If no input, redirect to take_name with a silence flag
    response.redirect("/take_name?silence=true")
    
    # Return the TwiML response
    return Response(str(response), mimetype="text/xml")

@voice_bp.route("/take_name", methods=["POST"])
def take_name():
    """
    Process the customer's name and ask for confirmation.
    
    This route:
    1. Extracts the name from speech input
    2. Stores it in the session
    3. Asks for confirmation
    4. Handles silence gracefully
    """
    # Initialize TwiML response
    response = VoiceResponse()
    
    # Check if this is a silent redirect
    silence = request.args.get("silence", "false").lower() == "true"
    
    if silence:
        # Handle silence by reprompting
        retry_count = session.get("name_silence_retry", 0)
        session["name_silence_retry"] = retry_count + 1
        
        # Add a more helpful prompt after repeated silence
        if retry_count > 1:
            response.say(
                "I still didn't catch your name. "
                "You can just say your first name, or press any key to use the keypad."
            )
        else:
            response.say("I didn't catch that. Could you please tell me your name?")
        
        # Set up gather parameters with adjusted timeouts
        timeout, speech_timeout = get_adaptive_timeouts("name", retry_count)
        
        with response.gather(
            action="/take_name",
            input="dtmf speech",
            timeout=timeout,
            speech_timeout=speech_timeout,
            speech_model="phone_call",
            enhanced=True,
        ) as g:
            g.say("What's your name?")
        
        # If still no input, redirect to main menu as a fallback
        if retry_count >= 2:
            response.say("Let's continue without your name for now.")
            response.redirect("/main_menu")
        else:
            response.redirect("/take_name?silence=true")
    else:
        # Process the customer's name input
        spoken_name = request.form.get("SpeechResult", "")
        digits = request.form.get("Digits", "")
        
        # Log the input
        logger.info(f"Name input received - Speech: '{spoken_name}', DTMF: '{digits}'")
        
        # Extract name from speech (if available)
        if spoken_name:
            # Use AI agent to extract name from the response
            extracted_name = extract_name_with_agent(spoken_name)
            
            # Store the name in session
            session["customer_name"] = extracted_name
            session["customer_name_raw"] = spoken_name
            
            # Ask for confirmation
            with response.gather(
                action="/confirm_name",
                input="dtmf speech",
                speech_model="phone_call",
                enhanced=True,
                speech_timeout=2,
                hints="yes, no, yeah, nope, correct, that's right, that's wrong",
                timeout=5,
            ) as g:
                g.say(f"Thanks, I heard {extracted_name}. Is that correct?")
        elif digits:
            # If they pressed keys instead of speaking, go to main menu
            # We can't easily collect a name via keypad
            response.say("Let's continue to the main menu.")
            response.redirect("/main_menu")
        else:
            # No input provided, handle as silence
            response.redirect("/take_name?silence=true")
    
    # Return the TwiML response
    return Response(str(response), mimetype="text/xml")

@voice_bp.route("/confirm_name", methods=["POST"])
def confirm_name():
    """
    Confirm the customer's name and proceed to the main menu.
    
    This route:
    1. Processes the yes/no confirmation
    2. Either accepts the name or asks again
    3. Proceeds to the main menu
    """
    # Initialize TwiML response
    response = VoiceResponse()
    
    # Get confirmation response
    spoken_resp = request.form.get("SpeechResult", "").lower()
    digits = request.form.get("Digits", "")
    
    # Log the response
    logger.info(f"Name confirmation - Speech: '{spoken_resp}', DTMF: '{digits}'")
    
    # Process confirmation
    confirmed = False
    
    # Check for affirmative responses
    if spoken_resp:
        # Common yes patterns
        yes_patterns = ["yes", "yeah", "yep", "correct", "right", "that's right", "that is right", 
                        "that's correct", "that is correct", "yes it is", "it is"]
        
        # Check if the response contains any yes pattern
        if any(yes_word in spoken_resp for yes_word in yes_patterns):
            confirmed = True
        
        # Check for explicit negatives
        no_patterns = ["no", "nope", "that's wrong", "that is wrong", "not correct", 
                       "that's not right", "that's not correct", "that is not correct"]
        
        if any(no_word in spoken_resp for no_word in no_patterns):
            confirmed = False
    
    # Check digit input - 1 for yes, 2 for no
    if digits == "1":
        confirmed = True
    elif digits == "2":
        confirmed = False
    
    # Act on the confirmation
    if confirmed:
        # Save confirmed name and proceed to main menu
        name = session.get("customer_name", "")
        session["customer_name_confirmed"] = True
        
        # Personalized greeting
        response.say(f"Thanks, {name}!")
        response.redirect("/main_menu")
    else:
        # If not confirmed, ask again but add a retry counter to prevent loops
        retry_count = session.get("name_confirm_retry", 0)
        session["name_confirm_retry"] = retry_count + 1
        
        # After 2 retries, just proceed with what we have or default name
        if retry_count >= 1:
            # Just proceed with what we have or a default
            if not session.get("customer_name"):
                session["customer_name"] = "Customer"
            
            # Mark as confirmed to avoid further prompts
            session["customer_name_confirmed"] = True
            
            response.say("Let's continue to the main menu.")
            response.redirect("/main_menu")
            return Response(str(response), mimetype="text/xml")
        
        # First retry - clear previous name and try again
        response.say("I apologize for getting that wrong. Let's try again.")
        
        # Clear previous name from session
        if "customer_name" in session:
            del session["customer_name"]
        if "customer_name_raw" in session:
            del session["customer_name_raw"]
        
        # Reset the gather for name
        with response.gather(
            action="/take_name",
            input="dtmf speech",
            speech_model="phone_call",
            enhanced=True,
            speech_timeout=3,
            timeout=6,
        ) as g:
            g.say("Could you please tell me your name again?")
        
        # If no response, redirect to main menu as fallback
        response.say("Let's continue to the main menu.")
        response.redirect("/main_menu")
    
    # Return the TwiML response
    return Response(str(response), mimetype="text/xml")

@voice_bp.route("/main_menu_fallback", methods=["POST"])
def main_menu_fallback():
    """
    Fallback handler for the main menu when voice recognition fails.
    
    This route provides a simplified DTMF-only menu for accessibility
    and fallback scenarios.
    """
    # Initialize TwiML response
    response = VoiceResponse()
    
    # Fallback message
    response.say(
        "I'm having trouble understanding voice commands. "
        "Let me give you the menu options by keypad."
    )
    
    # Create a DTMF-only menu
    with response.gather(
        action="/main_menu_dtmf_only",
        input="dtmf",
        timeout=10,
        num_digits=1,
        finish_on_key="#"
    ) as g:
        g.say(
            "Press 1 to order, 2 for menu questions, "
            "or 3 for a real person. "
            "Press 0 to hear these options again."
        )
    
    # If no response, retry with abbreviated options
    response.say("I didn't receive any input. Let's try again with shorter options.")
    
    # Simplified retry
    with response.gather(
        action="/main_menu_dtmf_only",
        input="dtmf",
        timeout=5,
        num_digits=1
    ) as g:
        g.say("Press 1 to order, 2 for menu questions, or 3 for a real person.")
    
    # Final fallback - transfer to staff
    response.say(
        "I'm not detecting any keypad input. Let me transfer you to our staff."
    )
    response.redirect("/handle_transfer_to_human")
    
    # Return the TwiML response
    return Response(str(response), mimetype="text/xml")

@voice_bp.route("/main_menu_dtmf_only", methods=["POST"])
def main_menu_dtmf_only():
    """
    Process DTMF (keypad) input for the main menu.
    
    This route:
    1. Processes numeric menu selections
    2. Redirects to appropriate handlers based on selection
    """
    # Initialize TwiML response
    response = VoiceResponse()
    
    # Get DTMF input
    digits = request.form.get("Digits", "")
    
    # Log selection
    logger.info(f"DTMF main menu selection: {digits}")
    
    # Process the selection
    if digits == "1":
        # Place an order
        response.say("I'll help you place an order. Let me redirect you to our order system.")
        response.redirect("/take_order")  # Redirect to order system
    elif digits == "2":
        # Menu information
        response.say("I'll help you with information about our menu.")
        
        # Set up gather for menu questions
        with response.gather(
            action="/handle_menu_questions",
            input="dtmf speech",
            speech_model="phone_call",
            enhanced=True,
            speech_timeout=3,
            timeout=8,
        ) as g:
            g.say(
                "You can ask me about our menu items, prices, or recommendations. "
                "What would you like to know?"
            )
        
        # Fallback for no input
        response.redirect("/main_menu_fallback")
    elif digits == "3":
        # Transfer to human
        response.say("I'll connect you with a staff member. Please hold.")
        response.redirect("/handle_transfer_to_human")
    elif digits == "0":
        # Repeat options
        response.redirect("/main_menu_dtmf_only")
    else:
        # Invalid selection
        response.say("I didn't recognize that selection. Let me repeat the options.")
        response.redirect("/main_menu_dtmf_only")
    
    # Return the TwiML response
    return Response(str(response), mimetype="text/xml")

@voice_bp.route("/main_menu", methods=["POST"])
def main_menu():
    """
    Main menu for the voice application.
    
    This route presents the main options to the caller and directs them
    to the appropriate handling routes based on their selection.
    """
    # Initialize TwiML response
    response = VoiceResponse()
    
    # Check if this is their first time at the main menu
    first_visit = session.get("main_menu_visits", 0) == 0
    session["main_menu_visits"] = session.get("main_menu_visits", 0) + 1
    
    # Menu prompt varies based on first visit vs return
    if first_visit:
        menu_prompt = (
            "I can help you place an order, answer questions about our menu, "
            "or connect you with our staff. Press 1 to order, 2 for menu questions, "
            "or 3 for a real person. What would you like to do today?"
        )
    else:
        # Returning to main menu - streamlined prompt
        menu_prompt = (
            "You're back at our main menu. Press 1 to order, 2 for menu questions, "
            "or 3 for a real person. What would you like to do today?"
        )
    
    # If we know the customer's name, personalize the prompt
    if session.get("customer_name_confirmed") and session.get("customer_name"):
        name = session.get("customer_name")
        if first_visit:
            menu_prompt = f"Alright {name}, {menu_prompt}"
    
    # Menu hints to improve speech recognition
    menu_hints = (
        "place an order, order food, I want to order, "
        "menu information, what's on the menu, menu questions, "
        "speak to someone, talk to a person, human please, transfer me"
    )
    
    # Set up gather for voice or DTMF input
    gather_params = setup_gather_params(
        timeout=8,
        speech_timeout=3,
        hints=menu_hints,
        input_type="dtmf speech"
    )
    
    with response.gather(
        action="/handle_main_menu_selection",
        **gather_params
    ) as g:
        g.say(menu_prompt)
    
    # Fallback for no response
    response.say("I didn't hear your selection. Let me give you some options.")
    response.redirect("/main_menu_fallback")
    
    # Return the TwiML response
    return Response(str(response), mimetype="text/xml")

@voice_bp.route("/handle_main_menu_selection", methods=["POST"])
def handle_main_menu_selection():
    """
    Process the customer's main menu selection.
    
    This route:
    1. Analyzes speech or DTMF input from main menu
    2. Identifies the customer's intent
    3. Redirects to the appropriate handler
    """
    # Initialize TwiML response
    response = VoiceResponse()
    
    # Get customer input
    spoken_input = request.form.get("SpeechResult", "").lower()
    digits = request.form.get("Digits", "")
    
    # Log the selection
    logger.info(f"Main menu selection - Speech: '{spoken_input}', DTMF: '{digits}'")
    
    # Process DTMF input first (simplest)
    if digits:
        if digits == "1":  # Order
            response.say("I'll help you place an order.")
            response.redirect("/take_order")  # Redirect to order system
            return Response(str(response), mimetype="text/xml")
        elif digits == "2":  # Menu info
            response.say("Let me tell you about our menu.")
            response.redirect("/handle_menu_questions?asked=false")
            return Response(str(response), mimetype="text/xml")
        elif digits == "3":  # Human
            response.say("I'll connect you with a staff member.")
            response.redirect("/handle_transfer_to_human")
            return Response(str(response), mimetype="text/xml")
    
    # Process speech input
    if spoken_input:
        # Check for ordering intent
        order_phrases = ["order", "place an order", "food", "want to eat", "hungry"]
        if any(phrase in spoken_input for phrase in order_phrases):
            response.say("I'll help you place an order.")
            response.redirect("/take_order")  # Redirect to order system
            return Response(str(response), mimetype="text/xml")
        
        # Check for menu intent
        menu_phrases = ["menu", "what do you have", "what's available", "specials", "prices"]
        if any(phrase in spoken_input for phrase in menu_phrases):
            response.say("Let me tell you about our menu.")
            response.redirect("/handle_menu_questions?asked=false")
            return Response(str(response), mimetype="text/xml")
        
        # Check for human intent
        human_phrases = ["human", "person", "staff", "speak to someone", "talk to someone", "manager", "agent"]
        if any(phrase in spoken_input for phrase in human_phrases):
            response.say("I'll connect you with a staff member.")
            response.redirect("/handle_transfer_to_human")
            return Response(str(response), mimetype="text/xml")
        
        # For more complex inputs, get help from the agent
        try:
            agent = OrderParsingAgent()
            intent = agent.classify_main_menu_intent(spoken_input)
            
            if intent == "order":
                response.say("I'll help you place an order.")
                response.redirect("/take_order")  # Redirect to order system
                return Response(str(response), mimetype="text/xml")
            elif intent == "menu":
                response.say("Let me tell you about our menu.")
                response.redirect("/handle_menu_questions?asked=false")
                return Response(str(response), mimetype="text/xml")
            elif intent == "human":
                response.say("I'll connect you with a staff member.")
                response.redirect("/handle_transfer_to_human")
                return Response(str(response), mimetype="text/xml")
        except Exception as e:
            logger.error(f"Error classifying main menu intent: {str(e)}")
    
    # If we can't determine intent, ask for clarification
    response.say(
        "I'm not sure what you'd like to do. Let me offer some specific options."
    )
    
    # Offer clearer choices with a new gather
    with response.gather(
        action="/handle_main_menu_selection",
        input="dtmf speech",
        speech_model="phone_call",
        enhanced=True,
        speech_timeout=3,
        timeout=6,
        hints="order, menu, human",
    ) as g:
        g.say(
            "Press 1 to order, 2 for menu questions, "
            "or 3 for a real person."
        )
    
    # Final fallback to DTMF-only menu
    response.redirect("/main_menu_fallback")
    
    # Return the TwiML response
    return Response(str(response), mimetype="text/xml")
