"""
Unit tests for Finite State Machine (FSM).
"""
import pytest
from app.fsm.core import ConversationState, ConversationEvent, FSMError
from app.utils.fsm_async import AsyncConversationFSM, AsyncFSMManager
from app.fsm.handlers.greeting import GreetingHandler
from app.fsm.handlers.main_menu import MainMenuHandler
from app.fsm.handlers.ordering import OrderingHandler


class TestFSMCore:
    """Test FSM core functionality."""
    
    @pytest.mark.asyncio
    async def test_fsm_initialization(self, mock_redis):
        """Test FSM initialization."""
        fsm = AsyncConversationFSM(
            session_id="test_session",
            redis_client=mock_redis
        )
        
        assert fsm.session_id == "test_session"
        assert fsm.current_state == ConversationState.GREETING
        assert fsm.context == {}
        assert fsm.history == []
    
    @pytest.mark.asyncio
    async def test_fsm_state_transitions(self, mock_redis):
        """Test valid state transitions."""
        fsm = AsyncConversationFSM(
            session_id="test_session",
            redis_client=mock_redis
        )
        
        # Greeting -> Main Menu
        await fsm.transition(ConversationState.MAIN_MENU)
        assert fsm.current_state == ConversationState.MAIN_MENU
        assert len(fsm.history) == 1
        
        # Main Menu -> Ordering
        await fsm.transition(ConversationState.ORDERING)
        assert fsm.current_state == ConversationState.ORDERING
        assert len(fsm.history) == 2
        
        # Ordering -> Validation
        await fsm.transition(ConversationState.VALIDATION)
        assert fsm.current_state == ConversationState.VALIDATION
        assert len(fsm.history) == 3
    
    @pytest.mark.asyncio
    async def test_fsm_invalid_transition(self, mock_redis):
        """Test invalid state transition."""
        fsm = AsyncConversationFSM(
            session_id="test_session",
            redis_client=mock_redis
        )
        
        # Try to go directly from Greeting to Fulfillment (invalid)
        with pytest.raises(FSMError):
            await fsm.transition(ConversationState.FULFILLMENT)
    
    @pytest.mark.asyncio
    async def test_fsm_context_management(self, mock_redis):
        """Test FSM context management."""
        fsm = AsyncConversationFSM(
            session_id="test_session",
            redis_client=mock_redis
        )
        
        # Update context
        await fsm.update_context({"customer_name": "John Doe"})
        assert fsm.context["customer_name"] == "John Doe"
        
        # Add more context
        await fsm.update_context({"order_type": "pickup"})
        assert fsm.context["customer_name"] == "John Doe"
        assert fsm.context["order_type"] == "pickup"
    
    @pytest.mark.asyncio
    async def test_fsm_event_processing(self, mock_redis):
        """Test FSM event processing."""
        fsm = AsyncConversationFSM(
            session_id="test_session",
            redis_client=mock_redis
        )
        
        # Process greeting completed event
        await fsm.process_event(ConversationEvent.CUSTOMER_GREETED)
        assert fsm.current_state == ConversationState.MAIN_MENU
        
        # Process order started event
        await fsm.process_event(ConversationEvent.ORDER_STARTED)
        assert fsm.current_state == ConversationState.ORDERING
    
    @pytest.mark.asyncio
    async def test_fsm_persistence(self, mock_redis):
        """Test FSM state persistence."""
        fsm = AsyncConversationFSM(
            session_id="test_session",
            redis_client=mock_redis
        )
        
        # Update state and context
        await fsm.transition(ConversationState.MAIN_MENU)
        await fsm.update_context({"customer_name": "Jane Doe"})
        
        # Save state
        await fsm.save()
        assert mock_redis.hset.called
        
        # Load state
        await fsm.load()
        assert mock_redis.hgetall.called


