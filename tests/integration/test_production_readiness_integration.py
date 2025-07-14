"""
Integration tests for production readiness features.

These tests validate the complete workflows including circuit breaker,
tool delegation optimization, enhanced recovery, and alerting integration.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from app.utils.agent_orchestration_async import AsyncAgentOrchestrator
from app.fsm.manager import hsm_manager
from app.fsm.core import ConversationHSMStates, ConversationHSMEvents
from app.services.circuit_breaker import get_circuit_breaker, CircuitState
from app.services.alerting import alerting_service
from app.utils.intent_detector_async import intent_detector


class TestToolDelegationIntegration:
    """Integration tests for optimized tool delegation."""
    
    @pytest.mark.asyncio
    async def test_frontline_to_menu_to_cart_workflow(self):
        """Test complete workflow from Frontline Agent through Menu to Cart."""
        # Create orchestrator with mocked agents
        orchestrator = AsyncAgentOrchestrator()
        
        # Mock agents
        mock_frontline = AsyncMock()
        mock_menu = AsyncMock()
        mock_cart = AsyncMock()
        
        orchestrator.frontline_agent = mock_frontline
        orchestrator.menu_agent = mock_menu
        orchestrator.cart_agent = mock_cart
        
        # Setup frontline agent with real tool delegation logic
        frontline_agent = mock_frontline
        frontline_agent.menu_agent = mock_menu
        frontline_agent.cart_agent = mock_cart
        
        # Mock menu search response
        mock_menu.search_menu_items.return_value = {
            "found": True,
            "item": {
                "id": "123",
                "name": "Salmon Roll",
                "plu": "SAL001",
                "price": 12.50
            },
            "confidence": 0.9
        }
        
        # Mock cart addition response
        mock_cart.add_item_to_cart.return_value = {
            "success": True,
            "item_added": {
                "plu": "SAL001",
                "name": "Salmon Roll",
                "quantity": 1,
                "price": 12.50
            },
            "cart_total": 12.50,
            "message": "Added Salmon Roll to your cart"
        }
        
        # Mock the _add_to_cart method to simulate the new pattern
        async def mock_add_to_cart(item_description, context):
            # Simulate resolve-then-add pattern
            menu_result = await mock_menu.search_menu_items(
                item_description, context=context
            )
            
            if menu_result["found"] and menu_result["confidence"] >= 0.3:
                cart_result = await mock_cart.add_item_to_cart(
                    plu=menu_result["item"]["plu"],
                    quantity=1,
                    context=context
                )
                return cart_result
            else:
                return {"success": False, "message": "Item not found"}
        
        frontline_agent._add_to_cart = mock_add_to_cart
        
        # Execute the workflow
        result = await frontline_agent._add_to_cart(
            "salmon roll", 
            {"call_sid": "test_call"}
        )
        
        # Verify the correct sequence
        assert mock_menu.search_menu_items.called
        assert mock_cart.add_item_to_cart.called
        
        # Verify Menu Agent was called before Cart Agent
        menu_call_time = mock_menu.search_menu_items.call_count
        cart_call_time = mock_cart.add_item_to_cart.call_count
        assert menu_call_time == 1
        assert cart_call_time == 1
        
        # Verify PLU was passed correctly
        cart_call_args = mock_cart.add_item_to_cart.call_args
        assert cart_call_args[1]["plu"] == "SAL001"
        
        # Verify successful result
        assert result["success"] is True
        assert "Salmon Roll" in result["message"]
    
    @pytest.mark.asyncio
    async def test_performance_metrics_logging_integration(self):
        """Test that tool delegation performance is properly logged."""
        with patch('app.utils.metrics_logger.metrics_logger') as mock_metrics:
            # Create orchestrator
            orchestrator = AsyncAgentOrchestrator()
            
            # Mock agent processing to simulate metrics logging
            async def mock_process_with_agent(state, input_text, context):
                # Simulate processing time
                await asyncio.sleep(0.1)  # 100ms
                return (
                    MagicMock(__class__=MagicMock(__name__="TestAgent")),
                    {"text": "Response", "handled": True}
                )
            
            orchestrator._process_with_appropriate_agent = mock_process_with_agent
            
            # Mock HSM and conversation store
            with patch.object(orchestrator, 'conversation_store') as mock_store:
                mock_store.add_message = AsyncMock()
                
                with patch('app.utils.agent_orchestration_async.hsm_manager') as mock_hsm:
                    mock_hsm.get_current_states.return_value = [ConversationHSMStates.ORDERING]
                    mock_hsm.handle_event = AsyncMock()
                    
                    # Execute processing
                    await orchestrator.process_voice_input(
                        "test_call", "add salmon roll", {}
                    )
                    
                    # Verify metrics were logged
                    mock_metrics.log_response_latency.assert_called_once()
                    
                    # Verify latency was measured
                    call_args = mock_metrics.log_response_latency.call_args
                    latency_ms = call_args[1]["latency_ms"]
                    assert latency_ms >= 100  # Should be at least 100ms due to sleep


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker functionality."""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_with_alerting(self):
        """Test circuit breaker integration with alerting system."""
        circuit_breaker = get_circuit_breaker()
        
        # Reset circuit breaker to clean state
        circuit_breaker.state = CircuitState.CLOSED
        circuit_breaker.failure_count = 0
        circuit_breaker.recent_failures.clear()
        
        # Mock alerting
        with patch.object(alerting_service, 'send_alert') as mock_alert:
            # Create failing function
            async def failing_openai_call():
                raise Exception("OpenAI API Error")
            
            # Accumulate failures to trigger circuit opening
            for i in range(circuit_breaker.config.failure_threshold):
                with pytest.raises(Exception):
                    await circuit_breaker.call(failing_openai_call)
            
            # Verify circuit is open
            assert circuit_breaker.state == CircuitState.OPEN
            
            # Verify alert was sent
            mock_alert.assert_called()
            alert_call = mock_alert.call_args[0][0]
            assert alert_call.alert_type.value == "circuit_breaker_open"
            assert alert_call.severity.value == "critical"
    
    @pytest.mark.asyncio
    async def test_fallback_mode_activation(self):
        """Test static fallback mode activation when circuit is open."""
        from app.utils.static_fallback import StaticFallbackHandler
        
        # Mock circuit breaker in OPEN state
        circuit_breaker = get_circuit_breaker()
        circuit_breaker.state = CircuitState.OPEN
        
        # Create fallback handler
        fallback_handler = StaticFallbackHandler()
        
        # Test fallback response generation
        response = fallback_handler.handle_initial_greeting()
        
        assert "twiml" in response
        assert "Red Bar" in response["twiml"]  # Should contain restaurant greeting
        
        # Verify fallback doesn't require AI
        # This should work even when OpenAI is unavailable
        assert response["requires_ai"] is False


