"""
Voice transfer module. This module contains routes for handling transfers to human agents and voicemail.
"""

import logging
import json
import time
import os
from flask import request, session, Response, current_app
from twilio.twiml.voice_response import VoiceResponse

# Import blueprint
from . import voice_bp

# Import helpers
from .voice_core import setup_gather_params

# Set up logger
logger = logging.getLogger(__name__)

@voice_bp.route("/handle_transfer_to_human", methods=["POST"])
def handle_transfer_to_human():
    """
    Transfer the call to a human agent or to voicemail.
    
    This route:
    1. Offers to transfer to a human agent
    2. Handles fallback to voicemail if no agents are available
    3. Processes any notes about the customer's issue
    """
    # Initialize TwiML response
    response = VoiceResponse()
    
    # Get transfer reason if provided
    transfer_reason = request.args.get("reason", "")
    
    # Default transfer message
    transfer_message = (
        "I'll transfer you to a team member who can help you further. "
        "Please hold while I connect you."
    )
    
    # Customize message based on reason
    if transfer_reason == "complex":
        transfer_message = (
            "This seems like a complex request that I'm not equipped to handle. "
            "Let me transfer you to a team member who can better assist you."
        )
    elif transfer_reason == "request":
        transfer_message = (
            "As requested, I'll transfer you to a staff member. "
            "Please hold while I connect you."
        )
    
    # Check for voicemail-only mode flag in config
    voicemail_only = current_app.config.get("VOICEMAIL_ONLY", False)
    
    if voicemail_only:
        # Skip the transfer attempt and go straight to voicemail
        response.say(
            "I'm sorry, our staff members are currently unavailable. "
            "I'll connect you to our voicemail system where you can leave a message."
        )
        response.redirect("/handle_voicemail")
        return Response(str(response), mimetype="text/xml")
    
    # Speak the transfer message
    response.say(transfer_message)
    
    # Get the transfer number from config
    transfer_number = current_app.config.get("TRANSFER_PHONE_NUMBER")
    
    if not transfer_number:
        # No transfer number configured, fall back to voicemail
        logger.warning("No transfer number configured, falling back to voicemail")
        response.say(
            "I'm sorry, I'm unable to transfer you to a staff member at this time. "
            "Let me connect you to our voicemail system instead."
        )
        response.redirect("/handle_voicemail")
        return Response(str(response), mimetype="text/xml")
    
    # Log the transfer attempt
    logger.info(f"Attempting to transfer call to {transfer_number}")
    
    # Add call metadata before transfer
    session["transfer_attempt_time"] = time.time()
    session["transfer_reason"] = transfer_reason or "customer request"
    
    # Set up the call transfer
    # Use Dial verb to maintain the call
    response.say("Please hold while I connect you.")
    
    try:
        # Attempt the transfer
        response.dial(
            transfer_number,
            action="/handle_transfer_result",
            timeout=20,  # Ring for 20 seconds max
            record="record-from-answer",  # Record the call after answer
            recordingStatusCallback="/recording_status"  # Webhook for recording status
        )
    except Exception as e:
        # Handle any errors in transfer setup
        logger.error(f"Error setting up transfer: {str(e)}")
        response.say(
            "I'm having trouble connecting you. "
            "Let me redirect you to our voicemail system."
        )
        response.redirect("/handle_voicemail")
    
    # Return the TwiML response
    return Response(str(response), mimetype="text/xml")

@voice_bp.route("/handle_transfer_result", methods=["POST"])
def handle_transfer_result():
    """
    Process the result of a transfer attempt.
    
    This route:
    1. Handles successful transfers
    2. Processes failures (busy, no-answer, etc.)
    3. Offers voicemail as a fallback
    """
    # Initialize TwiML response
    response = VoiceResponse()
    
    # Get transfer status from Twilio
    dial_status = request.form.get("DialCallStatus", "")
    
    # Log the transfer result
    logger.info(f"Transfer result: {dial_status}")
    
    # Handle the result based on status
    if dial_status == "completed":
        # Transfer was successful and completed
        logger.info("Transfer completed successfully")
        response.say(
            "Your call has been completed. Thank you for calling Red Bar Sushi."
        )
        
        # Call is complete, no more actions needed
        return Response(str(response), mimetype="text/xml")
    elif dial_status == "answered":
        # Transfer was answered but didn't complete (unusual case)
        logger.warning("Transfer was answered but didn't complete")
        response.say(
            "Your call was answered but disconnected unexpectedly. "
            "Would you like to leave a voicemail instead?"
        )
        
        # Offer voicemail option
        with response.gather(
            action="/handle_voicemail_choice",
            input="dtmf speech",
            speech_model="phone_call",
            enhanced=True,
            speech_timeout=2,
            timeout=5,
            hints="yes, no",
        ) as g:
            g.say("Press 1 or say yes to leave a voicemail, or press 2 to end the call.")
    else:
        # Transfer failed (busy, no-answer, failed)
        failure_reason = "unavailable"
        
        if dial_status == "busy":
            failure_reason = "busy"
        elif dial_status == "no-answer":
            failure_reason = "not answering"
        elif dial_status == "failed":
            failure_reason = "unavailable due to a connection issue"
        
        response.say(
            f"I'm sorry, but our staff is currently {failure_reason}. "
            "Would you like to leave a voicemail instead?"
        )
        
        # Offer voicemail option
        with response.gather(
            action="/handle_voicemail_choice",
            input="dtmf speech",
            speech_model="phone_call",
            enhanced=True,
            speech_timeout=2,
            timeout=5,
            hints="yes, no",
        ) as g:
            g.say("Press 1 or say yes to leave a voicemail, or press 2 to end the call.")
    
    # Default action if no input received
    response.say("I'll connect you to our voicemail system.")
    response.redirect("/handle_voicemail")
    
    # Return the TwiML response
    return Response(str(response), mimetype="text/xml")

