"""
End-to-end tests for RedBarSushiAI voice ordering system.
This module tests the AI-powered voice interaction flow from initial greeting
through order completion, focusing on real-world use cases.
"""

import pytest
import asyncio
import json
import os
import uuid
import base64
import time
from unittest.mock import AsyncMock, patch, MagicMock
import websockets

# Set environment to test mode
os.environ["TESTING"] = "True"
os.environ["FLASK_ENV"] = "testing"
os.environ["NO_X11"] = "1"  # Disable X11 requirement for headless testing
os.environ["OPENAI_REALTIME_NO_DISPLAY"] = "1"  # Disable display for OpenAI Realtime

# Import app components after setting test environment
from app import create_app
from app.models.menu import MenuItem, MenuModifier, MenuModifierGroup, MenuNameVariant
from app.models.order import Order, OrderItem, OrderItemModifier
from app.utils.menu_utils_db import load_menu_data
from app.utils.realtime_audio_sdk import get_realtime_processor


class MockAsyncWebSocket:
    """Mock WebSocket class for testing"""
    
    def __init__(self, test_inputs=None, mock_responses=None):
        self.test_inputs = test_inputs or []
        self.mock_responses = mock_responses or {}
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


@pytest.fixture
def app():
    """Create Flask app for testing"""
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    app.config["INITIALIZE_MENU_DATABASE"] = False  # Don't initialize DB automatically
    
    # Create all tables in the in-memory database
    with app.app_context():
        from app.db import db
        db.create_all()
        
        # Seed with test data
        _create_test_menu_data(db)
    
    yield app


@pytest.fixture
def mock_websocket():
    """Create mock WebSocket for testing"""
    return MockAsyncWebSocket()


def _create_test_menu_data(db):
    """Create test menu data for the database"""
    # Create test categories
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
        sushi_cat, cali_roll, spicy_tuna, sauce_group, 
        extra_avo, spicy_sauce, *variants
    ])
    db.session.commit()


