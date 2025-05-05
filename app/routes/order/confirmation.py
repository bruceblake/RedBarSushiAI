"""
Order confirmation routes for RedBarSushiAI.
This module provides the routes for order confirmation and processing.
"""

import json
import logging
import requests
import uuid
import time
from datetime import datetime
from flask import request, session, Response, jsonify
from twilio.twiml.voice_response import VoiceResponse

from app.routes.order import order_bp
from app.utils.order_utils import (
    user_said_yes,
    user_said_no,
    dtmf_yes_no,
)
from app.utils.deliverect import build_deliverect_order, send_order_to_deliverect
from app.utils.agent_utils import OrderParsingAgent, get_order_modifications
from app.utils.helpers import log_info, commit_with_retry
from app.config import DELIVERECT_API_URL, BASE_URL
from app import db
from app.models import Order

# Try to import tasks module for status updates
try:
    from tasks import send_order_status_update_task
except ImportError:
    # Create a dummy task for testing
    def send_order_status_update_task(*args, **kwargs):
        logger.warning(
            "Could not import send_order_status_update_task from tasks module. Will try again when needed."
        )

# Configure logger
logger = logging.getLogger(__name__)

@order_bp.route("/confirm_order_from_initial", methods=["POST"])
def confirm_order_from_initial():
    """
    Handle order confirmation after initial order has been placed.
    This route checks whether to proceed directly or check for modifiers first.
    """
    # Get the response from the user
    user_resp = request.form.get("SpeechResult", "").strip()
    dtmf_digits = request.form.get("Digits", "").strip()
    
    # Check if this is a yes/no response
    is_yes = user_said_yes(user_resp) or dtmf_yes_no(dtmf_digits) == "yes"
    is_no = user_said_no(user_resp) or dtmf_yes_no(dtmf_digits) == "no"
    
    # Build the response object
    response = VoiceResponse()
    
    # Handle silence (no speech or DTMF)
    if not user_resp and not dtmf_digits:
        # Count silence retries
        silence_retry = session.get("confirm_silence_retry", 0)
        session["confirm_silence_retry"] = silence_retry + 1
        
        if silence_retry >= 2:
            # After multiple tries, assume yes to keep the flow moving
            logger.info("Multiple silence retries, assuming confirmation")
            response.say("I'll take your silence as a confirmation.")
            response.redirect("/process_order_checkout")
        else:
            # Try asking again
            with response.gather(
                input="speech dtmf",
                action="/confirm_order_from_initial",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=3,
                timeout=5,
                num_digits=1
            ) as g:
                g.say(
                    "I didn't hear your response. Is your order correct? Say yes or press 1 to confirm. Say no or press 2 to make changes."
                )
        return Response(str(response), mimetype="text/xml")
    
    # Reset silence counter if we got a response
    session["confirm_silence_retry"] = 0
    
    # If the user confirms the order, process it
    if is_yes:
        # Confirmed the order, send to checkout
        response.say("Great! Let's process your order.")
        response.redirect("/process_order_checkout")
        return Response(str(response), mimetype="text/xml")
    
    # If the user wants to make changes, go to modification
    elif is_no:
        # User wants to modify the order
        with response.gather(
            input="speech",
            action="/new_modify_order",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto"
        ) as g:
            g.say(
                "Okay, let's update your order. Please tell me what changes you'd like to make. For example, you can say 'Add a California roll' or 'Remove the spicy tuna roll'."
            )
        return Response(str(response), mimetype="text/xml")
    
    # Handle unclear responses
    else:
        # Couldn't understand the response, try again
        with response.gather(
            input="speech dtmf",
            action="/confirm_order_from_initial",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=3,
            timeout=5,
            num_digits=1
        ) as g:
            g.say(
                "I'm sorry, I didn't understand your response. Please say 'yes' or press 1 to confirm your order. Say 'no' or press 2 to make changes."
            )
        return Response(str(response), mimetype="text/xml")

@order_bp.route("/confirm_order_after_modification", methods=["POST"])
def confirm_order_after_modification():
    """
    Handle order confirmation after the order has been modified.
    """
    # Get the response from the user
    user_resp = request.form.get("SpeechResult", "").strip()
    dtmf_digits = request.form.get("Digits", "").strip()
    
    # Check if this is a yes/no response
    is_yes = user_said_yes(user_resp) or dtmf_yes_no(dtmf_digits) == "yes"
    is_no = user_said_no(user_resp) or dtmf_yes_no(dtmf_digits) == "no"
    
    # Build the response object
    response = VoiceResponse()
    
    # Handle silence (no speech or DTMF)
    if not user_resp and not dtmf_digits:
        # Count silence retries
        silence_retry = session.get("confirm_mod_silence_retry", 0)
        session["confirm_mod_silence_retry"] = silence_retry + 1
        
        if silence_retry >= 2:
            # After multiple tries, assume yes to keep the flow moving
            logger.info("Multiple silence retries after mod, assuming confirmation")
            response.say("I'll take your silence as a confirmation.")
            response.redirect("/process_order_checkout")
        else:
            # Try asking again
            with response.gather(
                input="speech dtmf",
                action="/confirm_order_after_modification",
                enhanced=True,
                speech_model="phone_call",
                language="en-US",
                speech_timeout=3,
                timeout=5,
                num_digits=1
            ) as g:
                g.say(
                    "I didn't hear your response. Is your updated order correct? Say yes or press 1 to confirm. Say no or press 2 to make more changes."
                )
        return Response(str(response), mimetype="text/xml")
    
    # Reset silence counter if we got a response
    session["confirm_mod_silence_retry"] = 0
    
    # If the user confirms the order, process it
    if is_yes:
        # Confirmed the order, send to checkout
        response.say("Great! Let's process your updated order.")
        response.redirect("/process_order_checkout")
        return Response(str(response), mimetype="text/xml")
    
    # If the user wants to make more changes, go to modification again
    elif is_no:
        # User wants to modify the order again
        with response.gather(
            input="speech",
            action="/new_modify_order",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto"
        ) as g:
            g.say(
                "Okay, let's make more changes to your order. Please tell me what additional changes you'd like to make."
            )
        return Response(str(response), mimetype="text/xml")
    
    # Handle unclear responses
    else:
        # Couldn't understand the response, try again
        with response.gather(
            input="speech dtmf",
            action="/confirm_order_after_modification",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout=3,
            timeout=5,
            num_digits=1
        ) as g:
            g.say(
                "I'm sorry, I didn't understand your response. Please say 'yes' or press 1 to confirm your updated order. Say 'no' or press 2 to make more changes."
            )
        return Response(str(response), mimetype="text/xml")

# Export all functions
__all__ = ['confirm_order_from_initial', 'confirm_order_after_modification']