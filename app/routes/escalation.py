"""
Escalation routes for RedBarSushiAI.
This module provides routes for handling escalation and staff handoff.
"""

from flask import Blueprint, request, Response, jsonify, current_app
import logging
import json
import time
import os
from twilio.twiml.voice_response import VoiceResponse, Gather, Dial
from twilio.request_validator import RequestValidator

from app.agents.factory import agent_factory
from app.utils.conversation_store_sdk import agents_conversation_store
from app.utils.agents_sdk import text_to_speech

# Set up logger
logger = logging.getLogger(__name__)

# Create blueprint
escalation_bp = Blueprint("escalation", __name__, url_prefix="/escalation")

# Twilio validation
def validate_twilio_request(f):
    """Validate that the request actually came from Twilio"""
    # Use unique name for the decorated function to avoid conflicts
    def validate_twilio_request_wrapper(*args, **kwargs):
        # Get the request values
        twilio_signature = request.headers.get('X-Twilio-Signature', '')
        url = request.url
        params = request.form
        
        # Get the auth token from env
        auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
        
        # Skip validation in dev/test environments
        if os.environ.get('FLASK_ENV') == 'development' or not auth_token:
            return f(*args, **kwargs)
        
        # Create the validator
        validator = RequestValidator(auth_token)
        
        # Validate the request
        if validator.validate(url, params, twilio_signature):
            return f(*args, **kwargs)
        else:
            logger.warning(f"Invalid Twilio signature: {twilio_signature}")
            return Response("Invalid Twilio signature", status=403)
    
    # Update wrapper function's name and docstring
    validate_twilio_request_wrapper.__name__ = f.__name__ + '_validated'
    validate_twilio_request_wrapper.__doc__ = f.__doc__
    
    return validate_twilio_request_wrapper

@escalation_bp.route("/handle_dial_status", methods=["POST"])
@validate_twilio_request
def handle_dial_status():
    """
    Handle the status of a dial attempt.
    
    Returns:
        TwiML response based on dial status
    """
    # Get the dial status
    dial_status = request.form.get("DialCallStatus", "")
    call_sid = request.values.get("CallSid", "")
    
    logger.info(f"Dial status for call {call_sid}: {dial_status}")
    
    # Create a TwiML response
    response = VoiceResponse()
    
    # Handle the dial status
    if dial_status in ["answered", "completed"]:
        # Successfully connected, just end the call from our side
        response.hangup()
    else:
        # Failed to connect (no-answer, busy, failed, or canceled)
        response.say(
            "I'm sorry, but our staff is not available at the moment. "
            "Would you like us to call you back when someone becomes available?",
            voice="Polly.Amy-Neural"
        )
        
        # Add a gather for callback preference
        gather = Gather(
            input="speech dtmf",
            action="/voice_sdk/escalation/handle_callback_request",
            method="POST",
            timeout=5,
            speech_timeout="auto",
            enhanced=True,
            language="en-US"
        )
        gather.say("Please say yes or no, or press 1 for yes, 2 for no.", voice="Polly.Amy-Neural")
        response.append(gather)
        
        # If no input, assume no and thank the caller
        response.say(
            "Thank you for calling Red Bar Sushi. Have a great day!",
            voice="Polly.Amy-Neural"
        )
        response.hangup()
    
    return Response(str(response), mimetype="text/xml")

@escalation_bp.route("/handle_callback_request", methods=["POST"])
@validate_twilio_request
def handle_callback_request():
    """
    Handle a request for a callback.
    
    Returns:
        TwiML response to collect callback information
    """
    # Get the input
    speech_result = request.form.get("SpeechResult", "").lower()
    digits = request.form.get("Digits", "")
    call_sid = request.values.get("CallSid", "")
    
    logger.info(f"Callback request for call {call_sid}: speech={speech_result}, digits={digits}")
    
    # Check if the customer wants a callback
    wants_callback = False
    
    if speech_result:
        wants_callback = any(word in speech_result for word in ["yes", "yeah", "sure", "okay", "please"])
    elif digits:
        wants_callback = (digits == "1")
    
    # Create a TwiML response
    response = VoiceResponse()
    
    if wants_callback:
        # Update the conversation state
        agents_conversation_store.update_conversation(
            call_sid,
            {"callback_requested": True}
        )
        
        # Collect callback information
        response.say(
            "Great! Please tell me briefly what you're calling about, "
            "so we can have the right person call you back.",
            voice="Polly.Amy-Neural"
        )
        
        # Add a gather for the callback reason
        gather = Gather(
            input="speech",
            action="/voice_sdk/escalation/save_callback_reason",
            method="POST",
            timeout=5,
            speech_timeout="auto",
            enhanced=True,
            language="en-US"
        )
        gather.say("Please speak after the tone.", voice="Polly.Amy-Neural")
        response.append(gather)
        
        # If no input, thank the caller anyway
        response.say(
            "Thank you. We'll call you back as soon as possible.",
            voice="Polly.Amy-Neural"
        )
        response.hangup()
    else:
        # No callback wanted
        response.say(
            "Understood. Thank you for calling Red Bar Sushi. Have a great day!",
            voice="Polly.Amy-Neural"
        )
        response.hangup()
    
    return Response(str(response), mimetype="text/xml")

