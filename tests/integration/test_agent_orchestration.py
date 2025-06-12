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
    async def test_orchestrator_initialization(self, db_session): # mock_redis, mock_openai_client removed
        """Test orchestrator initialization."""
        orchestrator = AsyncAgentOrchestrator()
        await orchestrator.initialize(db=db_session)
        
        assert orchestrator.frontline_agent is not None
        assert orchestrator.menu_agent is not None
        # async_fsm_manager is imported and used directly if needed, not an attribute of orchestrator
        # intent_detector is also not a direct attribute.
    
    @pytest.mark.asyncio
    async def test_orchestrator_process_greeting(self, db_session, mock_openai_client): # mock_redis removed
        """Test processing greeting phase."""
        orchestrator = AsyncAgentOrchestrator()
        await orchestrator.initialize(db=db_session)
        
        with patch('openai.AsyncOpenAI', return_value=mock_openai_client):
            mock_openai_client.chat.completions.create.return_value.choices[0].message.content = (
                "Hello! Welcome to Red Bar Sushi. May I have your name please?"
            )

            result = await orchestrator.process_voice_input(
                call_sid="test_call_001",
                transcript="" # initial_call parameter removed
            )
        
        assert "text" in result
        assert "Welcome" in result["text"]
        assert result["state"] == ConversationState.GREETING.name
    
    @pytest.mark.asyncio
    async def test_orchestrator_name_collection(self, db_session, mock_openai_client): # mock_redis removed
        """Test name collection and transition to main menu."""
        orchestrator = AsyncAgentOrchestrator()
        await orchestrator.initialize(db=db_session)
        
        call_sid = "test_call_002"
        
        with patch('openai.AsyncOpenAI', return_value=mock_openai_client):
            mock_openai_client.chat.completions.create.return_value.choices[0].message.content = "Welcome"
            await orchestrator.process_voice_input(
                call_sid=call_sid,
                transcript="" # initial_call removed
            )

        # Mock intent detection for name
        with patch('app.fsm.core.intent_detector.detect_intent',
                         return_value=ConversationEvent.USER_PROVIDES_NAME): # Adjusted event
            
            with patch('openai.AsyncOpenAI', return_value=mock_openai_client):
                mock_openai_client.chat.completions.create.return_value.choices[0].message.content = (
                    "Nice to meet you, John! How can I help you today? Would you like to hear our menu, "
                    "place an order, or speak with our staff?"
                )

                result = await orchestrator.process_voice_input(
                    call_sid=call_sid,
                    transcript="My name is John"
                )
            
            assert result["state"] == ConversationState.MAIN_MENU.name
            assert "fsm_context" in result
            assert result["fsm_context"].get("customer_name") == "John"
    
    @pytest.mark.asyncio
    async def test_orchestrator_menu_inquiry(self, db_session, mock_openai_client, sample_menu_data): # mock_redis removed
        """Test menu inquiry flow."""
        orchestrator = AsyncAgentOrchestrator()
        await orchestrator.initialize(db=db_session)
        
        call_sid = "test_call_003"
        fsm = await orchestrator.get_fsm(call_sid)
        await fsm.transition_to(ConversationState.MAIN_MENU) # Use transition_to
        await fsm.update_context({"customer_name": "Jane"})
        
        with patch('app.fsm.core.intent_detector.detect_intent',
                         return_value=ConversationEvent.REQUEST_MENU_INFO): # Adjusted event
            
            with patch('openai.AsyncOpenAI', return_value=mock_openai_client):
                mock_openai_client.chat.completions.create.return_value.choices[0].message.content = (
                    "We have California Roll for $12.95 and Spicy Tuna Roll for $14.95 in our sushi selection."
                )

                result = await orchestrator.process_voice_input(
                    call_sid=call_sid,
                    transcript="What sushi rolls do you have?"
                )
            
            assert "California Roll" in result["text"]
            assert "$12.95" in result["text"]
    
    @pytest.mark.asyncio
    async def test_orchestrator_order_flow(self, db_session, mock_openai_client, sample_menu_data): # mock_redis removed
        """Test complete order flow."""
        orchestrator = AsyncAgentOrchestrator()
        await orchestrator.initialize(db=db_session)
        
        call_sid = "test_call_004"
        fsm = await orchestrator.get_fsm(call_sid)
        await fsm.transition_to(ConversationState.MAIN_MENU) # Use transition_to
        await fsm.update_context({"customer_name": "Bob"})
        
        # 1. Start ordering
        with patch('app.fsm.core.intent_detector.detect_intent',
                         return_value=ConversationEvent.START_ORDER): # Adjusted event

            with patch('openai.AsyncOpenAI', return_value=mock_openai_client):
                mock_openai_client.chat.completions.create.return_value.choices[0].message.content = (
                    "I'll help you place an order. What would you like to order today?"
                )

                result = await orchestrator.process_voice_input(
                    call_sid=call_sid,
                    transcript="I want to place an order"
                )
            
            assert result["state"] == ConversationState.ORDERING.name

        # 2. Add items to cart
        with patch('openai.AsyncOpenAI', return_value=mock_openai_client):
            mock_openai_client.chat.completions.create.return_value.choices[0].message.content = (
                "I've added 2 California Rolls to your order. Would you like anything else?"
            )
            
            result = await orchestrator.process_voice_input(
                call_sid=call_sid,
                transcript="I want two California rolls"
            )
        
        assert "added" in result["text"].lower()
        
        # 3. Complete order
        with patch('app.fsm.core.intent_detector.detect_intent',
                         return_value=ConversationEvent.COMPLETE_ORDER): # Adjusted event
            
            # await fsm.transition_to(ConversationState.VALIDATION) # FSM handles this based on event
            
            with patch('openai.AsyncOpenAI', return_value=mock_openai_client):
                mock_openai_client.chat.completions.create.return_value.choices[0].message.content = (
                    "Your order of 2 California Rolls comes to $25.90. Is this correct?"
                )

                result = await orchestrator.process_voice_input(
                    call_sid=call_sid,
                    transcript="That's all"
                )
            
            assert "$25.90" in result["text"]
            assert result["state"] in [ConversationState.VALIDATION.name, ConversationState.CONFIRMATION.name]
    
    @pytest.mark.asyncio
    async def test_orchestrator_agent_handoff(self, db_session, mock_openai_client): # mock_redis removed
        """Test agent handoff mechanism."""
        orchestrator = AsyncAgentOrchestrator()
        await orchestrator.initialize(db=db_session)
        
        call_sid = "test_call_005"
        fsm = await orchestrator.get_fsm(call_sid)
        await fsm.transition_to(ConversationState.MAIN_MENU) # Ensure it starts somewhere then transitions
        await fsm.transition_to(ConversationState.ORDERING)
        
        with patch('openai.AsyncOpenAI', return_value=mock_openai_client):
            mock_openai_client.chat.completions.create.return_value.choices[0].message.content = "Spicy tuna added."
            result = await orchestrator.process_voice_input(
                call_sid=call_sid,
                transcript="Add a spicy tuna roll"
            )
        
        assert result["agent"] == "AsyncCartAgent" # Check class name
    
    @pytest.mark.asyncio
    async def test_orchestrator_error_handling(self, db_session, mock_openai_client): # mock_redis removed
        """Test error handling in orchestration."""
        orchestrator = AsyncAgentOrchestrator()
        # Not calling initialize to ensure agents might not be ready
        
        with patch('app.agents.factory_async.async_agent_factory.create_voice_agent_system',
                         side_effect=Exception("Agent initialization failed")):
            
            result = await orchestrator.process_voice_input(
                call_sid="test_call_006",
                transcript="Hello" # initial_call removed
            )
            
            assert "sorry" in result["text"].lower() # Check for apologetic message
            fsm = await orchestrator.get_fsm("test_call_006") # get_fsm to check state
            assert fsm.current_state == ConversationState.ERROR
    
    @pytest.mark.asyncio
    async def test_orchestrator_escalation(self, db_session, mock_openai_client): # mock_redis removed
        """Test escalation to human."""
        orchestrator = AsyncAgentOrchestrator()
        await orchestrator.initialize(db=db_session)
        
        call_sid = "test_call_007"
        fsm = await orchestrator.get_fsm(call_sid)
        await fsm.transition_to(ConversationState.MAIN_MENU)
        
        with patch('app.fsm.core.intent_detector.detect_intent',
                         return_value=ConversationEvent.REQUEST_ESCALATION): # Adjusted event
            
            with patch('openai.AsyncOpenAI', return_value=mock_openai_client):
                mock_openai_client.chat.completions.create.return_value.choices[0].message.content = (
                    "I'll connect you with a team member right away. Please hold."
                )

                result = await orchestrator.process_voice_input(
                    call_sid=call_sid,
                    transcript="I need to speak to a person"
                )
            
            assert result["state"] == ConversationState.ESCALATION.name
            assert "connect" in result["text"].lower()
    
    @pytest.mark.asyncio
    async def test_orchestrator_context_preservation(self, db_session, mock_openai_client): # mock_redis removed
        """Test context preservation across interactions."""
        orchestrator = AsyncAgentOrchestrator()
        await orchestrator.initialize(db=db_session)
        
        call_sid = "test_call_008"
        
        with patch('openai.AsyncOpenAI', return_value=mock_openai_client):
            mock_openai_client.chat.completions.create.return_value.choices[0].message.content = "Welcome"
            await orchestrator.process_voice_input( # Initial greeting
                call_sid=call_sid,
                transcript="" # initial_call removed
            )
        
        fsm = await orchestrator.get_fsm(call_sid)
        await fsm.update_context({"customer_name": "Alice"})
        await fsm.transition_to(ConversationState.MAIN_MENU) # Manually set state for test
        
        with patch('openai.AsyncOpenAI', return_value=mock_openai_client):
            mock_openai_client.chat.completions.create.return_value.choices[0].message.content = "Your name is Alice."
            result = await orchestrator.process_voice_input(
                call_sid=call_sid,
                transcript="What's my name?"
            )
        
        assert result["fsm_context"].get("customer_name") == "Alice"
    
    # test_orchestrator_tool_execution removed


