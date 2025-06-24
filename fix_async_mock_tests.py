#!/usr/bin/env python3
"""
Fix the async mock issues in the tests.
"""

import re
from pathlib import Path

def fix_tests(file_path):
    """Fix the async mock issues."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix the menu test
    old_menu_test = """    @pytest.mark.asyncio
    async def test_menu_agent_for_menu_queries(self, initialized_orchestrator):
        \"\"\"Test that menu queries use the menu agent.\"\"\"
        orchestrator = initialized_orchestrator
        
        # Start conversation
        session_id = "test_menu"
        await orchestrator.start_new_conversation(session_id, {"test": True})
        
        # Mock the frontline agent to delegate to menu agent
        async def mock_process(transcript, context):
            # Simulate frontline agent delegating to menu agent
            if "menu" in transcript.lower():
                return {
                    "text": "Let me show you our menu. We have delicious sushi rolls...",
                    "agent": "FrontlineVoiceAI",
                    "handled": True,
                    "delegated_to": "menu"
                }
            return {
                "text": "How can I help you?",
                "agent": "FrontlineVoiceAI", 
                "handled": True
            }
        
        orchestrator.frontline_agent.process_voice_input = mock_process
        
        # Ask about menu
        response = await orchestrator.process_voice_input(session_id, "What's on your menu?")
        
        # Verify menu-related response
        assert response is not None
        assert "menu" in response.get("text", "").lower() or response.get("delegated_to") == "menu\""""
    
    new_menu_test = """    @pytest.mark.asyncio
    async def test_menu_agent_for_menu_queries(self, initialized_orchestrator):
        \"\"\"Test that menu queries use the menu agent.\"\"\"
        orchestrator = initialized_orchestrator
        
        # Start conversation
        session_id = "test_menu"
        await orchestrator.start_new_conversation(session_id, {"test": True})
        
        # Mock the frontline agent to delegate to menu agent
        orchestrator.frontline_agent.process_voice_input = AsyncMock(return_value={
            "text": "Let me show you our menu. We have delicious sushi rolls...",
            "agent": "FrontlineVoiceAI",
            "handled": True,
            "delegated_to": "menu"
        })
        
        # Ask about menu
        response = await orchestrator.process_voice_input(session_id, "What's on your menu?")
        
        # Verify menu-related response
        assert response is not None
        assert "menu" in response.get("text", "").lower() or response.get("delegated_to") == "menu\""""
    
    content = content.replace(old_menu_test, new_menu_test)
    
    # Fix the cart test
    old_cart_test = """    @pytest.mark.asyncio
    async def test_cart_agent_for_ordering(self, initialized_orchestrator):
        \"\"\"Test that ordering uses cart agent.\"\"\"
        orchestrator = initialized_orchestrator
        
        # Start conversation
        session_id = "test_ordering"
        await orchestrator.start_new_conversation(session_id, {"test": True})
        
        # Create a sequence of mocked responses for the conversation flow
        response_sequence = [
            # Response to name
            {
                "text": "Nice to meet you, John! How can I help you today?",
                "agent": "FrontlineVoiceAI",
                "handled": True,
                "state": "MAIN_MENU"
            },
            # Response to order request
            {
                "text": "Great! I'll help you place an order. What would you like?",
                "agent": "FrontlineVoiceAI",
                "handled": True,
                "state": "ORDERING"
            },
            # Response to adding item (delegated to cart)
            {
                "text": "I've added 1 tuna roll to your cart. Would you like anything else?",
                "agent": "FrontlineVoiceAI",
                "handled": True,
                "delegated_to": "cart",
                "actions": [{"type": "cart_updated", "items": [{"name": "Tuna Roll", "quantity": 1}]}]
            }
        ]
        
        call_count = 0
        async def mock_process(transcript, context):
            nonlocal call_count
            response = response_sequence[call_count] if call_count < len(response_sequence) else {
                "text": "I can help with that.",
                "agent": "FrontlineVoiceAI",
                "handled": True
            }
            call_count += 1
            return response
        
        orchestrator.frontline_agent.process_voice_input = mock_process
        
        # Provide name
        await orchestrator.process_voice_input(session_id, "My name is John")
        
        # Start ordering
        await orchestrator.process_voice_input(session_id, "I want to order")
        
        # Add item
        response = await orchestrator.process_voice_input(session_id, "Add one tuna roll")
        
        # Verify cart involvement
        assert response is not None
        assert response.get("delegated_to") == "cart" or any(
            action.get("type") == "cart_updated" for action in response.get("actions", [])
        )\""""
    
    new_cart_test = """    @pytest.mark.asyncio
    async def test_cart_agent_for_ordering(self, initialized_orchestrator):
        \"\"\"Test that ordering uses cart agent.\"\"\"
        orchestrator = initialized_orchestrator
        
        # Start conversation
        session_id = "test_ordering"
        await orchestrator.start_new_conversation(session_id, {"test": True})
        
        # Create a single mock that returns different responses based on the input
        async def mock_process(transcript, context):
            if "john" in transcript.lower():
                return {
                    "text": "Nice to meet you, John! How can I help you today?",
                    "agent": "FrontlineVoiceAI",
                    "handled": True,
                    "state": "MAIN_MENU"
                }
            elif "order" in transcript.lower():
                return {
                    "text": "Great! I'll help you place an order. What would you like?",
                    "agent": "FrontlineVoiceAI",
                    "handled": True,
                    "state": "ORDERING"
                }
            elif "tuna" in transcript.lower():
                return {
                    "text": "I've added 1 tuna roll to your cart. Would you like anything else?",
                    "agent": "FrontlineVoiceAI",
                    "handled": True,
                    "delegated_to": "cart",
                    "actions": [{"type": "cart_updated", "items": [{"name": "Tuna Roll", "quantity": 1}]}]
                }
            return {
                "text": "I can help with that.",
                "agent": "FrontlineVoiceAI",
                "handled": True
            }
        
        # Use AsyncMock with side_effect
        orchestrator.frontline_agent.process_voice_input = AsyncMock(side_effect=mock_process)
        
        # Provide name
        await orchestrator.process_voice_input(session_id, "My name is John")
        
        # Start ordering
        await orchestrator.process_voice_input(session_id, "I want to order")
        
        # Add item
        response = await orchestrator.process_voice_input(session_id, "Add one tuna roll")
        
        # Verify cart involvement
        assert response is not None
        assert response.get("delegated_to") == "cart" or any(
            action.get("type") == "cart_updated" for action in response.get("actions", [])
        )\""""
    
    content = content.replace(old_cart_test, new_cart_test)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"Fixed async mock issues in {file_path}")
    return True

def main():
    """Fix the tests."""
    test_file = Path("/home/proxyie/MySoftware/RedBarSushiAI/tests/integration/test_agent_orchestration_comprehensive.py")
    
    if fix_tests(test_file):
        print("\nAsync mock issues fixed successfully!")
    else:
        print("\nNo changes needed.")

if __name__ == "__main__":
    main()