class TestFSMHandlers:
    """Test FSM state handlers."""
    
    @pytest.mark.asyncio
    async def test_greeting_handler(self):
        """Test greeting state handler."""
        handler = GreetingHandler()
        context = {}
        
        result = await handler.handle(
            context,
            user_input="My name is John"
        )
        
        assert result["next_state"] == ConversationState.MAIN_MENU
        assert result["context"]["customer_name"] == "John"
        assert "response" in result
    
    @pytest.mark.asyncio
    async def test_main_menu_handler(self):
        """Test main menu handler."""
        handler = MainMenuHandler()
        context = {"customer_name": "John"}
        
        # Test order intent
        result = await handler.handle(
            context,
            user_input="I'd like to place an order"
        )
        
        assert result["next_state"] == ConversationState.ORDERING
        assert "response" in result
    
    @pytest.mark.asyncio
    async def test_ordering_handler(self):
        """Test ordering state handler."""
        handler = OrderingHandler()
        context = {
            "customer_name": "John",
            "cart": {
                "items": []
            }
        }
        
        result = await handler.handle(
            context,
            user_input="I want two California rolls"
        )
        
        assert result["next_state"] in [ConversationState.ORDERING, ConversationState.VALIDATION]
        assert "response" in result


class TestFSMManager:
    """Test FSM manager functionality."""
    
    @pytest.mark.asyncio
    async def test_fsm_manager_initialization(self, mock_redis):
        """Test FSM manager initialization."""
        manager = AsyncFSMManager(redis_client=mock_redis)
        
        assert manager.fsm_instances == {}
        assert manager.redis_client == mock_redis
    
    @pytest.mark.asyncio
    async def test_fsm_manager_create_instance(self, mock_redis):
        """Test creating FSM instance."""
        manager = AsyncFSMManager(redis_client=mock_redis)
        
        fsm = await manager.create_fsm("session_123")
        
        assert fsm.session_id == "session_123"
        assert "session_123" in manager.fsm_instances
        assert manager.fsm_instances["session_123"] == fsm
    
    @pytest.mark.asyncio
    async def test_fsm_manager_get_instance(self, mock_redis):
        """Test getting existing FSM instance."""
        manager = AsyncFSMManager(redis_client=mock_redis)
        
        # Create instance
        fsm1 = await manager.create_fsm("session_456")
        
        # Get same instance
        fsm2 = await manager.get_fsm("session_456")
        
        assert fsm1 == fsm2
    
    @pytest.mark.asyncio
    async def test_fsm_manager_remove_instance(self, mock_redis):
        """Test removing FSM instance."""
        manager = AsyncFSMManager(redis_client=mock_redis)
        
        # Create and remove
        await manager.create_fsm("session_789")
        await manager.remove_fsm("session_789")
        
        assert "session_789" not in manager.fsm_instances
        
        # Getting removed instance creates new one
        fsm = await manager.get_fsm("session_789")
        assert fsm is not None
        assert fsm.session_id == "session_789"
    
    @pytest.mark.asyncio
    async def test_fsm_manager_multiple_instances(self, mock_redis):
        """Test managing multiple FSM instances."""
        manager = AsyncFSMManager(redis_client=mock_redis)
        
        # Create multiple instances
        fsm1 = await manager.create_fsm("session_001")
        fsm2 = await manager.create_fsm("session_002")
        fsm3 = await manager.create_fsm("session_003")
        
        assert len(manager.fsm_instances) == 3
        assert manager.fsm_instances["session_001"] == fsm1
        assert manager.fsm_instances["session_002"] == fsm2
        assert manager.fsm_instances["session_003"] == fsm3
        
        # Each has independent state
        await fsm1.transition(ConversationState.MAIN_MENU)
        await fsm2.transition(ConversationState.MAIN_MENU)
        await fsm2.transition(ConversationState.ORDERING)
        
        assert fsm1.current_state == ConversationState.MAIN_MENU
        assert fsm2.current_state == ConversationState.ORDERING
        assert fsm3.current_state == ConversationState.GREETING