@voice_bp.route("/handle_voicemail_choice", methods=["POST"])
def handle_voicemail_choice():
    """
    Process the customer's choice regarding voicemail.
    
    This route:
    1. Interprets yes/no response for voicemail
    2. Redirects to voicemail or ends call accordingly
    """
    # Initialize TwiML response
    response = VoiceResponse()
    
    # Get customer response
    spoken_resp = request.form.get("SpeechResult", "").lower()
    digits = request.form.get("Digits", "")
    
    # Process the response
    if spoken_resp in ["yes", "yeah", "sure", "okay"] or digits == "1":
        # Customer wants to leave a voicemail
        response.say("I'll connect you to our voicemail system.")
        response.redirect("/handle_voicemail")
    else:
        # Customer doesn't want to leave a voicemail
        response.say(
            "Thank you for calling Red Bar Sushi. "
            "If you need further assistance, please call us back during regular business hours. "
            "Goodbye."
        )
    
    # Return the TwiML response
    return Response(str(response), mimetype="text/xml")

@voice_bp.route("/handle_voicemail", methods=["POST"])
def handle_voicemail():
    """
    Handle the voicemail recording process.
    
    This route:
    1. Provides instructions for leaving a voicemail
    2. Records the caller's message
    3. Confirms the recording was received
    """
    # Initialize TwiML response
    response = VoiceResponse()
    
    # Voicemail greeting
    response.say(
        "You've reached the voicemail for Red Bar Sushi. "
        "Please leave your name, phone number, and a brief message after the tone. "
        "Press pound when you're finished."
    )
    
    # Create a unique recording filename
    timestamp = int(time.time())
    caller_phone = session.get("sender", "unknown").replace("+", "")
    recording_filename = f"vm_{timestamp}_{caller_phone}"
    
    # Store the filename in session
    session["voicemail_filename"] = recording_filename
    
    # Set up the recording
    response.record(
        action="/save_voicemail",
        max_length=120,  # 2 minutes max
        timeout=5,  # Stop recording after 5 seconds of silence
        finish_on_key="#",
        play_beep=True,
        recording_status_callback="/recording_status",
        recording_status_callback_event="completed",
    )
    
    # In case they don't record but just hang up
    response.say("I didn't receive a message. Please call back if you'd like to leave a message.")
    
    # Return the TwiML response
    return Response(str(response), mimetype="text/xml")

@voice_bp.route("/save_voicemail", methods=["POST"])
def save_voicemail():
    """
    Process and save the voicemail recording.
    
    This route:
    1. Logs the recording URL from Twilio
    2. Thanks the caller for their message
    3. Ends the call
    """
    # Initialize TwiML response
    response = VoiceResponse()
    
    # Get recording data from Twilio
    recording_url = request.form.get("RecordingUrl", "")
    recording_sid = request.form.get("RecordingSid", "")
    recording_duration = request.form.get("RecordingDuration", "0")
    
    # Log the recording details
    logger.info(f"Voicemail recorded: {recording_sid}, duration: {recording_duration}s")
    
    # Store recording data in session
    session["voicemail_url"] = recording_url
    session["voicemail_sid"] = recording_sid
    session["voicemail_duration"] = recording_duration
    
    # Thank the caller
    response.say(
        "Thank you for your message. Our team will listen to it and get back to you as soon as possible. "
        "Goodbye."
    )
    
    # Return the TwiML response
    return Response(str(response), mimetype="text/xml")

@voice_bp.route("/recording_status", methods=["POST"])
def recording_status():
    """
    Webhook for recording status updates from Twilio.
    
    This route:
    1. Processes recording status updates
    2. Logs completion of recording
    3. Can trigger notifications about new voicemails
    """
    # Get recording status information
    recording_sid = request.form.get("RecordingSid", "")
    recording_status = request.form.get("RecordingStatus", "")
    recording_url = request.form.get("RecordingUrl", "")
    recording_duration = request.form.get("RecordingDuration", "0")
    
    # Log the status update
    logger.info(f"Recording status update: {recording_status} for SID {recording_sid}")
    
    # Process completed recordings
    if recording_status == "completed" and recording_url:
        # Log the completed recording
        logger.info(f"Recording completed: {recording_url}, duration: {recording_duration}s")
        
        # Store recording info for later use if needed
        # Here you would typically save this to a database
        
        # Could implement notification here (email, SMS, etc.)
        # about the new voicemail
    
    # Return an empty response
    return Response("", mimetype="text/xml")