@escalation_bp.route("/save_callback_reason", methods=["POST"])
@validate_twilio_request
def save_callback_reason():
    """
    Save the reason for a callback.
    
    Returns:
        TwiML response confirming the callback
    """
    # Get the input
    speech_result = request.form.get("SpeechResult", "")
    call_sid = request.values.get("CallSid", "")
    
    logger.info(f"Callback reason for call {call_sid}: {speech_result}")
    
    # Update the conversation state
    agents_conversation_store.update_conversation(
        call_sid,
        {
            "callback_reason": speech_result,
            "callback_timestamp": time.time()
        }
    )
    
    # Create a TwiML response
    response = VoiceResponse()
    
    # Ask for preferred callback time
    response.say(
        "Thank you. When would be a good time for us to call you back? "
        "For example, you can say 'this afternoon' or 'tomorrow morning'.",
        voice="Polly.Amy-Neural"
    )
    
    # Add a gather for callback time
    gather = Gather(
        input="speech",
        action="/voice_sdk/escalation/finalize_callback",
        method="POST",
        timeout=5,
        speech_timeout="auto",
        enhanced=True,
        language="en-US"
    )
    gather.say("Please speak after the tone.", voice="Polly.Amy-Neural")
    response.append(gather)
    
    # If no input, finalize without a specific time
    response.redirect("/voice_sdk/escalation/finalize_callback")
    
    return Response(str(response), mimetype="text/xml")

@escalation_bp.route("/finalize_callback", methods=["POST"])
@validate_twilio_request
def finalize_callback():
    """
    Finalize the callback request.
    
    Returns:
        TwiML response with goodbye message
    """
    # Get the input
    speech_result = request.form.get("SpeechResult", "")
    call_sid = request.values.get("CallSid", "")
    
    logger.info(f"Callback time for call {call_sid}: {speech_result}")
    
    # Get the phone number from the call
    phone_number = request.values.get("From", "")
    
    # Update the conversation state
    agents_conversation_store.update_conversation(
        call_sid,
        {
            "callback_time": speech_result,
            "customer_phone": phone_number,
            "callback_finalized": True
        }
    )
    
    # In a real implementation, this would create a task in a CRM or task system
    # For now, just log the callback request
    conversation_data = agents_conversation_store.get_conversation(call_sid)
    callback_reason = conversation_data.get("callback_reason", "No reason provided")
    
    # Log the complete callback request
    logger.info(
        f"CALLBACK REQUEST - Phone: {phone_number}, "
        f"Time: {speech_result or 'Any time'}, "
        f"Reason: {callback_reason}"
    )
    
    # Create a TwiML response
    response = VoiceResponse()
    
    # Thank the customer and say goodbye
    response.say(
        "Thank you. We'll call you back"
        + (f" {speech_result}" if speech_result else " as soon as possible")
        + ". Have a great day!",
        voice="Polly.Amy-Neural"
    )
    response.hangup()
    
    return Response(str(response), mimetype="text/xml")

@escalation_bp.route("/direct_transfer", methods=["POST"])
@validate_twilio_request
def direct_transfer():
    """
    Direct transfer endpoint used by the Escalation Agent.
    
    Returns:
        TwiML response with transfer instructions
    """
    # Get the call SID
    call_sid = request.values.get("CallSid", "")
    
    # Get the transfer parameters
    transfer_to = request.form.get("TransferTo", "")
    reason = request.form.get("Reason", "Customer requested")
    staff_type = request.form.get("StaffType", "general")
    
    logger.info(f"Direct transfer request for call {call_sid} to {transfer_to}")
    
    # Get the Escalation Agent
    escalation_agent = agent_factory.get_escalation_agent()
    
    if not escalation_agent:
        logger.error("Escalation Agent not available")
        response = VoiceResponse()
        response.say(
            "I'm sorry, but I'm unable to transfer your call at this time. "
            "Please try again later.",
            voice="Polly.Amy-Neural"
        )
        return Response(str(response), mimetype="text/xml")
    
    # Handle the escalation
    escalation_result = escalation_agent.handle_escalation_request(
        call_sid=call_sid,
        reason=reason,
        staff_type=staff_type
    )
    
    if escalation_result.get("success", False) and escalation_result.get("twiml"):
        # Return the TwiML directly
        return Response(escalation_result["twiml"], mimetype="text/xml")
    else:
        # Handle failure
        response = VoiceResponse()
        response.say(
            "I'm sorry, but I'm unable to transfer your call at this time. "
            "Would you like to leave a message for our staff?",
            voice="Polly.Amy-Neural"
        )
        
        # Add a gather for callback preference
        gather = Gather(
            input="speech",
            action="/voice_sdk/escalation/handle_callback_request",
            method="POST",
            timeout=5,
            speech_timeout="auto",
            enhanced=True,
            language="en-US"
        )
        gather.say("Please say yes or no.", voice="Polly.Amy-Neural")
        response.append(gather)
        
        return Response(str(response), mimetype="text/xml")