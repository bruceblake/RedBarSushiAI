"""
Voice routes with Realtime API integration for RedBarSushiAI.
This module provides WebSocket endpoints for Twilio Media Streams API integration
with OpenAI's Realtime API for sub-300ms latency audio processing.

This implementation utilizes:
1. Twilio's Media Streams API for real-time audio streaming
2. OpenAI's Realtime API for streaming audio processing
3. WebSockets for bidirectional communication
4. Tool-based agent integration for specialized tasks
5. VAD-driven conversation flow instead of turn-based interactions

To use this implementation, set VOICE_HANDLER=realtime in your environment.
"""

from flask import Blueprint, request, session, Response, jsonify, render_template
import logging
import json
import asyncio
import time
import os
import traceback
import uuid
import base64
from twilio.twiml.voice_response import VoiceResponse, Connect, Start, Stream

# Import WebSocket handler
from app import sock

# Import the enhanced agent factory
from app.agents.factory_with_orchestration import enhanced_agent_factory

# Import real-time audio processing utilities
from app.utils.realtime_audio_sdk import get_realtime_processor, pcm_to_ulaw

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

# Create Blueprint for Realtime voice routes
realtime_voice_bp = Blueprint("voice_orchestrated_realtime", __name__)

# Initialize global orchestration components
frontline_agent = None
agent_graph = None
slot_store = None
fsm_orchestrator = None
model_escalator = None
tool_registry = None

# Initialize the tool registry
class ToolRegistry:
    """
    Registry for tools that can be called by OpenAI's Realtime API.
    Maps tool calls to agent methods.
    """
    
    def __init__(self):
        """Initialize the tool registry."""
        self.tools = {}
    
    def register_tool(self, name, function, description=None, schema=None):
        """Register a new tool with the registry."""
        self.tools[name] = {
            "function": function,
            "description": description or function.__doc__ or "",
            "schema": schema or {}
        }
    
    def get_tool_definitions(self):
        """Get tool definitions in OpenAI's format."""
        definitions = []
        for name, tool in self.tools.items():
            definitions.append({
                "type": "function",
                "name": name,
                "description": tool["description"],
                "parameters": tool["schema"]
            })
        return definitions
    
    def execute_tool(self, name, args, session_id=None):
        """Execute a registered tool."""
        if name not in self.tools:
            raise ValueError(f"Tool '{name}' not registered")
        
        tool = self.tools[name]
        if session_id:
            return tool["function"](session_id=session_id, **args)
        else:
            return tool["function"](**args)

# Configuration for VAD-driven timeouts
def configure_vad_for_context(context="normal"):
    """
    Configure VAD settings optimized for different conversation contexts.
    
    Args:
        context: The context type (greeting, ordering, confirmation, etc.)
    
    Returns:
        Dict with VAD configuration parameters
    """
    # Base configuration - reasonable defaults
    base_config = {
        "mode": "dynamic_threshold",
        "timeout": 2.0,               # Default 2-second timeout
        "interrupt_assistant": True,  # Allow user interruptions
        "create_response": True,      # Auto-create responses on turn change
        "speech_started_delay": 0.3,  # Slight delay for better detection
    }
    
    # Context-specific adjustments
    if context == "greeting":
        # Short timeouts for simple responses
        base_config.update({
            "timeout": 1.5,
            "speech_started_delay": 0.2,
        })
    elif context == "ordering":
        # Longer timeouts for complex responses
        base_config.update({
            "timeout": 3.0,              # Longer silence tolerance
            "speech_started_delay": 0.4, # More delay for menu browsing
        })
    elif context == "confirmation":
        # Quick responses expected
        base_config.update({
            "timeout": 1.2,              # Shorter timeouts for yes/no
            "speech_started_delay": 0.2,
        })
    elif context == "complex_order":
        # Maximum patience for complex orders
        base_config.update({
            "timeout": 4.0,              # Very patient silence detection
            "speech_started_delay": 0.5, # Higher delay for complex thinking
        })
    
    return base_config

