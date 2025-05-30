"""
Unit tests for AsyncFrontlineVoiceAgentAI class.

This module tests the AI-enhanced frontline agent functionality,
including greeting handling, tool execution, and state management.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from app.agents.frontline_async_ai import AsyncFrontlineVoiceAgentAI
from app.agents.ai_mixin import AIIntelligenceMixin


class TestAsyncFrontlineVoiceAgentAI:
    """Test suite for AsyncFrontlineVoiceAgentAI class."""
    
    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client for testing."""
        with patch('app.agents.ai_mixin.openai') as mock_openai:
            # Mock the client creation
            mock_client = MagicMock()
            mock_openai.AsyncOpenAI.return_value = mock_client
            
            # Mock chat completion response
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message = MagicMock()
            mock_response.choices[0].message.content = "AI response"
            mock_response.choices[0].message.tool_calls = None
            
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            yield mock_client
    
    @pytest.fixture
    async def frontline_agent(self, mock_openai_client):
        """Create a frontline agent instance for testing."""
        with patch('app.config.settings.OPENAI_API_KEY', 'test-key'):
            agent = AsyncFrontlineVoiceAgentAI(agent_id="test_frontline_123")
            # Initialize the AI client
            agent._init_ai_client()
            return agent
    
    def test_initialization(self, mock_openai_client):
        """Test agent initialization with correct attributes."""
        with patch('app.config.settings.OPENAI_API_KEY', 'test-key'):
            agent = AsyncFrontlineVoiceAgentAI(agent_id="custom_id")
            
            assert agent.name == "FrontlineVoiceAI"
            assert agent.agent_id == "custom_id"
            assert agent.conversation_state == "GREETING"
            assert agent.greeting_done is False
            assert agent.context["customer_name"] is None
            assert agent.context["order_type"] is None
            assert agent.context["order_items"] == []
            assert len(agent.tools) == 7  # Number of defined tools
            assert "GREETING" in agent.states
            assert "Sarah" in agent.instructions
    
    def test_tool_definitions(self, mock_openai_client):
        """Test that all required tools are properly defined."""
        with patch('app.config.settings.OPENAI_API_KEY', 'test-key'):
            agent = AsyncFrontlineVoiceAgentAI()
            
            tool_names = [tool["function"]["name"] for tool in agent.tools]
            
            assert "lookup_menu_item" in tool_names
            assert "get_menu_categories" in tool_names
            assert "add_to_cart" in tool_names
            assert "update_customer_info" in tool_names
            assert "get_cart_summary" in tool_names
            assert "confirm_order" in tool_names
            assert "escalate_to_human" in tool_names
    
    @pytest.mark.asyncio
    async def test_process_voice_input_first_interaction(self, frontline_agent, mock_openai_client):
        """Test processing first interaction generates greeting."""
        # Mock AI response for greeting
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello! Welcome to Red Bar Sushi. I'm Sarah. May I have your name please?"
        mock_response.choices[0].message.tool_calls = None
        
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        context = {"first_interaction": True}
        response = await frontline_agent.process_voice_input("", context)
        
        assert response["text"] == "Hello! Welcome to Red Bar Sushi. I'm Sarah. May I have your name please?"
        assert response["handled"] is True
        assert response["agent"] == "FrontlineVoiceAI"
        assert len(frontline_agent.context["conversation_history"]) > 0
    
    @pytest.mark.asyncio
    async def test_process_voice_input_with_customer_name(self, frontline_agent, mock_openai_client):
        """Test processing input when customer provides their name."""
        # Setup context with greeting done
        frontline_agent.greeting_done = True
        frontline_agent.conversation_state = "GREETING"
        
        # Mock AI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Nice to meet you, John! How can I help you today?"
        mock_response.choices[0].message.tool_calls = [
            MagicMock(
                function=MagicMock(
                    name="update_customer_info",
                    arguments='{"name": "John"}'
                )
            )
        ]
        
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        response = await frontline_agent.process_voice_input("My name is John")
        
        # Verify the response
        assert "John" in response["text"]
        assert response["handled"] is True
        
        # Verify tool execution tracking
        assert "tool_calls" in response or "actions" in response
    
    @pytest.mark.asyncio
    async def test_execute_tool_lookup_menu_item(self, frontline_agent):
        """Test executing lookup_menu_item tool."""
        with patch.object(frontline_agent, 'delegate_to_specialist', new_callable=AsyncMock) as mock_delegate:
            mock_delegate.return_value = {
                "text": "California Roll - $12.95",
                "handled": True,
                "data": {"price": 12.95, "description": "Crab, avocado, cucumber"}
            }
            
            result = await frontline_agent.execute_tool(
                "lookup_menu_item",
                {"item_name": "California Roll"}
            )
            
            assert result["status"] == "success"
            assert "California Roll" in result["result"]
            mock_delegate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_tool_add_to_cart(self, frontline_agent):
        """Test executing add_to_cart tool."""
        with patch.object(frontline_agent, 'delegate_to_specialist', new_callable=AsyncMock) as mock_delegate:
            mock_delegate.return_value = {
                "text": "Added California Roll to cart",
                "handled": True,
                "cart_updated": True
            }
            
            result = await frontline_agent.execute_tool(
                "add_to_cart",
                {
                    "item_name": "California Roll",
                    "quantity": 2,
                    "modifiers": ["extra avocado"]
                }
            )
            
            assert result["status"] == "success"
            assert "Added" in result["result"]
            
            # Verify delegation was called with correct params
            call_args = mock_delegate.call_args[0]
            assert call_args[0] == "cart"
            assert "California Roll" in call_args[1]
            assert "2" in call_args[1]
    
    @pytest.mark.asyncio
    async def test_execute_tool_update_customer_info(self, frontline_agent):
        """Test executing update_customer_info tool."""
        result = await frontline_agent.execute_tool(
            "update_customer_info",
            {
                "name": "John Doe",
                "phone": "555-1234",
                "order_type": "pickup"
            }
        )
        
        assert result["status"] == "success"
        assert frontline_agent.context["customer_name"] == "John Doe"
        assert frontline_agent.context["order_type"] == "pickup"
        assert "John Doe" in result["result"]
    
    @pytest.mark.asyncio
    async def test_execute_tool_escalate_to_human(self, frontline_agent):
        """Test executing escalate_to_human tool."""
        result = await frontline_agent.execute_tool(
            "escalate_to_human",
            {"reason": "Customer requested manager"}
        )
        
        assert result["status"] == "success"
        assert result["escalate"] is True
        assert result["reason"] == "Customer requested manager"
    
    @pytest.mark.asyncio
    async def test_execute_tool_unknown(self, frontline_agent):
        """Test executing unknown tool returns error."""
        result = await frontline_agent.execute_tool(
            "unknown_tool",
            {"param": "value"}
        )
        
        assert result["status"] == "error"
        assert "Unknown tool" in result["message"]
    
    @pytest.mark.asyncio
    async def test_conversation_state_transitions(self, frontline_agent, mock_openai_client):
        """Test conversation state transitions."""
        # Test transition from GREETING to MAIN_MENU
        frontline_agent.conversation_state = "GREETING"
        frontline_agent.context["customer_name"] = "John"
        
        # Mock response with state transition
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "How can I help you today?"
        mock_response.choices[0].message.tool_calls = None
        
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        response = await frontline_agent.process_voice_input("Hi")
        
        # Check that state context is included in AI call
        call_args = mock_openai_client.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        
        # Verify conversation history is maintained
        assert any("system" in msg.get("role", "") for msg in messages)
    
    @pytest.mark.asyncio
    async def test_context_preservation(self, frontline_agent):
        """Test that context is preserved across interactions."""
        # Set initial context
        frontline_agent.update_context({
            "session_id": "123",
            "call_sid": "CALL123"
        })
        
        # Add customer info
        await frontline_agent.execute_tool(
            "update_customer_info",
            {"name": "Jane"}
        )
        
        # Verify context is preserved
        context = frontline_agent.get_context()
        assert context["session_id"] == "123"
        assert context["call_sid"] == "CALL123"
        assert context["customer_name"] == "Jane"
    
    @pytest.mark.asyncio
    async def test_ai_error_handling(self, frontline_agent, mock_openai_client):
        """Test handling of AI service errors."""
        # Mock AI error
        mock_openai_client.chat.completions.create.side_effect = Exception("API Error")
        
        response = await frontline_agent.process_voice_input("Test input")
        
        # Should return a fallback response
        assert response["handled"] is True
        assert response["agent"] == "FrontlineVoiceAI"
        assert "assist" in response["text"].lower() or "help" in response["text"].lower()


