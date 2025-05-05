"""
Voice routes with advanced orchestration for RedBarSushiAI.
This module provides the voice routes that use the advanced agentic patterns
including sequential handoffs, background escalation, and state-machine slot filling.
"""

from flask import Blueprint, request, session, Response, jsonify, send_from_directory
import logging
import json
import asyncio
import time
import os
import traceback
import uuid
from twilio.twiml.voice_response import VoiceResponse

# Import WebSocket handler
from app import sock

# Import the enhanced agent factory
from app.agents.factory_with_orchestration import enhanced_agent_factory

# Import real-time audio processing utilities
from app.utils.realtime_audio import get_audio_processor

# Import agent orchestration components
from app.utils.agent_orchestration import (
    AgentGraph,
    SlotStore,
    FSMOrchestrator,
    FSMState,
    ModelEscalator,
    initialize_orchestrators
)

# Set up logger
logger = logging.getLogger(__name__)

orchestrated_voice_bp = Blueprint("voice_orchestrated", __name__)

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

# Initialize the agent
frontline_agent = None
agent_graph = None
slot_store = None
fsm_orchestrator = None
model_escalator = None

def setup_gather_params(
    context, retry_count=0, include_dtmf=False, action=None, msg=None
):
    """
    Helper function to consistently set up gather parameters for voice responses.
    This ensures speech timeout settings are used consistently throughout the application.

    Args:
        context (str): The context of the interaction (order, menu, confirm, etc.)
        retry_count (int): How many times we've retried due to silence
        include_dtmf (bool): Whether to include DTMF input
        action (str): The action endpoint for the gather
        msg (str): Optional message to speak before waiting for input

    Returns:
        dict: Parameters to use for response.gather()
    """
    # Get appropriate timeouts
    speech_timeout, timeout = get_adaptive_timeouts(context, retry_count)

    # Build the gather parameters
    params = {
        "enhanced": True,
        "speech_model": "phone_call",
        "language": "en-US",
        "speech_timeout": speech_timeout,
        "timeout": timeout,
    }

    # Set input type
    if include_dtmf:
        params["input"] = "speech dtmf"
        params["num_digits"] = 1
    else:
        params["input"] = "speech"

    # Add action if provided
    if action:
        params["action"] = action

    return params


def get_adaptive_timeouts(context, retry_count=0):
    """
    Get adaptive timeout values based on context and retry count.
    This helps provide more time when customers need it while preventing
    excessive waiting when there's persistent silence.

    Args:
        context (str): The context of the interaction (order, menu, confirm, etc.)
        retry_count (int): How many times we've retried due to silence

    Returns:
        tuple: (speech_timeout, timeout) values to use
    """
    # Start with base values based on context
    if context in ["order", "complex_order"]:
        speech_timeout = SPEECH_TIMEOUT_LONG
        timeout = TIMEOUT_LONG
    elif context in ["menu", "question"]:
        speech_timeout = SPEECH_TIMEOUT_MEDIUM
        timeout = TIMEOUT_MEDIUM
    elif context in ["confirm", "yes_no", "name"]:
        speech_timeout = SPEECH_TIMEOUT_SHORT
        timeout = TIMEOUT_SHORT
    else:
        # Default to medium for unspecified contexts
        speech_timeout = SPEECH_TIMEOUT_MEDIUM
        timeout = TIMEOUT_MEDIUM

    # Adjust based on retry count but keep timeouts shorter
    if retry_count == 0:
        # First attempt - use base values
        pass
    elif retry_count == 1:
        # First retry - only add a small amount of extra time
        speech_timeout = min(speech_timeout + 2, SPEECH_TIMEOUT_EXTENDED)
        timeout = min(timeout + 2, TIMEOUT_EXTENDED)
    elif retry_count >= 2:
        # Second or further retry - start reducing timeouts to prevent excessive waiting
        speech_timeout = max(speech_timeout - 1, SPEECH_TIMEOUT_SHORT)
        timeout = max(timeout - 1, TIMEOUT_SHORT)

    # For complex orders, ensure minimum thresholds but keep them reasonable
    if context == "complex_order":
        speech_timeout = max(speech_timeout, SPEECH_TIMEOUT_LONG)
        timeout = max(timeout, TIMEOUT_LONG)

    return speech_timeout, timeout