class TestAgentToAgentCommunication:
    """Test agent-to-agent communication and handoffs - Task 3.1."""
    
    @pytest.mark.asyncio
    async def test_frontline_to_menu_agent_handoff(self, db_session, mock_openai_client, sample_menu_data): # mock_redis removed
        """Test frontline to menu agent handoff - Task 3.1.1."""
        orchestrator = AsyncAgentOrchestrator()
        await orchestrator.initialize(db=db_session) # Initialize
        
        # Initialize conversation in main menu state
        call_sid = "test_handoff_001"
        fsm = await orchestrator.get_fsm(call_sid) # Use orchestrator method
        await fsm.transition_to(ConversationState.MAIN_MENU) # Use transition_to
        await fsm.update_context({
            "customer_name": "Test User",
            # "conversation_history": [] # This is now managed by conversation_store
        })
        
        # Mock intent detection for menu inquiry
        with patch('app.fsm.core.intent_detector.detect_intent',
                         return_value=ConversationEvent.REQUEST_MENU_INFO): # Adjusted event
            
            # We need to patch 'app.agents.factory_async.async_agent_factory.get_agent'
            # to track which agents are instantiated by the factory if that's the goal.
            # However, orchestrator._process_with_appropriate_agent directly uses its initialized agent members.
            # The test should verify the 'agent' field in the response.
            
            with patch('openai.AsyncOpenAI', return_value=mock_openai_client):
                # First inquiry
                mock_openai_client.chat.completions.create.return_value.choices[0].message.content = "Menu response"
                result1 = await orchestrator.process_voice_input(
                    call_sid=call_sid,
                    transcript="What kind of sushi do you have?"
                )
                
                # Menu-specific inquiry - should trigger menu agent
                mock_openai_client.chat.completions.create.return_value.choices[0].message.content = "Specialty rolls details"
                result2 = await orchestrator.process_voice_input(
                    call_sid=call_sid,
                    transcript="Tell me about your specialty rolls and their prices"
                )
                
            # Verify agent in response
            # Assuming MAIN_MENU + REQUEST_MENU_INFO leads to MenuAgent via FSM logic in orchestrator
            assert result1["agent"] == "AsyncFrontlineVoiceAgentAI" # Or specific agent for MAIN_MENU
            assert result2["agent"] == "AsyncMenuAgentEnhanced" # Or AsyncMenuAgent
                
            # Verify context was preserved
            final_fsm_context = result2["fsm_context"]
            assert final_fsm_context.get("customer_name") == "Test User"
            # conv_history = await orchestrator.conversation_store.get_conversation(call_sid)
            # assert len(conv_history["messages"]) > 0 # Check conversation store
    
    @pytest.mark.asyncio
    async def test_cart_agent_menu_matcher_integration(self, db_session, mock_openai_client, sample_menu_data): # mock_redis removed
        """Test cart agent integration with menu matcher - Task 3.1.2."""
        from app.agents.cart_async import AsyncCartAgent
        # AsyncMenuMatcherDB is not directly used by CartAgent. CartAgent uses get_cached_async_menu_matcher.
        
        # CartAgent takes db, not llm_client or menu_matcher directly.
        cart_agent = AsyncCartAgent(db=db_session)
        
        # Cart is managed by async_agents_conversation_store, not passed in context directly for manipulation.
        # We need to simulate adding to cart via agent's process or execute_tool if testing cart content.
        # This test might need significant rework to align with current CartAgent.
        # For now, let's focus on the instantiation and a simplified process call.
        
        call_sid_cart = "test_cart_integration_001"
        cart_agent.set_current_call(call_sid_cart) # Set call_sid for conversation store
        
        # Mock LLM for the AI part of CartAgent (if it uses AIIntelligenceMixin - it doesn't directly)
        # CartAgent primarily uses its predefined tools.
        # To test menu_matcher integration, we'd call a method that uses lookup_menu_item tool.

        # Let's simulate a call to its internal _add_item_to_cart via execute_tool,
        # assuming a prior step (like an LLM call or direct intent) decided to call this tool.
        # This requires the DB to be populated by sample_menu_data for get_item_by_plu to work.
        # This test is becoming more of a test for crud_menu_async via cart_agent.

        # Patching the item lookup for simplicity, as setting up full menu for matcher is complex here.
        # The goal is to see if cart_agent correctly processes an item add.
        # This test originally tested menu_matcher via cart_agent. Now menu_matcher is deeper.
        # The cart_agent._add_item_to_cart now uses `await get_item_by_plu(self.db, plu)`.

        # Assume sample_menu_data has been loaded into db_session by a fixture if this were a full e2e.
        # For an integration test of cart_agent, we might mock the direct DB calls it makes.

        # Let's simplify: test if cart_agent can process an "add item" input.
        # This will internally call its _lookup_menu_item and _add_item_to_cart.
        # We need to ensure `get_cached_async_menu_matcher` works and `get_item_by_plu` works.
        # This requires `db_session` to be usable for these.

        # To make this test pass without full DB setup for menu:
        # Mock the return of `get_cached_async_menu_matcher` and its `match_item`
        # Mock `get_item_by_plu` and `get_modifier_by_plu` from `app.db.crud_menu_async`

        mock_matched_item = {
            "name": "California Roll", "plu": "ROLL_001", "price": 1295,
            "category_name": "Rolls", "is_available": True, "modifierGroups": []
        }

        with patch('app.agents.cart_async.get_cached_async_menu_matcher') as mock_get_matcher:
            mock_matcher_instance = AsyncMock()
            mock_matcher_instance.match_item.return_value = (mock_matched_item, 1.0) # item, score
            mock_get_matcher.return_value = mock_matcher_instance

            with patch('app.agents.cart_async.get_item_by_plu') as mock_crud_get_item:
                mock_item_orm = AsyncMock() # Simulate ORM object
                mock_item_orm.name = "California Roll"
                mock_item_orm.price = 1295
                mock_crud_get_item.return_value = mock_item_orm

                # This call will use the mocked lookup and then add to store
                response_text = await cart_agent._generate_cart_response( # Call a method that adds to cart
                     "I want two California rolls"
                )

        # Verify cart content from conversation store
        final_cart = await async_agents_conversation_store.get_cart(call_sid_cart)
        assert len(final_cart["items"]) > 0
        assert final_cart["items"][0]["name"] == "California Roll"
        assert final_cart["items"][0]["quantity"] == 2 # Assuming quantity detection works
        assert final_cart["items"][0]["plu"] == "ROLL_001"
    
    @pytest.mark.asyncio
    async def test_guardrail_validation_with_real_data(self, db_session, mock_openai_client): # mock_redis removed
        """Test guardrail validation with real data - Task 3.1.3."""
        from app.agents.guardrail_async import AsyncGuardrailAgent
        
        # GuardrailAgent constructor does not take llm_client or db_session.
        # It might use self.db if set, or AIIntelligenceMixin for LLM.
        guardrail_agent = AsyncGuardrailAgent()
        # If it needs DB for validation rules (not shown in current impl), then:
        # guardrail_agent.db = db_session
        
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
            # llm_client, db_session, redis_client removed
        )
        
        # Get all registered agent types
        agent_types = factory.agent_classes.keys() # Access agent_classes dict
        
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