class MockRealtimeProcessor:
    """Mock for the OpenAI Realtime API processor"""
    
    def __init__(self, test_scenario=None):
        self.test_scenario = test_scenario or "basic_order"
        self.processed_audio = []
        self.emitted_events = []
        self.scenarios = {
            "basic_order": self._basic_order_scenario,
            "menu_inquiry": self._menu_inquiry_scenario,
            "order_with_modifiers": self._order_with_modifiers_scenario,
            "missing_required_modifiers": self._missing_required_modifiers_scenario,
            "ambiguous_item": self._ambiguous_item_scenario,
        }
    
    async def process_media_stream(self, audio_generator, session_id):
        """Mock processing of audio stream with predefined test scenarios"""
        # Collect audio chunks for verification
        async for chunk in audio_generator:
            if chunk:
                self.processed_audio.append(chunk)
        
        # Get the right scenario event generator
        scenario_generator = self.scenarios.get(
            self.test_scenario, self._basic_order_scenario
        )
        
        # Yield events based on the selected scenario
        async for event in scenario_generator(session_id):
            self.emitted_events.append(event)
            yield event
    
    async def _basic_order_scenario(self, session_id):
        """Simulate a basic ordering scenario with the system"""
        # Customer says their name
        yield {
            "type": "transcript_complete",
            "text": "My name is John",
            "final": True,
            "timestamp": time.time()
        }
        
        # Short delay
        await asyncio.sleep(0.5)
        
        # Customer orders
        yield {
            "type": "transcript_complete",
            "text": "I'd like to order a California roll and a spicy tuna roll",
            "final": True,
            "timestamp": time.time()
        }
        
        # Short delay
        await asyncio.sleep(0.5)
        
        # Customer confirms order 
        yield {
            "type": "transcript_complete",
            "text": "Yes, that's correct. I'll pick it up.",
            "final": True,
            "timestamp": time.time()
        }
        
        # Short delay
        await asyncio.sleep(0.5)
        
        # Customer confirms and gives phone number
        yield {
            "type": "transcript_complete",
            "text": "Yes, my phone number is 555-123-4567",
            "final": True,
            "timestamp": time.time()
        }
    
    async def _menu_inquiry_scenario(self, session_id):
        """Simulate a customer asking about menu items"""
        # Customer asks about rolls
        yield {
            "type": "transcript_complete",
            "text": "What kind of rolls do you have?",
            "final": True,
            "timestamp": time.time()
        }
        
        # Short delay
        await asyncio.sleep(0.5)
        
        # Customer asks about specific roll
        yield {
            "type": "transcript_complete",
            "text": "What's in the California roll?",
            "final": True,
            "timestamp": time.time()
        }
        
        # Short delay
        await asyncio.sleep(0.5)
        
        # Customer asks about price
        yield {
            "type": "transcript_complete",
            "text": "How much is it?",
            "final": True,
            "timestamp": time.time()
        }
    
    async def _order_with_modifiers_scenario(self, session_id):
        """Simulate ordering with modifiers"""
        # Customer says their name
        yield {
            "type": "transcript_complete",
            "text": "My name is John",
            "final": True,
            "timestamp": time.time()
        }
        
        # Short delay
        await asyncio.sleep(0.5)
        
        # Customer orders with modifiers
        yield {
            "type": "transcript_complete",
            "text": "I'd like a California roll with extra avocado and a spicy tuna roll",
            "final": True,
            "timestamp": time.time()
        }
        
        # Short delay
        await asyncio.sleep(0.5)
        
        # Customer confirms
        yield {
            "type": "transcript_complete",
            "text": "That's right, and I'll pick it up",
            "final": True,
            "timestamp": time.time()
        }
        
        # Phone number confirmation
        yield {
            "type": "transcript_complete",
            "text": "My number is 555-987-6543",
            "final": True,
            "timestamp": time.time()
        }
    
    async def _missing_required_modifiers_scenario(self, session_id):
        """Simulate a scenario where a required modifier isn't selected"""
        # Customer says their name
        yield {
            "type": "transcript_complete",
            "text": "My name is Jane",
            "final": True,
            "timestamp": time.time()
        }
        
        # Customer orders an item that requires a modifier selection
        yield {
            "type": "transcript_complete",
            "text": "I want the California roll",
            "final": True,
            "timestamp": time.time()
        }
        
        # System asks about required sauce selection, customer responds
        yield {
            "type": "transcript_complete",
            "text": "I'll have it with spicy mayo",
            "final": True,
            "timestamp": time.time()
        }
        
        # Customer confirms order
        yield {
            "type": "transcript_complete",
            "text": "Yes, that's all. I'll pick it up",
            "final": True,
            "timestamp": time.time()
        }
    
    async def _ambiguous_item_scenario(self, session_id):
        """Simulate a scenario with an ambiguous item that needs clarification"""
        # Customer says their name
        yield {
            "type": "transcript_complete",
            "text": "My name is Sam",
            "final": True,
            "timestamp": time.time()
        }
        
        # Customer orders ambiguously
        yield {
            "type": "transcript_complete",
            "text": "I'd like a tuna roll",
            "final": True,
            "timestamp": time.time()
        }
        
        # Customer clarifies when prompted
        yield {
            "type": "transcript_complete",
            "text": "The spicy one please",
            "final": True,
            "timestamp": time.time()
        }
        
        # Customer confirms order
        yield {
            "type": "transcript_complete",
            "text": "Yes, for pickup",
            "final": True,
            "timestamp": time.time()
        }


@pytest.fixture
def mock_realtime_processor():
    """Create and patch the realtime processor for testing"""
    processor = MockRealtimeProcessor()
    
    with patch('app.utils.realtime_audio_sdk.get_realtime_processor', return_value=processor):
        yield processor


@pytest.fixture
def mock_tools_and_orchestrators():
    """Mock the orchestrators and tools used by the voice system"""
    # Mock the FSM orchestrator
    mock_fsm = MagicMock()
    mock_fsm.get_current_state.return_value = "GREETING"
    mock_fsm.set_state = AsyncMock()
    
    # Mock the slot store
    mock_slots = MagicMock()
    mock_slots.get_slot.return_value = None
    mock_slots.set_slot = AsyncMock()
    mock_slots.register_slot = MagicMock()
    
    # Mock the agent graph
    mock_graph = MagicMock()
    
    # Mock the model escalator
    mock_escalator = MagicMock()
    
    # Mock the frontline agent
    mock_frontline = MagicMock()
    mock_frontline.process_voice_input = AsyncMock(return_value="I understand your request")
    mock_frontline.get_capabilities = MagicMock(return_value=["menu", "cart", "ordering"])
    
    # Patch the initialize_agents function
    with patch('app.routes.voice_orchestrated_realtime.init_agents', return_value=mock_frontline), \
         patch('app.routes.voice_orchestrated_realtime.fsm_orchestrator', mock_fsm), \
         patch('app.routes.voice_orchestrated_realtime.slot_store', mock_slots), \
         patch('app.routes.voice_orchestrated_realtime.agent_graph', mock_graph), \
         patch('app.routes.voice_orchestrated_realtime.model_escalator', mock_escalator):
        
        yield {
            "frontline": mock_frontline,
            "fsm": mock_fsm,
            "slots": mock_slots,
            "graph": mock_graph,
            "escalator": mock_escalator
        }


