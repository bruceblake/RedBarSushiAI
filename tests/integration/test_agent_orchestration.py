"""
Integration tests for agent orchestration.
"""
import pytest
from unittest.mock import AsyncMock, patch
from app.utils.agent_orchestration_async import AsyncAgentOrchestrator
from app.agents.factory_async import AsyncAgentFactory
from app.fsm.core import ConversationState, ConversationEvent


class TestAgentOrchestration:
    """Test agent orchestration system."""
    
    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self, db_session, mock_redis, mock_openai_client):
        """Test orchestrator initialization."""
        orchestrator = AsyncAgentOrchestrator(
            db_session=db_session,
            redis_client=mock_redis,
            llm_client=mock_openai_client
        )
        
        assert orchestrator.agent_factory is not None
        assert orchestrator.fsm_manager is not None
        assert orchestrator.intent_detector is not None
    
    @pytest.mark.asyncio
    async def test_orchestrator_process_greeting(self, db_session, mock_redis, mock_openai_client):
        """Test processing greeting phase."""
        orchestrator = AsyncAgentOrchestrator(
            db_session=db_session,
            redis_client=mock_redis,
            llm_client=mock_openai_client
        )
        
        # Mock AI response
        mock_openai_client.chat.completions.create.return_value.choices[0].message.content = (
            "Hello! Welcome to Red Bar Sushi. May I have your name please?"
        )
        
        result = await orchestrator.process_voice_input(
            call_sid="test_call_001",
            transcript="",  # Initial call
            initial_call=True
        )
        
        assert "response" in result
        assert "Welcome" in result["response"]
        assert result["state"] == ConversationState.GREETING.value
    
    @pytest.mark.asyncio
    async def test_orchestrator_name_collection(self, db_session, mock_redis, mock_openai_client):
        """Test name collection and transition to main menu."""
        orchestrator = AsyncAgentOrchestrator(
            db_session=db_session,
            redis_client=mock_redis,
            llm_client=mock_openai_client
        )
        
        # Initialize FSM
        await orchestrator.process_voice_input(
            call_sid="test_call_002",
            transcript="",
            initial_call=True
        )
        
        # Mock intent detection for name
        with patch.object(orchestrator.intent_detector, 'detect_intent', 
                         return_value=ConversationEvent.CUSTOMER_GREETED):
            
            mock_openai_client.chat.completions.create.return_value.choices[0].message.content = (
                "Nice to meet you, John! How can I help you today? Would you like to hear our menu, "
                "place an order, or speak with our staff?"
            )
            
            result = await orchestrator.process_voice_input(
                call_sid="test_call_002",
                transcript="My name is John"
            )
            
            assert result["state"] == ConversationState.MAIN_MENU.value
            assert "context" in result
            assert result["context"].get("customer_name") == "John"
    
    @pytest.mark.asyncio
    async def test_orchestrator_menu_inquiry(self, db_session, mock_redis, mock_openai_client, sample_menu_data):
        """Test menu inquiry flow."""
        orchestrator = AsyncAgentOrchestrator(
            db_session=db_session,
            redis_client=mock_redis,
            llm_client=mock_openai_client
        )
        
        # Set up FSM in main menu state
        fsm = await orchestrator.fsm_manager.get_fsm("test_call_003")
        await fsm.transition(ConversationState.MAIN_MENU)
        await fsm.update_context({"customer_name": "Jane"})
        
        # Mock intent for menu inquiry
        with patch.object(orchestrator.intent_detector, 'detect_intent',
                         return_value=ConversationEvent.MENU_INQUIRY):
            
            mock_openai_client.chat.completions.create.return_value.choices[0].message.content = (
                "We have California Roll for $12.95 and Spicy Tuna Roll for $14.95 in our sushi selection."
            )
            
            result = await orchestrator.process_voice_input(
                call_sid="test_call_003",
                transcript="What sushi rolls do you have?"
            )
            
            assert "California Roll" in result["response"]
            assert "$12.95" in result["response"]
    
    @pytest.mark.asyncio
    async def test_orchestrator_order_flow(self, db_session, mock_redis, mock_openai_client, sample_menu_data):
        """Test complete order flow."""
        orchestrator = AsyncAgentOrchestrator(
            db_session=db_session,
            redis_client=mock_redis,
            llm_client=mock_openai_client
        )
        
        # Set up FSM in main menu state
        fsm = await orchestrator.fsm_manager.get_fsm("test_call_004")
        await fsm.transition(ConversationState.MAIN_MENU)
        await fsm.update_context({"customer_name": "Bob"})
        
        # 1. Start ordering
        with patch.object(orchestrator.intent_detector, 'detect_intent',
                         return_value=ConversationEvent.ORDER_STARTED):
            
            mock_openai_client.chat.completions.create.return_value.choices[0].message.content = (
                "I'll help you place an order. What would you like to order today?"
            )
            
            result = await orchestrator.process_voice_input(
                call_sid="test_call_004",
                transcript="I want to place an order"
            )
            
            assert result["state"] == ConversationState.ORDERING.value
        
        # 2. Add items to cart
        mock_openai_client.chat.completions.create.return_value.choices[0].message.content = (
            "I've added 2 California Rolls to your order. Would you like anything else?"
        )
        
        result = await orchestrator.process_voice_input(
            call_sid="test_call_004",
            transcript="I want two California rolls"
        )
        
        assert "added" in result["response"].lower()
        
        # 3. Complete order
        with patch.object(orchestrator.intent_detector, 'detect_intent',
                         return_value=ConversationEvent.CART_FINALIZED):
            
            await fsm.transition(ConversationState.VALIDATION)
            
            mock_openai_client.chat.completions.create.return_value.choices[0].message.content = (
                "Your order of 2 California Rolls comes to $25.90. Is this correct?"
            )
            
            result = await orchestrator.process_voice_input(
                call_sid="test_call_004",
                transcript="That's all"
            )
            
            assert "$25.90" in result["response"]
    
    @pytest.mark.asyncio
    async def test_orchestrator_agent_handoff(self, db_session, mock_redis, mock_openai_client):
        """Test agent handoff mechanism."""
        orchestrator = AsyncAgentOrchestrator(
            db_session=db_session,
            redis_client=mock_redis,
            llm_client=mock_openai_client
        )
        
        # Set up in ordering state
        fsm = await orchestrator.fsm_manager.get_fsm("test_call_005")
        await fsm.transition(ConversationState.MAIN_MENU)
        await fsm.transition(ConversationState.ORDERING)
        
        # Test handoff from frontline to cart agent
        result = await orchestrator.process_voice_input(
            call_sid="test_call_005",
            transcript="Add a spicy tuna roll"
        )
        
        # Verify cart agent was used
        assert result["agent_used"] in ["cart", "frontline"]
    
    @pytest.mark.asyncio
    async def test_orchestrator_error_handling(self, db_session, mock_redis, mock_openai_client):
        """Test error handling in orchestration."""
        orchestrator = AsyncAgentOrchestrator(
            db_session=db_session,
            redis_client=mock_redis,
            llm_client=mock_openai_client
        )
        
        # Simulate agent error
        with patch.object(orchestrator.agent_factory, 'get_agent',
                         side_effect=Exception("Agent initialization failed")):
            
            result = await orchestrator.process_voice_input(
                call_sid="test_call_006",
                transcript="Hello",
                initial_call=True
            )
            
            assert "error" in result
            assert result["error"] is True
    
    @pytest.mark.asyncio
    async def test_orchestrator_escalation(self, db_session, mock_redis, mock_openai_client):
        """Test escalation to human."""
        orchestrator = AsyncAgentOrchestrator(
            db_session=db_session,
            redis_client=mock_redis,
            llm_client=mock_openai_client
        )
        
        # Set up FSM
        fsm = await orchestrator.fsm_manager.get_fsm("test_call_007")
        await fsm.transition(ConversationState.MAIN_MENU)
        
        # Request human
        with patch.object(orchestrator.intent_detector, 'detect_intent',
                         return_value=ConversationEvent.ESCALATION_REQUESTED):
            
            mock_openai_client.chat.completions.create.return_value.choices[0].message.content = (
                "I'll connect you with a team member right away. Please hold."
            )
            
            result = await orchestrator.process_voice_input(
                call_sid="test_call_007",
                transcript="I need to speak to a person"
            )
            
            assert result["state"] == ConversationState.ESCALATION.value
            assert "connect" in result["response"].lower()
    
    @pytest.mark.asyncio
    async def test_orchestrator_context_preservation(self, db_session, mock_redis, mock_openai_client):
        """Test context preservation across interactions."""
        orchestrator = AsyncAgentOrchestrator(
            db_session=db_session,
            redis_client=mock_redis,
            llm_client=mock_openai_client
        )
        
        call_sid = "test_call_008"
        
        # First interaction - set name
        await orchestrator.process_voice_input(
            call_sid=call_sid,
            transcript="",
            initial_call=True
        )
        
        fsm = await orchestrator.fsm_manager.get_fsm(call_sid)
        await fsm.update_context({"customer_name": "Alice"})
        await fsm.transition(ConversationState.MAIN_MENU)
        
        # Second interaction - name should be preserved
        result = await orchestrator.process_voice_input(
            call_sid=call_sid,
            transcript="What's my name?"
        )
        
        assert fsm.context["customer_name"] == "Alice"
    
    @pytest.mark.asyncio
    async def test_orchestrator_tool_execution(self, db_session, mock_redis, mock_openai_client, sample_menu_data):
        """Test tool execution through orchestrator."""
        orchestrator = AsyncAgentOrchestrator(
            db_session=db_session,
            redis_client=mock_redis,
            llm_client=mock_openai_client
        )
        
        # Execute menu search tool
        result = await orchestrator.execute_tool(
            call_sid="test_call_009",
            tool_name="search_menu",
            tool_args={"query": "california"}
        )
        
        assert result["success"] is True
        assert "results" in result["data"]
        assert len(result["data"]["results"]) > 0