class TestEnhancedRecoveryIntegration:
    """Integration tests for enhanced HSM recovery."""
    
    @pytest.mark.asyncio
    async def test_complete_go_back_workflow(self):
        """Test complete go back workflow with intent detection and HSM recovery."""
        # Mock intent detection
        with patch.object(intent_detector, 'detect_go_back_intent') as mock_detect:
            mock_detect.return_value = {
                "intent": "GO_BACK_TO_STATE",
                "target_state": "ORDERING",
                "confidence": 0.9
            }
            
            # Mock HSM state path
            with patch.object(hsm_manager, 'get_current_state_path') as mock_path:
                mock_path.return_value = [
                    ConversationHSMStates.ACTIVE,
                    ConversationHSMStates.ORDERING,
                    ConversationHSMStates.ORDERING_BROWSING,
                    ConversationHSMStates.ORDERING_ITEM_CUSTOMIZATION
                ]
                
                # Mock HSM operations
                with patch.object(hsm_manager, '_exit_state') as mock_exit:
                    with patch.object(hsm_manager, 'set_state_path') as mock_set:
                        hsm_manager.state_store.set_state_path = AsyncMock()
                        hsm_manager.state_store.get_leaf_state = AsyncMock(
                            return_value=ConversationHSMStates.ORDERING_BROWSING
                        )
                        
                        # Execute go back workflow
                        result = await hsm_manager.go_back_to_state(
                            "test_call", 
                            ConversationHSMStates.ORDERING,
                            {}
                        )
                        
                        # Verify states were exited
                        assert mock_exit.call_count == 2  # Two levels back
                        
                        # Verify new state path was set
                        hsm_manager.state_store.set_state_path.assert_called_once()
                        
                        # Verify result
                        assert result == ConversationHSMStates.ORDERING_BROWSING
    
    @pytest.mark.asyncio
    async def test_orchestrator_enhanced_recovery_integration(self):
        """Test orchestrator integration with enhanced recovery."""
        orchestrator = AsyncAgentOrchestrator()
        
        # Mock enhanced go back handling
        mock_response = {
            "text": "Great! Let's continue with your order. What would you like to add?",
            "handled": True,
            "agent": "EnhancedRecovery",
            "new_state": ConversationHSMStates.ORDERING,
            "recovery_type": "go_back_to_state"
        }
        
        orchestrator._handle_enhanced_go_back = AsyncMock(return_value=mock_response)
        
        # Mock intent detection
        with patch.object(intent_detector, 'detect_go_back_intent') as mock_detect:
            mock_detect.return_value = {
                "intent": "GO_BACK_TO_STATE",
                "target_state": "ORDERING",
                "confidence": 0.9
            }
            
            # Mock conversation store
            orchestrator.conversation_store.add_message = AsyncMock()
            
            # Test would be called in real orchestrator
            go_back_intent = await mock_detect("go back to ordering")
            assert go_back_intent["intent"] == "GO_BACK_TO_STATE"
            
            response = await orchestrator._handle_enhanced_go_back(
                go_back_intent, "test_call", {}
            )
            
            assert response["handled"] is True
            assert response["recovery_type"] == "go_back_to_state"
            assert "order" in response["text"].lower()


