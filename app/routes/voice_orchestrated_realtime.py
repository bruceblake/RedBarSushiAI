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
import sys
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

# Import enhanced diagnostics
from app.utils.enhanced_diagnostics import (
    log_websocket_handshake,
    log_websocket_message,
    send_heartbeat,
    log_system_status,
    log_audio_processing_stats,
    log_realtime_session_details,
    check_redis_connection
)

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
    
    # Log all registered routes at startup to help diagnose routing issues
    try:
        from flask import current_app
        
        # Log WebSocket routes
        if hasattr(current_app, 'websocket'):
            logger.critical("======== REGISTERED WEBSOCKET ROUTES ========")
            all_ws_routes = list(current_app.websocket.url_map.iter_rules())
            logger.critical(f"Total WebSocket routes: {len(all_ws_routes)}")
            for rule in all_ws_routes:
                logger.critical(f"WebSocket route: {rule.rule} - Endpoint: {rule.endpoint}")
            logger.critical("=========================================")
            
        # Log Flask routes
        logger.critical("======== REGISTERED FLASK ROUTES ========")
        all_routes = list(current_app.url_map.iter_rules())
        logger.critical(f"Total Flask routes: {len(all_routes)}")
        for rule in all_routes:
            logger.critical(f"Route: {rule.rule} - Methods: {rule.methods} - Endpoint: {rule.endpoint}")
        logger.critical("=========================================")
        
    except Exception as e:
        logger.critical(f"Error logging routes: {str(e)}")
    
    # Only initialize once
    if frontline_agent is not None:
        logger.critical("[REALTIME_INIT] Agents already initialized, skipping initialization")
        return
    
    logger.critical("[REALTIME_INIT] Starting orchestrated agent initialization")
    
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


# Add diagnostic debugging function
def diagnostics_output(session_id, context="general"):
    """Output comprehensive diagnostics for troubleshooting."""
    import platform
    import socket
    import psutil
    
    try:
        logger.critical(f"========== VOICE MEDIA DIAGNOSTICS [{context}] ==========")
        logger.critical(f"Session ID: {session_id}")
        logger.critical(f"Timestamp: {time.time()}")
        
        # System info
        logger.critical(f"Python version: {sys.version}")
        logger.critical(f"Platform: {platform.platform()}")
        logger.critical(f"Hostname: {socket.gethostname()}")
        
        # Process info
        process = psutil.Process()
        logger.critical(f"Process ID: {process.pid}")
        logger.critical(f"Process CPU: {process.cpu_percent()}%")
        logger.critical(f"Process memory: {process.memory_info().rss / (1024 * 1024):.1f} MB")
        
        # Network info
        net_connections = process.connections()
        logger.critical(f"Active network connections: {len(net_connections)}")
        
        # Redis connectivity
        try:
            from app.utils.conversation_store import redis_client
            if redis_client and redis_client.ping():
                logger.critical(f"Redis connectivity: OK")
            else:
                logger.critical(f"Redis connectivity: FAILED")
        except Exception as e:
            logger.critical(f"Redis connectivity check error: {e}")
        
        # Database connectivity
        try:
            from app.db import db
            db_ok = False
            with db.engine.connect() as conn:
                result = conn.execute("SELECT 1")
                db_ok = result.scalar() == 1
            logger.critical(f"Database connectivity: {'OK' if db_ok else 'FAILED'}")
        except Exception as e:
            logger.critical(f"Database connectivity check error: {e}")
        
        # Thread info
        import threading
        logger.critical(f"Active threads: {threading.active_count()}")
        
        # Asyncio task info
        try:
            tasks = asyncio.all_tasks()
            logger.critical(f"Active asyncio tasks: {len(tasks)}")
        except Exception as e:
            logger.critical(f"Asyncio task check error: {e}")
        
        logger.critical(f"========== END DIAGNOSTICS ==========")
    except Exception as e:
        logger.error(f"Error generating diagnostics: {e}")

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

@realtime_voice_bp.route("/debug", methods=["GET"])
def debug_websocket_config():
    """Debug endpoint to show WebSocket configuration."""
    import subprocess
    import json
    
    try:
        # Run the debug_websocket.py script
        result = subprocess.run(
            ["/home/proxyie/MySoftware/RedBarSushiAI/debug_websocket.py"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Return the output
        output = {
            "status": "success" if result.returncode == 0 else "error",
            "output": result.stdout,
            "error": result.stderr if result.stderr else None
        }
        
        return jsonify(output)
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        })