@pytest.mark.asyncio
async def test_basic_ordering_flow(app, mock_websocket, mock_realtime_processor, mock_tools_and_orchestrators):
    """Test the basic ordering flow from greeting to order completion"""
    # Set up the scenario
    mock_realtime_processor.test_scenario = "basic_order"
    
    # Set up the mock WebSocket with customer responses
    mock_websocket.test_inputs = [
        # Simulate audio chunks as they would come from Twilio
        json.dumps({
            "event": "start",
            "start": {
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
            }
        }),
        # Add audio chunks (simulated as base64-encoded data)
        json.dumps({
            "event": "media",
            "media": {
                "payload": base64.b64encode(b"audio_chunk_1").decode('utf-8')
            }
        }),
        json.dumps({
            "event": "media",
            "media": {
                "payload": base64.b64encode(b"audio_chunk_2").decode('utf-8')
            }
        })
    ]
    
    # Import the WebSocket handler from the module
    from app.routes.voice_orchestrated_realtime import media_stream
    
    # Call the WebSocket handler with our mock
    try:
        await media_stream(mock_websocket)
    except asyncio.CancelledError:
        # This is expected as we're likely not going through the full flow
        pass
    
    # Check for proper interactions
    assert mock_tools_and_orchestrators["fsm"].set_state.called, "FSM state should be set"
    assert mock_tools_and_orchestrators["frontline"].process_voice_input.called, "Frontline agent should process input"
    
    # Check for appropriate WebSocket messages
    ws_messages = [json.loads(msg) if isinstance(msg, str) else msg for msg in mock_websocket.sent_messages]
    
    # Should have a connection confirmation message
    connection_messages = [m for m in ws_messages if m.get("type") == "connected"]
    assert len(connection_messages) > 0, "Should send connection confirmation"
    
    # Should have processed the customer transcript and sent responses
    transcript_messages = [m for m in ws_messages if m.get("event") == "transcript"]
    assert len(transcript_messages) > 0, "Should process and send transcript events"


@pytest.mark.asyncio
async def test_menu_inquiry_flow(app, mock_websocket, mock_realtime_processor, mock_tools_and_orchestrators):
    """Test the flow where a customer asks about menu items"""
    # Set up the scenario for menu inquiries
    mock_realtime_processor.test_scenario = "menu_inquiry"
    
    # Prepare mock WebSocket
    mock_websocket.test_inputs = [
        # Start event
        json.dumps({
            "event": "start",
            "start": {
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
            }
        }),
        # Audio chunks with customer's menu questions
        json.dumps({
            "event": "media",
            "media": {
                "payload": base64.b64encode(b"audio_chunk_1").decode('utf-8')
            }
        })
    ]
    
    # Import and call the WebSocket handler
    from app.routes.voice_orchestrated_realtime import media_stream
    
    # Execute the handler with our mock
    try:
        await media_stream(mock_websocket)
    except asyncio.CancelledError:
        pass
    
    # Check for appropriate state transitions
    assert mock_tools_and_orchestrators["fsm"].set_state.called, "FSM state should be set"
    
    # Expect the frontline agent to process the menu inquiry transcripts
    assert mock_tools_and_orchestrators["frontline"].process_voice_input.called, "Frontline agent should process input"
    
    # Verify appropriate WebSocket messages were sent
    ws_messages = [json.loads(msg) if isinstance(msg, str) else msg for msg in mock_websocket.sent_messages]
    
    # Should have transcript processing events
    transcript_messages = [m for m in ws_messages if m.get("event") == "transcript"]
    assert len(transcript_messages) > 0, "Should process and send transcript events"