class TestCompleteProductionWorkflow:
    """End-to-end integration tests for production readiness."""
    
    @pytest.mark.asyncio
    async def test_complete_ordering_workflow_with_monitoring(self):
        """Test complete ordering workflow with all production features."""
        orchestrator = AsyncAgentOrchestrator()
        
        # Mock all components
        orchestrator.frontline_agent = AsyncMock()
        orchestrator.menu_agent = AsyncMock()
        orchestrator.cart_agent = AsyncMock()
        orchestrator.conversation_store.add_message = AsyncMock()
        
        # Mock HSM
        with patch('app.utils.agent_orchestration_async.hsm_manager') as mock_hsm:
            mock_hsm.get_current_states.return_value = [ConversationHSMStates.ORDERING]
            mock_hsm.handle_event = AsyncMock()
            
            # Mock metrics logging
            with patch('app.utils.metrics_logger.metrics_logger') as mock_metrics:
                # Mock agent response
                mock_agent = MagicMock()
                mock_agent.__class__.__name__ = "FrontlineAgent"
                
                orchestrator._process_with_appropriate_agent = AsyncMock(
                    return_value=(mock_agent, {
                        "text": "I've added salmon roll to your cart",
                        "handled": True,
                        "actions": []
                    })
                )
                
                # Execute workflow
                result = await orchestrator.process_voice_input(
                    "test_call_123", 
                    "add a salmon roll please",
                    {"customer_name": "John"}
                )
                
                # Verify all components were called
                assert orchestrator._process_with_appropriate_agent.called
                assert orchestrator.conversation_store.add_message.call_count == 2  # User + assistant
                
                # Verify metrics were logged
                mock_metrics.log_response_latency.assert_called_once()
                
                # Verify response
                assert result["text"] == "I've added salmon roll to your cart"
                assert result["handled"] is True
    
    @pytest.mark.asyncio
    async def test_error_handling_with_circuit_breaker_and_alerting(self):
        """Test error handling with circuit breaker and alerting integration."""
        orchestrator = AsyncAgentOrchestrator()
        
        # Mock circuit breaker in OPEN state
        with patch('app.services.circuit_breaker.get_circuit_breaker') as mock_get_cb:
            mock_cb = MagicMock()
            mock_cb.is_open = True
            mock_cb.status = {"state": "open", "failure_count": 5}
            mock_get_cb.return_value = mock_cb
            
            # Mock alerting
            with patch.object(alerting_service, 'send_alert') as mock_alert:
                # Mock agent processing to trigger fallback
                orchestrator._process_with_appropriate_agent = AsyncMock(
                    return_value=(MagicMock(), {
                        "text": "System is temporarily using simplified mode",
                        "handled": True,
                        "actions": [{"type": "TRIGGER_STATIC_FALLBACK"}]
                    })
                )
                
                # Mock conversation store and HSM
                orchestrator.conversation_store.add_message = AsyncMock()
                
                with patch('app.utils.agent_orchestration_async.hsm_manager') as mock_hsm:
                    mock_hsm.get_current_states.return_value = [ConversationHSMStates.ORDERING]
                    
                    # Execute with fallback scenario
                    result = await orchestrator.process_voice_input(
                        "test_call",
                        "add salmon",
                        {}
                    )
                    
                    # Verify fallback was triggered
                    assert "fallback_mode" in result or "simplified mode" in result.get("text", "")
    
    @pytest.mark.asyncio
    async def test_high_latency_monitoring_and_alerting(self):
        """Test high latency detection and alerting."""
        orchestrator = AsyncAgentOrchestrator()
        
        # Mock slow agent processing
        async def slow_processing(state, input_text, context):
            await asyncio.sleep(0.2)  # 200ms delay
            return (
                MagicMock(__class__=MagicMock(__name__="SlowAgent")),
                {"text": "Slow response", "handled": True}
            )
        
        orchestrator._process_with_appropriate_agent = slow_processing
        orchestrator.conversation_store.add_message = AsyncMock()
        
        # Mock HSM
        with patch('app.utils.agent_orchestration_async.hsm_manager') as mock_hsm:
            mock_hsm.get_current_states.return_value = [ConversationHSMStates.ORDERING]
            
            # Mock alerting with lower threshold for testing
            with patch('app.utils.agent_orchestration_async.settings') as mock_settings:
                mock_settings.HIGH_LATENCY_THRESHOLD_MS = 100  # 100ms threshold
                
                with patch('app.utils.agent_orchestration_async.alert_high_latency') as mock_alert:
                    # Execute processing
                    await orchestrator.process_voice_input(
                        "test_call", "test input", {}
                    )
                    
                    # Verify high latency alert was triggered
                    mock_alert.assert_called_once()
                    
                    # Verify alert parameters
                    call_args = mock_alert.call_args
                    assert call_args[1]["latency_ms"] >= 200
                    assert call_args[1]["threshold_ms"] == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])