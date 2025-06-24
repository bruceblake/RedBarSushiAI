"""
Integration tests for disambiguation functionality.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from app.utils.agent_orchestration_async import AsyncAgentOrchestrator
from app.utils.disambiguation import DisambiguationDetector, DisambiguationType
from app.fsm.core import ConversationState
from app.agents.base_async import BaseAsyncAgent


class TestDisambiguationIntegration:
    """Test disambiguation integration with menu matching and orchestration."""
    
    @pytest_asyncio.fixture
    async def disambig_orchestrator(self, test_db, mock_redis, mock_openai_client, sample_menu_items):
        """Create orchestrator with disambiguation support."""
        orchestrator = AsyncAgentOrchestrator()
        
        # Mock initialization
        with patch('app.utils.agent_orchestration_async.async_agent_factory') as mock_factory:
            mock_voice_system = AsyncMock(spec=BaseAsyncAgent)
            mock_voice_system.specialist_agents = {}
            mock_factory.create_voice_agent_system.return_value = mock_voice_system
            
            # Create mock agents
            mock_agents = {}
            for agent_type in ['frontline', 'cart', 'menu', 'guardrail', 'fulfillment', 'escalation']:
                agent = AsyncMock(spec=BaseAsyncAgent)
                agent.name = agent_type
                mock_agents[agent_type] = agent
            
            async def get_agent_side_effect(agent_type, **kwargs):
                return mock_agents.get(agent_type)
            
            mock_factory.get_agent.side_effect = get_agent_side_effect
            
            await orchestrator.initialize(db=test_db)
            
            # Store mock agents and menu items for test access
            orchestrator._mock_agents = mock_agents
            orchestrator._test_menu_items = sample_menu_items
        
        return orchestrator
    
    @pytest.mark.asyncio
    async def test_price_disambiguation(self, disambig_orchestrator):
        """Test disambiguation when items have same price."""
        orchestrator = disambig_orchestrator
        
        session_id = "test_disambig_001"
        await orchestrator.create_session(session_id)
        
        session = orchestrator.sessions[session_id]
        session["fsm"].current_state = ConversationState.ORDERING
        session["context"]["cart"] = []
        
        # Mock menu agent finding multiple items with same price
        menu_matches = [
            {
                "name": "California Roll",
                "price": 12.95,
                "plu": "CAL001",
                "description": "Crab, avocado, cucumber"
            },
            {
                "name": "Vegetable Roll",
                "price": 12.95,
                "plu": "VEG001",
                "description": "Assorted fresh vegetables"
            }
        ]
        
        # First request - ambiguous
        orchestrator.menu_agent.process = AsyncMock(return_value={
            "text": "I found multiple rolls for $12.95. Would you like the California Roll with crab and avocado, or the Vegetable Roll with fresh vegetables?",
            "agent": "menu",
            "handled": True,
            "disambiguation": {
                "type": DisambiguationType.PRICE_MATCH,
                "matches": menu_matches,
                "awaiting_response": True
            }
        })
        
        with patch('app.utils.agent_orchestration_async.intent_detector') as mock_intent:
            mock_intent.detect_intent = AsyncMock(return_value=None)
            
            response = await orchestrator.process(
                session_id,
                "I want the $12.95 roll"
            )
        
        # Should ask for clarification
        assert "California Roll" in response["text"]
        assert "Vegetable Roll" in response["text"]
        assert session["context"].get("disambiguation") is not None
        
        # Second request - clarification
        orchestrator.cart_agent.process = AsyncMock(return_value={
            "text": "I've added 1 California Roll to your order.",
            "agent": "cart",
            "handled": True,
            "cart": [{
                "name": "California Roll",
                "quantity": 1,
                "price": 12.95,
                "plu": "CAL001"
            }]
        })
        
        response = await orchestrator.process(
            session_id,
            "The California one"
        )
        
        # Should resolve and add to cart
        assert "added 1 California Roll" in response["text"]
        assert len(session["context"]["cart"]) == 1
        assert session["context"]["cart"][0]["name"] == "California Roll"
        assert session["context"].get("disambiguation") is None
    
    @pytest.mark.asyncio
    async def test_name_similarity_disambiguation(self, disambig_orchestrator):
        """Test disambiguation for similar sounding items."""
        orchestrator = disambig_orchestrator
        
        session_id = "test_disambig_002"
        await orchestrator.create_session(session_id)
        
        session = orchestrator.sessions[session_id]
        session["fsm"].current_state = ConversationState.ORDERING
        
        # Mock similar matches
        similar_matches = [
            {
                "name": "Spicy Tuna Roll",
                "price": 14.95,
                "plu": "STR001"
            },
            {
                "name": "Spicy Salmon Roll",
                "price": 15.95,
                "plu": "SSR001"
            },
            {
                "name": "Spicy Yellowtail Roll",
                "price": 16.95,
                "plu": "SYR001"
            }
        ]
        
        orchestrator.menu_agent.process = AsyncMock(return_value={
            "text": "I found several spicy rolls. We have Spicy Tuna for $14.95, Spicy Salmon for $15.95, or Spicy Yellowtail for $16.95. Which would you like?",
            "agent": "menu",
            "handled": True,
            "disambiguation": {
                "type": DisambiguationType.NAME_SIMILARITY,
                "matches": similar_matches,
                "awaiting_response": True
            }
        })
        
        with patch('app.utils.agent_orchestration_async.intent_detector') as mock_intent:
            mock_intent.detect_intent = AsyncMock(return_value=None)
            
            response = await orchestrator.process(
                session_id,
                "I want a spicy roll"
            )
        
        # Should list all options with prices
        assert "Spicy Tuna" in response["text"]
        assert "Spicy Salmon" in response["text"]
        assert "Spicy Yellowtail" in response["text"]
        assert "$14.95" in response["text"]
        assert "$15.95" in response["text"]
        assert "$16.95" in response["text"]
    
    @pytest.mark.asyncio
    async def test_position_disambiguation(self, disambig_orchestrator):
        """Test disambiguation by position in list."""
        orchestrator = disambig_orchestrator
        
        session_id = "test_disambig_003"
        await orchestrator.create_session(session_id)
        
        session = orchestrator.sessions[session_id]
        session["fsm"].current_state = ConversationState.MENU_QUERY_SUBSTATE
        
        # Set up disambiguation context from previous query
        session["context"]["disambiguation"] = {
            "matches": [
                {"name": "Rainbow Roll", "price": 18.95, "plu": "RBW001"},
                {"name": "Dragon Roll", "price": 17.95, "plu": "DRG001"},
                {"name": "Phoenix Roll", "price": 16.95, "plu": "PHX001"}
            ],
            "awaiting_response": True
        }
        
        # User selects by position
        orchestrator.menu_agent.process = AsyncMock(return_value={
            "text": "The Dragon Roll is our signature roll with shrimp tempura, topped with eel and avocado. It's $17.95.",
            "agent": "menu",
            "handled": True,
            "selected_item": {
                "name": "Dragon Roll",
                "price": 17.95,
                "plu": "DRG001"
            }
        })
        
        with patch('app.utils.agent_orchestration_async.intent_detector') as mock_intent:
            mock_intent.detect_intent = AsyncMock(return_value=None)
            
            response = await orchestrator.process(
                session_id,
                "The second one"
            )
        
        # Should select Dragon Roll (second in list)
        assert "Dragon Roll" in response["text"]
        assert "$17.95" in response["text"]
        assert session["context"].get("disambiguation") is None
    
    @pytest.mark.asyncio
    async def test_multi_turn_disambiguation(self, disambig_orchestrator):
        """Test multi-turn disambiguation conversation."""
        orchestrator = disambig_orchestrator
        
        session_id = "test_disambig_004"
        await orchestrator.create_session(session_id)
        
        session = orchestrator.sessions[session_id]
        session["fsm"].current_state = ConversationState.ORDERING
        
        # Turn 1: Initial ambiguous request
        orchestrator.menu_agent.process = AsyncMock(return_value={
            "text": "We have several tempura items. Are you looking for Shrimp Tempura ($8.95), Vegetable Tempura ($6.95), or a Tempura Roll ($14.95)?",
            "agent": "menu",
            "handled": True,
            "disambiguation": {
                "type": DisambiguationType.CATEGORY_MATCH,
                "awaiting_response": True
            }
        })
        
        with patch('app.utils.agent_orchestration_async.intent_detector') as mock_intent:
            mock_intent.detect_intent = AsyncMock(return_value=None)
            
            response1 = await orchestrator.process(
                session_id,
                "I want tempura"
            )
        
        assert "Shrimp Tempura" in response1["text"]
        assert "Vegetable Tempura" in response1["text"]
        
        # Turn 2: Still ambiguous
        orchestrator.menu_agent.process = AsyncMock(return_value={
            "text": "For rolls with tempura, we have the Shrimp Tempura Roll ($14.95) and the Crunchy Tempura Roll ($13.95). Which would you prefer?",
            "agent": "menu",
            "handled": True,
            "disambiguation": {
                "type": DisambiguationType.NAME_SIMILARITY,
                "awaiting_response": True
            }
        })
        
        response2 = await orchestrator.process(
            session_id,
            "The roll please"
        )
        
        assert "Shrimp Tempura Roll" in response2["text"]
        assert "Crunchy Tempura Roll" in response2["text"]
        
        # Turn 3: Final selection
        orchestrator.cart_agent.process = AsyncMock(return_value={
            "text": "Perfect! I've added 1 Shrimp Tempura Roll to your order.",
            "agent": "cart",
            "handled": True,
            "cart": [{
                "name": "Shrimp Tempura Roll",
                "quantity": 1,
                "price": 14.95
            }]
        })
        
        response3 = await orchestrator.process(
            session_id,
            "The shrimp one"
        )
        
        assert "added 1 Shrimp Tempura Roll" in response3["text"]
        assert len(session["context"]["cart"]) == 1
    
    @pytest.mark.asyncio
    async def test_disambiguation_timeout(self, disambig_orchestrator):
        """Test disambiguation context timeout/clearing."""
        orchestrator = disambig_orchestrator
        
        session_id = "test_disambig_005"
        await orchestrator.create_session(session_id)
        
        session = orchestrator.sessions[session_id]
        session["fsm"].current_state = ConversationState.ORDERING
        
        # Set up disambiguation context
        session["context"]["disambiguation"] = {
            "matches": [
                {"name": "Item 1", "price": 10.00},
                {"name": "Item 2", "price": 12.00}
            ],
            "awaiting_response": True,
            "timestamp": 1234567890  # Old timestamp
        }
        
        # User changes topic instead of clarifying
        orchestrator.cart_agent.process = AsyncMock(return_value={
            "text": "Sure! Your current order total is $25.90.",
            "agent": "cart",
            "handled": True
        })
        
        with patch('app.utils.agent_orchestration_async.intent_detector') as mock_intent:
            mock_intent.detect_intent = AsyncMock(return_value=None)
            
            response = await orchestrator.process(
                session_id,
                "What's my total so far?"
            )
        
        # Disambiguation should be cleared
        assert "total is $25.90" in response["text"]
        assert session["context"].get("disambiguation") is None
    
    @pytest.mark.asyncio
    async def test_disambiguation_with_modifiers(self, disambig_orchestrator):
        """Test disambiguation handling with item modifiers."""
        orchestrator = disambig_orchestrator
        
        session_id = "test_disambig_006"
        await orchestrator.create_session(session_id)
        
        session = orchestrator.sessions[session_id]
        session["fsm"].current_state = ConversationState.ORDERING
        
        # Ambiguous request with modifier
        orchestrator.menu_agent.process = AsyncMock(return_value={
            "text": "For spicy items without wasabi, we have the Spicy Tuna Roll or Spicy Salmon Roll. Both can be made without wasabi. Which would you prefer?",
            "agent": "menu",
            "handled": True,
            "disambiguation": {
                "type": DisambiguationType.MODIFIER_COMBINATION,
                "modifiers": ["no wasabi"],
                "awaiting_response": True
            }
        })
        
        with patch('app.utils.agent_orchestration_async.intent_detector') as mock_intent:
            mock_intent.detect_intent = AsyncMock(return_value=None)
            
            response = await orchestrator.process(
                session_id,
                "I want something spicy but no wasabi"
            )
        
        assert "Spicy Tuna Roll" in response["text"]
        assert "Spicy Salmon Roll" in response["text"]
        assert "without wasabi" in response["text"]
    
    @pytest.mark.asyncio
    async def test_no_disambiguation_single_match(self, disambig_orchestrator):
        """Test no disambiguation needed for unique matches."""
        orchestrator = disambig_orchestrator
        
        session_id = "test_disambig_007"
        await orchestrator.create_session(session_id)
        
        session = orchestrator.sessions[session_id]
        session["fsm"].current_state = ConversationState.ORDERING
        
        # Direct match - no disambiguation
        orchestrator.cart_agent.process = AsyncMock(return_value={
            "text": "I've added 1 Edamame to your order.",
            "agent": "cart",
            "handled": True,
            "cart": [{
                "name": "Edamame",
                "quantity": 1,
                "price": 5.95,
                "plu": "EDA001"
            }]
        })
        
        with patch('app.utils.agent_orchestration_async.intent_detector') as mock_intent:
            mock_intent.detect_intent = AsyncMock(return_value=None)
            
            response = await orchestrator.process(
                session_id,
                "Add edamame"  # Unique item
            )
        
        # Should add directly without disambiguation
        assert "added 1 Edamame" in response["text"]
        assert session["context"].get("disambiguation") is None
        assert len(session["context"]["cart"]) == 1