@realtime_voice_bp.route("/", methods=["GET", "POST"])
def receive_call():
    """
    Handle an incoming voice call with the Realtime API integration.
    Uses Twilio Media Streams for real-time audio processing.
    """
    # Create a log file for this specific call
    call_sid = request.values.get("CallSid", str(uuid.uuid4()))
    log_dir = os.path.join(os.getcwd(), 'logs')
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except:
            pass  # If we can't create the dir, we'll fallback to default logging
    
    # Set up call-specific logging
    try:
        # Create a call-specific file handler
        call_log_file = os.path.join(log_dir, f'call_{call_sid}.log')
        call_file_handler = logging.FileHandler(call_log_file)
        call_file_handler.setLevel(logging.DEBUG)
        call_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
        call_file_handler.setFormatter(call_formatter)
        logger.addHandler(call_file_handler)
        
        # Also log to a common calls log file
        calls_log_file = os.path.join(log_dir, 'incoming_calls.log')
        calls_file_handler = logging.FileHandler(calls_log_file)
        calls_file_handler.setLevel(logging.INFO)
        calls_file_handler.setFormatter(call_formatter)
        logger.addHandler(calls_file_handler)
        
        logger.info(f"================== NEW CALL RECEIVED - SID: {call_sid} ==================")
    except Exception as log_error:
        logger.error(f"Failed to set up call-specific logging: {log_error}")
    
    try:
        # Log extensive details about the request to diagnose routing issues
        logger.info("==== INCOMING REALTIME CALL DETAILS ====")
        logger.info(f"Call SID: {call_sid}")
        logger.info(f"Request came from: {request.remote_addr}")
        logger.info(f"User agent: {request.user_agent}")
        logger.info(f"Host header: {request.host}")
        logger.info(f"URL: {request.url}")
        logger.info(f"Base URL: {request.base_url}")
        logger.info(f"Request method: {request.method}")
        logger.info(f"Environment: {os.environ.get('FLASK_ENV', 'undefined')}")
        logger.info(f"Is this staging?: {os.environ.get('IS_STAGING', 'No, not explicitly marked as staging')}")
        logger.info(f"Current working directory: {os.getcwd()}")
        
        # Log all request values for debugging
        logger.info("Full request values:")
        for key, value in request.values.items():
            logger.info(f"  - {key}: {value}")
            
        # Log all request headers
        logger.info("Request headers:")
        for name, value in request.headers:
            logger.info(f"  - {name}: {value}")
            
        # Log request form data if any
        if request.form:
            logger.info("Form data:")
            for key, value in request.form.items():
                logger.info(f"  - {key}: {value}")
                
        # Log request args if any
        if request.args:
            logger.info("URL parameters:")
            for key, value in request.args.items():
                logger.info(f"  - {key}: {value}")
                
        logger.info("==== END CALL DETAILS ====")
        
        # Get call details from Twilio
        caller_number = request.values.get("From", "")
        
        # Log the timestamp for timing analysis
        start_time = time.time()
        logger.info(f"Call handling start time: {start_time}")
        
        # Add an environment identifier to make it clear which environment is responding
        env_name = "STAGING" if os.environ.get("IS_STAGING") or os.environ.get("FLASK_ENV") == "staging" else "PRODUCTION"
        logger.info(f"Environment identified as: {env_name}")
        
        # Create WebSocket URL for Media Streams
        # Direct Twilio to the exact same hostname that it reached us on
        # This avoids potential DNS resolution issues
        host = request.headers.get('Host') or request.host
        logger.critical(f"[WEBSOCKET URL] Request host: {host}")
        logger.critical(f"[WEBSOCKET URL] Request headers host: {request.headers.get('Host', 'not-found')}")
        
        # Log all request and host information
        logger.critical(f"[WEBSOCKET URL] Request is_secure: {request.is_secure}")
        logger.critical(f"[WEBSOCKET URL] Request.url: {request.url}")
        logger.critical(f"[WEBSOCKET URL] Request.base_url: {request.base_url}")
        logger.critical(f"[WEBSOCKET URL] Request.host_url: {request.host_url}")
        logger.critical(f"[WEBSOCKET URL] Request.remote_addr: {request.remote_addr}")
        logger.critical(f"[WEBSOCKET URL] X-Forwarded-Host: {request.headers.get('X-Forwarded-Host', 'not-found')}")
        logger.critical(f"[WEBSOCKET URL] X-Forwarded-Proto: {request.headers.get('X-Forwarded-Proto', 'not-found')}")
        logger.critical(f"[WEBSOCKET URL] CF-Connecting-IP: {request.headers.get('CF-Connecting-IP', 'not-found')}")
        logger.critical(f"[WEBSOCKET URL] True-Client-IP: {request.headers.get('True-Client-IP', 'not-found')}")
        logger.critical(f"[WEBSOCKET URL] X-Forwarded-For: {request.headers.get('X-Forwarded-For', 'not-found')}")
        
        # For Render, we need to use the public-facing hostname
        render_external_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
        if render_external_hostname:
            logger.critical(f"[WEBSOCKET URL] Found RENDER_EXTERNAL_HOSTNAME: {render_external_hostname}")
            host = render_external_hostname
            
        # Always use wss:// in production or staging environment
        # More robust environment detection, including checking host for staging/prod indicators 
        is_prod_or_staging = (os.environ.get("FLASK_ENV") in ["production", "staging"] or 
                             os.environ.get("IS_STAGING") or 
                             "staging" in host or "production" in host or
                             ".onrender.com" in host or  # Render is always production/staging
                             os.environ.get("RENDER") or
                             os.environ.get("RENDER_SERVICE_ID"))
        
        # Consider any request to a .onrender.com domain as HTTPS
        is_https_request = request.is_secure or "https" in request.base_url or ".onrender.com" in host
        
        # Log environment detection variables
        logger.critical(f"[WEBSOCKET URL] FLASK_ENV: {os.environ.get('FLASK_ENV', 'not-set')}")
        logger.critical(f"[WEBSOCKET URL] IS_STAGING: {os.environ.get('IS_STAGING', 'not-set')}")
        logger.critical(f"[WEBSOCKET URL] 'staging' in host: {'staging' in host}")
        logger.critical(f"[WEBSOCKET URL] 'production' in host: {'production' in host}")
        logger.critical(f"[WEBSOCKET URL] '.onrender.com' in host: {'.onrender.com' in host}")
        logger.critical(f"[WEBSOCKET URL] RENDER env var: {os.environ.get('RENDER', 'not-set')}")
        logger.critical(f"[WEBSOCKET URL] RENDER_SERVICE_ID env var: {os.environ.get('RENDER_SERVICE_ID', 'not-set')}")
        logger.critical(f"[WEBSOCKET URL] is_prod_or_staging result: {is_prod_or_staging}")
        logger.critical(f"[WEBSOCKET URL] is_https_request result: {is_https_request}")
        
        # ALWAYS use wss:// for Twilio Media Streams when in Render or any production environment
        # Twilio requires secure WebSockets
        protocol = "wss"  # Force wss:// for Twilio Media Streams
        
        # Try both WebSocket routes - the debug route is more likely to work if there's an issue
        # with the more complex media route
        ws_media_url = f"{protocol}://{host}/ws/voice/media"
        ws_debug_url = f"{protocol}://{host}/ws/voice/debug"
        
        # Use the debug URL for testing if we see issues
        ws_url = ws_media_url
        
        # Log more details about the WebSocket URL
        logger.critical(f"[WEBSOCKET URL] Final WebSocket URL: {ws_url}")
        logger.critical(f"[WEBSOCKET URL] Protocol used: {protocol}")
        logger.critical(f"[WEBSOCKET URL] Debug URL available at: {ws_debug_url}")
        logger.info(f"WebSocket URL for Media Streams: {ws_url} (Environment: {os.environ.get('FLASK_ENV', 'unknown')}, is_prod_or_staging: {is_prod_or_staging}, is_https_request: {is_https_request})")
        
        # Initialize TwiML response with Media Streams
        response = VoiceResponse()
        logger.info("Creating TwiML response with Media Streams")
        
        # Start by informing the caller which environment they're connected to
        # This happens before the Stream is connected
        greeting_message = f"Welcome to {env_name} Red Bar Sushi AI ordering system."
        logger.info(f"Initial greeting: '{greeting_message}'")
        logger.critical(f"[TWIML] Initial greeting: '{greeting_message}'")
        response.say(greeting_message)
        
        # Log detailed information to help diagnose WebSocket issues
        logger.critical("============== DETAILED DEBUG INFO ==============")
        logger.critical(f"[WEBSOCKET_DEBUG] Call SID: {call_sid}")
        logger.critical(f"[WEBSOCKET_DEBUG] WebSocket URL: {ws_url}")
        logger.critical(f"[WEBSOCKET_DEBUG] Environment: {env_name}")
        logger.critical(f"[WEBSOCKET_DEBUG] Flask app name: {__name__}")
        
        # Log available Flask routes
        try:
            from flask import current_app
            logger.critical("[WEBSOCKET_DEBUG] Listing all WebSocket routes:")
            if hasattr(current_app, 'websocket'):
                for rule in current_app.websocket.url_map.iter_rules():
                    logger.critical(f"[WEBSOCKET_DEBUG] WebSocket route: {rule.rule} → {rule.endpoint}")
            
            # Log info about the WebSocket handler
            ws_handlers = [rule for rule in current_app.websocket.url_map.iter_rules() if rule.rule == '/ws/voice/media']
            if ws_handlers:
                logger.critical(f"[WEBSOCKET_DEBUG] Found WebSocket handler for /ws/voice/media: {ws_handlers[0].endpoint}")
            else:
                logger.critical("[WEBSOCKET_DEBUG] *** No WebSocket handler found for /ws/voice/media ***")
        except Exception as route_error:
            logger.critical(f"[WEBSOCKET_DEBUG] Error listing routes: {str(route_error)}")
        
        # Debug Twilio WebSocket client settings
        logger.critical("[WEBSOCKET_DEBUG] Twilio WebSocket client settings:")
        logger.critical(f"[WEBSOCKET_DEBUG] User-Agent: {request.headers.get('User-Agent', 'Not found')}")
        logger.critical(f"[WEBSOCKET_DEBUG] Origin: {request.headers.get('Origin', 'Not found')}")
        logger.critical(f"[WEBSOCKET_DEBUG] X-Twilio-Signature: {request.headers.get('X-Twilio-Signature', 'Not found')}")
        
        # Log server information
        import platform
        import socket
        logger.critical(f"[WEBSOCKET_DEBUG] Server Python version: {platform.python_version()}")
        logger.critical(f"[WEBSOCKET_DEBUG] Server OS: {platform.platform()}")
        logger.critical(f"[WEBSOCKET_DEBUG] Server hostname: {socket.gethostname()}")
        logger.critical(f"[WEBSOCKET_DEBUG] Server IP address: {socket.gethostbyname(socket.gethostname())}")
        logger.critical("===================================================")
        
        # Start Media Stream with the WebSocket endpoint
        logger.info(f"Adding Media Stream start with URL: {ws_url}, track: inbound_track")
        logger.critical(f"[TWIML] Adding Media Stream start with URL: {ws_url}, track: inbound_track")
        start = Start()
        start.stream(url=ws_url, track="inbound_track")
        response.append(start)
        
        # Connect bidirectional audio stream
        logger.info(f"Adding Media Stream connect with URL: {ws_url}, track: both_tracks")
        logger.critical(f"[TWIML] Adding Media Stream connect with URL: {ws_url}, track: both_tracks")
        connect = Connect()
        connect.stream(url=ws_url, track="both_tracks")
        response.append(connect)
        
        # Log the generated TwiML for debugging
        twiml_response = str(response)
        logger.info(f"Generated TwiML response: {twiml_response}")
        
        # Log the response generation time
        end_time = time.time()
        processing_time = end_time - start_time
        logger.info(f"TwiML response generated in {processing_time:.3f} seconds")
        
        # Remove the handlers to prevent logging to this file for other requests
        if 'call_file_handler' in locals():
            logger.removeHandler(call_file_handler)
        if 'calls_file_handler' in locals():
            logger.removeHandler(calls_file_handler)
            
        return Response(twiml_response, mimetype="text/xml")
        
    except Exception as e:
        logger.error(f"Error handling incoming call: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Try to generate an error response
        try:
            error_response = VoiceResponse()
            error_response.say("We're sorry, but an error occurred while processing your call. Please try again later.")
            return Response(str(error_response), mimetype="text/xml")
        except:
            return Response("Error processing call", status=500)
            
    finally:
        # Clean up the handlers
        try:
            if 'call_file_handler' in locals():
                logger.removeHandler(call_file_handler)
            if 'calls_file_handler' in locals():
                logger.removeHandler(calls_file_handler)
        except:
            pass

@sock.route("/ws/voice/media")  # Explicitly set websocket=True
async def media_stream(ws):
    """
    WebSocket endpoint for Twilio Media Streams API integration with OpenAI Realtime.
    Handles real-time audio from Twilio phone calls with OpenAI's Realtime API.
    """
    # Log detailed connection info to make diagnosing WebSocket issues easier
    connection_time = time.time()
    connection_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())  # This will be used for all logging
    keepalive_task = None  # Will hold the keep-alive task when created
    
    print(f"⚡⚡⚡ [WEBSOCKET CONNECTION] New connection at {connection_time}, ID: {session_id} ⚡⚡⚡")
    logger.critical(f"⚡⚡⚡ [WEBSOCKET CONNECTION] New WebSocket connection to /ws/voice/media at {connection_time}, ID: {session_id} ⚡⚡⚡")
    
    # Create immediately a comprehensive log of system status
    log_system_status(session_id, "websocket_connect")
    
    # Set up enhanced logging for this session
    log_dir = os.path.join(os.getcwd(), 'logs')
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except:
            pass  # If we can't create the dir, we'll fallback to default logging
    
    try:
        # Create a session-specific file handler
        session_log_file = os.path.join(log_dir, f'media_stream_{session_id}.log')
        session_file_handler = logging.FileHandler(session_log_file)
        session_file_handler.setLevel(logging.DEBUG)
        session_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
        session_file_handler.setFormatter(session_formatter)
        logger.addHandler(session_file_handler)
        
        # Also log to a common WebSocket log file
        ws_log_file = os.path.join(log_dir, 'websocket_connections.log')
        ws_file_handler = logging.FileHandler(ws_log_file)
        ws_file_handler.setLevel(logging.INFO)
        ws_file_handler.setFormatter(session_formatter)
        logger.addHandler(ws_file_handler)
        
        logger.info(f"███████████████████████████████████████████████████████████████")
        logger.info(f"████ NEW WEBSOCKET CONNECTION - SESSION ID: {session_id} ████")
        logger.info(f"███████████████████████████████████████████████████████████████")
    except Exception as log_error:
        logger.error(f"Failed to set up session-specific logging: {log_error}")
    
    # Log WebSocket handshake details
    try:
        if hasattr(ws, 'request'):
            log_websocket_handshake(ws.request, "post-upgrade")
        
        logger.critical(f"[WEBSOCKET DEBUG] WebSocket object type: {type(ws).__name__}")
        logger.critical(f"[WEBSOCKET DEBUG] WebSocket object methods: {[method for method in dir(ws) if not method.startswith('_') and callable(getattr(ws, method))]}")
    except Exception as handshake_error:
        logger.error(f"[WEBSOCKET DEBUG] Error logging handshake details: {handshake_error}")
        logger.error(traceback.format_exc())
    
    # Start the keep-alive task to prevent connection timeouts
    try:
        logger.info(f"[WEBSOCKET:{session_id}] Starting keep-alive task")
        keepalive_task = asyncio.create_task(
            send_heartbeat(ws, session_id, interval=10.0),  # Send heartbeat every 10 seconds
            name=f"heartbeat-{session_id}"
        )
        logger.info(f"[WEBSOCKET:{session_id}] Keep-alive task started with 10-second interval")
    except Exception as task_error:
        logger.error(f"[WEBSOCKET:{session_id}] Error starting keep-alive task: {task_error}")
        logger.error(traceback.format_exc())
    
    # Test the WebSocket connection with a simple echo
    try:
        # Send a test message
        logger.critical(f"[WEBSOCKET:{session_id}] Sending connection test message")
        test_msg = json.dumps({
            "type": "connection_test", 
            "time": time.time(), 
            "id": session_id,
            "message": "Testing WebSocket connection"
        })
        await ws.send(test_msg)
        logger.critical(f"[WEBSOCKET:{session_id}] ✅ Successfully sent test message")
        
        # Try to receive an initial message with a short timeout
        try:
            logger.critical(f"[WEBSOCKET:{session_id}] Waiting for initial message (1s timeout)")
            initial_msg = await asyncio.wait_for(ws.receive(), timeout=1.0)
            logger.critical(f"[WEBSOCKET:{session_id}] ✅ Received initial message")
            
            # Log the message using the enhanced logging
            await log_websocket_message(initial_msg, "RECV", "initial", session_id)
        except asyncio.TimeoutError:
            logger.warning(f"[WEBSOCKET:{session_id}] ⚠️ No initial message received within 1 second timeout")
            logger.warning(f"[WEBSOCKET:{session_id}] This is normal if Twilio is waiting to send the first media chunk")
        except Exception as recv_error:
            logger.error(f"[WEBSOCKET:{session_id}] ❌ Error receiving initial message: {recv_error}")
            logger.error(traceback.format_exc())
    except Exception as test_error:
        logger.error(f"[WEBSOCKET:{session_id}] ❌ Error during WebSocket connection test: {test_error}")
        logger.error(traceback.format_exc())
    
    # Now initialize the main WebSocket handling
    try:
        # Track detailed metrics and events
        ws_events = []
        
        # Connection stats 
        metrics = {
            "connection_start_time": time.time(),
            "audio_chunks_received": 0,
            "events_processed": 0,
            "events_sent": 0,
            "silence_events": 0,
            "tool_calls": 0,
            "transcripts_processed": 0,
            "last_activity_time": time.time(),
        }
        
        # Track detailed stats about audio chunks
        audio_stats = {
            "first_chunk_time": None,
            "last_chunk_time": None,
            "min_chunk_size": float('inf'),
            "max_chunk_size": 0,
            "total_audio_size": 0,
            "chunk_count": 0,
            "chunk_sizes": [],
            "transcripts_generated": 0,
            "silence_events": 0
        }
        
        # Function to log the connection summary when it ends
        def log_connection_summary(reason="normal_close"):
            end_time = time.time()
            duration = end_time - metrics["connection_start_time"]
            logger.info("==== WEBSOCKET CONNECTION SUMMARY ====")
            logger.info(f"Session ID: {session_id}")
            logger.info(f"Connection duration: {duration:.2f} seconds")
            logger.info(f"Audio chunks received: {metrics['audio_chunks_received']}")
            logger.info(f"Events processed: {metrics['events_processed']}")
            logger.info(f"Events sent: {metrics['events_sent']}")
            logger.info(f"Silence events: {metrics['silence_events']}")
            logger.info(f"Tool calls: {metrics['tool_calls']}")
            logger.info(f"Transcripts processed: {metrics['transcripts_processed']}")
            logger.info(f"Close reason: {reason}")
            logger.info("==== END WEBSOCKET CONNECTION SUMMARY ====")
            logger.info(f"███████████████████████████████████████████████████████████████")
            logger.info(f"████ WEBSOCKET CONNECTION CLOSED - SESSION ID: {session_id} ████")
            logger.info(f"███████████████████████████████████████████████████████████████")

        try:
            logger.info(f"[MEDIA_STREAM] New media stream connection: {session_id}")
            
            # Initialize the Realtime processor
            # Log first attempt at real-time API initialization
            logger.info(f"[REALTIME:{session_id}] Attempting to initialize OpenAI Realtime processor")
            try:
                realtime_processor = get_realtime_processor()
                
                # Log success and extract configuration
                logger.info(f"[REALTIME:{session_id}] ✅ Successfully initialized realtime processor: {id(realtime_processor)}")
                
                # Get and log the session configuration if available
                if hasattr(realtime_processor, 'get_config'):
                    session_config = realtime_processor.get_config()
                    log_realtime_session_details(session_config, "starting", session_id)
                else:
                    logger.info(f"[REALTIME:{session_id}] Session config not available")
                    
                # Check if we're using the optimized client or fallback
                is_fallback = False
                if hasattr(realtime_processor, 'is_fallback'):
                    is_fallback = realtime_processor.is_fallback
                    logger.critical(f"[REALTIME:{session_id}] Using fallback WebSocket implementation: {is_fallback}")
                
                # If using fallback, log warning and more details
                if is_fallback:
                    logger.warning(f"[REALTIME:{session_id}] ⚠️ USING FALLBACK WEBSOCKET IMPLEMENTATION")
                    logger.warning(f"[REALTIME:{session_id}] The optimized OpenAI Realtime client is not available")
                    logger.warning(f"[REALTIME:{session_id}] This may cause issues with audio processing and VAD")
                    
                    # Log platform details to help diagnose why optimized client isn't available
                    import platform
                    logger.warning(f"[REALTIME:{session_id}] Platform details: {platform.platform()}")
                    logger.warning(f"[REALTIME:{session_id}] Python architecture: {platform.architecture()}")
                    logger.warning(f"[REALTIME:{session_id}] Machine: {platform.machine()}")
                    logger.warning(f"[REALTIME:{session_id}] Python implementation: {platform.python_implementation()}")
                    
            except Exception as rt_error:
                logger.error(f"[REALTIME:{session_id}] ❌ Failed to initialize Realtime processor: {rt_error}")
                logger.error(f"[REALTIME:{session_id}] Initialization error trace: {traceback.format_exc()}")
                raise RuntimeError(f"Failed to initialize OpenAI Realtime processor: {rt_error}")
        
            # Initialize orchestrated agents
            try:
                logger.info(f"[AGENT:{session_id}] Initializing orchestrated agents")
                frontline = init_agents()
                logger.info(f"[AGENT:{session_id}] ✅ Agents initialized successfully")
                logger.info(f"[AGENT:{session_id}] Agent type: {type(frontline).__name__}")
                
                # Log agent capabilities for debugging
                if hasattr(frontline, 'get_capabilities'):
                    capabilities = frontline.get_capabilities()
                    logger.info(f"[AGENT:{session_id}] Agent capabilities: {capabilities}")
                    
                # Log agent configuration if available
                if hasattr(frontline, 'config'):
                    logger.info(f"[AGENT:{session_id}] Agent config: {frontline.config}")
                    
                # Log agent model if available
                if hasattr(frontline, 'model'):
                    logger.info(f"[AGENT:{session_id}] Agent model: {frontline.model}")
                
                # Check Redis connection health
                try:
                    from app.utils.conversation_store import redis_client
                    if redis_client:
                        redis_health = check_redis_connection(redis_client, session_id)
                        logger.info(f"[AGENT:{session_id}] Redis connection health check: {'✅ Healthy' if redis_health else '❌ Unhealthy'}")
                except Exception as redis_error:
                    logger.error(f"[AGENT:{session_id}] ⚠️ Redis check error: {redis_error}")
                
                # Send connection confirmation to client
                confirm_msg = {
                    "type": "connected",
                    "session_id": session_id,
                    "timestamp": time.time(),
                    "message": "Connected to Red Bar Sushi AI system"
                }
                logger.info(f"[WEBSOCKET:{session_id}] Sending connection confirmation")
                await ws.send(json.dumps(confirm_msg))
                await log_websocket_message(json.dumps(confirm_msg), "SEND", "connected", session_id)
                metrics["events_sent"] += 1
            except Exception as e:
                logger.error(f"[MEDIA_STREAM] ❌ Failed to initialize agents: {str(e)}")
                logger.error(f"[MEDIA_STREAM] Agent initialization error trace: {traceback.format_exc()}")
                
                # Send detailed error info to client
                await ws.send(json.dumps({
                    "type": "error",
                    "error": f"Failed to initialize agents: {str(e)}",
                    "timestamp": time.time(),
                    "details": traceback.format_exc(),
                    "session_id": session_id
                }))
                log_connection_summary("agent_initialization_failed")
                return
            
            # Store messages from Twilio
            twilio_messages = []
            
            # Store audio data from Twilio in a queue
            incoming_audio_queue = asyncio.Queue()
            
            # Track detailed stats about audio chunks
            audio_stats = {
                "first_chunk_time": None,
                "last_chunk_time": None,
                "min_chunk_size": float('inf'),
                "max_chunk_size": 0,
                "total_audio_size": 0,
                "chunk_sizes": []
            }
            
            # Process Twilio Media Streams messages
            async def process_twilio_messages():
                try:
                    logger.info(f"[MEDIA_STREAM] Starting Twilio message processor")
                    twilio_start_time = time.time()
                    message_count = 0
                    
                    # Save the time of key events for diagnostic purposes
                    diagnostic_events = {
                        "first_audio_received": None,
                        "first_transcript_received": None,
                        "greeting_sent": None
                    }
                
                    message_count = 0
                    logger.info("[MEDIA_STREAM] Starting Twilio message processing task")
                    
                    while True:
                        try:
                            message = await asyncio.wait_for(ws.receive(), timeout=30.0)
                            message_count += 1
                            metrics["last_activity_time"] = time.time()
                            
                            # Handle different message types from Twilio
                            if isinstance(message, str):
                                try:
                                    data = json.loads(message)
                                    event_type = data.get("event", "unknown")
                                    
                                    # Log the received message with appropriate detail level
                                    if event_type == "media":
                                        # For media events, just log that we received one to reduce noise
                                        if message_count % 20 == 0:  # Log only every 20th media message
                                            logger.debug(f"[MEDIA_STREAM] Received media event #{message_count}")
                                    else:
                                        # For non-media events, log the full event
                                        logger.info(f"[MEDIA_STREAM] Received Twilio event: {event_type}")
                                        logger.debug(f"[MEDIA_STREAM] Full event data: {data}")
                                
                                    # Keep track of all control messages
                                    if event_type != "media":
                                        twilio_messages.append(data)
                                    
                                    # Handle specific event types
                                    if event_type == "start":
                                        logger.info(f"[MEDIA_STREAM] Media stream started: {data}")
                                        # Log media format for debugging
                                        if "start" in data:
                                            media_format = data["start"].get("mediaFormat", {})
                                            logger.info(f"[MEDIA_STREAM] Media format: {media_format}")
                                        
                                        # Initialize FSM state
                                        logger.info("[MEDIA_STREAM] Setting initial FSM state: GREETING")
                                        fsm_orchestrator.set_state(session_id, FSMState.GREETING)
                                        
                                        # Initialize other state tracking
                                        logger.info("[MEDIA_STREAM] Registering slots for customer data")
                                        slot_store.register_slot(session_id, "customer_name", required=True)
                                        slot_store.register_slot(session_id, "order_type", required=True)
                                    
                                    elif event_type == "stop":
                                        logger.info(f"[MEDIA_STREAM] Media stream stopped: {data}")
                                        logger.info("[MEDIA_STREAM] Twilio requested stream stop")
                                        break
                                        
                                    elif event_type == "media":
                                        # Process media chunk
                                        payload = data.get("media", {}).get("payload")
                                        if payload:
                                            try:
                                                # Decode base64 audio
                                                audio_chunk = base64.b64decode(payload)
                                                chunk_size = len(audio_chunk)
                                                metrics["audio_chunks_received"] += 1
                                                
                                                # Track audio stats
                                                now = time.time()
                                                if audio_stats["first_chunk_time"] is None:
                                                    audio_stats["first_chunk_time"] = now
                                                audio_stats["last_chunk_time"] = now
                                                audio_stats["min_chunk_size"] = min(audio_stats["min_chunk_size"], chunk_size)
                                                audio_stats["max_chunk_size"] = max(audio_stats["max_chunk_size"], chunk_size)
                                                audio_stats["total_audio_size"] += chunk_size
                                                audio_stats["chunk_sizes"].append(chunk_size)
                                                
                                                # Add to queue for processing
                                                await incoming_audio_queue.put(audio_chunk)
                                                
                                                # Every 20th chunk, send a heartbeat that specifically indicates the audio stream
                                                # is still active and being processed
                                                if metrics["audio_chunks_received"] % 20 == 0:
                                                    try:
                                                        audio_heartbeat = {
                                                            "type": "audio_heartbeat",
                                                            "chunk_count": metrics["audio_chunks_received"],
                                                            "session_id": session_id,
                                                            "timestamp": time.time()
                                                        }
                                                        await ws.send(json.dumps(audio_heartbeat))
                                                    except Exception as hb_error:
                                                        logger.warning(f"[AUDIO:{session_id}] Could not send audio heartbeat: {hb_error}")
                                                
                                                # Log audio stats periodically
                                                if metrics["audio_chunks_received"] % 100 == 0:
                                                    # Calculate average chunk size from the last 100 chunks
                                                    recent_chunks = audio_stats["chunk_sizes"][-100:]
                                                    avg_chunk_size = sum(recent_chunks) / len(recent_chunks)
                                                    
                                                    # Calculate audio rate
                                                    audio_duration = audio_stats["last_chunk_time"] - audio_stats["first_chunk_time"]
                                                    if audio_duration > 0:
                                                        chunks_per_second = metrics["audio_chunks_received"] / audio_duration
                                                        bytes_per_second = audio_stats["total_audio_size"] / audio_duration
                                                        
                                                        logger.info(f"[AUDIO:{session_id}] Stats: {metrics['audio_chunks_received']} chunks, " 
                                                                    f"avg size: {avg_chunk_size:.1f} bytes, "
                                                                    f"rate: {chunks_per_second:.1f} chunks/sec, "
                                                                    f"{bytes_per_second:.1f} bytes/sec")
                                                        
                                                        # Every 500 chunks, log comprehensive audio stats
                                                        if metrics["audio_chunks_received"] % 500 == 0:
                                                            log_audio_processing_stats(audio_stats, session_id)
                                            
                                                # Count this message
                                                message_count += 1
                                                
                                                # Track key diagnostic events
                                                if message.get("event") == "media" and diagnostic_events["first_audio_received"] is None:
                                                    diagnostic_events["first_audio_received"] = time.time() - twilio_start_time
                                                    logger.info(f"[MEDIA_STREAM] First audio received after {diagnostic_events['first_audio_received']:.3f}s")
                                                    
                                                if message.get("event") == "transcript" and diagnostic_events["first_transcript_received"] is None:
                                                    diagnostic_events["first_transcript_received"] = time.time() - twilio_start_time
                                                    logger.info(f"[MEDIA_STREAM] First transcript received after {diagnostic_events['first_transcript_received']:.3f}s")
                                                
                                                # Periodically log status
                                                if message_count % 20 == 0:
                                                    elapsed = time.time() - twilio_start_time
                                                    rate = message_count / elapsed if elapsed > 0 else 0
                                                    logger.info(f"[MEDIA_STREAM] Twilio message stats: {message_count} messages, {elapsed:.1f}s, {rate:.1f} msg/sec")
        except Exception as decode_error:
                                                logger.error(f"[MEDIA_STREAM] Error decoding audio: {decode_error}")
                                        else:
                                            logger.warning("[MEDIA_STREAM] Received media event with empty payload")
                                    
                                    elif event_type == "mark":
                                        # Handle mark events (Twilio control events)
                                        logger.info(f"[MEDIA_STREAM] Mark event: {data}")
                                    
                                except json.JSONDecodeError as e:
                                    logger.warning(f"[MEDIA_STREAM] Failed to parse JSON message: {e}")
                                    logger.warning(f"[MEDIA_STREAM] Message content (truncated): {message[:100]}")
                            
                            elif isinstance(message, bytes):
                                # Handle raw audio data
                                chunk_size = len(message)
                                metrics["audio_chunks_received"] += 1
                                
                                # Update audio stats
                                now = time.time()
                                if audio_stats["first_chunk_time"] is None:
                                    audio_stats["first_chunk_time"] = now
                                audio_stats["last_chunk_time"] = now
                                audio_stats["min_chunk_size"] = min(audio_stats["min_chunk_size"], chunk_size)
                                audio_stats["max_chunk_size"] = max(audio_stats["max_chunk_size"], chunk_size)
                                audio_stats["total_audio_size"] += chunk_size
                                audio_stats["chunk_sizes"].append(chunk_size)
                                
                                # Add to queue for processing
                                await incoming_audio_queue.put(message)
                                
                                # Log periodically to avoid flooding 
                                if metrics["audio_chunks_received"] % 100 == 0:
                                    logger.debug(f"[MEDIA_STREAM] Processed {metrics['audio_chunks_received']} raw audio chunks")
                            else:
                                # Unknown message type
                                logger.warning(f"[MEDIA_STREAM] Received unknown message type: {type(message)}")
                            
                        except asyncio.TimeoutError:
                            # No messages for 30 seconds
                            elapsed = time.time() - metrics["last_activity_time"]
                            logger.warning(f"[MEDIA_STREAM] No Twilio messages received for {elapsed:.1f} seconds")
                            
                            # Check if we should exit due to inactivity
                            if elapsed > 60:  # Exit after 60 seconds of no activity
                                logger.warning("[MEDIA_STREAM] Exiting due to inactivity (60+ seconds)")
                                break
                            # Otherwise continue waiting
                            continue
                            
                except Exception as message_error:
                    logger.error(f"[MEDIA_STREAM] Error processing Twilio message: {message_error}")
                    logger.error(f"[MEDIA_STREAM] Message error trace: {traceback.format_exc()}")
                
                logger.info(f"[MEDIA_STREAM] Twilio message processing task completed after processing {message_count} messages")
            
            # Start processing Twilio messages
            logger.info("[MEDIA_STREAM] Starting Twilio message processing task")
            try:
                twilio_task = asyncio.create_task(process_twilio_messages())
            except Exception as task_error:
                logger.error(f"[MEDIA_STREAM] Error creating Twilio task: {str(task_error)}")
                logger.error(f"[MEDIA_STREAM] Task creation error trace: {traceback.format_exc()}")
            
            # Track greeting and flow state
            greeting_sent = False
            greeting_timestamp = None
            first_transcript_received = None
            first_silence_event = None
            first_response_sent = None
            
            # Process incoming audio with Realtime API
            try:
                logger.info(f"[STREAM:{session_id}] Setting up Realtime audio stream processing")
                async def audio_generator():
                    logger.info(f"[AUDIO:{session_id}] Starting audio generator")
                    chunks_yielded = 0
                    last_yield_time = time.time()
                    generator_start_time = time.time()
                    
                    # Add a function to log generator stats
                    def log_generator_stats(reason="periodic"):
                        duration = time.time() - generator_start_time
                        rate = chunks_yielded / duration if duration > 0 else 0
                        time_since_last = time.time() - last_yield_time
                        
                        logger.info(f"[AUDIO:{session_id}] Generator stats ({reason}): {chunks_yielded} chunks yielded, {duration:.1f}s running, {rate:.1f} chunks/sec")
                        logger.info(f"[AUDIO:{session_id}] Time since last yield: {time_since_last:.1f}s")
                        
                    try:
                        # Log the initial state
                        logger.info(f"[AUDIO:{session_id}] Audio generator ready, queue size: {incoming_audio_queue.qsize()}")
                        
                        while True:
                            try:
                                # Use a timeout to prevent blocking forever
                                audio_chunk = await asyncio.wait_for(incoming_audio_queue.get(), timeout=15.0)
                                chunks_yielded += 1
                                last_yield_time = time.time()
                                
                                # Log progress with different frequencies based on count
                                if chunks_yielded == 1:
                                    # Always log the first chunk
                                    logger.info(f"[AUDIO:{session_id}] ✅ First audio chunk yielded, size: {len(audio_chunk)} bytes")
                                elif chunks_yielded <= 10 and chunks_yielded % 2 == 0:
                                    # Log early chunks more frequently
                                    logger.debug(f"[AUDIO:{session_id}] Audio generator yielded chunk #{chunks_yielded}, size: {len(audio_chunk)} bytes")
                                elif chunks_yielded % 100 == 0:
                                    # Log periodic statistics
                                    log_generator_stats("periodic")
                                
                                # Yield the audio chunk to the Realtime API
                                yield audio_chunk
                                
                                # Mark the task as done
                                incoming_audio_queue.task_done()
                            
                            except asyncio.TimeoutError:
                                # Log timeout with increasing severity based on time since last yield
                                time_since_last = time.time() - last_yield_time
                                
                                if time_since_last < 20:
                                    logger.debug(f"[AUDIO:{session_id}] No audio received for {time_since_last:.1f}s in generator")
                                elif time_since_last < 30:
                                    logger.info(f"[AUDIO:{session_id}] No audio received for {time_since_last:.1f}s in generator")
                                else:
                                    logger.warning(f"[AUDIO:{session_id}] ⚠️ No audio received for {time_since_last:.1f}s in generator")
                                
                                # Log generator stats on timeout
                                log_generator_stats("timeout")
                                
                                # Check if we should exit due to inactivity
                                if twilio_task.done():
                                    logger.warning(f"[AUDIO:{session_id}] Exiting audio generator - Twilio task is complete")
                                    break
                                    
                                if time_since_last > 60:
                                    logger.warning(f"[AUDIO:{session_id}] Exiting audio generator - no audio for 60+ seconds")
                                    log_system_status(session_id, "audio_timeout")
                                    break
                                    
                                # Send a diagnostic message to the client about the timeout
                                try:
                                    await ws.send(json.dumps({
                                        "type": "diagnostic",
                                        "event": "audio_timeout",
                                        "time_since_last": time_since_last,
                                        "timestamp": time.time(),
                                        "session_id": session_id
                                    }))
                                except Exception as ws_err:
                                    logger.error(f"[AUDIO:{session_id}] ❌ Could not send timeout diagnostic: {ws_err}")
                                
                                # Otherwise keep waiting
                                continue
                            
                            except Exception as chunk_error:
                                logger.error(f"[AUDIO:{session_id}] ❌ Error getting audio chunk: {chunk_error}")
                                logger.error(traceback.format_exc())
                                
                                # Try to send diagnostic info to client
                                try:
                                    await ws.send(json.dumps({
                                        "type": "diagnostic",
                                        "event": "audio_error",
                                        "error": str(chunk_error),
                                        "timestamp": time.time(),
                                        "session_id": session_id
                                    }))
                                except Exception:
                                    pass
                                    
                                # Continue trying to get more chunks - more resilient
                                continue
                                
                    except Exception as gen_error:
                        logger.error(f"[AUDIO:{session_id}] ❌ Fatal audio generator error: {gen_error}")
                        logger.error(traceback.format_exc())
                        
                        # Try to send diagnostic info to client
                        try:
                            await ws.send(json.dumps({
                                "type": "error",
                                "error_type": "audio_generator",
                                "text": f"Audio generator error: {str(gen_error)}",
                                "timestamp": time.time()
                            }))
                        except Exception:
                            pass
                            
                    finally:
                        # Log final stats
                        duration = time.time() - generator_start_time
                        rate = chunks_yielded / duration if duration > 0 else 0
                        logger.info(f"[AUDIO:{session_id}] Audio generator exiting after yielding {chunks_yielded} chunks over {duration:.1f}s ({rate:.1f} chunks/sec)")
            except Exception as setup_error:
                logger.error(f"[MEDIA_STREAM] Error setting up audio generator: {setup_error}")
                logger.error(traceback.format_exc())
            
            # Process the media stream
            logger.info(f"[STREAM:{session_id}] Starting Realtime media stream processing")
            
            # Track detailed events for debugging
            event_counts = {}
            processed_events = 0
            stream_start_time = time.time()
            last_event_time = time.time()
            
            # Structure to track timing of key events for diagnostics
            event_timing = {
                "stream_start": stream_start_time,
                "first_event": None,
                "first_transcript": None,
                "first_silence": None,
                "first_tool_call": None,
                "greeting_sent": None,
                "post_greeting_silence": None,
                "post_greeting_transcript": None,
            }
            
            try:
                logger.info(f"[STREAM:{session_id}] Creating and starting Realtime stream")
                async for event in realtime_processor.process_media_stream(audio_generator(), session_id):
                    # Track event timing
                    current_time = time.time()
                    time_since_last = current_time - last_event_time
                    last_event_time = current_time
                    
                    # Record first event timing
                    if event_timing["first_event"] is None:
                        event_timing["first_event"] = current_time
                        elapsed = current_time - stream_start_time
                        logger.info(f"[STREAM:{session_id}] ✅ First event received after {elapsed:.3f}s")
                    
                    # Update metrics
                    metrics["events_processed"] += 1
                    processed_events += 1
                    metrics["last_activity_time"] = current_time
                
                    # Handle different event types
                    event_type = event.get("type", "")
                    event_counts[event_type] = event_counts.get(event_type, 0) + 1
                    
                    # Set event type-specific timing metrics
                    if event_type == "transcript_complete" and event_timing["first_transcript"] is None:
                        event_timing["first_transcript"] = current_time
                        elapsed = current_time - stream_start_time
                        logger.info(f"[STREAM:{session_id}] ✅ First transcript received after {elapsed:.3f}s")
                        
                        # Record post-greeting transcript if greeting was already sent
                        if greeting_sent and event_timing["post_greeting_transcript"] is None:
                            event_timing["post_greeting_transcript"] = current_time
                            time_after_greeting = current_time - greeting_timestamp
                            logger.info(f"[STREAM:{session_id}] ✅ First transcript after greeting received {time_after_greeting:.3f}s after greeting")
                    
                    elif event_type == "silence_detected" and event_timing["first_silence"] is None:
                        event_timing["first_silence"] = current_time
                        elapsed = current_time - stream_start_time
                        logger.info(f"[STREAM:{session_id}] ✅ First silence event received after {elapsed:.3f}s")
                        
                        # Record post-greeting silence if greeting was already sent
                        if greeting_sent and event_timing["post_greeting_silence"] is None:
                            event_timing["post_greeting_silence"] = current_time
                            time_after_greeting = current_time - greeting_timestamp
                            logger.critical(f"[STREAM:{session_id}] ✅ CRITICAL: First silence after greeting detected {time_after_greeting:.3f}s after greeting")
                    
                    elif event_type == "tool_call" and event_timing["first_tool_call"] is None:
                        event_timing["first_tool_call"] = current_time
                        elapsed = current_time - stream_start_time
                        logger.info(f"[STREAM:{session_id}] ✅ First tool call received after {elapsed:.3f}s")
                    
                    # Log every event with appropriate detail level based on count and type
                    if processed_events <= 10 or processed_events % 20 == 0 or event_type not in ["audio", "ping", "pong"]:
                        log_level = logging.INFO
                        # Use WARNING for silence events to make them stand out
                        if event_type == "silence_detected":
                            log_level = logging.WARNING
                        
                        # Format event counts nicely
                        event_counts_str = ", ".join([f"{k}: {v}" for k, v in event_counts.items()])
                        
                        # Calculate timing info
                        elapsed_total = current_time - stream_start_time
                        event_rate = processed_events / elapsed_total if elapsed_total > 0 else 0
                        
                        logger.log(log_level, f"[STREAM:{session_id}] Event #{processed_events}: type={event_type}, " +
                                             f"time_since_last={time_since_last:.3f}s, " +
                                             f"elapsed={elapsed_total:.1f}s, rate={event_rate:.1f}/s")
                        
                    # Record the event for debugging
                    ws_events.append({
                        "time": current_time,
                        "type": event_type,
                        "event_count": processed_events,
                        "time_since_start": current_time - stream_start_time,
                        "time_since_last": time_since_last
                    })
                    
                    # Log detailed event counts periodically or on key events
                    if processed_events % 50 == 0 or (event_type in ["silence_detected", "transcript_complete"] and processed_events > 10):
                        logger.info(f"[STREAM:{session_id}] Processed {processed_events} events: {event_counts_str}")
                
                    # Handle specific event types
                    if event_type == "transcript_complete":
                        # Process complete transcript with frontline agent
                        transcript = event.get("text", "")
                        if transcript:
                            metrics["transcripts_processed"] += 1
                            logger.info(f"[MEDIA_STREAM] Processing transcript #{metrics['transcripts_processed']}: {transcript}")
                            
                            # Process with orchestrated agent
                            try:
                                logger.info(f"[MEDIA_STREAM] Sending transcript to frontline agent")
                                start_time = time.time()
                                agent_response = frontline.process_voice_input(session_id, transcript)
                                processing_time = time.time() - start_time
                                logger.info(f"[MEDIA_STREAM] ✅ Agent processed transcript in {processing_time:.2f}s")
                                logger.info(f"[MEDIA_STREAM] Agent response: {agent_response}")
                                
                                # Send transcript to client
                                await ws.send(json.dumps({
                                    "event": "transcript",
                                    "transcript": transcript,
                                    "timestamp": time.time()
                                }))
                                metrics["events_sent"] += 1
                                
                                # Send agent response to client
                                await ws.send(json.dumps({
                                    "event": "message",
                                    "text": agent_response,
                                    "timestamp": time.time()
                                }))
                                metrics["events_sent"] += 1
                                
                                # Generate TTS audio from response
                                logger.info("[MEDIA_STREAM] Sending agent response as TTS audio")
                                await ws.send(json.dumps({
                                    "event": "media",
                                    "streamSid": session_id,
                                    "media": {
                                        "payload": base64.b64encode(agent_response.encode('utf-8')).decode('utf-8')
                                    }
                                }))
                                metrics["events_sent"] += 1
                                
                            except Exception as agent_error:
                                logger.error(f"[MEDIA_STREAM] ❌ Error processing transcript with agent: {agent_error}")
                                logger.error(f"[MEDIA_STREAM] Agent error trace: {traceback.format_exc()}")
                                
                                # Send error to client
                                await ws.send(json.dumps({
                                    "event": "error",
                                    "text": f"Error processing your input: {str(agent_error)}",
                                    "timestamp": time.time()
                                }))
                                metrics["events_sent"] += 1
                        else:
                            logger.warning("[MEDIA_STREAM] Received empty transcript_complete event")
                
                    elif event_type == "tool_call":
                        # Handle tool calls from the model
                        metrics["tool_calls"] += 1
                        tool_name = event.get("name", "")
                        tool_arguments = event.get("arguments", {})
                        tool_id = event.get("id", "")
                        
                        logger.info(f"[MEDIA_STREAM] Tool call #{metrics['tool_calls']}: {tool_name}")
                        logger.debug(f"[MEDIA_STREAM] Tool arguments: {tool_arguments}")
                        
                        # Execute tool with frontline agent through registry
                        try:
                            if tool_registry and tool_name in tool_registry.tools:
                                logger.info(f"[MEDIA_STREAM] Executing tool {tool_name} via registry")
                                start_time = time.time()
                                
                                tool_result = tool_registry.execute_tool(
                                    tool_name, 
                                    tool_arguments, 
                                    session_id=session_id
                                )
                                
                                execution_time = time.time() - start_time
                                logger.info(f"[MEDIA_STREAM] ✅ Tool {tool_name} executed in {execution_time:.2f}s")
                                logger.debug(f"[MEDIA_STREAM] Tool result: {tool_result}")
                                
                                # Send tool result back to WebSocket
                                await ws.send(json.dumps({
                                    "event": "tool_result",
                                    "name": tool_name,
                                    "result": tool_result,
                                    "timestamp": time.time()
                                }))
                                metrics["events_sent"] += 1
                            else:
                                logger.warning(f"[MEDIA_STREAM] Tool {tool_name} not found in registry")
                        except Exception as tool_error:
                            logger.error(f"[MEDIA_STREAM] ❌ Error executing tool {tool_name}: {tool_error}")
                            logger.error(f"[MEDIA_STREAM] Tool error trace: {traceback.format_exc()}")
                            
                            # Send error to client
                            await ws.send(json.dumps({
                                "event": "error",
                                "text": f"Error executing tool {tool_name}: {str(tool_error)}",
                                "timestamp": time.time()
                            }))
                            metrics["events_sent"] += 1
                
                    elif event_type == "silence_detected":
                        # Handle silence detection
                        metrics["silence_events"] += 1
                        logger.info(f"[MEDIA_STREAM] Silence detected (event #{metrics['silence_events']})")
                        
                        try:
                            # Get current FSM state
                            current_state = fsm_orchestrator.get_current_state(session_id)
                            logger.info(f"[MEDIA_STREAM] Current FSM state: {current_state}")
                            
                            # Generate appropriate response based on state
                            if not greeting_sent:
                                # Send initial greeting if none sent yet
                                greeting_timestamp = time.time()
                                event_timing["greeting_sent"] = greeting_timestamp
                                
                                logger.critical(f"[GREETING:{session_id}] ⚠️ SENDING INITIAL GREETING after {greeting_timestamp - stream_start_time:.3f}s of processing")
                                greeting = "Welcome to Red Bar Sushi. How can I help you today?"
                                
                                # Send greeting to client
                                try:
                                    greeting_msg = {
                                        "event": "message",
                                        "text": greeting,
                                        "timestamp": greeting_timestamp,
                                        "session_id": session_id
                                    }
                                    await ws.send(json.dumps(greeting_msg))
                                    await log_websocket_message(json.dumps(greeting_msg), "SEND", "greeting_text", session_id)
                                    metrics["events_sent"] += 1
                                    
                                    # Convert greeting to audio (base64 for now)
                                    audio_msg = {
                                        "event": "media",
                                        "streamSid": session_id,
                                        "media": {
                                            "payload": base64.b64encode(greeting.encode('utf-8')).decode('utf-8')
                                        },
                                        "timestamp": time.time()
                                    }
                                    await ws.send(json.dumps(audio_msg))
                                    metrics["events_sent"] += 1
                                    
                                    # Log detailed system status at greeting time
                                    log_system_status(session_id, "greeting_sent")
                                    
                                    # Send a diagnostic event with key metrics
                                    diagnostic_msg = {
                                        "type": "diagnostic",
                                        "event": "greeting_sent",
                                        "timestamp": time.time(),
                                        "session_id": session_id,
                                        "audio_chunks_received": metrics["audio_chunks_received"],
                                        "events_processed": metrics["events_processed"],
                                        "time_since_start": time.time() - stream_start_time,
                                        "time_since_first_event": event_timing["first_event"] and (time.time() - event_timing["first_event"])
                                    }
                                    await ws.send(json.dumps(diagnostic_msg))
                                    
                                    greeting_sent = True
                                    logger.critical(f"[GREETING:{session_id}] ✅ INITIAL GREETING SUCCESSFULLY SENT")
                                except Exception as greeting_error:
                                    # If we fail to send the greeting, this is critical
                                    logger.critical(f"[GREETING:{session_id}] ❌ CRITICAL: Failed to send initial greeting: {greeting_error}")
                                    logger.critical(traceback.format_exc())
                                    
                                    # Try to log this error back to Twilio to help with diagnostics
                                    try:
                                        error_msg = {
                                            "type": "error",
                                            "error_type": "greeting_failure",
                                            "text": f"Failed to send greeting: {str(greeting_error)}",
                                            "timestamp": time.time(),
                                            "session_id": session_id
                                        }
                                        await ws.send(json.dumps(error_msg))
                                    except:
                                        pass
                            elif current_state == FSMState.GREETING:
                                # In greeting state, prompt for name
                                logger.info("[MEDIA_STREAM] In GREETING state, prompting for name")
                                prompt = "Could you please tell me your name?"
                                
                                # Send prompt to client
                                await ws.send(json.dumps({
                                    "event": "message",
                                    "text": prompt,
                                    "timestamp": time.time()
                                }))
                                metrics["events_sent"] += 1
                                
                                # Convert prompt to audio (base64 for now)
                                await ws.send(json.dumps({
                                    "event": "media",
                                    "streamSid": session_id,
                                    "media": {
                                        "payload": base64.b64encode(prompt.encode('utf-8')).decode('utf-8')
                                    }
                                }))
                                metrics["events_sent"] += 1
                                logger.info("[MEDIA_STREAM] ✅ Name prompt sent")
                            else:
                                # Generic prompt based on state
                                logger.info(f"[MEDIA_STREAM] In state {current_state}, sending generic prompt")
                                prompt = "Is there anything else I can help you with?"
                                
                                # Send prompt to client
                                await ws.send(json.dumps({
                                    "event": "message",
                                    "text": prompt,
                                    "timestamp": time.time()
                                }))
                                metrics["events_sent"] += 1
                                
                                # Convert prompt to audio (base64 for now)
                                await ws.send(json.dumps({
                                    "event": "media",
                                    "streamSid": session_id,
                                    "media": {
                                        "payload": base64.b64encode(prompt.encode('utf-8')).decode('utf-8')
                                    }
                                }))
                                metrics["events_sent"] += 1
                                logger.info("[MEDIA_STREAM] ✅ Generic prompt sent")
                        except Exception as silence_error:
                            logger.error(f"[MEDIA_STREAM] ❌ Error processing silence event: {silence_error}")
                            logger.error(f"[MEDIA_STREAM] Silence error trace: {traceback.format_exc()}")
                
                    elif event_type == "audio":
                        # Handle audio data for TTS response
                        audio_data = event.get("data", "")
                        if audio_data:
                            logger.debug(f"[MEDIA_STREAM] Received TTS audio data ({len(audio_data)} chars)")
                            try:
                                # Forward audio to Twilio
                                await ws.send(json.dumps({
                                    "event": "media",
                                    "streamSid": session_id,
                                    "media": {
                                        "payload": audio_data
                                    }
                                }))
                                metrics["events_sent"] += 1
                            except Exception as audio_error:
                                logger.error(f"[MEDIA_STREAM] ❌ Error sending audio data: {audio_error}")
                        else:
                            logger.warning("[MEDIA_STREAM] Received empty audio data")
                            
                    elif event_type == "error":
                        # Handle error events
                        error_msg = event.get("error", "Unknown error")
                        logger.error(f"[MEDIA_STREAM] Received error event: {error_msg}")
                        
                        # Forward error to client
                        await ws.send(json.dumps({
                            "event": "error",
                            "text": error_msg,
                            "timestamp": time.time()
                        }))
                        metrics["events_sent"] += 1
            
                logger.info(f"[MEDIA_STREAM] Media stream processing complete after {processed_events} events")
                logger.info(f"[MEDIA_STREAM] Event counts by type: {event_counts}")
            except Exception as stream_error:
                logger.error(f"[MEDIA_STREAM] Error in media stream processing loop: {str(stream_error)}")
                logger.error(f"[MEDIA_STREAM] Stream loop error trace: {traceback.format_exc()}")
        
        except Exception as e:
            logger.error(f"[MEDIA_STREAM] ❌ Error in media stream processing: {str(e)}")
            # Output diagnostic information on error
            diagnostics_output("error" if "session_id" not in locals() else session_id, "exception")
            logger.error(f"[MEDIA_STREAM] Processing error trace: {traceback.format_exc()}")
            
            # Try to send error to client
            try:
                await ws.send(json.dumps({
                    "event": "error",
                    "text": f"System error: {str(e)}",
                    "timestamp": time.time()
                }))
            except:
                pass
        
        # Clean up and summarize connection
        
        # Cancel keep-alive task if it's running
        if 'keepalive_task' in locals() and not keepalive_task.done():
            logger.info("[MEDIA_STREAM] Cancelling keep-alive task")
            keepalive_task.cancel()
            try:
                await keepalive_task
            except asyncio.CancelledError:
                pass
        
        try:
            # Cancel Twilio task if still running
            if not twilio_task.done():
                logger.info("[MEDIA_STREAM] Cancelling Twilio message processing task")
                twilio_task.cancel()
                try:
                    await twilio_task
                except asyncio.CancelledError:
                    pass
                
            logger.info(f"[MEDIA_STREAM] WebSocket session complete: {session_id}")
            log_connection_summary("normal_close")
            
        except Exception as cleanup_error:
            logger.error(f"[MEDIA_STREAM] Error during connection cleanup: {cleanup_error}")
    
    except Exception as e:
        logger.error(f"[MEDIA_STREAM] ❌ Unhandled error in media stream: {str(e)}")
        logger.error(f"[MEDIA_STREAM] Unhandled error trace: {traceback.format_exc()}")
        
        # Try to send error to client
        try:
            await ws.send(json.dumps({
                "event": "error",
                "text": f"System error: {str(e)}",
                "timestamp": time.time()
            }))
            
            # Try to log connection summary
            if 'log_connection_summary' in locals():
                log_connection_summary(f"unhandled_error: {str(e)}")
                
            # Try to close WebSocket with error code
            await ws.close(code=1011, reason=f"Internal error: {str(e)}")
        except:
            pass
            
    finally:
        # Clean up session-specific logging
        try:
            if 'session_file_handler' in locals():
                logger.removeHandler(session_file_handler)
            if 'ws_file_handler' in locals():
                logger.removeHandler(ws_file_handler)
        except:
            pass

@sock.route("/ws/voice/debug")
async def debug_websocket(ws):
    """Simple WebSocket endpoint to verify WebSocket connectivity."""
    print("[DEBUG WEBSOCKET] Connection established")
    logger.critical("[DEBUG WEBSOCKET] WebSocket connection established to /ws/voice/debug")
    
    try:
        # Send a simple message to the client
        await ws.send(json.dumps({
            "message": "WebSocket connection established successfully",
            "time": time.time()
        }))
        
        # Echo any messages back to the client
        while True:
            try:
                message = await asyncio.wait_for(ws.receive(), timeout=30.0)
                logger.critical(f"[DEBUG WEBSOCKET] Received message: {message}")
                
                # Echo the message back
                await ws.send(json.dumps({
                    "echo": message,
                    "time": time.time()
                }))
            except asyncio.TimeoutError:
                # Send a ping to keep the connection alive
                await ws.send(json.dumps({"ping": time.time()}))
            except Exception as e:
                logger.critical(f"[DEBUG WEBSOCKET] Error: {str(e)}")
                break
    except Exception as e:
        logger.critical(f"[DEBUG WEBSOCKET] Error: {str(e)}")
    
    logger.critical("[DEBUG WEBSOCKET] WebSocket connection closed")

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