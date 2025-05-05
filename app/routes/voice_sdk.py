"""
Voice routes for RedBarSushiAI using OpenAI Agents SDK.
This module provides the voice routes for handling Twilio calls with OpenAI Agents SDK.
"""

from flask import Blueprint, request, Response, jsonify, current_app
import logging
import json
import time
import os
import traceback
import uuid
from twilio.twiml.voice_response import VoiceResponse, Gather
import openai

from app.agents.factory import agent_factory
from app.utils.conversation_store_sdk import agents_conversation_store
from app.utils.agents_sdk import text_to_speech

# Set up logger
logger = logging.getLogger(__name__)

# Create blueprint
voice_sdk_bp = Blueprint("voice_sdk", __name__)

# Initialize the agent factory
frontline_agent = None

@voice_sdk_bp.before_app_first_request
def initialize_agents():
    """Initialize the agents when the app starts."""
    global frontline_agent
    
    try:
        # Create all agents
        frontline_agent = agent_factory.create_agents()
        if frontline_agent:
            logger.info("Successfully initialized agents")
        else:
            logger.error("Failed to initialize agents")
    except Exception as e:
        logger.error(f"Error initializing agents: {str(e)}")

# Speech timeout configuration
SPEECH_TIMEOUT_SHORT = "auto"  # For simple responses (yes/no)
SPEECH_TIMEOUT_MEDIUM = "auto"  # For name, phone number
SPEECH_TIMEOUT_LONG = "auto"  # For orders, menu questions
SPEECH_TIMEOUT_EXTENDED = "auto"  # For complex orders

# Regular timeout configuration (waiting for any input)
TIMEOUT_SHORT = 3
TIMEOUT_MEDIUM = 4
TIMEOUT_LONG = 5
TIMEOUT_EXTENDED = 6

# Progressive timeout settings
MAX_SILENCE_RETRIES = 3

@voice_sdk_bp.route("/", methods=["GET", "POST"])
def receive_call():
    """
    Receive a new voice call and start the conversation.
    
    Returns:
        TwiML response to greet the caller and start the media stream
    """
    # Log call details
    logger.info("==== INCOMING CALL RECEIVED (AGENTS SDK) ====")
    logger.info(f"Request came from: {request.remote_addr}")
    logger.info(f"User agent: {request.user_agent}")
    logger.info(f"Host header: {request.host}")
    logger.info(f"URL: {request.url}")
    logger.info(f"Request method: {request.method}")
    logger.info(f"Environment: {os.environ.get('FLASK_ENV', 'undefined')}")
    logger.info(f"From number: {request.values.get('From', 'Not provided')}")
    
    # Check if we have the agent
    if not frontline_agent:
        logger.error("Frontline Voice Agent not initialized")
        response = VoiceResponse()
        response.say("I'm sorry, our voice assistant is currently unavailable. Please try again later.")
        return Response(str(response), mimetype="text/xml")
    
    # Get the caller's phone number
    caller_number = request.values.get("From", "")
    call_sid = request.values.get("CallSid", "")
    
    # Log the call SID
    logger.info(f"Call SID: {call_sid}")
    
    # Determine environment for greeting
    env_name = (
        "STAGING"
        if os.environ.get("IS_STAGING") or os.environ.get("FLASK_ENV") == "staging"
        else "PRODUCTION"
    )
    
    # Create a TwiML response
    response = VoiceResponse()
    
    # Determine whether to use traditional Gather or real-time Stream
    use_streaming = request.args.get("stream", "false").lower() == "true"
    
    if use_streaming:
        # Use Stream for real-time, bidirectional media
        # Add an initial greeting before starting the stream
        response.say(
            f"Hello! This is the {env_name} environment. Thank you for calling Red Bar Sushi.",
            voice="Polly.Amy-Neural"
        )
        
        # Start the bidirectional stream
        # The "url" parameter should point to your WebSocket endpoint
        base_url = request.host_url.rstrip('/')
        ws_url = f"{base_url.replace('http://', 'ws://').replace('https://', 'wss://')}/ws/media?CallSid={call_sid}"
        
        # Configure the stream
        stream = response.stream(
            name="media_stream",
            url=ws_url,
            track="both_tracks"  # Receive inbound audio and send outbound
        )
        
        # Define stream parameters
        stream.parameter(name="format", value="mulaw")
        stream.parameter(name="rate", value="8000")
        
    else:
        # Traditional Gather approach for request-response voice mode
        # Add an initial greeting
        response.say(
            f"Hello! This is the {env_name} environment. Thank you for calling Red Bar Sushi.",
            voice="Polly.Amy-Neural"
        )
        
        # Start a gather to get the customer's request
        gather = Gather(
            input="speech",
            action="/voice_sdk/process_input",
            method="POST",
            timeout=5,
            speech_timeout="auto",
            enhanced=True,
            language="en-US"
        )
        gather.say("How can I help you today?", voice="Polly.Amy-Neural")
        response.append(gather)
        
        # If the user doesn't say anything, redirect to the input processor
        response.redirect("/voice_sdk/process_input")
    
    return Response(str(response), mimetype="text/xml")