def handle_silence(
    response, session_key, action, context, max_retries=MAX_SILENCE_RETRIES
):
    """
    Centralized silence handling for Twilio VoiceResponse.
    Provides consistent handling of silence across different routes.

    Args:
        response: The VoiceResponse object
        session_key: The session key to track retry count
        action: The action URL for gather
        context: Context for timeout selection (order, menu, etc)
        max_retries: Maximum retries before giving up

    Returns:
        Response object with appropriate gather settings
    """
    # Get current retry count and increment
    retry_count = session.get(session_key, 0)
    session[session_key] = retry_count + 1

    # Log the silence handling
    logger.info(f"Handling silence for {context} (retry {retry_count}/{max_retries})")

    # Check if we've hit the limit
    if retry_count >= max_retries:
        logger.warning(
            f"Too many silences ({retry_count}) in {context}, redirecting to fallback"
        )
        response.redirect("/voice_orchestrated/main_menu_fallback")
        return Response(str(response), mimetype="text/xml")

    # Get appropriate timeouts based on context and retry count
    speech_timeout, timeout = get_adaptive_timeouts(context, retry_count)
    logger.info(
        f"Using adaptive timeouts: speech={speech_timeout}s, timeout={timeout}s"
    )

    # Helper messages based on silence retries - make them shorter and more direct
    if retry_count == 0:
        message = f"I didn't hear anything. Please speak again."
    elif retry_count == 1:
        message = f"I still can't hear you. Please speak up or press a key."
    else:
        message = f"If you're there, please speak loudly or press any key to continue."

    # For menu context, add more helpful but brief guidance
    if context == "menu":
        message += " Ask about menu items, prices, or popular dishes."
    elif context == "order":
        message += " Tell me what you'd like to order."

    # Configure the gather using standardized parameters
    gather_params = setup_gather_params(
        context=context,
        retry_count=retry_count,
        include_dtmf=(retry_count > 0),  # Add DTMF option after first retry
        action=action,
    )

    with response.gather(**gather_params) as g:
        g.say(message)

    # Add fallback
    response.redirect(action)
    return Response(str(response), mimetype="text/xml")


def init_agents():
    """Initialize the orchestrated agents if not already done."""
    global frontline_agent, agent_graph, slot_store, fsm_orchestrator, model_escalator
    
    # Check if already initialized
    if frontline_agent is not None:
        return frontline_agent
    
    logger.info("Initializing orchestrated agents")
    
    # Create the orchestration components if not yet created
    if agent_graph is None:
        agent_graph, slot_store, fsm_orchestrator, model_escalator = initialize_orchestrators()
    
    # Create the agents with orchestration
    frontline_agent = enhanced_agent_factory.create_agents()
    
    if frontline_agent is None:
        logger.error("Failed to create frontline agent")
        raise RuntimeError("Failed to initialize orchestrated agents")
    
    logger.info("Orchestrated agents initialized successfully")
    return frontline_agent