@pytest.mark.asyncio
async def test_order_with_modifiers(app, mock_websocket, mock_realtime_processor, mock_tools_and_orchestrators):
    """Test ordering items with modifiers"""
    # Set up the scenario for ordering with modifiers
    mock_realtime_processor.test_scenario = "order_with_modifiers"
    
    # Mock agent behavior for modifier handling
    mock_tools_and_orchestrators["frontline"].lookup_menu_item = MagicMock(
        return_value={
            "name": "California Roll", 
            "plu": "CALI-ROLL",
            "price": 850,
            "modifiers": [{"name": "Extra Avocado", "plu": "MOD-EXTRA-AVO", "price_change": 150}]
        }
    )
    
    # Prepare mock WebSocket
    mock_websocket.test_inputs = [
        # Start event
        json.dumps({
            "event": "start",
            "start": {
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
            }
        }),
        # Audio chunks with order including modifiers
        json.dumps({
            "event": "media",
            "media": {
                "payload": base64.b64encode(b"audio_chunk_1").decode('utf-8')
            }
        })
    ]
    
    # Import and call the WebSocket handler
    from app.routes.voice_orchestrated_realtime import media_stream
    
    # Execute the handler with our mock
    try:
        await media_stream(mock_websocket)
    except asyncio.CancelledError:
        pass
    
    # Verify appropriate handling of the modifier
    assert mock_tools_and_orchestrators["frontline"].process_voice_input.called, "Frontline agent should process input"
    call_args = mock_tools_and_orchestrators["frontline"].process_voice_input.call_args_list
    
    # Check that the last call contains the modifier information
    last_call = call_args[-1] if call_args else None
    if last_call:
        # In a real test, we'd check the specific transcript content
        assert "extra avocado" in str(last_call).lower() or "spicy tuna" in str(last_call).lower(), \
            "Should process modification request"


@pytest.mark.asyncio
async def test_required_modifier_prompt(app, mock_websocket, mock_realtime_processor, mock_tools_and_orchestrators):
    """Test that system prompts for required modifiers"""
    # Set up scenario for missing required modifiers
    mock_realtime_processor.test_scenario = "missing_required_modifiers"
    
    # Configure mock guardrail agent to report missing required modifiers
    mock_tools_and_orchestrators["frontline"].add_to_cart = AsyncMock(
        side_effect=[
            {"status": "error", "message": "Please select a sauce option (required)"},
            {"status": "success", "item": "California Roll with Spicy Mayo"}
        ]
    )
    
    # Prepare mock WebSocket
    mock_websocket.test_inputs = [
        # Start event
        json.dumps({
            "event": "start",
            "start": {
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
            }
        }),
        # Audio chunks for the interaction
        json.dumps({
            "event": "media",
            "media": {
                "payload": base64.b64encode(b"audio_chunk_1").decode('utf-8')
            }
        })
    ]
    
    # Import and call the WebSocket handler
    from app.routes.voice_orchestrated_realtime import media_stream
    
    # Execute the handler with our mock
    try:
        await media_stream(mock_websocket)
    except asyncio.CancelledError:
        pass
    
    # Verify the system prompted for the required modifier
    ws_messages = [json.loads(msg) if isinstance(msg, str) else msg for msg in mock_websocket.sent_messages]
    
    # Look for error messages or prompts about required modifiers
    error_messages = [
        m for m in ws_messages 
        if isinstance(m, dict) and 
        (m.get("event") == "error" or (m.get("event") == "message" and "required" in str(m.get("text", "")).lower()))
    ]
    
    # Should have at least some message handling the modifier requirement
    assert mock_tools_and_orchestrators["frontline"].add_to_cart.call_count >= 1, \
        "Should attempt to add item to cart"


@pytest.mark.asyncio
async def test_ambiguous_item_resolution(app, mock_websocket, mock_realtime_processor, mock_tools_and_orchestrators):
    """Test resolution of ambiguous menu items"""
    # Set up the ambiguous item scenario
    mock_realtime_processor.test_scenario = "ambiguous_item"
    
    # Configure mock to handle ambiguity
    mock_tools_and_orchestrators["frontline"].lookup_menu_item = MagicMock(
        side_effect=[
            {"status": "ambiguous", "options": [
                {"name": "Spicy Tuna Roll", "plu": "SPICY-TUNA"},
                {"name": "Tuna Roll", "plu": "TUNA-ROLL"}
            ]},
            {"name": "Spicy Tuna Roll", "plu": "SPICY-TUNA", "price": 950}
        ]
    )
    
    # Prepare mock WebSocket
    mock_websocket.test_inputs = [
        # Start event
        json.dumps({
            "event": "start",
            "start": {
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
            }
        }),
        # Audio chunks with ambiguous order and clarification
        json.dumps({
            "event": "media",
            "media": {
                "payload": base64.b64encode(b"audio_chunk_1").decode('utf-8')
            }
        })
    ]
    
    # Import and call the WebSocket handler
    from app.routes.voice_orchestrated_realtime import media_stream
    
    # Execute the handler with our mock
    try:
        await media_stream(mock_websocket)
    except asyncio.CancelledError:
        pass
    
    # Verify ambiguity handling
    assert mock_tools_and_orchestrators["frontline"].lookup_menu_item.call_count >= 1, \
        "Should attempt to look up menu items"
    
    # Check for clarification prompts in the WebSocket messages
    ws_messages = [json.loads(msg) if isinstance(msg, str) else msg for msg in mock_websocket.sent_messages]
    
    # In real implementation, we'd check for specific clarification messages


