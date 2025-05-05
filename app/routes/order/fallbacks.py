"""
Order fallback routes for RedBarSushiAI.
This module provides the routes for handling fallback scenarios during order processing.
"""

import json
import logging
from flask import request, session, Response
from twilio.twiml.voice_response import VoiceResponse

from app.routes.order import order_bp
from app.utils.order_utils import user_said_yes, user_said_no, dtmf_yes_no

# Configure logger
logger = logging.getLogger(__name__)

@order_bp.route("/understanding_fallback", methods=["POST"])
def understanding_fallback():
    """
    Handle fallback when the system can't understand the order.
    Provides options for the user to retry or get help.
    """
    # Get the response
    user_resp = request.form.get("SpeechResult", "").strip()
    dtmf_digits = request.form.get("Digits", "").strip()
    
    # Build the response
    response = VoiceResponse()
    
    # Check if the user pressed a key
    if dtmf_digits == "1":
        # User wants to hear popular menu items
        response.say(
            "Some of our popular items include: California Roll, Spicy Tuna Roll, Dragon Roll, Rainbow Roll, and Salmon Nigiri. You can also order our specialty rolls like the Red Bar Roll or the Volcano Roll."
        )
        
        # Ask for the order again
        with response.gather(
            input="speech",
            action="/take_order",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7
        ) as g:
            g.say("Please tell me what you'd like to order now.")
            
    elif dtmf_digits == "2":
        # User wants to return to main menu
        response.redirect("/main_menu")
        
    else:
        # Try to process speech response as a new order
        response.redirect("/take_order")
        
    return Response(str(response), mimetype="text/xml")

@order_bp.route("/modification_silence_fallback", methods=["POST"])
def modification_silence_fallback():
    """
    Handle fallback when the user is silent during order modification.
    Provides options for the user to continue or cancel.
    """
    # Build the response
    response = VoiceResponse()
    
    # Get the current order from session
    try:
        current_order = json.loads(session.get("order_items_json", "[]"))
        if current_order:
            # User has an existing order, offer to continue with it
            with response.gather(
                input="speech dtmf",
                action="/modification_silence_fallback_response",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=5,
                timeout=7,
                num_digits=1
            ) as g:
                g.say(
                    "Would you like to continue with your current order without changes? Say yes or press 1 to continue with your current order. Say no or press 2 to cancel your order."
                )
        else:
            # No existing order, go back to take order
            response.say("Let's try ordering again.")
            response.redirect("/take_order")
            
    except Exception as e:
        logger.error(f"Error in modification silence fallback: {e}")
        response.say("I'm sorry, there was an error with your order. Let's start again.")
        response.redirect("/take_order")
        
    return Response(str(response), mimetype="text/xml")

@order_bp.route("/modification_silence_fallback_response", methods=["POST"])
def modification_silence_fallback_response():
    """
    Handle response to modification silence fallback.
    """
    # Get the response
    user_resp = request.form.get("SpeechResult", "").strip()
    dtmf_digits = request.form.get("Digits", "").strip()
    
    # Check if this is a yes/no response
    is_yes = user_said_yes(user_resp) or dtmf_yes_no(dtmf_digits) == "yes"
    is_no = user_said_no(user_resp) or dtmf_yes_no(dtmf_digits) == "no"
    
    # Build the response
    response = VoiceResponse()
    
    if is_yes:
        # User wants to continue with current order
        response.say("Great! Let's continue with your current order.")
        response.redirect("/confirm_order_from_initial")
    else:
        # User wants to cancel or didn't give a clear response
        response.say("Let's start a new order.")
        response.redirect("/take_order")
        
    return Response(str(response), mimetype="text/xml")

@order_bp.route("/handle_newly_snoozed_in_checkout", methods=["POST"])
def handle_newly_snoozed_in_checkout():
    """
    Handle the situation where items become unavailable during checkout.
    Allows the user to adjust their order.
    """
    # Get the response
    user_resp = request.form.get("SpeechResult", "").strip()
    dtmf_digits = request.form.get("Digits", "").strip()
    
    # Check if this is a yes/no response
    is_yes = user_said_yes(user_resp) or dtmf_yes_no(dtmf_digits) == "yes"
    is_no = user_said_no(user_resp) or dtmf_yes_no(dtmf_digits) == "no"
    
    # Build the response
    response = VoiceResponse()
    
    if is_yes:
        # User wants to continue without unavailable items
        response.say("Great, let's continue with the available items in your order.")
        response.redirect("/process_order_checkout?retry=true")
    elif is_no:
        # User wants to modify their order
        with response.gather(
            input="speech",
            action="/new_modify_order",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7
        ) as g:
            g.say(
                "Okay, let's modify your order. Please tell me what changes you'd like to make."
            )
    else:
        # Unclear response, ask again
        with response.gather(
            input="speech dtmf",
            action="/handle_newly_snoozed_in_checkout",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7,
            num_digits=1
        ) as g:
            g.say(
                "I didn't understand your response. Would you like to continue with just the available items? Say yes or press 1 to continue with available items. Say no or press 2 to modify your order."
            )
            
    return Response(str(response), mimetype="text/xml")

