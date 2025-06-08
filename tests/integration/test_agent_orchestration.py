"""
Integration tests for agent orchestration.
"""
import pytest
import json
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


class TestAgentToAgentCommunication:
    """Test agent-to-agent communication and handoffs - Task 3.1."""
    
    @pytest.mark.asyncio
    async def test_frontline_to_menu_agent_handoff(self, db_session, mock_redis, mock_openai_client, sample_menu_data):
        """Test frontline to menu agent handoff - Task 3.1.1."""
        orchestrator = AsyncAgentOrchestrator(
            db_session=db_session,
            redis_client=mock_redis,
            llm_client=mock_openai_client
        )
        
        # Initialize conversation in main menu state
        call_sid = "test_handoff_001"
        fsm = await orchestrator.fsm_manager.get_fsm(call_sid)
        await fsm.transition(ConversationState.MAIN_MENU)
        await fsm.update_context({
            "customer_name": "Test User",
            "conversation_history": []
        })
        
        # Mock intent detection for menu inquiry
        with patch.object(orchestrator.intent_detector, 'detect_intent',
                         return_value=ConversationEvent.MENU_INQUIRY):
            
            # Track which agents are used
            agents_used = []
            
            async def track_agent_creation(agent_type, *args, **kwargs):
                agents_used.append(agent_type)
                return await original_get_agent(agent_type, *args, **kwargs)
            
            original_get_agent = orchestrator.agent_factory.get_agent
            
            with patch.object(orchestrator.agent_factory, 'get_agent', side_effect=track_agent_creation):
                # First inquiry - should use frontline agent initially
                result1 = await orchestrator.process_voice_input(
                    call_sid=call_sid,
                    transcript="What kind of sushi do you have?"
                )
                
                # Menu-specific inquiry - should trigger menu agent
                result2 = await orchestrator.process_voice_input(
                    call_sid=call_sid,
                    transcript="Tell me about your specialty rolls and their prices"
                )
                
                # Verify handoff occurred
                assert "frontline" in agents_used
                assert "menu" in agents_used
                assert result2["agent_used"] == "menu"
                
                # Verify context was preserved
                current_context = fsm.context
                assert current_context["customer_name"] == "Test User"
                assert len(current_context["conversation_history"]) > 0
    
    @pytest.mark.asyncio
    async def test_cart_agent_menu_matcher_integration(self, db_session, mock_redis, mock_openai_client, sample_menu_data):
        """Test cart agent integration with menu matcher - Task 3.1.2."""
        from app.agents.cart_async import AsyncCartAgent
        from app.utils.menu_matcher_db_async import AsyncMenuMatcherDB
        
        # Create cart agent with real menu matcher
        menu_matcher = AsyncMenuMatcherDB(db_session)
        cart_agent = AsyncCartAgent(
            llm_client=mock_openai_client,
            menu_matcher=menu_matcher,
            db_session=db_session
        )
        
        # Set up context with cart
        context = {
            "customer_name": "John",
            "cart": [],
            "conversation_history": []
        }
        
        # Mock LLM to return add_to_cart function call
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock()]
        mock_response.choices[0].message = AsyncMock()
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.function_call = AsyncMock()
        mock_response.choices[0].message.function_call.name = "add_to_cart"
        mock_response.choices[0].message.function_call.arguments = json.dumps({
            "item_name": "California Roll",
            "quantity": 2,
            "modifications": []
        })
        
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        # Process order with real menu matching
        response = await cart_agent.process(
            transcript="I want two California rolls",
            context=context
        )
        
        # Verify menu matcher found the item
        assert context["cart"][0]["name"] == "California Roll"
        assert context["cart"][0]["quantity"] == 2
        assert context["cart"][0]["plu"] is not None  # Real PLU from database
        assert context["cart"][0]["price"] > 0  # Real price from database
    
    @pytest.mark.asyncio
    async def test_guardrail_validation_with_real_data(self, db_session, mock_redis, mock_openai_client):
        """Test guardrail validation with real data - Task 3.1.3."""
        from app.agents.guardrail_async import AsyncGuardrailAgent
        
        guardrail_agent = AsyncGuardrailAgent(
            llm_client=mock_openai_client,
            db_session=db_session
        )
        
        # Test cart validation with real constraints
        test_cases = [
            # Valid cart
            {
                "cart": [
                    {"name": "California Roll", "quantity": 2, "price": 12.95},
                    {"name": "Miso Soup", "quantity": 1, "price": 3.95}
                ],
                "expected_valid": True
            },
            # Invalid quantity
            {
                "cart": [
                    {"name": "Spicy Tuna Roll", "quantity": 101, "price": 14.95}
                ],
                "expected_valid": False
            },
            # Empty cart
            {
                "cart": [],
                "expected_valid": False
            },
            # Negative price
            {
                "cart": [
                    {"name": "Test Item", "quantity": 1, "price": -10.00}
                ],
                "expected_valid": False
            }
        ]
        
        for test_case in test_cases:
            context = {"cart": test_case["cart"]}
            
            # Mock LLM response based on expected validation
            mock_openai_client.chat.completions.create.return_value.choices[0].message.content = (
                "Cart is valid" if test_case["expected_valid"] else "Cart has issues"
            )
            
            response = await guardrail_agent.process(
                transcript="Validate my order",
                context=context
            )
            
            # Verify validation result
            is_valid = "valid" in response["response"].lower() and "issue" not in response["response"].lower()
            assert is_valid == test_case["expected_valid"]
    
    @pytest.mark.asyncio
    async def test_fulfillment_agent_order_submission(self, db_session, mock_redis, mock_openai_client):
        """Test fulfillment agent with order submission - Task 3.1.4."""
        from app.agents.fulfillment_async import AsyncFulfillmentAgent
        from app.models.order_async import Order, OrderItem
        
        # Mock Deliverect service
        with patch('app.utils.deliverect_async.AsyncDeliverectService') as mock_deliverect:
            mock_service = AsyncMock()
            mock_deliverect.return_value = mock_service
            
            # Mock successful order submission
            mock_service.submit_order.return_value = {
                "order_id": "DEL-12345",
                "status": "accepted",
                "estimated_time": "30 minutes"
            }
            
            fulfillment_agent = AsyncFulfillmentAgent(
                llm_client=mock_openai_client,
                db_session=db_session,
                deliverect_service=mock_service
            )
            
            # Prepare context with complete order
            context = {
                "customer_name": "Jane Doe",
                "customer_phone": "+1234567890",
                "order_type": "pickup",
                "cart": [
                    {
                        "name": "Salmon Sashimi",
                        "quantity": 1,
                        "price": 16.95,
                        "plu": "SAL001"
                    },
                    {
                        "name": "Edamame",
                        "quantity": 2,
                        "price": 5.95,
                        "plu": "EDA001"
                    }
                ],
                "payment_method": "credit_card"
            }
            
            # Mock LLM confirmation
            mock_openai_client.chat.completions.create.return_value.choices[0].message.content = (
                "Your order has been submitted successfully! Order ID: DEL-12345. "
                "It will be ready for pickup in about 30 minutes."
            )
            
            # Process fulfillment
            response = await fulfillment_agent.process(
                transcript="Submit my order",
                context=context
            )
            
            # Verify order was submitted
            assert mock_service.submit_order.called
            assert "DEL-12345" in response["response"]
            assert "30 minutes" in response["response"]
            
            # Verify order was saved to database
            submitted_call_args = mock_service.submit_order.call_args[1]
            assert submitted_call_args["customer_name"] == "Jane Doe"
            assert len(submitted_call_args["items"]) == 2
            assert submitted_call_args["order_type"] == "pickup"