class TestFrontlineAgentIntegration:
    """Integration tests for frontline agent with other components."""
    
    @pytest.fixture
    async def integrated_agent(self, mock_openai_client):
        """Create agent with mock specialists."""
        with patch('app.config.settings.OPENAI_API_KEY', 'test-key'):
            agent = AsyncFrontlineVoiceAgentAI()
            agent._init_ai_client()
            
            # Create mock specialists
            menu_specialist = Mock()
            menu_specialist.name = "MenuSpecialist"
            menu_specialist.process_input = AsyncMock(return_value={
                "text": "We have California Roll for $12.95",
                "handled": True,
                "data": {"items": ["California Roll"]}
            })
            
            cart_specialist = Mock()
            cart_specialist.name = "CartSpecialist"
            cart_specialist.process_input = AsyncMock(return_value={
                "text": "Added to cart",
                "handled": True,
                "cart_updated": True
            })
            
            agent.register_specialist("menu", menu_specialist)
            agent.register_specialist("cart", cart_specialist)
            
            return agent
    
    @pytest.mark.asyncio
    async def test_menu_inquiry_flow(self, integrated_agent, mock_openai_client):
        """Test complete menu inquiry flow."""
        # Mock AI response for menu inquiry
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Let me check our menu for you."
        mock_response.choices[0].message.tool_calls = [
            MagicMock(
                function=MagicMock(
                    name="lookup_menu_item",
                    arguments='{"item_name": "California Roll"}'
                )
            )
        ]
        
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        response = await integrated_agent.process_voice_input(
            "What's the price of California Roll?"
        )
        
        # Verify response includes menu information
        assert response["handled"] is True
        assert "menu" in response["text"].lower() or "check" in response["text"].lower()
    
    @pytest.mark.asyncio
    async def test_order_flow(self, integrated_agent, mock_openai_client):
        """Test complete ordering flow."""
        # Set customer name first
        integrated_agent.context["customer_name"] = "John"
        integrated_agent.conversation_state = "ORDERING"
        
        # Mock AI response for ordering
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "I'll add that to your order."
        mock_response.choices[0].message.tool_calls = [
            MagicMock(
                function=MagicMock(
                    name="add_to_cart",
                    arguments='{"item_name": "California Roll", "quantity": 2}'
                )
            )
        ]
        
        mock_openai_client.chat.completions.create.return_value = mock_response
        
        response = await integrated_agent.process_voice_input(
            "I'd like two California rolls please"
        )
        
        assert response["handled"] is True
        assert "add" in response["text"].lower() or "order" in response["text"].lower()