@voice_sdk_bp.route("/process_input", methods=["POST"])
def process_input():
    """
    Process speech input from the caller.
    
    Returns:
        TwiML response with the agent's reply
    """
    # Get the speech input
    speech_input = request.form.get("SpeechResult", "")
    call_sid = request.values.get("CallSid", "")
    
    # Log the input
    logger.info(f"Speech input from {call_sid}: {speech_input}")
    
    # Check for silence (no input)
    if not speech_input:
        # Track silence retries
        conversation_data = agents_conversation_store.get_conversation(call_sid)
        silence_count = conversation_data.get("silence_count", 0) + 1
        
        # Update the conversation data
        agents_conversation_store.update_conversation(
            call_sid,
            {"silence_count": silence_count}
        )
        
        # Create response
        response = VoiceResponse()
        
        # Handle progressive silence based on count
        if silence_count >= MAX_SILENCE_RETRIES:
            # After too many silences, provide a friendly message and end the call
            response.say(
                "I haven't heard from you. Please call back when you're ready to order. Thank you for calling Red Bar Sushi.",
                voice="Polly.Amy-Neural"
            )
            response.hangup()
        else:
            # Create an appropriate reprompt
            if silence_count == 1:
                prompt = "I didn't hear anything. How can I help you today?"
            elif silence_count == 2:
                prompt = "I still can't hear you. Please speak up or press any key to continue."
            else:
                prompt = "If you're there, please speak loudly or press any key to continue."
            
            # Gather with adjusted timeouts
            gather = Gather(
                input="speech dtmf",
                action="/voice_sdk/process_input",
                method="POST",
                timeout=5 + silence_count,  # Increase timeout with each retry
                speech_timeout="auto",
                enhanced=True,
                language="en-US"
            )
            gather.say(prompt, voice="Polly.Amy-Neural")
            response.append(gather)
            
            # Add a fallback if nothing is detected
            response.redirect("/voice_sdk/process_input")
        
        return Response(str(response), mimetype="text/xml")
    
    # Reset silence counter if we got input
    agents_conversation_store.update_conversation(
        call_sid,
        {"silence_count": 0}
    )
    
    # Process the input using the Frontline Voice Agent
    try:
        agent_response = frontline_agent.process_voice_input(call_sid, speech_input)
        
        # Create the TwiML response
        response = VoiceResponse()
        
        # Add the agent's response
        response.say(agent_response, voice="Polly.Amy-Neural")
        
        # Check if this is a goodbye message (ends with "Goodbye", "have a nice day", etc.)
        is_goodbye = any(
            phrase in agent_response.lower() 
            for phrase in ["goodbye", "have a nice day", "thank you for calling"]
        )
        
        if is_goodbye:
            # End the call gracefully
            response.hangup()
        else:
            # Continue the conversation with another gather
            gather = Gather(
                input="speech",
                action="/voice_sdk/process_input",
                method="POST",
                timeout=5,
                speech_timeout="auto",
                enhanced=True,
                language="en-US"
            )
            response.append(gather)
            
            # Add a fallback if nothing is detected
            response.redirect("/voice_sdk/process_input")
        
        return Response(str(response), mimetype="text/xml")
    
    except Exception as e:
        logger.error(f"Error processing input: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Create error response
        response = VoiceResponse()
        response.say(
            "I'm sorry, but I'm having trouble processing your request. Please try again later.",
            voice="Polly.Amy-Neural"
        )
        response.hangup()
        
        return Response(str(response), mimetype="text/xml")

@voice_sdk_bp.route("/healthcheck", methods=["GET"])
def healthcheck():
    """
    Health check endpoint for the voice service.
    
    Returns:
        JSON response with health status
    """
    # Check if the Frontline Voice Agent is initialized
    agent_status = "ok" if frontline_agent else "error"
    
    return jsonify({
        "status": "ok",
        "service": "voice_sdk",
        "agent_status": agent_status
    })