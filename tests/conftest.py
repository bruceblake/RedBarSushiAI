"""
Main conftest.py for all tests.
This file contains common fixtures and configurations for all test types.
"""

import pytest
import os
import json
import asyncio
import requests
from unittest.mock import patch, MagicMock, AsyncMock

# Set testing environment variables
os.environ["TESTING"] = "True"
os.environ["FLASK_ENV"] = "testing"
os.environ["NO_X11"] = "1"  # Disable X11 requirement for headless testing
os.environ["OPENAI_REALTIME_NO_DISPLAY"] = "1"  # Disable display for OpenAI Realtime

# MCP server endpoint configuration
MCP_PORT = os.environ.get("MCP_PORT", "4244")

# Different MCP URLs depending on the context
# 1. If running on host machine
HOST_MCP_URL = f"http://localhost:{MCP_PORT}/sse"
# 2. If running inside container in same Docker network
CONTAINER_MCP_URL = f"http://redbarsushi_mcp:{MCP_PORT}/sse"
# 3. If running in arbitrary container that needs to call back to host
HOST_DOCKER_INTERNAL_MCP_URL = f"http://host.docker.internal:{MCP_PORT}/sse"

# Detect environment to determine which URL to use
# If we're running inside a container, we should use CONTAINER_MCP_URL
in_container = os.environ.get("RUNNING_IN_CONTAINER", "false").lower() == "true"

if in_container:
    # Use container-to-container address if we're in a container
    MCP_URL = CONTAINER_MCP_URL
    print(f"Running inside container, using MCP URL: {MCP_URL}")
else:
    # Use localhost if we're on the host
    MCP_URL = HOST_MCP_URL
    print(f"Running on host, using MCP URL: {MCP_URL}")

# Use MCP_WORKING_URL if set (this is set by test_mcp_connectivity.py when it finds a working URL)
if "MCP_WORKING_URL" in os.environ:
    MCP_URL = f"{os.environ['MCP_WORKING_URL']}/sse"
    print(f"Using previously verified working MCP URL: {MCP_URL}")

# Helper function to invoke MCP tools
def mcp_call(method, params=None):
    """Call an MCP tool via the SSE API"""
    # Prepare the tool call payload
    tool_call = {
        "name": method,
        "arguments": params or {}
    }
    
    # Convert to query parameter
    import urllib.parse
    encoded_tool_call = urllib.parse.quote(json.dumps(tool_call))
    
    # Build URL with tool call
    sse_url = f"{MCP_URL}?tool_call={encoded_tool_call}"
    
    try:
        # Make request with streaming
        response = requests.get(sse_url, stream=True, timeout=15)
        response.raise_for_status()
        
        # Process SSE events
        result = None
        
        for line in response.iter_lines():
            if not line:
                continue
                
            line_str = line.decode('utf-8')
            if line_str.startswith("data: "):
                data_str = line_str[6:]  # Remove "data: " prefix
                try:
                    data = json.loads(data_str)
                    if data.get("type") == "tool_result":
                        result = data.get("result")
                        break
                except json.JSONDecodeError:
                    pass
        
        # Close connection
        response.close()
        
        if result:
            return result
        else:
            return {"error": "No tool result received"}
    
    except Exception as e:
        # If primary URL fails, try fallback URLs
        print(f"Error connecting to primary MCP URL {sse_url}: {e}")
        
        # Try alternative URLs if the primary one fails
        alt_urls = []
        if MCP_URL != HOST_MCP_URL:
            alt_urls.append(HOST_MCP_URL)
        if MCP_URL != CONTAINER_MCP_URL:
            alt_urls.append(CONTAINER_MCP_URL)
        if MCP_URL != HOST_DOCKER_INTERNAL_MCP_URL:
            alt_urls.append(HOST_DOCKER_INTERNAL_MCP_URL)
        
        for base_url in alt_urls:
            try:
                alt_sse_url = f"{base_url}?tool_call={encoded_tool_call}"
                print(f"Trying alternative MCP URL: {alt_sse_url}")
                
                alt_response = requests.get(alt_sse_url, stream=True, timeout=5)
                alt_response.raise_for_status()
                
                # Process SSE events
                alt_result = None
                
                for line in alt_response.iter_lines():
                    if not line:
                        continue
                        
                    line_str = line.decode('utf-8')
                    if line_str.startswith("data: "):
                        data_str = line_str[6:]  # Remove "data: " prefix
                        try:
                            data = json.loads(data_str)
                            if data.get("type") == "tool_result":
                                alt_result = data.get("result")
                                break
                        except json.JSONDecodeError:
                            pass
                
                # Close connection
                alt_response.close()
                
                if alt_result:
                    # Remember this working URL for future calls
                    global MCP_URL
                    MCP_URL = base_url
                    os.environ["MCP_WORKING_URL"] = base_url
                    print(f"Switching to working MCP URL: {base_url}")
                    return alt_result
            except Exception as alt_e:
                print(f"Alternative URL {base_url} also failed: {alt_e}")
                continue
        
        # If all URLs failed, return the original error
        return {"error": f"Error connecting to MCP: {str(e)}", "status": "error"}


