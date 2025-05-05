"""
Contact handling routes for RedBarSushiAI.
This module provides routes for handling customer contact information and callbacks.
"""

import json
import logging
import re
from datetime import datetime
from flask import request, session, Response, jsonify
from twilio.twiml.voice_response import VoiceResponse
from twilio.twiml.messaging_response import MessagingResponse

# Import blueprint reference directly to avoid circular imports
from app.routes.order.__init__ import order_bp
from app.utils.helpers import log_info, commit_with_retry
from app import db, twilio_client
from app.models import ContactRequest

# Configure logger
logger = logging.getLogger(__name__)

@order_bp.route("/save_callback_request", methods=["POST"])
def save_callback_request():
    """
    Save customer callback request information.
    """
    # Get the speech result from the request
    user_resp = request.form.get("SpeechResult", "").strip()
    call_sid = request.form.get("CallSid", "unknown")
    caller_number = request.form.get("From", "unknown")
    
    # Build the response object
    response = VoiceResponse()
    
    # Handle silence (no speech)
    if not user_resp:
        # Try again
        with response.gather(
            input="speech",
            action="/save_callback_request",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto"
        ) as g:
            g.say(
                "I didn't catch that. Please tell me your name and the best phone number to reach you."
            )
        return Response(str(response), mimetype="text/xml")
    
    # Try to extract name and phone number from the response
    # This is a simple approach - in a real system, we'd use NLP
    name = ""
    phone_number = ""
    
    # Try to extract a phone number using regex
    phone_pattern = re.compile(r'(\d{3}[-\.\s]??\d{3}[-\.\s]??\d{4}|\(\d{3}\)\s*\d{3}[-\.\s]??\d{4}|\d{10})')
    phone_matches = phone_pattern.findall(user_resp)
    
    if phone_matches:
        # Use the first match
        phone_match = phone_matches[0]
        phone_number = re.sub(r'[^0-9]', '', phone_match)
        
        # Remove the phone number from the response to extract the name
        name_text = user_resp.replace(phone_match, "").strip()
    else:
        # No phone number found, treat the whole response as the name
        name_text = user_resp
        
        # Use the caller's number as fallback
        if caller_number and caller_number.startswith("+"):
            phone_number = caller_number[1:]  # Remove the + prefix
        
    # Use a simple heuristic to extract the name
    # Just take the first two words as the name if it's not too long
    name_parts = name_text.split()
    if len(name_parts) >= 2:
        name = " ".join(name_parts[:2])
    else:
        name = name_text
    
    # Log the extracted information
    logger.info(f"Extracted callback info - Name: '{name}', Phone: '{phone_number}'")
    
    # Save to the database if we have a contact request model
    try:
        if hasattr(db.Model, "ContactRequest"):
            contact_request = ContactRequest(
                name=name,
                phone_number=phone_number,
                call_sid=call_sid,
                request_type="callback",
                created_at=datetime.now()
            )
            db.session.add(contact_request)
            commit_with_retry(db.session)
            logger.info(f"Saved callback request ID: {contact_request.id}")
    except Exception as e:
        logger.error(f"Failed to save callback request: {e}")
    
    # Send confirmation to the user
    response.say(
        f"Thank you, {name}. We've received your callback request. A member of our team will call you back as soon as possible. Thank you for your patience."
    )
    response.hangup()
    
    return Response(str(response), mimetype="text/xml")

@order_bp.route("/save_contact_info", methods=["POST"])
def save_contact_info():
    """
    Save customer contact information.
    """
    # Get the speech result from the request
    user_resp = request.form.get("SpeechResult", "").strip()
    call_sid = request.form.get("CallSid", "unknown")
    caller_number = request.form.get("From", "unknown")
    
    # Build the response object
    response = VoiceResponse()
    
    # Handle silence (no speech)
    if not user_resp:
        # Try again
        with response.gather(
            input="speech",
            action="/save_contact_info",
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto"
        ) as g:
            g.say(
                "I didn't catch that. Please tell me your name and the best phone number to reach you."
            )
        return Response(str(response), mimetype="text/xml")
    
    # Try to extract name and phone number from the response
    # This is a simple approach - in a real system, we'd use NLP
    name = ""
    phone_number = ""
    
    # Try to extract a phone number using regex
    phone_pattern = re.compile(r'(\d{3}[-\.\s]??\d{3}[-\.\s]??\d{4}|\(\d{3}\)\s*\d{3}[-\.\s]??\d{4}|\d{10})')
    phone_matches = phone_pattern.findall(user_resp)
    
    if phone_matches:
        # Use the first match
        phone_match = phone_matches[0]
        phone_number = re.sub(r'[^0-9]', '', phone_match)
        
        # Remove the phone number from the response to extract the name
        name_text = user_resp.replace(phone_match, "").strip()
    else:
        # No phone number found, treat the whole response as the name
        name_text = user_resp
        
        # Use the caller's number as fallback
        if caller_number and caller_number.startswith("+"):
            phone_number = caller_number[1:]  # Remove the + prefix
        
    # Use a simple heuristic to extract the name
    # Just take the first two words as the name if it's not too long
    name_parts = name_text.split()
    if len(name_parts) >= 2:
        name = " ".join(name_parts[:2])
    else:
        name = name_text
    
    # Log the extracted information
    logger.info(f"Extracted contact info - Name: '{name}', Phone: '{phone_number}'")
    
    # Save to the database if we have a contact request model
    try:
        if hasattr(db.Model, "ContactRequest"):
            contact_request = ContactRequest(
                name=name,
                phone_number=phone_number,
                call_sid=call_sid,
                request_type="menu_notification",
                created_at=datetime.now()
            )
            db.session.add(contact_request)
            commit_with_retry(db.session)
            logger.info(f"Saved contact request ID: {contact_request.id}")
    except Exception as e:
        logger.error(f"Failed to save contact request: {e}")
    
    # Send confirmation to the user
    response.say(
        f"Thank you, {name}. We've saved your contact information. We'll notify you when our menu is back online. Thank you for your interest in Red Bar Sushi!"
    )
    response.hangup()
    
    return Response(str(response), mimetype="text/xml")

# Export all functions
__all__ = ['save_callback_request', 'save_contact_info']