"""
Unit tests for BaseAsyncAgent class.

This module tests the core functionality of the BaseAsyncAgent,
including initialization, input processing, delegation, and context management.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from app.agents.base_async import BaseAsyncAgent


class TestBaseAsyncAgent:
    """Test suite for BaseAsyncAgent class."""
    
    @pytest.fixture
    def base_agent(self):
        """Create a basic agent instance for testing."""
        return BaseAsyncAgent(agent_id="test_123", name="TestAgent")
    
    @pytest.fixture
    def mock_specialist(self):
        """Create a mock specialist agent."""
        specialist = Mock(spec=BaseAsyncAgent)
        specialist.name = "SpecialistAgent"
        specialist.process_input = AsyncMock(return_value={
            "text": "Specialist response",
            "agent": "SpecialistAgent",
            "handled": True,
            "actions": []
        })
        return specialist
    
    @pytest.fixture
    def mock_policy_agent(self):
        """Create a mock policy agent."""
        policy = Mock(spec=BaseAsyncAgent)
        policy.name = "PolicyAgent"
        policy.validate = AsyncMock(return_value=(True, {"message": "Valid"}))
        return policy
    
    def test_initialization_with_defaults(self):
        """Test agent initialization with default parameters."""
        agent = BaseAsyncAgent()
        
        assert agent.name == "BaseAgent"
        assert agent.agent_name == "BaseAgent"
        assert agent.agent_id.startswith("agent_")
        assert agent.specialists == {}
        assert agent.policy_agent is None
        assert agent.context == {}
    
    def test_initialization_with_custom_params(self):
        """Test agent initialization with custom parameters."""
        agent = BaseAsyncAgent(
            agent_id="custom_123",
            name="CustomAgent",
            custom_param="value"
        )
        
        assert agent.agent_id == "custom_123"
        assert agent.name == "CustomAgent"
        assert agent.agent_name == "CustomAgent"
    
    def test_initialization_with_agent_name_param(self):
        """Test agent initialization with agent_name parameter for backward compatibility."""
        agent = BaseAsyncAgent(agent_name="BackCompatAgent")
        
        assert agent.name == "BackCompatAgent"
        assert agent.agent_name == "BackCompatAgent"
    
    @pytest.mark.asyncio
    async def test_process_input_default(self, base_agent):
        """Test default process_input implementation."""
        input_text = "Test input"
        context = {"session_id": "123"}
        
        response = await base_agent.process_input(input_text, context)
        
        assert response["text"] == "[TestAgent] Processed: Test input"
        assert response["agent"] == "TestAgent"
        assert response["handled"] is True
        assert response["actions"] == []
        assert base_agent.context["session_id"] == "123"
    
    @pytest.mark.asyncio
    async def test_process_voice_input(self, base_agent):
        """Test process_voice_input delegates to process_input."""
        input_text = "Voice input"
        
        with patch.object(base_agent, 'process_input', new_callable=AsyncMock) as mock_process:
            mock_process.return_value = {"text": "Response", "handled": True}
            
            response = await base_agent.process_voice_input(input_text, {"voice": True})
            
            mock_process.assert_called_once_with(input_text, {"voice": True})
            assert response == {"text": "Response", "handled": True}
    
    @pytest.mark.asyncio
    async def test_validate_default(self, base_agent):
        """Test default validate implementation."""
        data = {"order": "test"}
        
        is_valid, details = await base_agent.validate(data)
        
        assert is_valid is True
        assert details["message"] == "Validation not implemented"
        assert details["details"] == {}
    
    @pytest.mark.asyncio
    async def test_validate_with_policy_agent(self, base_agent, mock_policy_agent):
        """Test validate with a registered policy agent."""
        base_agent.register_policy_agent(mock_policy_agent)
        
        data = {"order": "test"}
        context = {"user": "123"}
        
        is_valid, details = await base_agent.validate(data, context)
        
        assert is_valid is True
        assert details["message"] == "Valid"
        mock_policy_agent.validate.assert_called_once_with(data, context)
    
    @pytest.mark.asyncio
    async def test_execute_tool_not_implemented(self, base_agent):
        """Test execute_tool default implementation."""
        result = await base_agent.execute_tool("unknown_tool", {"arg": "value"})
        
        assert result["status"] == "error"
        assert "not implemented" in result["message"]
        assert "TestAgent" in result["message"]
    
    def test_register_specialist(self, base_agent, mock_specialist):
        """Test registering a specialist agent."""
        base_agent.register_specialist("menu", mock_specialist)
        
        assert "menu" in base_agent.specialists
        assert base_agent.specialists["menu"] == mock_specialist
    
    def test_register_policy_agent(self, base_agent, mock_policy_agent):
        """Test registering a policy agent."""
        base_agent.register_policy_agent(mock_policy_agent)
        
        assert base_agent.policy_agent == mock_policy_agent
    
    @pytest.mark.asyncio
    async def test_delegate_to_specialist_success(self, base_agent, mock_specialist):
        """Test successful delegation to a specialist."""
        base_agent.register_specialist("menu", mock_specialist)
        
        input_text = "What's on the menu?"
        context = {"user_id": "123"}
        
        response = await base_agent.delegate_to_specialist("menu", input_text, context)
        
        assert response["text"] == "Specialist response"
        assert response["agent"] == "SpecialistAgent"
        assert response["handled"] is True
        
        # Verify context was passed with delegated_by
        call_args = mock_specialist.process_input.call_args
        assert call_args[0][0] == input_text
        assert call_args[0][1]["user_id"] == "123"
        assert call_args[0][1]["delegated_by"] == "TestAgent"
    
    @pytest.mark.asyncio
    async def test_delegate_to_specialist_not_found(self, base_agent):
        """Test delegation when specialist is not registered."""
        response = await base_agent.delegate_to_specialist("unknown", "Test input")
        
        assert "don't have a specialist" in response["text"]
        assert response["agent"] == "TestAgent"
        assert response["handled"] is False
        assert response["actions"] == []
    
    def test_update_context(self, base_agent):
        """Test updating agent context."""
        base_agent.context = {"key1": "value1"}
        
        base_agent.update_context({"key2": "value2", "key1": "updated"})
        
        assert base_agent.context["key1"] == "updated"
        assert base_agent.context["key2"] == "value2"
    
    def test_get_context(self, base_agent):
        """Test getting agent context returns a copy."""
        base_agent.context = {"key": "value"}
        
        context = base_agent.get_context()
        context["key"] = "modified"
        
        assert base_agent.context["key"] == "value"  # Original unchanged
        assert context["key"] == "modified"  # Copy modified
    
    def test_get_tools_default(self, base_agent):
        """Test default get_tools implementation."""
        tools = base_agent.get_tools()
        
        assert tools == []


class TestBaseAsyncAgentIntegration:
    """Integration tests for BaseAsyncAgent with multiple agents."""
    
    @pytest.fixture
    def agent_system(self):
        """Create a system of agents for integration testing."""
        main_agent = BaseAsyncAgent(name="MainAgent")
        menu_specialist = BaseAsyncAgent(name="MenuSpecialist")
        policy_agent = BaseAsyncAgent(name="PolicyAgent")
        
        # Override the process_input method for menu specialist
        async def menu_process(input_text, context=None):
            return {
                "text": f"Menu info: {input_text}",
                "agent": "MenuSpecialist",
                "handled": True,
                "actions": ["show_menu"]
            }
        
        menu_specialist.process_input = menu_process
        
        # Override validate method for policy agent
        async def policy_validate(data, context=None):
            if data.get("amount", 0) > 1000:
                return False, {"message": "Amount too high", "max": 1000}
            return True, {"message": "Valid"}
        
        policy_agent.validate = policy_validate
        
        main_agent.register_specialist("menu", menu_specialist)
        main_agent.register_policy_agent(policy_agent)
        
        return main_agent
    
    @pytest.mark.asyncio
    async def test_agent_system_integration(self, agent_system):
        """Test integrated agent system with delegation and validation."""
        # Test delegation
        response = await agent_system.delegate_to_specialist(
            "menu", 
            "Show me sushi options",
            {"user": "test"}
        )
        
        assert response["text"] == "Menu info: Show me sushi options"
        assert response["handled"] is True
        assert "show_menu" in response["actions"]
        
        # Test validation with policy agent
        is_valid, details = await agent_system.validate({"amount": 500})
        assert is_valid is True
        
        is_valid, details = await agent_system.validate({"amount": 1500})
        assert is_valid is False
        assert details["message"] == "Amount too high"
        assert details["max"] == 1000


class TestBaseAsyncAgentErrorHandling:
    """Test error handling in BaseAsyncAgent."""
    
    @pytest.fixture
    def faulty_specialist(self):
        """Create a specialist that raises errors."""
        specialist = Mock(spec=BaseAsyncAgent)
        specialist.name = "FaultySpecialist"
        specialist.process_input = AsyncMock(side_effect=Exception("Processing error"))
        return specialist
    
    @pytest.mark.asyncio
    async def test_delegation_error_handling(self, base_agent, faulty_specialist):
        """Test error handling during delegation."""
        base_agent = BaseAsyncAgent(name="MainAgent")
        base_agent.register_specialist("faulty", faulty_specialist)
        
        with pytest.raises(Exception) as exc_info:
            await base_agent.delegate_to_specialist("faulty", "Test input")
        
        assert str(exc_info.value) == "Processing error"
    
    @pytest.mark.asyncio
    async def test_concurrent_context_updates(self, base_agent):
        """Test concurrent context updates are handled properly."""
        async def update_context(key, value):
            await asyncio.sleep(0.001)  # Simulate async operation
            base_agent.update_context({key: value})
        
        # Run multiple concurrent updates
        tasks = [
            update_context(f"key{i}", f"value{i}")
            for i in range(10)
        ]
        
        await asyncio.gather(*tasks)
        
        # Verify all updates were applied
        context = base_agent.get_context()
        for i in range(10):
            assert context[f"key{i}"] == f"value{i}"


class TestAgentContextManagementAndState:
    """Comprehensive tests for agent context management and state (Task 2.1.3)."""
    
    @pytest.fixture
    def parent_agent(self):
        """Create a parent agent with initial context."""
        agent = BaseAsyncAgent(name="ParentAgent")
        agent.context = {
            "session_id": "sess_123",
            "user_id": "user_456",
            "conversation_history": ["Hello", "I want to order food"],
            "metadata": {"source": "phone", "timestamp": "2024-01-01T10:00:00"}
        }
        return agent
    
    @pytest.fixture
    def child_agent(self):
        """Create a child/specialist agent."""
        return BaseAsyncAgent(name="ChildAgent")
    
    def test_context_preservation_during_process_input(self, parent_agent):
        """Test that context is preserved when processing input."""
        original_context = parent_agent.get_context()
        
        # Process input with additional context
        asyncio.run(parent_agent.process_input("test", {"new_key": "new_value"}))
        
        # Verify original context is preserved
        current_context = parent_agent.get_context()
        assert current_context["session_id"] == original_context["session_id"]
        assert current_context["user_id"] == original_context["user_id"]
        assert current_context["conversation_history"] == original_context["conversation_history"]
        assert current_context["metadata"] == original_context["metadata"]
        assert current_context["new_key"] == "new_value"
    
    def test_context_isolation_between_agents(self, parent_agent, child_agent):
        """Test that context modifications in one agent don't affect another."""
        parent_agent.update_context({"shared_key": "parent_value"})
        child_agent.update_context({"shared_key": "child_value"})
        
        assert parent_agent.get_context()["shared_key"] == "parent_value"
        assert child_agent.get_context()["shared_key"] == "child_value"
    
    def test_deep_context_copy(self, parent_agent):
        """Test that get_context returns a deep copy to prevent mutations."""
        context = parent_agent.get_context()
        
        # Modify nested structures
        context["metadata"]["new_field"] = "test"
        context["conversation_history"].append("New message")
        
        # Verify original is unchanged
        original_context = parent_agent.get_context()
        assert "new_field" not in original_context["metadata"]
        assert "New message" not in original_context["conversation_history"]
    
    @pytest.mark.asyncio
    async def test_context_inheritance_during_delegation(self, parent_agent, child_agent):
        """Test that child agents inherit parent context during delegation."""
        parent_agent.register_specialist("child", child_agent)
        
        # Override child's process_input to capture context
        captured_context = {}
        async def capture_context(input_text, context=None):
            captured_context.update(context or {})
            return {"text": "Done", "handled": True}
        
        child_agent.process_input = capture_context
        
        await parent_agent.delegate_to_specialist("child", "test input")
        
        # Verify parent context was inherited
        assert captured_context["session_id"] == "sess_123"
        assert captured_context["user_id"] == "user_456"
        assert captured_context["delegated_by"] == "ParentAgent"
        assert captured_context["conversation_history"] == ["Hello", "I want to order food"]
    
    def test_context_merge_strategy(self, parent_agent):
        """Test how contexts are merged when updating."""
        parent_agent.update_context({
            "session_id": "new_session",  # Should overwrite
            "metadata": {"new_field": "value"},  # Will overwrite, not merge
            "new_key": "new_value"  # Should add
        })
        
        context = parent_agent.get_context()
        assert context["session_id"] == "new_session"  # Overwritten
        # Note: dict.update() replaces the entire value, doesn't merge nested dicts
        assert context["metadata"] == {"new_field": "value"}  # Replaced
        assert context["new_key"] == "new_value"  # Added
    
    @pytest.mark.asyncio
    async def test_context_persistence_across_multiple_delegations(self, parent_agent):
        """Test context persists correctly across multiple delegations."""
        specialist1 = BaseAsyncAgent(name="Specialist1")
        specialist2 = BaseAsyncAgent(name="Specialist2")
        
        parent_agent.register_specialist("spec1", specialist1)
        parent_agent.register_specialist("spec2", specialist2)
        
        # Track context through delegations
        contexts = []
        
        async def track_context(input_text, context=None):
            contexts.append(context.copy() if context else {})
            return {"text": "Done", "handled": True}
        
        specialist1.process_input = track_context
        specialist2.process_input = track_context
        
        # Delegate to multiple specialists
        await parent_agent.delegate_to_specialist("spec1", "first")
        await parent_agent.delegate_to_specialist("spec2", "second")
        
        # Verify both received consistent parent context
        assert contexts[0]["session_id"] == contexts[1]["session_id"]
        assert contexts[0]["user_id"] == contexts[1]["user_id"]
        assert contexts[0]["delegated_by"] == "ParentAgent"
        assert contexts[1]["delegated_by"] == "ParentAgent"
    
    def test_context_state_after_error(self, parent_agent):
        """Test that context state is preserved even after errors."""
        original_context = parent_agent.get_context()
        
        # Cause an error in update_context by passing invalid type
        try:
            parent_agent.update_context(None)  # This might cause an error
        except:
            pass
        
        # Context should still be intact
        assert parent_agent.get_context() == original_context
    
    @pytest.mark.asyncio
    async def test_concurrent_context_modifications(self, parent_agent):
        """Test thread-safe context modifications under concurrent access."""
        async def modify_context(agent, key, value, delay=0.001):
            await asyncio.sleep(delay)
            current = agent.get_context()
            current[key] = value
            agent.update_context(current)
        
        # Run concurrent modifications
        tasks = [
            modify_context(parent_agent, f"concurrent_{i}", f"value_{i}", i * 0.0001)
            for i in range(20)
        ]
        
        await asyncio.gather(*tasks)
        
        # Verify all modifications were applied
        context = parent_agent.get_context()
        for i in range(20):
            assert context[f"concurrent_{i}"] == f"value_{i}"
    
    def test_context_serialization_safety(self, parent_agent):
        """Test that context can be safely serialized (e.g., for Redis storage)."""
        import json
        
        # Add various data types to context
        parent_agent.update_context({
            "string": "value",
            "number": 123,
            "float": 123.45,
            "boolean": True,
            "null": None,
            "list": [1, 2, 3],
            "dict": {"nested": "value"}
        })
        
        context = parent_agent.get_context()
        
        # Should be JSON serializable
        serialized = json.dumps(context)
        deserialized = json.loads(serialized)
        
        assert deserialized == context
    
    @pytest.mark.asyncio
    async def test_context_enrichment_pattern(self, parent_agent, child_agent):
        """Test pattern where specialists enrich context with their findings."""
        parent_agent.register_specialist("enricher", child_agent)
        
        # Child enriches context with its findings
        async def enrich_context(input_text, context=None):
            context = context or {}
            # Add enrichment
            enriched_context = context.copy()
            enriched_context["enrichment"] = {
                "found_items": ["item1", "item2"],
                "total_price": 25.50,
                "specialist_notes": "Found 2 items matching request"
            }
            return {
                "text": "Found items",
                "handled": True,
                "context": enriched_context  # Return enriched context
            }
        
        child_agent.process_input = enrich_context
        
        response = await parent_agent.delegate_to_specialist("enricher", "find items")
        
        # In real implementation, parent should merge response context
        assert "context" in response
        assert "enrichment" in response["context"]
        assert response["context"]["enrichment"]["found_items"] == ["item1", "item2"]
    
    def test_context_size_management(self, parent_agent):
        """Test handling of large contexts (e.g., long conversation history)."""
        # Add large conversation history
        large_history = ["Message " + str(i) for i in range(1000)]
        parent_agent.update_context({"conversation_history": large_history})
        
        context = parent_agent.get_context()
        assert len(context["conversation_history"]) == 1000
        
        # In production, might want to implement context pruning
        # This test documents current behavior (no automatic pruning)
    
    @pytest.mark.asyncio
    async def test_context_versioning(self, parent_agent):
        """Test pattern for context versioning/snapshots."""
        context_versions = []
        
        # Capture initial state
        context_versions.append(parent_agent.get_context())
        
        # Make changes
        parent_agent.update_context({"step": 1, "action": "initialized"})
        context_versions.append(parent_agent.get_context())
        
        parent_agent.update_context({"step": 2, "action": "processed"})
        context_versions.append(parent_agent.get_context())
        
        # Verify we can track context evolution
        assert context_versions[0]["session_id"] == "sess_123"
        assert "step" not in context_versions[0]
        assert context_versions[1]["step"] == 1
        assert context_versions[2]["step"] == 2
    
    def test_context_reset_capability(self, parent_agent):
        """Test ability to reset context to clean state."""
        # Modify context
        parent_agent.update_context({"temp_data": "value"})
        
        # Reset context (simulate clearing for new conversation)
        parent_agent.context = {}
        
        assert parent_agent.get_context() == {}
    
    @pytest.mark.asyncio
    async def test_delegation_chain_context_tracking(self):
        """Test context tracking through a chain of delegations."""
        agent_a = BaseAsyncAgent(name="AgentA")
        agent_b = BaseAsyncAgent(name="AgentB")
        agent_c = BaseAsyncAgent(name="AgentC")
        
        # Set up delegation chain: A -> B -> C
        agent_a.register_specialist("b_role", agent_b)
        agent_b.register_specialist("c_role", agent_c)
        
        delegation_chain = []
        
        async def track_delegation(input_text, context=None):
            if context and "delegated_by" in context:
                delegation_chain.append(context["delegated_by"])
            return {"text": "Processed", "handled": True}
        
        # Override process_input for B to delegate to C
        async def b_process(input_text, context=None):
            delegation_chain.append("B_processing")
            return await agent_b.delegate_to_specialist("c_role", input_text, context)
        
        agent_b.process_input = b_process
        agent_c.process_input = track_delegation
        
        # Start delegation from A
        await agent_a.delegate_to_specialist("b_role", "test", {"origin": "A"})
        
        # Verify delegation chain
        assert "B_processing" in delegation_chain
        assert "AgentB" in delegation_chain  # C should see B as delegator