@orchestrated_voice_bp.route("/", methods=["GET", "POST"])
def receive_call():
    """Handle an incoming voice call with the orchestrated agent system."""
    # Log extensive details about the request to diagnose routing issues
    logger.info("==== INCOMING ORCHESTRATED CALL RECEIVED ====")
    logger.info(f"Request came from: {request.remote_addr}")
    logger.info(f"User agent: {request.user_agent}")
    logger.info(f"Host header: {request.host}")
    logger.info(f"URL: {request.url}")
    logger.info(f"Base URL: {request.base_url}")
    logger.info(f"Request method: {request.method}")
    logger.info(f"Environment: {os.environ.get('FLASK_ENV', 'undefined')}")
    logger.info(
        f"Is this staging?: {os.environ.get('IS_STAGING', 'No, not explicitly marked as staging')}"
    )
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"From number: {request.values.get('From', 'Not provided')}")
    logger.info("==== END CALL DETAILS ====")

    # Set initial session variables
    from app.config import DEFAULT_TEST_CUSTOMER_NUMBER

    # Get the caller's phone number
    caller_number = request.values.get("From", "")
    call_sid = request.values.get("CallSid", "")

    # In staging environment, use a default test number to ensure SMS deliverability
    is_staging = (
        os.environ.get("IS_STAGING") or os.environ.get("FLASK_ENV") == "staging"
    )

    # Initialize session variables
    session["ordering_in_progress"] = False
    session["call_sid"] = call_sid  # Store the CallSid in session for later use

    # Initialize the agent if not already done
    try:
        frontline = init_agents()
    except Exception as e:
        logger.error(f"Failed to initialize agents: {str(e)}")
        response = VoiceResponse()
        response.say("We're experiencing technical difficulties. Please try again later.")
        return Response(str(response), mimetype="text/xml")

    response = VoiceResponse()

    # Add an environment identifier to make it clear which environment is responding
    env_name = (
        "STAGING"
        if os.environ.get("IS_STAGING") or os.environ.get("FLASK_ENV") == "staging"
        else "PRODUCTION"
    )

    # Use gather params with the proper context
    gather_params = setup_gather_params(context="name", action="/voice_orchestrated/process_input")

    with response.gather(**gather_params) as g:
        g.say(
            f"Hello! This is the {env_name} environment. Thank you for calling Red Bar Sushi. How can I help you today?"
        )

    # Add a redirect outside the gather block to handle silence
    response.redirect("/voice_orchestrated/process_input")

    return Response(str(response), mimetype="text/xml")