# Define test markers
def pytest_configure(config):
    """
    Configure pytest with custom markers.
    """
    config.addinivalue_line("markers", "e2e: mark a test as an end-to-end test")
    config.addinivalue_line("markers", "voice: mark a test focused on voice processing")
    config.addinivalue_line("markers", "menu: mark a test focused on menu handling")
    config.addinivalue_line("markers", "order: mark a test focused on order processing")
    config.addinivalue_line("markers", "websocket: mark a test focused on WebSocket communications")


@pytest.fixture
def app():
    """Create Flask app for testing with in-memory SQLite database"""
    # Import here to avoid circular imports
    from app import create_app
    
    app = create_app({
        "TESTING": True, 
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "INITIALIZE_MENU_DATABASE": False,  # Don't initialize DB automatically
        "SECRET_KEY": "test_secret_key",
        "PRESERVE_CONTEXT_ON_EXCEPTION": False
    })
    
    # Create all tables in the in-memory database
    with app.app_context():
        from app.db import db
        db.create_all()
        
        # Seed with test data if needed
        _create_test_data(db)
    
    yield app
    
    # Clean up
    with app.app_context():
        from app.db import db
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create a test client for the Flask app"""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a CLI test runner for the Flask app"""
    return app.test_cli_runner()


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing"""
    mock_client = MagicMock()
    mock_client.get.return_value = None  # Default behavior
    mock_client.set.return_value = True
    mock_client.delete.return_value = True
    mock_client.exists.return_value = 0
    mock_client.hgetall.return_value = {}
    mock_client.hset.return_value = 1
    
    # Patch the Redis client
    with patch('redis.Redis', return_value=mock_client), \
         patch('app.utils.conversation_store.redis_client', mock_client), \
         patch('app.utils.menu_cache.redis_client', mock_client):
        yield mock_client


@pytest.fixture
def mock_twilio():
    """Mock Twilio client for testing"""
    mock_client = MagicMock()
    mock_messages = MagicMock()
    mock_messages.create.return_value = MagicMock(sid="test_message_sid")
    mock_client.messages = mock_messages
    
    # Patch the Twilio client
    with patch('twilio.rest.Client', return_value=mock_client), \
         patch('app.twilio_client', mock_client):
        yield mock_client


@pytest.fixture
def mock_deliverect():
    """Mock Deliverect API for testing"""
    # Create a mock response for the create order endpoint
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "orderId": "test-order-id-123",
        "status": 10,  # Initial received status
        "channelOrderId": "RBS-TEST-123"
    }
    
    # Patch the requests library or specific deliverect function
    with patch('app.utils.deliverect.orders.create_order', return_value=mock_response), \
         patch('app.utils.deliverect.orders.get_order_status', return_value={"status": 10}):
        yield mock_response


@pytest.fixture
def mock_openai():
    """Mock OpenAI client for testing"""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="Test response from OpenAI"))]
    )
    
    # Patch the OpenAI client
    with patch('openai.OpenAI', return_value=mock_client), \
         patch('openai.AsyncOpenAI', return_value=mock_client):
        yield mock_client


@pytest.fixture
def mock_realtime_processor():
    """Mock the realtime audio processor for testing"""
    class MockProcessor:
        def __init__(self):
            self.events = []
            self.processed_audio = []
            
        async def process_media_stream(self, audio_generator, session_id):
            # Collect audio chunks for verification
            async for chunk in audio_generator:
                if chunk:
                    self.processed_audio.append(chunk)
            
            # Yield events
            for event in self.events:
                yield event
    
    processor = MockProcessor()
    
    # Add some default events
    processor.events = [
        {
            "type": "transcript_complete",
            "text": "I'd like to order a California roll",
            "final": True,
            "timestamp": 12345.67
        }
    ]
    
    # Patch the realtime processor
    with patch('app.utils.realtime_audio_sdk.get_realtime_processor', return_value=processor):
        yield processor


@pytest.fixture
def mock_agents():
    """Mock agents for testing"""
    # Mock the frontline agent
    mock_frontline = MagicMock()
    mock_frontline.process_voice_input = AsyncMock(return_value="I understand your request")
    mock_frontline.get_capabilities = MagicMock(return_value=["menu", "cart", "ordering"])
    mock_frontline.lookup_menu_item = AsyncMock(return_value={"name": "California Roll", "price": 850})
    mock_frontline.add_to_cart = AsyncMock(return_value={"status": "success"})
    mock_frontline.get_cart = AsyncMock(return_value={"items": [], "total_price": 0})
    mock_frontline.complete_order = AsyncMock(return_value={"status": "success", "order_id": "test-123"})
    
    # Mock the orchestrators
    mock_fsm = MagicMock()
    mock_fsm.get_current_state.return_value = "GREETING"
    mock_fsm.set_state = AsyncMock()
    
    mock_slots = MagicMock()
    mock_slots.get_slot.return_value = None
    mock_slots.set_slot = AsyncMock()
    mock_slots.register_slot = MagicMock()
    
    mock_graph = MagicMock()
    mock_escalator = MagicMock()
    
    # Patch the agents and orchestrators
    with patch('app.routes.voice.__init__.realtime_voice_bp', mock_frontline), \
         patch('app.routes.voice.main.fsm_orchestrator', mock_fsm), \
         patch('app.routes.voice.main.slot_store', mock_slots), \
         patch('app.routes.voice.main.agent_graph', mock_graph), \
         patch('app.routes.voice.main.model_escalator', mock_escalator):
        
        yield {
            "frontline": mock_frontline,
            "fsm": mock_fsm,
            "slots": mock_slots,
            "graph": mock_graph,
            "escalator": mock_escalator
        }


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket for testing"""
    class MockAsyncWebSocket:
        """Mock WebSocket class for testing"""
        
        def __init__(self, test_inputs=None):
            self.test_inputs = test_inputs or []
            self.sent_messages = []
            self.received_messages = []
            self.closed = False
            self.close_code = None
            self.close_reason = None
        
        async def send(self, message):
            """Mock send method"""
            self.sent_messages.append(message)
            
        async def receive(self):
            """Mock receive method, returns predefined test inputs"""
            if not self.test_inputs:
                # If no more inputs, simulate waiting by yielding control
                await asyncio.sleep(0.1)
                return None
                
            msg = self.test_inputs.pop(0)
            self.received_messages.append(msg)
            return msg
        
        async def close(self, code=1000, reason=""):
            """Mock close method"""
            self.closed = True
            self.close_code = code
            self.close_reason = reason
    
    # Default mock with start event
    mock_ws = MockAsyncWebSocket([
        json.dumps({
            "event": "start",
            "start": {
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
            }
        })
    ])
    
    yield mock_ws