@realtime_voice_bp.before_app_request
def initialize_agents():
    """Initialize the orchestrated agents when the app starts."""
    global frontline_agent, agent_graph, slot_store, fsm_orchestrator, model_escalator, tool_registry
    
    # Only initialize once
    if frontline_agent is not None:
        logger.debug("[REALTIME_INIT] Agents already initialized, skipping initialization")
        return
    
    logger.info("[REALTIME_INIT] Starting orchestrated agent initialization")
    
    try:
        # Create all agents through the enhanced factory
        logger.info("[REALTIME_INIT] Creating agents through enhanced factory")
        frontline_agent = enhanced_agent_factory.create_agents()
        logger.debug(f"[REALTIME_INIT] Frontline agent type: {type(frontline_agent).__name__}")
        
        # Initialize the orchestration components
        logger.info("[REALTIME_INIT] Creating orchestration components")
        agent_graph = AgentGraph()
        logger.debug(f"[REALTIME_INIT] Created agent graph: {id(agent_graph)}")
        
        slot_store = SlotStore()
        logger.debug(f"[REALTIME_INIT] Created slot store: {id(slot_store)}")
        
        fsm_orchestrator = FSMOrchestrator()
        logger.debug(f"[REALTIME_INIT] Created FSM orchestrator: {id(fsm_orchestrator)}")
        
        model_escalator = ModelEscalator()
        logger.debug(f"[REALTIME_INIT] Created model escalator: {id(model_escalator)}")
        
        # Initialize the tool registry
        tool_registry = ToolRegistry()
        logger.debug(f"[REALTIME_INIT] Created tool registry: {id(tool_registry)}")
        
        # Initialize the orchestrators with our components
        logger.info("[REALTIME_INIT] Initializing orchestrators with components")
        result = initialize_orchestrators(agent_graph, slot_store, fsm_orchestrator, model_escalator)
        logger.debug(f"[REALTIME_INIT] Orchestrator initialization result: {result}")
        
        # Register tools for the Realtime API
        if frontline_agent:
            register_default_tools(frontline_agent, tool_registry)
            logger.info("[REALTIME_INIT] Registered default tools")
        
        if frontline_agent:
            logger.info("[REALTIME_INIT] Successfully initialized orchestrated agents")
            # Log agent capabilities
            if hasattr(frontline_agent, 'get_capabilities'):
                capabilities = frontline_agent.get_capabilities()
                logger.debug(f"[REALTIME_INIT] Frontline agent capabilities: {capabilities}")
            # Log if model info is available
            if hasattr(frontline_agent, 'model'):
                logger.debug(f"[REALTIME_INIT] Frontline agent model: {frontline_agent.model}")
        else:
            logger.error("[REALTIME_INIT] Failed to initialize orchestrated agents - frontline_agent is None")
    except Exception as e:
        logger.error(f"[REALTIME_INIT] Error initializing orchestrated agents: {str(e)}")
        logger.error(f"[REALTIME_INIT] Traceback: {traceback.format_exc()}")
        # Log environment information for debugging
        logger.debug(f"[REALTIME_INIT] OPENAI_API_KEY set: {'Yes' if os.environ.get('OPENAI_API_KEY') else 'No'}")
        logger.debug(f"[REALTIME_INIT] REDIS_URL: {os.environ.get('REDIS_URL', 'Not set')}")
        logger.debug(f"[REALTIME_INIT] Python path: {os.environ.get('PYTHONPATH', 'Not set')}")
        logger.debug(f"[REALTIME_INIT] Current directory: {os.getcwd()}")

