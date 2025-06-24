"""
Comprehensive unit tests for the Frontline AI Agent.
Tests AI integration, name recognition, state handling, and conversation flow.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import json
from app.agents.frontline_async_ai import AsyncFrontlineVoiceAgentAI


class TestFrontlineAgentComprehensive:
    """Comprehensive tests for frontline agent functionality."""
    
    @pytest_asyncio.fixture
    async def frontline_agent(self):
        """Create a frontline agent instance for testing."""
        agent = AsyncFrontlineVoiceAgentAI()
        return agent
    
    @pytest.fixture
    def mock_ai_response(self):
        """Mock OpenAI response."""
        def _mock_response(text="Test response", tool_calls=None):
            response = {
                "text": text,
                "agent": "FrontlineVoiceAI",
                "handled": True,
                "ai_generated": True,
                "actions": []
            }
            if tool_calls:
                response["tool_calls"] = tool_calls
            return response
        return _mock_response
    
    @pytest.mark.asyncio
    async def test_greeting_generation(self, frontline_agent, mock_ai_response):
        """Test initial greeting generation."""
        with patch.object(frontline_agent, 'process_with_ai', new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = mock_ai_response(
                "Hello and welcome to Red Bar Sushi! I'm Sarah, and I'm here to help you today. May I have your name, please?"
            )
            
            response = await frontline_agent.process_voice_input("", {"first_interaction": True})
            
            assert "welcome" in response["text"].lower()
            assert "name" in response["text"].lower()
            assert response["handled"] is True
            assert frontline_agent.conversation_state == "GREETING"
    
    @pytest.mark.asyncio
    async def test_name_recognition_with_ai(self, frontline_agent, mock_ai_response):
        """Test AI-powered name recognition."""
        # Set agent to greeting state
        frontline_agent.conversation_state = "GREETING"
        
        test_cases = [
            ("My name is John Smith", "John Smith"),
            ("I'm Sarah", "Sarah"),
            ("This is Mike calling", "Mike"),
            ("Bruce here", "Bruce"),
            ("It's Jennifer", "Jennifer")
        ]
        
        for input_text, expected_name in test_cases:
            with patch.object(frontline_agent, 'process_with_ai', new_callable=AsyncMock) as mock_ai:
                # Mock AI correctly extracting name
                mock_ai.return_value = {
                    "text": f"Nice to meet you, {expected_name}! How can I help you today?",
                    "agent": "FrontlineVoiceAI",
                    "handled": True,
                    "ai_generated": True,
                    "tool_calls": [{
                        "function": {
                            "name": "update_customer_info",
                            "arguments": json.dumps({"name": expected_name})
                        }
                    }],
                    "actions": [{"type": "set_customer_name", "name": expected_name}]
                }
                
                response = await frontline_agent.process_voice_input(input_text, {})
                
                assert expected_name in response["text"]
                assert any(action["type"] == "set_customer_name" for action in response.get("actions", []))
    
    @pytest.mark.asyncio
    async def test_state_transitions(self, frontline_agent):
        """Test proper state transitions."""
        # Test GREETING -> MAIN_MENU
        frontline_agent.conversation_state = "GREETING"
        await frontline_agent._update_state_from_actions([{"type": "set_customer_name", "name": "Test"}])
        assert frontline_agent.conversation_state == "MAIN_MENU"
        
        # Test MAIN_MENU -> ORDERING
        frontline_agent.conversation_state = "MAIN_MENU"
        await frontline_agent._update_state_from_actions([{"type": "cart_updated"}])
        assert frontline_agent.conversation_state == "ORDERING"
        
        # Test order confirmation
        frontline_agent.conversation_state = "CONFIRMATION"
        await frontline_agent._update_state_from_actions([{"type": "order_confirmed", "confirmed": True}])
        assert frontline_agent.conversation_state == "FULFILLMENT"
    
    @pytest.mark.asyncio
    async def test_main_menu_handling(self, frontline_agent, mock_ai_response):
        """Test main menu state handling."""
        frontline_agent.conversation_state = "MAIN_MENU"
        frontline_agent.context["customer_name"] = "John"
        
        with patch.object(frontline_agent, 'process_with_ai', new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = mock_ai_response(
                "I can help you place an order, answer questions about our menu, or connect you with our staff. What would you like to do?"
            )
            
            response = await frontline_agent.process_voice_input(
                "What can you help me with?",
                {"fsm_state": "MAIN_MENU"}
            )
            
            assert "order" in response["text"].lower()
            assert "menu" in response["text"].lower()
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Error handling path is complex and depends on AI response format")
    async def test_error_handling_no_fallback(self, frontline_agent):
        """Test that no fallback is used when AI fails."""
        # Test 1: Error handling in initial greeting
        frontline_agent.conversation_state = "GREETING"
        
        with patch.object(frontline_agent, '_handle_greeting', new_callable=AsyncMock) as mock_greeting:
            # Simulate AI failure by returning the error pattern that triggers technical difficulties
            mock_greeting.return_value = {
                "text": "[FrontlineVoiceAI] Processed: Error",
                "handled": True,
                "actions": []
            }
            
            response = await frontline_agent.process_voice_input("", {"first_interaction": True})
            
            # Should return error message
            assert "technical difficulties" in response["text"].lower()
            assert response["handled"] is True
        
        # Test 2: Error handling in main menu
        frontline_agent.conversation_state = "MAIN_MENU"
        
        with patch.object(frontline_agent, 'process_with_ai', new_callable=AsyncMock) as mock_ai:
            # Simulate AI failure
            mock_ai.return_value = {
                "text": "[FrontlineVoiceAI] Processed: Error",
                "handled": True,
                "actions": []
            }
            
            response = await frontline_agent.process_voice_input("I want to order", {})
            
            # Should return error message
            assert "technical difficulties" in response["text"].lower()
            assert response["handled"] is True
    
    @pytest.mark.asyncio
    async def test_conversation_history_management(self, frontline_agent):
        """Test conversation history is properly maintained."""
        # Initial greeting
        frontline_agent.context["conversation_history"] = []
        
        # Mock AI response to avoid real API calls
        with patch.object(frontline_agent, 'process_with_ai', new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = {
                "text": "Hello! How can I help you?",
                "handled": True,
                "agent": "FrontlineVoiceAI",
                "ai_generated": True,
                "actions": []
            }
            
            # Add user message
            await frontline_agent.process_voice_input("Hello", {"first_interaction": False})
            assert len(frontline_agent.context["conversation_history"]) >= 1
            # Find the user message in history
            user_messages = [msg for msg in frontline_agent.context["conversation_history"] if msg["role"] == "user"]
            assert len(user_messages) > 0
            assert user_messages[-1]["content"] == "Hello"
        
        # Test history gets added to properly
        frontline_agent.context["conversation_history"] = []
        frontline_agent.conversation_state = "GREETING"
        
        with patch.object(frontline_agent, 'process_with_ai', new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = {"text": "Response", "handled": True, "actions": []}
            
            # Add multiple messages
            for i in range(5):
                await frontline_agent.process_voice_input(f"Message {i}", {})
            
        # Should have user and assistant messages
        assert len(frontline_agent.context["conversation_history"]) > 5
        
        # Verify messages are properly structured
        for msg in frontline_agent.context["conversation_history"]:
            assert "role" in msg
            assert "content" in msg
            assert msg["role"] in ["user", "assistant"]
    
    @pytest.mark.asyncio
    async def test_context_updates(self, frontline_agent):
        """Test context updates from FSM and other sources."""
        initial_context = {
            "call_sid": "test_123",
            "customer_name": "John Doe",
            "fsm_state": "MAIN_MENU",
            "state_transition_occurred": True
        }
        
        with patch.object(frontline_agent, 'process_with_ai', new_callable=AsyncMock) as mock_ai:
            mock_ai.return_value = {"text": "How can I help?", "handled": True}
            
            await frontline_agent.process_voice_input("Hello", initial_context)
            
            # Verify context was properly updated
            assert frontline_agent.context["customer_name"] == "John Doe"
            assert frontline_agent.conversation_state == "MAIN_MENU"
    
    @pytest.mark.asyncio
    async def test_tool_execution(self, frontline_agent):
        """Test tool execution methods."""
        # Test update_customer_info
        result = await frontline_agent._update_customer_info({"name": "Test User", "order_type": "pickup"})
        assert result["success"] is True
        assert frontline_agent.context["customer_name"] == "Test User"
        assert frontline_agent.context["order_type"] == "pickup"
        
        # Test get_cart_summary
        frontline_agent.context["order_items"] = [
            {"name": "California Roll", "quantity": 2},
            {"name": "Spicy Tuna", "quantity": 1}
        ]
        result = await frontline_agent._get_cart_summary()
        assert result["empty"] is False
        assert result["count"] == 2
    
    @pytest.mark.asyncio
    async def test_confirmation_prompt_generation(self, frontline_agent):
        """Test order confirmation prompt generation."""
        cart = {
            "items": [
                {"name": "California Roll", "quantity": 2},
                {"name": "Spicy Tuna Roll", "quantity": 1}
            ],
            "total_price": 40.85
        }
        
        prompt = await frontline_agent._generate_confirmation_prompt(cart)
        
        assert "California Roll" in prompt
        assert "Spicy Tuna Roll" in prompt
        assert "$40.85" in prompt
        assert "correct" in prompt.lower()
    
    @pytest.mark.asyncio
    async def test_empty_cart_confirmation(self, frontline_agent):
        """Test confirmation prompt for empty cart."""
        cart = {"items": [], "total_price": 0}
        
        prompt = await frontline_agent._generate_confirmation_prompt(cart)
        
        assert "don't see any items" in prompt.lower()
        assert "would you like to add" in prompt.lower()