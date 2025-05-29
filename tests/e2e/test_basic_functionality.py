"""
Basic functionality tests for RedBarSushiAI.
These tests verify core components work correctly.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.fsm.core import ConversationState, ConversationEvent, AsyncConversationFSM
from app.utils.intent_detector_async import AsyncIntentDetector
from app.utils.menu_matcher_cache_async import clear_cached_menu_matcher
from app.api.conversation_relay.handler import ConversationRelayHandler


class TestFSMTransitions:
    """Test FSM state transitions."""
    
    @pytest.mark.asyncio
    async def test_greeting_to_main_menu_transition(self):
        """Test FSM transitions from GREETING to MAIN_MENU."""
        fsm = AsyncConversationFSM("TEST_CALL")
        
        # Start conversation
        await fsm.trigger(ConversationEvent.START_CONVERSATION)
        assert fsm.current_state == ConversationState.GREETING
        
        # Provide name
        await fsm.trigger(ConversationEvent.USER_PROVIDES_NAME)
        assert fsm.current_state == ConversationState.MAIN_MENU
    
    @pytest.mark.asyncio
    async def test_main_menu_to_ordering_transition(self):
        """Test FSM transitions from MAIN_MENU to ORDERING."""
        fsm = AsyncConversationFSM("TEST_CALL")
        fsm.current_state = ConversationState.MAIN_MENU
        
        # Start order
        await fsm.trigger(ConversationEvent.START_ORDER)
        assert fsm.current_state == ConversationState.ORDERING
    
    @pytest.mark.asyncio
    async def test_ordering_to_confirmation_flow(self):
        """Test order completion flow."""
        fsm = AsyncConversationFSM("TEST_CALL")
        fsm.current_state = ConversationState.ORDERING
        
        # Complete order
        await fsm.trigger(ConversationEvent.COMPLETE_ORDER)
        assert fsm.current_state in [ConversationState.VALIDATION, ConversationState.CONFIRMATION]


class TestIntentDetection:
    """Test LLM-based intent detection."""
    
    @pytest.mark.asyncio
    async def test_intent_detector_initialization(self):
        """Test intent detector can be initialized."""
        with patch('app.utils.intent_detector_async.AsyncOpenAI'):
            detector = AsyncIntentDetector()
            assert detector.client is not None
            assert detector.model == "gpt-4o-mini"
    
    @pytest.mark.asyncio
    async def test_empty_transcript_returns_none(self):
        """Test empty transcript handling."""
        with patch('app.utils.intent_detector_async.AsyncOpenAI'):
            detector = AsyncIntentDetector()
            result = await detector.detect_intent("", ConversationState.GREETING, {})
            assert result is None


class TestConversationRelay:
    """Test ConversationRelay handler."""
    
    @pytest.mark.asyncio
    async def test_handler_initialization(self):
        """Test handler can be initialized."""
        mock_ws = AsyncMock()
        handler = ConversationRelayHandler(mock_ws)
        assert handler.websocket == mock_ws
        assert handler.session_id is None
        assert handler.call_sid is None
    
    @pytest.mark.asyncio
    async def test_setup_event_stores_session_data(self):
        """Test setup event stores session information."""
        mock_ws = AsyncMock()
        handler = ConversationRelayHandler(mock_ws)
        
        setup_message = {
            "type": "setup",
            "sessionId": "ES123",
            "callSid": "CA123",
            "from": "+1234567890"
        }
        
        with patch('app.utils.agent_orchestration_async.async_agent_orchestrator.start_new_conversation'):
            with patch('app.utils.agent_orchestration_async.async_agent_orchestrator.process_voice_input') as mock_process:
                mock_process.return_value = {"text": ""}
                await handler.handle_setup(setup_message)
        
        assert handler.session_id == "ES123"
        assert handler.call_sid == "CA123"
        assert handler.from_number == "+1234567890"


class TestMenuCache:
    """Test menu cache functionality."""
    
    @pytest.mark.asyncio
    async def test_cache_clear_function_exists(self):
        """Test cache clear function is available."""
        # Should not raise exception
        await clear_cached_menu_matcher()


class TestAgentOrchestrator:
    """Test agent orchestrator basics."""
    
    @pytest.mark.asyncio
    async def test_orchestrator_has_required_methods(self):
        """Test orchestrator has required methods."""
        from app.utils.agent_orchestration_async import async_agent_orchestrator
        
        assert hasattr(async_agent_orchestrator, 'start_new_conversation')
        assert hasattr(async_agent_orchestrator, 'process_voice_input')
        assert hasattr(async_agent_orchestrator, 'handle_interruption')
        assert hasattr(async_agent_orchestrator, 'get_fsm')


class TestAPIEndpoints:
    """Test API endpoints are registered."""
    
    def test_voice_endpoints_exist(self):
        """Test voice endpoints are registered."""
        from app.main import app
        
        routes = [route.path for route in app.routes if hasattr(route, 'path')]
        
        # Check critical endpoints
        assert any('/voice' in path for path in routes)
        assert any('/conversation-relay' in path for path in routes)
    
    def test_menu_endpoints_exist(self):
        """Test menu endpoints are registered."""
        from app.main import app
        
        routes = [route.path for route in app.routes if hasattr(route, 'path')]
        
        # Check menu endpoints
        assert any('/menu' in path for path in routes)


@pytest.mark.asyncio
async def test_basic_imports():
    """Test all critical imports work."""
    # These imports should not raise exceptions
    from app.main import app
    from app.fsm.core import AsyncConversationFSM
    from app.utils.agent_orchestration_async import async_agent_orchestrator
    from app.agents.factory_async import async_agent_factory
    from app.api.conversation_relay.handler import ConversationRelayHandler
    
    assert app is not None
    assert AsyncConversationFSM is not None
    assert async_agent_orchestrator is not None