def init_agents():
    """Initialize the orchestrated agents if not already done."""
    global frontline_agent, agent_graph, slot_store, fsm_orchestrator, model_escalator, tool_registry
    
    # Check if already initialized
    if frontline_agent is not None:
        logger.debug("[REALTIME_AGENT] Using existing frontline agent instance")
        return frontline_agent
    
    logger.info("[REALTIME_AGENT] Initializing orchestrated agents on-demand")
    
    # Create the orchestration components if not yet created
    if agent_graph is None:
        logger.info("[REALTIME_AGENT] Creating orchestration components from scratch")
        try:
            agent_graph, slot_store, fsm_orchestrator, model_escalator = initialize_orchestrators()
            logger.debug(f"[REALTIME_AGENT] Created agent_graph: {id(agent_graph)}, slot_store: {id(slot_store)}")
            logger.debug(f"[REALTIME_AGENT] Created fsm_orchestrator: {id(fsm_orchestrator)}, model_escalator: {id(model_escalator)}")
        except Exception as e:
            logger.error(f"[REALTIME_AGENT] Failed to initialize orchestrators: {str(e)}")
            logger.error(f"[REALTIME_AGENT] Orchestrator error traceback: {traceback.format_exc()}")
            raise RuntimeError(f"Failed to initialize orchestrators: {str(e)}")
    else:
        logger.debug("[REALTIME_AGENT] Using existing orchestration components")
    
    # Initialize the tool registry if not yet created
    if tool_registry is None:
        tool_registry = ToolRegistry()
        logger.debug(f"[REALTIME_AGENT] Created tool registry: {id(tool_registry)}")
    
    # Log environment status
    logger.debug(f"[REALTIME_AGENT] REDIS_URL: {os.environ.get('REDIS_URL', 'Not set')}")
    logger.debug(f"[REALTIME_AGENT] OPENAI_API_KEY length: {len(os.environ.get('OPENAI_API_KEY', ''))}")
    logger.debug(f"[REALTIME_AGENT] Render environment: {'Yes' if os.environ.get('RENDER') or os.environ.get('RENDER_SERVICE_ID') else 'No'}")
    
    # Create the agents with orchestration
    logger.info("[REALTIME_AGENT] Creating frontline agent with enhanced factory")
    try:
        frontline_agent = enhanced_agent_factory.create_agents()
        logger.debug(f"[REALTIME_AGENT] Created frontline agent type: {type(frontline_agent).__name__}")
    except Exception as e:
        logger.error(f"[REALTIME_AGENT] Failed to create frontline agent: {str(e)}")
        logger.error(f"[REALTIME_AGENT] Agent creation error traceback: {traceback.format_exc()}")
        raise RuntimeError(f"Failed to create frontline agent: {str(e)}")
    
    if frontline_agent is None:
        logger.error("[REALTIME_AGENT] Failed to create frontline agent - returned None")
        raise RuntimeError("Failed to initialize orchestrated agents - factory returned None")
    
    # Register tools for the Realtime API
    register_default_tools(frontline_agent, tool_registry)
    logger.info("[REALTIME_AGENT] Registered default tools")
    
    # Log configuration
    logger.info("[REALTIME_AGENT] Orchestrated agents initialized successfully")
    if hasattr(frontline_agent, 'config'):
        logger.debug(f"[REALTIME_AGENT] Agent config: {frontline_agent.config}")
        
    # Check what specialized agents are available
    if hasattr(frontline_agent, 'agents'):
        logger.debug(f"[REALTIME_AGENT] Specialized agents: {list(frontline_agent.agents.keys())}")
    
    # Verify Redis connections by attempting to set a test value
    try:
        if slot_store and hasattr(slot_store, 'redis_client') and slot_store.redis_client:
            slot_store.redis_client.set('test_key', 'test_value', ex=60)
            result = slot_store.redis_client.get('test_key')
            logger.debug(f"[REALTIME_AGENT] Redis test result: {result == b'test_value'}")
    except Exception as e:
        logger.warning(f"[REALTIME_AGENT] Redis test failed: {str(e)}")
    
    return frontline_agent

def register_default_tools(frontline_agent, registry):
    """Register default tools with the registry."""
    
    # Lookup menu item
    registry.register_tool(
        name="lookup_menu_item",
        function=frontline_agent.lookup_menu_item if hasattr(frontline_agent, 'lookup_menu_item') else lambda **kwargs: {"error": "Function not available"},
        description="Look up a menu item by name to get its details",
        schema={
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "The name of the menu item to look up"
                }
            },
            "required": ["item_name"]
        }
    )
    
    # Add item to cart
    registry.register_tool(
        name="add_item_to_cart",
        function=frontline_agent.add_to_cart if hasattr(frontline_agent, 'add_to_cart') else lambda **kwargs: {"error": "Function not available"},
        description="Add an item to the customer's cart",
        schema={
            "type": "object",
            "properties": {
                "item_plu": {
                    "type": "string",
                    "description": "The PLU of the menu item"
                },
                "quantity": {
                    "type": "integer",
                    "description": "The quantity to add"
                },
                "modifiers": {
                    "type": "array",
                    "description": "List of modifiers to apply",
                    "items": {
                        "type": "object",
                        "properties": {
                            "modifier_plu": {"type": "string"},
                            "quantity": {"type": "integer"}
                        }
                    }
                }
            },
            "required": ["item_plu", "quantity"]
        }
    )
    
    # Get cart contents
    registry.register_tool(
        name="get_cart",
        function=frontline_agent.get_cart if hasattr(frontline_agent, 'get_cart') else lambda **kwargs: {"error": "Function not available"},
        description="Get the current contents of the customer's cart",
        schema={
            "type": "object",
            "properties": {}
        }
    )
    
    # Complete order
    registry.register_tool(
        name="complete_order",
        function=frontline_agent.complete_order if hasattr(frontline_agent, 'complete_order') else lambda **kwargs: {"error": "Function not available"},
        description="Complete the customer's order and submit it",
        schema={
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Customer's name"
                },
                "phone_number": {
                    "type": "string",
                    "description": "Customer's phone number"
                },
                "order_type": {
                    "type": "integer",
                    "description": "1 for pickup, 2 for delivery"
                },
                "delivery_address": {
                    "type": "string",
                    "description": "Delivery address (required for delivery orders)"
                }
            },
            "required": ["customer_name", "phone_number", "order_type"]
        }
    )

