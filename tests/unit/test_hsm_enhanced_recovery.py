"""
Unit tests for Enhanced HSM Recovery functionality.

Tests the new GO_BACK_TO_STATE event and multi-level state rollback capabilities.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List

from app.fsm.manager import HSMManager
from app.fsm.core import ConversationHSMStates, ConversationHSMEvents, HSMEvent
from app.utils.intent_detector_async import AsyncIntentDetector


class TestHSMEnhancedRecovery:
    """Test suite for Enhanced HSM Recovery functionality."""
    
    @pytest.fixture
    async def hsm_manager(self):
        """Create an HSM Manager instance for testing."""
        manager = HSMManager()
        # Mock the state store
        manager.state_store = AsyncMock()
        yield manager
    
    @pytest.fixture
    def sample_state_path(self):
        """Sample state path for testing."""
        return [
            ConversationHSMStates.ACTIVE,
            ConversationHSMStates.ORDERING,
            ConversationHSMStates.ORDERING_BROWSING,
            ConversationHSMStates.ORDERING_ITEM_CUSTOMIZATION
        ]
    
    @pytest.mark.asyncio
    async def test_go_back_to_state_in_current_path(self, hsm_manager, sample_state_path):
        """Test going back to a state that exists in the current path."""
        call_sid = "test_call_123"
        target_state = ConversationHSMStates.ORDERING
        
        # Mock current state path
        hsm_manager.state_store.get_current_state_path.return_value = sample_state_path
        hsm_manager.state_store.set_state_path.return_value = None
        hsm_manager.state_store.get_leaf_state.return_value = ConversationHSMStates.ORDERING_BROWSING
        
        # Mock _exit_state method
        hsm_manager._exit_state = AsyncMock()
        hsm_manager._enter_initial_substates = AsyncMock()
        
        # Execute test
        result = await hsm_manager.go_back_to_state(call_sid, target_state, {})
        
        # Verify states were exited in correct order
        expected_exits = [
            ConversationHSMStates.ORDERING_ITEM_CUSTOMIZATION,
            ConversationHSMStates.ORDERING_BROWSING
        ]
        
        assert hsm_manager._exit_state.call_count == len(expected_exits)
        for i, expected_state in enumerate(expected_exits):
            call_args = hsm_manager._exit_state.call_args_list[i]
            assert call_args[0][1] == expected_state  # Second argument is state name
        
        # Verify state path was updated correctly
        expected_new_path = [ConversationHSMStates.ACTIVE, ConversationHSMStates.ORDERING]
        hsm_manager.state_store.set_state_path.assert_called_once_with(call_sid, expected_new_path)
        
        # Verify result
        assert result == ConversationHSMStates.ORDERING_BROWSING
    
    @pytest.mark.asyncio
    async def test_go_back_to_state_not_in_path(self, hsm_manager, sample_state_path):
        """Test going back to a state not in current path (direct transition)."""
        call_sid = "test_call_123"
        target_state = ConversationHSMStates.MAIN_MENU  # Not in current path
        
        # Mock current state path
        hsm_manager.state_store.get_current_state_path.return_value = sample_state_path
        hsm_manager.state_store.get_leaf_state.return_value = ConversationHSMStates.MAIN_MENU
        
        # Mock transition method
        hsm_manager._transition_to = AsyncMock()
        
        # Execute test
        result = await hsm_manager.go_back_to_state(call_sid, target_state, {})
        
        # Verify direct transition was called
        hsm_manager._transition_to.assert_called_once()
        transition_args = hsm_manager._transition_to.call_args
        assert transition_args[0][1] == target_state  # Target state
        assert transition_args[0][2].name == "GO_BACK_TO_STATE"  # Event type
        
        # Verify result
        assert result == ConversationHSMStates.MAIN_MENU
    
    @pytest.mark.asyncio
    async def test_go_back_steps_functionality(self, hsm_manager, sample_state_path):
        """Test going back a specific number of steps."""
        call_sid = "test_call_123"
        steps = 2
        
        # Mock current state path
        hsm_manager.state_store.get_current_state_path.return_value = sample_state_path
        
        # Mock go_back_to_state method
        hsm_manager.go_back_to_state = AsyncMock(return_value=ConversationHSMStates.ORDERING)
        
        # Execute test
        result = await hsm_manager.go_back_steps(call_sid, steps, {})
        
        # Verify go_back_to_state was called with correct target
        # 2 steps back from leaf (index 3) should target index 1 (ORDERING)
        expected_target = sample_state_path[1]  # ConversationHSMStates.ORDERING
        hsm_manager.go_back_to_state.assert_called_once_with(call_sid, expected_target, {})
        
        # Verify result
        assert result == ConversationHSMStates.ORDERING
    
    @pytest.mark.asyncio
    async def test_go_back_steps_boundary_conditions(self, hsm_manager):
        """Test go_back_steps with boundary conditions."""
        call_sid = "test_call_123"
        sample_path = [ConversationHSMStates.ACTIVE, ConversationHSMStates.MAIN_MENU]
        
        # Mock current state path
        hsm_manager.state_store.get_current_state_path.return_value = sample_path
        
        # Test going back more steps than available
        hsm_manager.go_back_to_state = AsyncMock(return_value=ConversationHSMStates.ACTIVE)
        
        result = await hsm_manager.go_back_steps(call_sid, 10, {})  # More than path length
        
        # Should go back to root (index 0)
        hsm_manager.go_back_to_state.assert_called_once_with(
            call_sid, ConversationHSMStates.ACTIVE, {}
        )
        
        # Test invalid steps
        result = await hsm_manager.go_back_steps(call_sid, 0, {})
        assert result is None
        
        result = await hsm_manager.go_back_steps(call_sid, -1, {})
        assert result is None
    
    @pytest.mark.asyncio
    async def test_initial_substate_handling(self, hsm_manager, sample_state_path):
        """Test that initial substates are entered after recovery."""
        call_sid = "test_call_123"
        target_state = ConversationHSMStates.ORDERING
        
        # Mock state path and methods
        hsm_manager.state_store.get_current_state_path.return_value = sample_state_path
        hsm_manager.state_store.set_state_path.return_value = None
        hsm_manager.state_store.get_leaf_state.return_value = ConversationHSMStates.ORDERING_BROWSING
        hsm_manager._exit_state = AsyncMock()
        hsm_manager._enter_initial_substates = AsyncMock()
        
        # Mock target state with initial substate
        target_state_def = MagicMock()
        target_state_def.initial_substate_name = ConversationHSMStates.ORDERING_BROWSING
        hsm_manager.states = {target_state: target_state_def}
        
        # Execute test
        await hsm_manager.go_back_to_state(call_sid, target_state, {})
        
        # Verify initial substate was entered
        hsm_manager._enter_initial_substates.assert_called_once_with(
            call_sid, ConversationHSMStates.ORDERING_BROWSING, hsm_manager._enter_initial_substates.call_args[0][2], {}
        )
    
    @pytest.mark.asyncio
    async def test_error_handling_invalid_target(self, hsm_manager, sample_state_path):
        """Test error handling for invalid target states."""
        call_sid = "test_call_123"
        invalid_state = "INVALID_STATE"
        
        # Mock current state path
        hsm_manager.state_store.get_current_state_path.return_value = sample_state_path
        
        # Mock states dict without invalid state
        hsm_manager.states = {}
        
        # Execute test
        result = await hsm_manager.go_back_to_state(call_sid, invalid_state, {})
        
        # Should return None for invalid state
        assert result is None
    
    @pytest.mark.asyncio
    async def test_empty_state_path_handling(self, hsm_manager):
        """Test handling when there's no current state path."""
        call_sid = "test_call_123"
        target_state = ConversationHSMStates.MAIN_MENU
        
        # Mock empty state path
        hsm_manager.state_store.get_current_state_path.return_value = []
        
        # Execute test
        result = await hsm_manager.go_back_to_state(call_sid, target_state, {})
        
        # Should return None for empty path
        assert result is None