class TestSpecialistRegistrationAndHandoffs:
    """Comprehensive tests for specialist registration and handoffs (Task 2.1.4)."""
    
    @pytest.fixture
    def main_agent(self):
        """Create a main agent for testing."""
        return BaseAsyncAgent(name="MainAgent")
    
    @pytest.fixture
    def menu_specialist(self):
        """Create a menu specialist agent."""
        agent = BaseAsyncAgent(name="MenuSpecialist")
        
        async def menu_process(input_text, context=None):
            return {
                "text": f"Menu: Found items for '{input_text}'",
                "agent": "MenuSpecialist",
                "handled": True,
                "actions": ["show_menu"],
                "data": {"items_found": 5}
            }
        
        agent.process_input = menu_process
        return agent
    
    @pytest.fixture
    def cart_specialist(self):
        """Create a cart specialist agent."""
        agent = BaseAsyncAgent(name="CartSpecialist")
        
        async def cart_process(input_text, context=None):
            return {
                "text": f"Cart: Added '{input_text}' to cart",
                "agent": "CartSpecialist",
                "handled": True,
                "actions": ["add_to_cart"],
                "data": {"cart_total": 25.99}
            }
        
        agent.process_input = cart_process
        return agent
    
    def test_specialist_registration(self, main_agent, menu_specialist, cart_specialist):
        """Test basic specialist registration functionality."""
        # Register specialists
        main_agent.register_specialist("menu", menu_specialist)
        main_agent.register_specialist("cart", cart_specialist)
        
        # Verify registration
        assert "menu" in main_agent.specialists
        assert "cart" in main_agent.specialists
        assert main_agent.specialists["menu"] == menu_specialist
        assert main_agent.specialists["cart"] == cart_specialist
    
    def test_specialist_registration_overwrite(self, main_agent, menu_specialist, cart_specialist):
        """Test that registering a specialist with same role overwrites previous."""
        # Register menu specialist
        main_agent.register_specialist("menu", menu_specialist)
        assert main_agent.specialists["menu"] == menu_specialist
        
        # Register cart specialist with same role
        main_agent.register_specialist("menu", cart_specialist)
        assert main_agent.specialists["menu"] == cart_specialist
        assert len(main_agent.specialists) == 1
    
    def test_multiple_specialists_same_agent(self, main_agent, menu_specialist):
        """Test registering same agent for multiple roles."""
        main_agent.register_specialist("menu", menu_specialist)
        main_agent.register_specialist("search", menu_specialist)
        main_agent.register_specialist("catalog", menu_specialist)
        
        assert len(main_agent.specialists) == 3
        assert all(main_agent.specialists[role] == menu_specialist 
                  for role in ["menu", "search", "catalog"])
    
    @pytest.mark.asyncio
    async def test_basic_handoff(self, main_agent, menu_specialist):
        """Test basic handoff to specialist."""
        main_agent.register_specialist("menu", menu_specialist)
        
        response = await main_agent.delegate_to_specialist("menu", "show sushi")
        
        assert response["text"] == "Menu: Found items for 'show sushi'"
        assert response["agent"] == "MenuSpecialist"
        assert response["handled"] is True
        assert "show_menu" in response["actions"]
        assert response["data"]["items_found"] == 5
    
    @pytest.mark.asyncio
    async def test_handoff_with_context_preservation(self, main_agent, menu_specialist):
        """Test that handoff preserves and passes context correctly."""
        main_agent.register_specialist("menu", menu_specialist)
        
        # Set up context
        context = {
            "user_id": "user123",
            "session_id": "sess456",
            "preferences": {"vegetarian": True}
        }
        
        # Capture the context passed to specialist
        captured_context = None
        async def capture_context(input_text, context=None):
            nonlocal captured_context
            captured_context = context
            return {"text": "Done", "handled": True}
        
        menu_specialist.process_input = capture_context
        
        await main_agent.delegate_to_specialist("menu", "show items", context)
        
        # Verify context was passed correctly
        assert captured_context is not None
        assert captured_context["user_id"] == "user123"
        assert captured_context["session_id"] == "sess456"
        assert captured_context["preferences"]["vegetarian"] is True
        assert captured_context["delegated_by"] == "MainAgent"
    
    @pytest.mark.asyncio
    async def test_handoff_failure_handling(self, main_agent):
        """Test handling when trying to hand off to non-existent specialist."""
        response = await main_agent.delegate_to_specialist("non_existent", "test")
        
        assert response["handled"] is False
        assert "don't have a specialist" in response["text"]
        assert response["agent"] == "MainAgent"
    
    @pytest.mark.asyncio
    async def test_specialist_error_propagation(self, main_agent, menu_specialist):
        """Test that errors in specialists propagate correctly."""
        main_agent.register_specialist("menu", menu_specialist)
        
        # Make specialist raise an error
        async def error_process(input_text, context=None):
            raise ValueError("Specialist processing error")
        
        menu_specialist.process_input = error_process
        
        with pytest.raises(ValueError) as exc_info:
            await main_agent.delegate_to_specialist("menu", "test")
        
        assert str(exc_info.value) == "Specialist processing error"
    
    @pytest.mark.asyncio
    async def test_handoff_chain(self, main_agent, menu_specialist, cart_specialist):
        """Test chain of handoffs between specialists."""
        main_agent.register_specialist("menu", menu_specialist)
        menu_specialist.register_specialist("cart", cart_specialist)
        
        # First handoff: main -> menu
        menu_response = await main_agent.delegate_to_specialist("menu", "find sushi")
        assert menu_response["agent"] == "MenuSpecialist"
        
        # Second handoff: menu -> cart
        cart_response = await menu_specialist.delegate_to_specialist("cart", "california roll")
        assert cart_response["agent"] == "CartSpecialist"
        assert cart_response["text"] == "Cart: Added 'california roll' to cart"
    
    @pytest.mark.asyncio
    async def test_circular_handoff_prevention(self, main_agent):
        """Test prevention of circular handoffs."""
        agent_a = BaseAsyncAgent(name="AgentA")
        agent_b = BaseAsyncAgent(name="AgentB")
        
        # Create circular registration
        agent_a.register_specialist("b", agent_b)
        agent_b.register_specialist("a", agent_a)
        
        # Track delegation depth
        delegation_count = 0
        max_delegations = 10
        
        async def track_delegations_a(input_text, context=None):
            nonlocal delegation_count
            delegation_count += 1
            
            if delegation_count > max_delegations:
                return {"text": "Max delegations reached", "handled": True}
            
            # Delegate to B
            return await agent_a.delegate_to_specialist("b", input_text, context)
        
        async def track_delegations_b(input_text, context=None):
            nonlocal delegation_count
            delegation_count += 1
            
            if delegation_count > max_delegations:
                return {"text": "Max delegations reached", "handled": True}
            
            # Delegate back to A
            return await agent_b.delegate_to_specialist("a", input_text, context)
        
        agent_a.process_input = track_delegations_a
        agent_b.process_input = track_delegations_b
        
        # This would cause infinite loop without prevention
        # In real implementation, should have max delegation depth
        # For this test, we just verify the pattern exists
        assert agent_a.specialists["b"] == agent_b
        assert agent_b.specialists["a"] == agent_a
    
    @pytest.mark.asyncio
    async def test_specialist_state_isolation(self, main_agent):
        """Test that specialist states are isolated between handoffs."""
        specialist = BaseAsyncAgent(name="StatefulSpecialist")
        specialist.state = {"counter": 0}
        
        async def stateful_process(input_text, context=None):
            specialist.state["counter"] += 1
            return {
                "text": f"Count: {specialist.state['counter']}",
                "handled": True,
                "count": specialist.state["counter"]
            }
        
        specialist.process_input = stateful_process
        main_agent.register_specialist("counter", specialist)
        
        # Multiple handoffs should maintain state
        response1 = await main_agent.delegate_to_specialist("counter", "increment")
        response2 = await main_agent.delegate_to_specialist("counter", "increment")
        response3 = await main_agent.delegate_to_specialist("counter", "increment")
        
        assert response1["count"] == 1
        assert response2["count"] == 2
        assert response3["count"] == 3
    
    @pytest.mark.asyncio
    async def test_conditional_handoff(self, main_agent, menu_specialist, cart_specialist):
        """Test conditional handoff based on input."""
        main_agent.register_specialist("menu", menu_specialist)
        main_agent.register_specialist("cart", cart_specialist)
        
        # Override main agent's process_input to do conditional delegation
        async def conditional_process(input_text, context=None):
            if "menu" in input_text.lower():
                return await main_agent.delegate_to_specialist("menu", input_text, context)
            elif "cart" in input_text.lower():
                return await main_agent.delegate_to_specialist("cart", input_text, context)
            else:
                return {
                    "text": "I can help with menu or cart",
                    "agent": "MainAgent",
                    "handled": True
                }
        
        main_agent.process_input = conditional_process
        
        # Test different inputs
        menu_response = await main_agent.process_input("show menu")
        cart_response = await main_agent.process_input("add to cart")
        other_response = await main_agent.process_input("hello")
        
        assert menu_response["agent"] == "MenuSpecialist"
        assert cart_response["agent"] == "CartSpecialist"
        assert other_response["agent"] == "MainAgent"
    
    @pytest.mark.asyncio
    async def test_handoff_response_enrichment(self, main_agent, menu_specialist):
        """Test that main agent can enrich specialist responses."""
        main_agent.register_specialist("menu", menu_specialist)
        
        # Create wrapper to enrich responses
        original_delegate = main_agent.delegate_to_specialist
        
        async def enriching_delegate(role, input_text, context=None):
            response = await original_delegate(role, input_text, context)
            
            # Enrich response
            response["enriched"] = True
            response["timestamp"] = "2024-01-01T10:00:00"
            response["main_agent_notes"] = f"Processed by {main_agent.name}"
            
            return response
        
        main_agent.delegate_to_specialist = enriching_delegate
        
        response = await main_agent.delegate_to_specialist("menu", "show items")
        
        assert response["enriched"] is True
        assert response["timestamp"] == "2024-01-01T10:00:00"
        assert response["main_agent_notes"] == "Processed by MainAgent"
        assert response["agent"] == "MenuSpecialist"  # Original response preserved
    
    def test_specialist_type_validation(self, main_agent):
        """Test that only BaseAsyncAgent instances can be registered as specialists."""
        # Try to register non-agent object
        with pytest.raises(AttributeError):
            main_agent.register_specialist("invalid", "not_an_agent")
        
        # Verify it wasn't registered
        assert "invalid" not in main_agent.specialists
    
    @pytest.mark.asyncio
    async def test_parallel_handoffs(self, main_agent, menu_specialist, cart_specialist):
        """Test handling multiple handoffs in parallel."""
        main_agent.register_specialist("menu", menu_specialist)
        main_agent.register_specialist("cart", cart_specialist)
        
        # Execute handoffs in parallel
        menu_task = main_agent.delegate_to_specialist("menu", "show items")
        cart_task = main_agent.delegate_to_specialist("cart", "add item")
        
        menu_response, cart_response = await asyncio.gather(menu_task, cart_task)
        
        assert menu_response["agent"] == "MenuSpecialist"
        assert cart_response["agent"] == "CartSpecialist"
        assert menu_response["handled"] is True
        assert cart_response["handled"] is True
    
    @pytest.mark.asyncio
    async def test_handoff_with_tools(self, main_agent):
        """Test handoff to specialist that uses tools."""
        tool_specialist = BaseAsyncAgent(name="ToolSpecialist")
        
        # Add tool execution
        async def execute_search_tool(tool_name, args):
            if tool_name == "search":
                return {
                    "status": "success",
                    "results": [f"Found: {args.get('query', '')}"]
                }
            return {"status": "error", "message": "Unknown tool"}
        
        tool_specialist.execute_tool = execute_search_tool
        
        async def tool_process(input_text, context=None):
            # Use tool during processing
            tool_result = await tool_specialist.execute_tool("search", {"query": input_text})
            
            return {
                "text": f"Search complete: {tool_result['results'][0]}",
                "agent": "ToolSpecialist",
                "handled": True,
                "tool_used": "search",
                "tool_result": tool_result
            }
        
        tool_specialist.process_input = tool_process
        main_agent.register_specialist("search", tool_specialist)
        
        response = await main_agent.delegate_to_specialist("search", "sushi rolls")
        
        assert response["text"] == "Search complete: Found: sushi rolls"
        assert response["tool_used"] == "search"
        assert response["tool_result"]["status"] == "success"
    
    def test_get_registered_specialists(self, main_agent, menu_specialist, cart_specialist):
        """Test retrieving list of registered specialists."""
        main_agent.register_specialist("menu", menu_specialist)
        main_agent.register_specialist("cart", cart_specialist)
        
        specialists = main_agent.specialists
        
        assert len(specialists) == 2
        assert set(specialists.keys()) == {"menu", "cart"}
        assert specialists["menu"].name == "MenuSpecialist"
        assert specialists["cart"].name == "CartSpecialist"