@realtime_voice_bp.route("/", methods=["GET", "POST"])
def receive_call():
    """
    Handle an incoming voice call with the Realtime API integration.
    Uses Twilio Media Streams for real-time audio processing.
    """
    # Log extensive details about the request to diagnose routing issues
    logger.info("==== INCOMING REALTIME CALL RECEIVED ====")
    logger.info(f"Request came from: {request.remote_addr}")
    logger.info(f"User agent: {request.user_agent}")
    logger.info(f"Host header: {request.host}")
    logger.info(f"URL: {request.url}")
    logger.info(f"Base URL: {request.base_url}")
    logger.info(f"Request method: {request.method}")
    logger.info(f"Environment: {os.environ.get('FLASK_ENV', 'undefined')}")
    logger.info(f"Is this staging?: {os.environ.get('IS_STAGING', 'No, not explicitly marked as staging')}")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"From number: {request.values.get('From', 'Not provided')}")
    logger.info("==== END CALL DETAILS ====")
    
    # Get call details from Twilio
    caller_number = request.values.get("From", "")
    call_sid = request.values.get("CallSid", "")
    
    # Add an environment identifier to make it clear which environment is responding
    env_name = "STAGING" if os.environ.get("IS_STAGING") or os.environ.get("FLASK_ENV") == "staging" else "PRODUCTION"
    
    # Create WebSocket URL for Media Streams
    # Use the request host to determine the WebSocket URL
    host = request.host
    protocol = "wss" if "https" in request.base_url else "ws"
    ws_url = f"{protocol}://{host}/ws/media"
    logger.info(f"WebSocket URL for Media Streams: {ws_url}")
    
    # Initialize TwiML response with Media Streams
    response = VoiceResponse()
    
    # Start by informing the caller which environment they're connected to
    # This happens before the Stream is connected
    response.say(f"Welcome to {env_name} Red Bar Sushi AI ordering system.")
    
    # Start Media Stream with the WebSocket endpoint
    start = Start()
    start.stream(url=ws_url, track="inbound_track")
    response.append(start)
    
    # Connect bidirectional audio stream
    connect = Connect()
    connect.stream(url=ws_url, track="both_tracks")
    response.append(connect)
    
    return Response(str(response), mimetype="text/xml")