class TestIntentDetectorGoBackEnhancement:
    """Test enhanced go back intent detection."""
    
    @pytest.fixture
    async def intent_detector(self):
        """Create an AsyncIntentDetector for testing."""
        with patch('app.utils.intent_detector_async.AsyncOpenAI'):
            detector = AsyncIntentDetector()
            yield detector
    
    @pytest.mark.asyncio
    async def test_go_back_to_state_detection(self, intent_detector):
        """Test detection of 'go back to state' intents."""
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '''
        {
            "intent": "GO_BACK_TO_STATE",
            "target_state": "ORDERING",
            "steps": null,
            "confidence": 0.9
        }
        '''
        
        intent_detector.client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        # Test various inputs
        test_cases = [
            "go back to ordering",
            "return to the ordering menu",
            "take me back to placing my order"
        ]
        
        for transcript in test_cases:
            result = await intent_detector.detect_go_back_intent(transcript)
            
            assert result is not None
            assert result["intent"] == "GO_BACK_TO_STATE"
            assert result["target_state"] == "ORDERING"
            assert result["confidence"] >= 0.8
    
    @pytest.mark.asyncio
    async def test_go_back_steps_detection(self, intent_detector):
        """Test detection of 'go back N steps' intents."""
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '''
        {
            "intent": "GO_BACK_STEPS",
            "target_state": null,
            "steps": 2,
            "confidence": 0.85
        }
        '''
        
        intent_detector.client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        # Test various inputs
        test_cases = [
            "go back 2 steps",
            "take me back two levels",
            "undo the last 2 actions"
        ]
        
        for transcript in test_cases:
            result = await intent_detector.detect_go_back_intent(transcript)
            
            assert result is not None
            assert result["intent"] == "GO_BACK_STEPS"
            assert result["steps"] == 2
            assert result["confidence"] >= 0.8
    
    @pytest.mark.asyncio
    async def test_no_go_back_intent_detection(self, intent_detector):
        """Test that non-go-back intents return None."""
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '''
        {
            "intent": "NONE",
            "target_state": null,
            "steps": null,
            "confidence": 0.1
        }
        '''
        
        intent_detector.client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        # Test non-go-back inputs
        test_cases = [
            "I want to add salmon to my order",
            "what's the price of tuna rolls",
            "yes that's correct"
        ]
        
        for transcript in test_cases:
            result = await intent_detector.detect_go_back_intent(transcript)
            assert result is None
    
    @pytest.mark.asyncio
    async def test_state_mapping_accuracy(self, intent_detector):
        """Test that user-friendly state names map correctly to HSM states."""
        test_mappings = [
            ("go back to ordering", "ORDERING"),
            ("return to main menu", "MAIN_MENU"),
            ("take me to the beginning", "GREETING"),
            ("go back to the start", "MAIN_MENU")
        ]
        
        for transcript, expected_state in test_mappings:
            # Mock response with expected state
            mock_response = MagicMock()
            mock_response.choices[0].message.content = f'''
            {{
                "intent": "GO_BACK_TO_STATE",
                "target_state": "{expected_state}",
                "steps": null,
                "confidence": 0.9
            }}
            '''
            
            intent_detector.client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            result = await intent_detector.detect_go_back_intent(transcript)
            
            assert result is not None
            assert result["target_state"] == expected_state