@order_bp.route("/handle_busy_options", methods=["POST"])
def handle_busy_options():
    """
    Handle options when the restaurant is in busy mode.
    """
    # Get the response
    user_resp = request.form.get("SpeechResult", "").strip()
    dtmf_digits = request.form.get("Digits", "").strip()
    
    # Build the response
    response = VoiceResponse()
    
    if dtmf_digits == "1" or "menu" in user_resp.lower():
        # User wants menu information
        response.say("I'd be happy to tell you about our menu.")
        response.redirect("/menu_info")
    elif dtmf_digits == "2" or "callback" in user_resp.lower() or "call back" in user_resp.lower():
        # User wants to leave callback info
        with response.gather(
            input="speech",
            action="/save_callback_request",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto"
        ) as g:
            g.say(
                "Please tell me your name and the best phone number to reach you."
            )
    elif dtmf_digits == "3" or "end" in user_resp.lower() or "hang up" in user_resp.lower():
        # User wants to end call
        response.say("Thank you for calling Red Bar Sushi. We hope to serve you soon. Goodbye!")
        response.hangup()
    else:
        # Unclear or no response, repeat options
        with response.gather(
            input="speech dtmf",
            action="/handle_busy_options",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7,
            num_digits=1
        ) as g:
            g.say(
                "Press 1 to get menu information, press 2 to leave your name and number for a callback, or press 3 to end the call."
            )
            
    return Response(str(response), mimetype="text/xml")

@order_bp.route("/handle_menu_unavailable", methods=["POST"])
def handle_menu_unavailable():
    """
    Handle options when the menu is unavailable.
    """
    # Get the response
    user_resp = request.form.get("SpeechResult", "").strip()
    dtmf_digits = request.form.get("Digits", "").strip()
    
    # Build the response
    response = VoiceResponse()
    
    if dtmf_digits == "1" or "speak" in user_resp.lower() or "team" in user_resp.lower():
        # User wants to speak with a team member
        response.say("Please hold while I transfer you to a team member who can tell you about our daily specials.")
        response.dial("+18005551234")  # Replace with actual restaurant number
    elif dtmf_digits == "2" or "contact" in user_resp.lower() or "information" in user_resp.lower():
        # User wants to leave contact info
        with response.gather(
            input="speech",
            action="/save_contact_info",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto"
        ) as g:
            g.say(
                "Please tell me your name and the best phone number to reach you when our menu is back online."
            )
    elif dtmf_digits == "3" or "end" in user_resp.lower() or "hang up" in user_resp.lower():
        # User wants to end call
        response.say("Thank you for calling Red Bar Sushi. We apologize for the inconvenience. Goodbye!")
        response.hangup()
    else:
        # Unclear or no response, repeat options
        with response.gather(
            input="speech dtmf",
            action="/handle_menu_unavailable",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7,
            num_digits=1
        ) as g:
            g.say(
                "Press 1 to speak with a team member about our daily specials, press 2 to leave your contact information for when our menu is back online, or press 3 to end the call."
            )
            
    return Response(str(response), mimetype="text/xml")

@order_bp.route("/handle_technical_difficulties", methods=["POST"])
def handle_technical_difficulties():
    """
    Handle options when there are technical difficulties.
    """
    # Get the response
    user_resp = request.form.get("SpeechResult", "").strip()
    dtmf_digits = request.form.get("Digits", "").strip()
    
    # Build the response
    response = VoiceResponse()
    
    if dtmf_digits == "1" or "speak" in user_resp.lower() or "team" in user_resp.lower():
        # User wants to speak with a team member
        response.say("Please hold while I transfer you to a team member who can take your order manually.")
        response.dial("+18005551234")  # Replace with actual restaurant number
    elif dtmf_digits == "2" or "contact" in user_resp.lower() or "information" in user_resp.lower():
        # User wants to leave contact info
        with response.gather(
            input="speech",
            action="/save_callback_request",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto"
        ) as g:
            g.say(
                "Please tell me your name and the best phone number to reach you."
            )
    elif dtmf_digits == "3" or "end" in user_resp.lower() or "hang up" in user_resp.lower():
        # User wants to end call
        response.say("Thank you for calling Red Bar Sushi. We apologize for the technical difficulties. Goodbye!")
        response.hangup()
    else:
        # Unclear or no response, repeat options
        with response.gather(
            input="speech dtmf",
            action="/handle_technical_difficulties",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7,
            num_digits=1
        ) as g:
            g.say(
                "Press 1 to speak with a team member who can take your order manually, press 2 to leave your contact information for a callback, or press 3 to end the call."
            )
            
    return Response(str(response), mimetype="text/xml")

@order_bp.route("/handle_unavailable_order", methods=["POST"])
def handle_unavailable_order():
    """
    Handle options when the entire order is unavailable.
    """
    # Get the response
    user_resp = request.form.get("SpeechResult", "").strip()
    dtmf_digits = request.form.get("Digits", "").strip()
    
    # Build the response
    response = VoiceResponse()
    
    if dtmf_digits == "1" or "order" in user_resp.lower() or "something else" in user_resp.lower():
        # User wants to order something else
        response.say("Let's try ordering something else.")
        response.redirect("/take_order")
    elif dtmf_digits == "2" or "menu" in user_resp.lower():
        # User wants to hear the menu
        response.say("I'd be happy to tell you about our menu.")
        response.redirect("/menu_info")
    elif dtmf_digits == "3" or "end" in user_resp.lower() or "hang up" in user_resp.lower():
        # User wants to end call
        response.say("Thank you for calling Red Bar Sushi. We hope to serve you soon. Goodbye!")
        response.hangup()
    else:
        # Unclear or no response, repeat options
        with response.gather(
            input="speech dtmf",
            action="/handle_unavailable_order",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=5,
            timeout=7,
            num_digits=1
        ) as g:
            g.say(
                "Press 1 to order something else, press 2 to hear our menu options, or press 3 to end the call."
            )
            
    return Response(str(response), mimetype="text/xml")

# Export all functions
__all__ = [
    'understanding_fallback',
    'modification_silence_fallback',
    'modification_silence_fallback_response',
    'handle_newly_snoozed_in_checkout',
    'handle_busy_options',
    'handle_menu_unavailable',
    'handle_technical_difficulties',
    'handle_unavailable_order'
]