@sock.route("/ws/media")
async def media_stream(ws):
    """
    WebSocket endpoint for Twilio Media Streams API integration with OpenAI Realtime.
    Handles real-time audio from Twilio phone calls with OpenAI's Realtime API.
    """
    try:
        # Generate session ID for this connection
        session_id = str(uuid.uuid4())
        logger.info(f"[MEDIA_STREAM] New media stream connection: {session_id}")
        
        # Initialize the Realtime processor
        realtime_processor = get_realtime_processor()
        logger.info(f"[MEDIA_STREAM] Initialized realtime processor: {id(realtime_processor)}")
        
        # Initialize orchestrated agents
        try:
            frontline = init_agents()
            logger.info(f"[MEDIA_STREAM] Initialized agents for session: {session_id}")
        except Exception as e:
            logger.error(f"[MEDIA_STREAM] Failed to initialize agents: {str(e)}")
            await ws.send(json.dumps({
                "type": "error",
                "error": "Failed to initialize agents",
                "timestamp": time.time()
            }))
            return
        
        # Send connection confirmation to client
        await ws.send(json.dumps({
            "type": "connected",
            "session_id": session_id,
            "timestamp": time.time(),
            "message": "Connected to Red Bar Sushi AI system"
        }))
        
        # Store messages from Twilio
        twilio_messages = []
        
        # Store audio data from Twilio in a queue
        incoming_audio_queue = asyncio.Queue()
        
        # Process Twilio Media Streams messages
        async def process_twilio_messages():
            try:
                while True:
                    message = await ws.receive()
                    
                    # Handle different message types from Twilio
                    if isinstance(message, str):
                        try:
                            data = json.loads(message)
                            twilio_messages.append(data)
                            
                            if data.get("event") == "start":
                                logger.info(f"[MEDIA_STREAM] Media stream started: {data}")
                                # Initialize FSM state
                                fsm_orchestrator.set_state(session_id, FSMState.GREETING)
                                # Initialize other state tracking
                                slot_store.register_slot(session_id, "customer_name", required=True)
                                slot_store.register_slot(session_id, "order_type", required=True)
                                
                            elif data.get("event") == "stop":
                                logger.info(f"[MEDIA_STREAM] Media stream stopped: {data}")
                                break
                                
                            elif data.get("event") == "media":
                                # Process media chunk
                                payload = data.get("media", {}).get("payload")
                                if payload:
                                    # Decode base64 audio
                                    audio_chunk = base64.b64decode(payload)
                                    # Add to queue for processing
                                    await incoming_audio_queue.put(audio_chunk)
                                    
                            elif data.get("event") == "mark":
                                # Handle mark events (Twilio control events)
                                logger.info(f"[MEDIA_STREAM] Mark event: {data}")
                                
                        except json.JSONDecodeError as e:
                            logger.warning(f"[MEDIA_STREAM] Failed to parse JSON message: {e}")
                    elif isinstance(message, bytes):
                        # Handle raw audio data
                        await incoming_audio_queue.put(message)
                    
            except Exception as e:
                logger.error(f"[MEDIA_STREAM] Error processing Twilio messages: {str(e)}")
                logger.error(traceback.format_exc())
        
        # Start processing Twilio messages
        twilio_task = asyncio.create_task(process_twilio_messages())
        
        # Track if we've sent an initial greeting
        greeting_sent = False
        
        # Process incoming audio with Realtime API
        try:
            async def audio_generator():
                while True:
                    try:
                        audio_chunk = await incoming_audio_queue.get()
                        yield audio_chunk
                    except Exception as e:
                        logger.error(f"[MEDIA_STREAM] Error getting audio chunk: {e}")
                        break
            
            # Process the media stream
            async for event in realtime_processor.process_media_stream(audio_generator(), session_id):
                # Handle different event types
                event_type = event.get("type", "")
                
                if event_type == "transcript_complete":
                    # Process complete transcript with frontline agent
                    transcript = event.get("text", "")
                    if transcript:
                        logger.info(f"[MEDIA_STREAM] Processing transcript: {transcript}")
                        
                        # Process with orchestrated agent
                        agent_response = frontline.process_voice_input(session_id, transcript)
                        
                        # Send transcript to client
                        await ws.send(json.dumps({
                            "event": "transcript",
                            "transcript": transcript,
                            "timestamp": time.time()
                        }))
                        
                        # Send agent response to client
                        await ws.send(json.dumps({
                            "event": "message",
                            "text": agent_response,
                            "timestamp": time.time()
                        }))
                        
                        # Generate TTS audio from response
                        await ws.send(json.dumps({
                            "event": "media",
                            "streamSid": session_id,
                            "media": {
                                "payload": base64.b64encode(agent_response.encode('utf-8')).decode('utf-8')
                            }
                        }))
                
                elif event_type == "tool_call":
                    # Handle tool calls from the model
                    tool_name = event.get("name", "")
                    tool_arguments = event.get("arguments", {})
                    tool_id = event.get("id", "")
                    
                    logger.info(f"[MEDIA_STREAM] Tool call: {tool_name} with args: {tool_arguments}")
                    
                    # Execute tool with frontline agent through registry
                    try:
                        if tool_registry and tool_name in tool_registry.tools:
                            tool_result = tool_registry.execute_tool(
                                tool_name, 
                                tool_arguments, 
                                session_id=session_id
                            )
                            
                            # Send tool result back to WebSocket
                            await ws.send(json.dumps({
                                "event": "tool_result",
                                "name": tool_name,
                                "result": tool_result,
                                "timestamp": time.time()
                            }))
                    except Exception as tool_error:
                        logger.error(f"[MEDIA_STREAM] Error executing tool {tool_name}: {tool_error}")
                        logger.error(traceback.format_exc())
                
                elif event_type == "silence_detected":
                    # Handle silence detection
                    logger.info(f"[MEDIA_STREAM] Silence detected")
                    
                    # Get current FSM state
                    current_state = fsm_orchestrator.get_current_state(session_id)
                    
                    # Generate appropriate response based on state
                    if not greeting_sent:
                        # Send initial greeting if none sent yet
                        greeting = "Welcome to Red Bar Sushi. How can I help you today?"
                        
                        # Send greeting to client
                        await ws.send(json.dumps({
                            "event": "message",
                            "text": greeting,
                            "timestamp": time.time()
                        }))
                        
                        # Convert greeting to audio (base64 for now)
                        await ws.send(json.dumps({
                            "event": "media",
                            "streamSid": session_id,
                            "media": {
                                "payload": base64.b64encode(greeting.encode('utf-8')).decode('utf-8')
                            }
                        }))
                        
                        greeting_sent = True
                    elif current_state == FSMState.GREETING:
                        # In greeting state, prompt for name
                        prompt = "Could you please tell me your name?"
                        
                        # Send prompt to client
                        await ws.send(json.dumps({
                            "event": "message",
                            "text": prompt,
                            "timestamp": time.time()
                        }))
                        
                        # Convert prompt to audio (base64 for now)
                        await ws.send(json.dumps({
                            "event": "media",
                            "streamSid": session_id,
                            "media": {
                                "payload": base64.b64encode(prompt.encode('utf-8')).decode('utf-8')
                            }
                        }))
                    else:
                        # Generic prompt based on state
                        prompt = "Is there anything else I can help you with?"
                        
                        # Send prompt to client
                        await ws.send(json.dumps({
                            "event": "message",
                            "text": prompt,
                            "timestamp": time.time()
                        }))
                        
                        # Convert prompt to audio (base64 for now)
                        await ws.send(json.dumps({
                            "event": "media",
                            "streamSid": session_id,
                            "media": {
                                "payload": base64.b64encode(prompt.encode('utf-8')).decode('utf-8')
                            }
                        }))
                
                elif event_type == "audio":
                    # Handle audio data for TTS response
                    audio_data = event.get("data", "")
                    if audio_data:
                        # Forward audio to Twilio
                        await ws.send(json.dumps({
                            "event": "media",
                            "streamSid": session_id,
                            "media": {
                                "payload": audio_data
                            }
                        }))
        
        except Exception as e:
            logger.error(f"[MEDIA_STREAM] Error in media stream processing: {str(e)}")
            logger.error(traceback.format_exc())
        
        # Cancel Twilio task if still running
        if not twilio_task.done():
            twilio_task.cancel()
        
        logger.info(f"[MEDIA_STREAM] WebSocket session complete: {session_id}")
    
    except Exception as e:
        logger.error(f"[MEDIA_STREAM] Error in media stream: {str(e)}")
        logger.error(traceback.format_exc())
        try:
            await ws.close()
        except:
            pass

@realtime_voice_bp.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint for the Realtime voice routes.
    Verifies that the agents and Realtime API components are properly initialized.
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
            agent_graph and slot_store and fsm_orchestrator and model_escalator and tool_registry
        ) else "missing_components"
    except Exception as e:
        orchestration_status = f"error: {str(e)}"
    
    # Check Realtime processor
    try:
        realtime_processor = get_realtime_processor()
        realtime_status = "available" if realtime_processor else "unavailable"
    except Exception as e:
        realtime_status = f"error: {str(e)}"
    
    return jsonify({
        "status": "ok" if agent_status == "initialized" and 
                        orchestration_status == "all_components_available" and
                        realtime_status == "available" else "error",
        "service": "voice_orchestrated_realtime",
        "agents": agent_status,
        "orchestration": orchestration_status,
        "realtime": realtime_status,
        "timestamp": time.time()
    })

@realtime_voice_bp.route("/demo", methods=["GET"])
def demo_page():
    """
    Serve the realtime demo page.
    """
    return render_template("realtime_demo.html")