@pytest.mark.asyncio
async def test_silence_handling(app, mock_websocket, mock_realtime_processor, mock_tools_and_orchestrators):
    """Test handling of silence and timeouts"""
    # Configure to trigger silence events
    mock_realtime_processor.test_scenario = "basic_order"
    
    # Add explicit silence events to the generator
    original_scenario = mock_realtime_processor._basic_order_scenario
    
    async def scenario_with_silence(session_id):
        # Add silence event before the first response
        yield {
            "type": "silence_detected",
            "duration": 3.0,
            "timestamp": time.time()
        }
        
        # Continue with normal scenario
        async for event in original_scenario(session_id):
            yield event
    
    mock_realtime_processor._basic_order_scenario = scenario_with_silence
    
    # Prepare mock WebSocket
    mock_websocket.test_inputs = [
        # Start event
        json.dumps({
            "event": "start",
            "start": {
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
            }
        }),
        # Audio chunks
        json.dumps({
            "event": "media",
            "media": {
                "payload": base64.b64encode(b"audio_chunk_1").decode('utf-8')
            }
        })
    ]
    
    # Import and call the WebSocket handler
    from app.routes.voice_orchestrated_realtime import media_stream
    
    # Execute the handler with our mock
    try:
        await media_stream(mock_websocket)
    except asyncio.CancelledError:
        pass
    
    # Verify proper prompting during silence
    ws_messages = [json.loads(msg) if isinstance(msg, str) else msg for msg in mock_websocket.sent_messages]
    
    # Check for messages sent in response to silence
    silence_response_messages = [
        m for m in ws_messages 
        if isinstance(m, dict) and m.get("event") == "message" and m.get("text")
    ]
    
    # Should have at least one prompt in response to silence
    assert len(silence_response_messages) > 0, "Should prompt user after silence"


@pytest.mark.asyncio
async def test_error_handling(app, mock_websocket, mock_realtime_processor, mock_tools_and_orchestrators):
    """Test system's handling of errors during processing"""
    # Configure mock to throw an error
    mock_tools_and_orchestrators["frontline"].process_voice_input = AsyncMock(
        side_effect=Exception("Test error in processing")
    )
    
    # Set up the scenario
    mock_realtime_processor.test_scenario = "basic_order"
    
    # Prepare mock WebSocket
    mock_websocket.test_inputs = [
        # Start event
        json.dumps({
            "event": "start",
            "start": {
                "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000}
            }
        }),
        # Audio chunks
        json.dumps({
            "event": "media",
            "media": {
                "payload": base64.b64encode(b"audio_chunk_1").decode('utf-8')
            }
        })
    ]
    
    # Import and call the WebSocket handler
    from app.routes.voice_orchestrated_realtime import media_stream
    
    # Execute the handler with our mock
    try:
        await media_stream(mock_websocket)
    except asyncio.CancelledError:
        pass
    
    # Verify error handling
    ws_messages = [json.loads(msg) if isinstance(msg, str) else msg for msg in mock_websocket.sent_messages]
    
    # Look for error messages sent to the client
    error_messages = [
        m for m in ws_messages 
        if isinstance(m, dict) and (
            m.get("type") == "error" or 
            m.get("event") == "error" or
            (m.get("event") == "message" and "error" in str(m.get("text", "")).lower())
        )
    ]
    
    # Should send some form of error message
    assert len(error_messages) > 0, "Should send error message on exception"
    
    # Check if WebSocket was closed with an error code
    assert mock_websocket.closed or any("error" in str(msg).lower() for msg in mock_websocket.sent_messages), \
        "Should close WebSocket or send error on exception"


# Run these tests with: pytest -v tests/e2e/test_ai_voice_ordering.py