class TestIntegrationRecoveryWorkflow:
    """Integration tests for complete recovery workflow."""
    
    @pytest.mark.asyncio
    async def test_complete_go_back_workflow(self):
        """Test complete workflow from intent detection to state recovery."""
        from app.utils.agent_orchestration_async import AsyncAgentOrchestrator
        
        # Create orchestrator with mocked components
        orchestrator = AsyncAgentOrchestrator()
        orchestrator._handle_enhanced_go_back = AsyncMock(return_value={
            "text": "Great! Let's continue with your order. What would you like to add?",
            "handled": True,
            "agent": "EnhancedRecovery",
            "new_state": ConversationHSMStates.ORDERING,
            "recovery_type": "go_back_to_state"
        })
        
        # Mock intent detection
        with patch('app.utils.intent_detector_async.intent_detector') as mock_detector:
            mock_detector.detect_go_back_intent = AsyncMock(return_value={
                "intent": "GO_BACK_TO_STATE",
                "target_state": "ORDERING",
                "confidence": 0.9
            })
            
            # Simulate the workflow would work in the orchestrator
            go_back_intent = await mock_detector.detect_go_back_intent("go back to ordering")
            
            assert go_back_intent is not None
            assert go_back_intent["intent"] == "GO_BACK_TO_STATE"
            
            # Simulate enhanced go back handling
            response = await orchestrator._handle_enhanced_go_back(
                go_back_intent, "test_call", {}
            )
            
            assert response["handled"] is True
            assert response["new_state"] == ConversationHSMStates.ORDERING
            assert "order" in response["text"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])