def _create_test_data(db):
    """Create test data for the database"""
    # Import models here to avoid circular imports
    from app.models.menu import MenuItem, MenuModifier, MenuModifierGroup, MenuNameVariant, ItemModifierGroup
    from app.models.location import Location
    
    # Create a test location
    test_location = Location(
        id=1,
        name="Red Bar Sushi Test Location",
        address="123 Test St",
        city="Testville",
        state="NY",
        zip="10001",
        phone="555-123-1000",
        channelLinkId="test-channel-link-id",
        business_hours="9:00-22:00"
    )
    
    # Create test menu categories
    sushi_cat = MenuModifierGroup(
        id=1,
        deliverect_group_id="cat_sushi",
        name="Sushi Rolls",
        min_selection=0,
        max_selection=0
    )
    
    # Create test menu items
    cali_roll = MenuItem(
        id=1,
        name="California Roll",
        description="Crab, avocado, and cucumber",
        price=850,  # $8.50
        plu="CALI-ROLL",
        deliverect_item_id="item_cali_roll",
        is_available=True
    )
    
    spicy_tuna = MenuItem(
        id=2,
        name="Spicy Tuna Roll",
        price=950,  # $9.50
        plu="SPICY-TUNA",
        deliverect_item_id="item_spicy_tuna",
        description="Fresh tuna with spicy sauce",
        is_available=True
    )
    
    # Create test modifier groups
    sauce_group = MenuModifierGroup(
        id=101,
        deliverect_group_id="mod_gr_sauce",
        name="Sauce Options",
        min_selection=0,
        max_selection=3
    )
    
    # Create test modifiers
    extra_avo = MenuModifier(
        id=201,
        modifier_group_id=101,
        name="Extra Avocado",
        price_change=150,  # $1.50
        plu="MOD-EXTRA-AVO",
        deliverect_modifier_id="mod_extra_avo",
        is_available=True
    )
    
    spicy_sauce = MenuModifier(
        id=202,
        modifier_group_id=101,
        name="Spicy Mayo",
        price_change=100,  # $1.00
        plu="MOD-SPICY-MAYO",
        deliverect_modifier_id="mod_spicy_mayo",
        is_available=True
    )
    
    # Create item-modifier group associations
    cali_sauce_assoc = ItemModifierGroup(
        menu_item_id=1,  # California Roll
        modifier_group_id=101  # Sauce Group
    )
    
    # Create name variants for natural language matching
    variants = [
        MenuNameVariant(variant_phrase="california roll", canonical_name="California Roll", target_plu="CALI-ROLL"),
        MenuNameVariant(variant_phrase="cali roll", canonical_name="California Roll", target_plu="CALI-ROLL"),
        MenuNameVariant(variant_phrase="spicy tuna", canonical_name="Spicy Tuna Roll", target_plu="SPICY-TUNA"),
        MenuNameVariant(variant_phrase="spicy tuna roll", canonical_name="Spicy Tuna Roll", target_plu="SPICY-TUNA"),
        MenuNameVariant(variant_phrase="extra avocado", canonical_name="Extra Avocado", target_plu="MOD-EXTRA-AVO"),
        MenuNameVariant(variant_phrase="spicy mayo", canonical_name="Spicy Mayo", target_plu="MOD-SPICY-MAYO"),
    ]
    
    # Add to database
    db.session.add_all([
        test_location, sushi_cat, cali_roll, spicy_tuna, sauce_group, 
        extra_avo, spicy_sauce, cali_sauce_assoc, *variants
    ])
    db.session.commit()