@orchestrated_voice_bp.route("/process_input", methods=["POST"])
def process_input():
    """Process speech input and use the orchestrated agent to generate a response."""
    # Get speech input, if present
    speech_input = request.form.get("SpeechResult", "")
    digits = request.form.get("Digits", "")
    call_sid = request.values.get("CallSid", session.get("call_sid", ""))
    
    # Initialize response
    response = VoiceResponse()
    
    # Check if speech is empty, which means the user was silent
    if not speech_input and not digits:
        # Track how many silence retries we've done
        silence_retry_count = session.get("orchestrated_silence_count", 0)
        session["orchestrated_silence_count"] = silence_retry_count + 1
        
        # Handle silence with appropriate contexts
        if silence_retry_count >= 2:
            return handle_silence(
                response, 
                "orchestrated_silence_count", 
                "/voice_orchestrated/main_menu_fallback",
                "menu", 
                MAX_SILENCE_RETRIES
            )
        else:
            return handle_silence(
                response, 
                "orchestrated_silence_count", 
                "/voice_orchestrated/process_input",
                "menu", 
                MAX_SILENCE_RETRIES
            )
    
    # Reset silence counter when we get speech
    session["orchestrated_silence_count"] = 0
    
    # Get the agent
    try:
        frontline = init_agents()
    except Exception as e:
        logger.error(f"Failed to initialize agents for processing: {str(e)}")
        response.say("We're experiencing technical difficulties. Please try again later.")
        return Response(str(response), mimetype="text/xml")
    
    # Combine DTMF and speech for processing
    user_input = speech_input
    if digits and not speech_input:
        user_input = f"DTMF: {digits}"
    
    try:
        # Pass the call_sid and user input to the agent for processing
        agent_response = frontline.process_voice_input(call_sid, user_input)
        
        # Check if this is a handoff or authentication
        auth_in_progress = False
        
        # Check the current FSM state
        current_state = fsm_orchestrator.get_current_state(call_sid)
        
        # If in authentication flow, we need to check for completion
        if current_state not in [FSMState.INITIAL, FSMState.AUTHENTICATED]:
            logger.info(f"Call {call_sid} is in authentication state: {current_state.value}")
            auth_in_progress = True
        
        # If authenticated, check if we need to proceed to order
        if current_state == FSMState.AUTHENTICATED:
            logger.info(f"Authentication completed for call {call_sid}")
            # Check if the next step was ordering
            order_intent = slot_store.get_slot(call_sid, "last_intent")
            if order_intent == "place_order":
                auth_in_progress = False  # We've completed auth, proceed with normal flow
        
        # Speak the response from the agent
        response.say(agent_response)
        
        # If we're in authentication flow or we're done, we need specific handling
        if auth_in_progress:
            # Continue with authentication - stay in the FSM flow
            action = "/voice_orchestrated/process_input"
        else:
            # Normal flow - prepare for next input
            action = "/voice_orchestrated/process_input"
        
        # Set up gather for the next input
        gather_params = setup_gather_params(
            context="menu" if not auth_in_progress else "confirm",
            action=action
        )
        
        # Add a gather for the next input
        response.gather(**gather_params)
        
        # Add a redirect for silence handling
        response.redirect(action)
        
    except Exception as e:
        logger.error(f"Error processing input with orchestrated agent: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Handle errors gracefully
        response.say("I'm sorry, we encountered an error processing your request. Please try again.")
        
        # Add a gather for the next input
        gather_params = setup_gather_params(
            context="menu",
            action="/voice_orchestrated/process_input"
        )
        response.gather(**gather_params)
        
        # Add a redirect for silence
        response.redirect("/voice_orchestrated/process_input")
    
    return Response(str(response), mimetype="text/xml")


@orchestrated_voice_bp.route("/main_menu_fallback", methods=["POST", "GET"])
def main_menu_fallback():
    """
    Fallback for when we can't get input or other issues.
    Provides a menu focused on DTMF inputs for more reliability.
    """
    # Reset all retry counters
    session["orchestrated_silence_count"] = 0
    
    logger.info("Entering orchestrated main_menu_fallback - all silence counters reset")
    
    # Create voice response focused on DTMF input
    response = VoiceResponse()
    with response.gather(
        input="dtmf speech",  # Allow both but emphasize DTMF in the prompt
        action="/voice_orchestrated/process_input",
        num_digits=1,
        timeout=TIMEOUT_MEDIUM,
        speech_timeout=SPEECH_TIMEOUT_MEDIUM,
    ) as g:
        g.say(
            "Welcome to Red Bar Sushi! We may be having trouble hearing you. "
            "Please use your phone keypad or speak clearly. "
            "Press or say 1 to order, press or say 2 for menu questions, "
            "or press or say 3 to speak with a person."
        )
        # Add a brief pause to give them time to process
        g.pause(length=1)
        g.say("Again, press 1 to order, 2 for menu, or 3 for help.")
    
    # Add fallback if we still get nothing - in the worst case, don't hang up
    response.redirect("/voice_orchestrated/dtmf_only")
    
    return Response(str(response), mimetype="text/xml")


@orchestrated_voice_bp.route("/dtmf_only", methods=["POST", "GET"])
def dtmf_only():
    """
    Last resort fallback that only accepts DTMF input.
    Used when there are persistent audio quality issues.
    """
    logger.warning("Entering DTMF-only mode - audio quality may be very poor")
    
    response = VoiceResponse()
    with response.gather(
        input="dtmf",  # DTMF only
        action="/voice_orchestrated/process_input",
        num_digits=1,
        timeout=TIMEOUT_EXTENDED,  # Use extended timeout for DTMF-only mode
    ) as g:
        g.say(
            "We're having trouble with the audio connection. Please use your phone keypad only."
        )
        g.pause(length=1)
        g.say("Press 1 to place an order.")
        g.pause(length=1)
        g.say("Press 2 for menu information.")
        g.pause(length=1)
        g.say("Press 3 to speak with a staff member.")
        g.pause(length=3)
        g.say("Press any key now to continue.")
    
    # If we still don't get any input, provide a friendly message and end the call
    response.say(
        "We apologize for the technical difficulties. Please call back or visit our website at redbar sushi dot com. Thank you for your patience."
    )
    
    return Response(str(response), mimetype="text/xml")


@orchestrated_voice_bp.route("/graceful_exit", methods=["POST", "GET"])
def graceful_exit():
    """
    Provides a graceful exit with a goodbye message before ending the call.
    """
    response = VoiceResponse()
    response.say("Thank you for calling Red Bar Sushi. Have a great day!")
    response.hangup()
    return Response(str(response), mimetype="text/xml")


@orchestrated_voice_bp.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint for the orchestrated voice routes.
    Verifies that the agents and orchestration components are properly initialized.
    """
    # Check if we can initialize the agents
    try:
        frontline = init_agents()
        agent_status = "initialized" if frontline else "failed"
    except Exception as e:
        agent_status = f"error: {str(e)}"
    
    # Check orchestration components
    try:
        orchestration_status = "all_components_available" if (
            agent_graph and slot_store and fsm_orchestrator and model_escalator
        ) else "missing_components"
    except Exception as e:
        orchestration_status = f"error: {str(e)}"
    
    return jsonify({
        "status": "ok" if agent_status == "initialized" and orchestration_status == "all_components_available" else "error",
        "service": "voice_orchestrated",
        "agents": agent_status,
        "orchestration": orchestration_status,
        "timestamp": time.time()
    })

@orchestrated_voice_bp.route("/demo", methods=["GET"])
def demo_page():
    """
    Serve the orchestrated demo page.
    """
    return send_from_directory("static", "orchestrated_demo.html")


# --------------------- WebSocket Routes for Real-Time Audio ---------------------

@sock.route("/api/ws/orchestrated_conversation")
async def orchestrated_conversation(ws):
    """
    WebSocket endpoint for real-time conversation with orchestrated agents.
    Provides streaming voice capabilities with advanced agentic patterns.
    """
    try:
        # Get the audio processor
        audio_processor = get_audio_processor()
        logger.info(
            f"Initializing orchestrated conversation WebSocket with processor type: {type(audio_processor).__name__}"
        )
        
        # Generate session ID for this conversation
        session_id = str(uuid.uuid4())
        
        # Initialize the agents
        try:
            frontline = init_agents()
        except Exception as e:
            logger.error(f"Failed to initialize agents for WebSocket: {str(e)}")
            await ws.send(json.dumps({
                "type": "error",
                "error": "Failed to initialize agents"
            }))
            return
        
        # Send initial message to client
        await ws.send(
            json.dumps({
                "type": "connection_established",
                "session_id": session_id,
                "message": "Ready to receive audio or text for orchestrated conversation",
            })
        )
        
        # Define an async generator to receive audio chunks
        async def receive_audio_stream():
            all_audio = bytes()
            while True:
                try:
                    # Receive data from WebSocket
                    message = await ws.receive()
                    
                    if isinstance(message, bytes):
                        # Audio data
                        all_audio += message
                        yield message
                    elif isinstance(message, str):
                        # Control message or text input
                        try:
                            data = json.loads(message)
                            
                            # Check message type
                            if data.get("type") == "end":
                                logger.info(f"End of audio stream for session {session_id}")
                                break
                            elif data.get("type") == "text":
                                # Direct text input instead of audio
                                logger.info(f"Received direct text input: {data.get('text', '')[:50]}...")
                                
                                # Process the text directly with orchestrated agent
                                text_input = data.get("text", "")
                                
                                try:
                                    # Process the text with the orchestrated agent
                                    response = frontline.process_voice_input(session_id, text_input)
                                    
                                    # Send the response
                                    await ws.send(json.dumps({
                                        "type": "agent_response",
                                        "text": response,
                                        "timestamp": time.time()
                                    }))
                                    
                                    # Get current state from FSM
                                    current_state = fsm_orchestrator.get_current_state(session_id)
                                    state_info = {
                                        "state": current_state.value,
                                        "is_authenticated": (current_state == FSMState.AUTHENTICATED),
                                        "slots": slot_store.get_all_slots(session_id)
                                    }
                                    
                                    # Send state information
                                    await ws.send(json.dumps({
                                        "type": "state_update",
                                        "state_info": state_info,
                                        "timestamp": time.time()
                                    }))
                                    
                                except Exception as e:
                                    logger.error(f"Error processing orchestrated text: {str(e)}")
                                    await ws.send(json.dumps({
                                        "type": "error",
                                        "error": f"Error processing text: {str(e)}",
                                        "timestamp": time.time()
                                    }))
                                
                                # Send a signal that we're done processing this text message
                                await ws.send(json.dumps({
                                    "type": "text_processing_complete",
                                    "timestamp": time.time()
                                }))
                                
                                # Reset to receive new input
                                all_audio = bytes()
                                return
                        except json.JSONDecodeError:
                            logger.warning(f"Received non-JSON text message: {message[:50]}...")
                            continue
                except Exception as e:
                    logger.error(f"Error receiving WebSocket message: {str(e)}")
                    break
            
            # If we received audio but no text message processed it
            if all_audio:
                # Process the complete audio with basic processor if real-time not available
                if not hasattr(audio_processor, "process_audio_stream"):
                    result = await audio_processor.process_audio(all_audio)
                    text_input = result.get("text", "")
                    
                    # Send the transcript to the client
                    await ws.send(json.dumps({
                        "type": "transcript_complete",
                        "text": text_input,
                        "timestamp": time.time()
                    }))
                    
                    # Process with orchestrated agent
                    try:
                        response = frontline.process_voice_input(session_id, text_input)
                        
                        # Send the response
                        await ws.send(json.dumps({
                            "type": "agent_response",
                            "text": response,
                            "timestamp": time.time()
                        }))
                        
                        # Get current state from FSM
                        current_state = fsm_orchestrator.get_current_state(session_id)
                        state_info = {
                            "state": current_state.value,
                            "is_authenticated": (current_state == FSMState.AUTHENTICATED),
                            "slots": slot_store.get_all_slots(session_id)
                        }
                        
                        # Send state information
                        await ws.send(json.dumps({
                            "type": "state_update",
                            "state_info": state_info,
                            "timestamp": time.time()
                        }))
                        
                    except Exception as e:
                        logger.error(f"Error processing orchestrated voice: {str(e)}")
                        await ws.send(json.dumps({
                            "type": "error",
                            "error": f"Error processing voice: {str(e)}",
                            "timestamp": time.time()
                        }))
        
        # Real-time or basic processing based on available implementation
        if hasattr(audio_processor, "process_audio_stream"):
            # Content type for audio (client can specify in headers)
            content_type = "audio/webm"
            
            # Process audio stream and collect transcript
            full_transcript = ""
            
            # Start audio processing
            async for segment in audio_processor.process_audio_stream(
                receive_audio_stream(), content_type
            ):
                # Send transcript segments to client
                await ws.send(json.dumps(segment))
                
                # If this is the final transcript, process it
                if segment.get("type") == "transcript_complete":
                    full_transcript = segment.get("text", "")
                    
                    # Process with orchestrated agent
                    try:
                        logger.info(f"Processing orchestrated conversation with transcript: {full_transcript[:50]}...")
                        response = frontline.process_voice_input(session_id, full_transcript)
                        
                        # Send the response
                        await ws.send(json.dumps({
                            "type": "agent_response",
                            "text": response,
                            "timestamp": time.time()
                        }))
                        
                        # Get current state from FSM
                        current_state = fsm_orchestrator.get_current_state(session_id)
                        state_info = {
                            "state": current_state.value,
                            "is_authenticated": (current_state == FSMState.AUTHENTICATED),
                            "slots": slot_store.get_all_slots(session_id)
                        }
                        
                        # Send state information
                        await ws.send(json.dumps({
                            "type": "state_update",
                            "state_info": state_info,
                            "timestamp": time.time()
                        }))
                        
                        # Generate speech from the response if real-time TTS is available
                        if hasattr(audio_processor, "generate_speech"):
                            await ws.send(json.dumps({
                                "type": "speech_starting",
                                "timestamp": time.time()
                            }))
                            
                            # Stream the speech chunks
                            async for speech_chunk in audio_processor.generate_speech(response):
                                await ws.send(speech_chunk)
                            
                            await ws.send(json.dumps({
                                "type": "speech_complete",
                                "timestamp": time.time()
                            }))
                    
                    except Exception as e:
                        logger.error(f"Error processing orchestrated voice: {str(e)}")
                        logger.error(traceback.format_exc())
                        await ws.send(json.dumps({
                            "type": "error",
                            "error": f"Error processing voice: {str(e)}",
                            "timestamp": time.time()
                        }))
        else:
            # Basic processor - already handled in receive_audio_stream
            await receive_audio_stream()
        
        # Final message
        await ws.send(json.dumps({
            "type": "session_complete",
            "session_id": session_id,
            "message": "Orchestrated conversation session complete",
            "timestamp": time.time()
        }))
    
    except Exception as e:
        logger.error(f"WebSocket error in orchestrated conversation: {str(e)}")
        logger.error(traceback.format_exc())
        try:
            await ws.send(json.dumps({
                "type": "error", 
                "error": str(e),
                "timestamp": time.time()
            }))
        except:
            pass