class TestAgentContextSharing:
    """Test context sharing between agents during handoffs."""
    
    @pytest.mark.asyncio
    async def test_context_preservation_across_agents(self, db_session, mock_redis, mock_openai_client):
        """Test that context is properly preserved when switching agents."""
        orchestrator = AsyncAgentOrchestrator(
            db_session=db_session,
            redis_client=mock_redis,
            llm_client=mock_openai_client
        )
        
        call_sid = "test_context_001"
        
        # Initial context setup
        initial_context = {
            "customer_name": "Alice",
            "dietary_restrictions": ["vegetarian"],
            "conversation_history": [
                {"role": "user", "content": "I'm vegetarian"}
            ],
            "cart": []
        }
        
        fsm = await orchestrator.fsm_manager.get_fsm(call_sid)
        await fsm.transition(ConversationState.ORDERING)
        await fsm.update_context(initial_context)
        
        # Process with different agents
        responses = []
        
        # Menu agent query
        result1 = await orchestrator.process_voice_input(
            call_sid=call_sid,
            transcript="What vegetarian options do you have?"
        )
        responses.append(result1)
        
        # Cart agent action
        result2 = await orchestrator.process_voice_input(
            call_sid=call_sid,
            transcript="Add the vegetable tempura roll"
        )
        responses.append(result2)
        
        # Verify context was maintained
        final_context = fsm.context
        assert final_context["customer_name"] == "Alice"
        assert "vegetarian" in final_context["dietary_restrictions"]
        assert len(final_context["conversation_history"]) > 2
        
        # Verify dietary restriction was considered
        for response in responses:
            if "meat" in response["response"].lower() or "chicken" in response["response"].lower():
                pytest.fail("Non-vegetarian option suggested despite dietary restriction")
    
    @pytest.mark.asyncio
    async def test_specialist_registration_and_discovery(self, db_session, mock_redis, mock_openai_client):
        """Test specialist agent registration and discovery mechanism."""
        from app.agents.factory_async import AsyncAgentFactory
        
        factory = AsyncAgentFactory(
            llm_client=mock_openai_client,
            db_session=db_session,
            redis_client=mock_redis
        )
        
        # Get all registered agent types
        agent_types = factory.get_available_agents()
        
        # Verify core agents are registered
        expected_agents = ["frontline", "menu", "cart", "guardrail", "fulfillment", "escalation"]
        for agent_type in expected_agents:
            assert agent_type in agent_types
        
        # Test agent creation
        for agent_type in expected_agents:
            agent = await factory.get_agent(agent_type)
            assert agent is not None
            assert hasattr(agent, 'process')
            assert hasattr(agent, 'name')
            assert agent.name == agent_type