# Define an enum class for FSM states to be used in tests
class FSMState:
    GREETING = "GREETING"
    MAIN_MENU = "MAIN_MENU"
    MENU_INQUIRY = "MENU_INQUIRY"
    ORDERING = "ORDERING"
    ITEM_CLARIFICATION = "ITEM_CLARIFICATION"
    VALIDATION = "VALIDATION"
    CONFIRMATION = "CONFIRMATION"
    PAYMENT = "PAYMENT"
    FULFILLMENT = "FULFILLMENT"
    FOLLOW_UP = "FOLLOW_UP"
    STAFF_HANDOFF = "STAFF_HANDOFF"
    COMPLETION = "COMPLETION"


#######################
# MCP Tool Fixtures
#######################

@pytest.fixture(scope="session")
def mcp_ping():
    """MCP ping fixture"""
    return lambda: mcp_call("ping")

@pytest.fixture(scope="session")
def http_get():
    """MCP http_get fixture"""
    return lambda path, **kw: mcp_call("http_get", {"path": path, **kw})

@pytest.fixture(scope="session")
def http_post():
    """MCP http_post fixture"""
    return lambda path, **kw: mcp_call("http_post", {"path": path, **kw})

@pytest.fixture(scope="session")
def invoke_route():
    """MCP invoke_route fixture"""
    return lambda method, path, **kw: mcp_call("invoke_route", {"method": method, "path": path, **kw})

@pytest.fixture(scope="session")
def ws_echo():
    """MCP ws_echo fixture"""
    return lambda path="/api/ws/echo", message="ping": mcp_call("ws_echo", {"path": path, "message": message})

@pytest.fixture(scope="session")
def ws_script():
    """MCP ws_script fixture"""
    return lambda path, script_name: mcp_call("ws_script", {"path": path, "script_name": script_name})

@pytest.fixture(scope="session")
def route_map():
    """MCP route_map fixture"""
    return lambda: mcp_call("route_map")

@pytest.fixture(scope="session")
def flask_config():
    """MCP flask_config fixture"""
    return lambda key=None: mcp_call("flask_config", {"key": key} if key else {})

@pytest.fixture(scope="session")
def redis_get():
    """MCP redis_get fixture"""
    return lambda key: mcp_call("redis_get", {"key": key})

@pytest.fixture(scope="session")
def sql_query():
    """MCP sql fixture"""
    return lambda query: mcp_call("sql", {"query": query})

# Add fixtures for additional MCP tools as needed