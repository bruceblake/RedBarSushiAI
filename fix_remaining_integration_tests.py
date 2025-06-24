#!/usr/bin/env python3
"""
Fix remaining integration tests.
"""

import re
from pathlib import Path

def fix_tests(file_path):
    """Fix the remaining integration tests."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix the test_session fixture
    old_fixture = """    @pytest_asyncio.fixture
    async def test_session(self):
        \"\"\"Create test session with orchestrator.\"\"\"
        orchestrator = AsyncAgentOrchestrator()
        mock_db = AsyncMock(spec=AsyncSession)
        await orchestrator.initialize(db=mock_db)
        
        # Mock intent detector
        with patch('app.utils.agent_orchestration_async.async_intent_detector') as mock_detector:
            mock_detector.detect_intent = AsyncMock()
            
            # Create session
            session_id = "test_session"
            # Initialize session through start_new_conversation
            await orchestrator.start_new_conversation(session_id, {"test": True})
            
            yield orchestrator, session_id, mock_detector"""
    
    new_fixture = """    @pytest_asyncio.fixture
    async def test_session(self):
        \"\"\"Create test session with orchestrator.\"\"\"
        orchestrator = AsyncAgentOrchestrator()
        mock_db = AsyncMock(spec=AsyncSession)
        await orchestrator.initialize(db=mock_db)
        
        # Create session
        session_id = "test_session"
        # Initialize session through start_new_conversation
        await orchestrator.start_new_conversation(session_id, {"test": True})
        
        yield orchestrator, session_id"""
    
    content = content.replace(old_fixture, new_fixture)
    
    # Fix test_complete_order_flow to not use mock_intent
    old_test = """    @pytest.mark.asyncio
    async def test_complete_order_flow(self, test_session):
        \"\"\"Test complete order flow from greeting to completion.\"\"\"
        orchestrator, session_id, mock_intent = test_session"""
    
    new_test = """    @pytest.mark.asyncio
    async def test_complete_order_flow(self, test_session):
        \"\"\"Test complete order flow from greeting to completion.\"\"\"
        orchestrator, session_id = test_session"""
    
    content = content.replace(old_test, new_test)
    
    # Remove all references to mock_intent in TestConversationFlow
    content = re.sub(r'mock_intent\.detect_intent\.return_value = expected_event\n\s+', '', content)
    content = re.sub(r'mock_intent\.detect_intent\.return_value = ConversationEvent\.\w+\n\s+', '', content)
    
    # Fix test_error_recovery_flow
    old_recovery = """    @pytest.mark.asyncio
    async def test_error_recovery_flow(self, test_session):
        \"\"\"Test error recovery flow.\"\"\"
        orchestrator, session_id, mock_intent = test_session"""
    
    new_recovery = """    @pytest.mark.asyncio
    async def test_error_recovery_flow(self, test_session):
        \"\"\"Test error recovery flow.\"\"\"
        orchestrator, session_id = test_session"""
    
    content = content.replace(old_recovery, new_recovery)
    
    # Fix test_cancellation_flow
    old_cancel = """    @pytest.mark.asyncio
    async def test_cancellation_flow(self, test_session):
        \"\"\"Test order cancellation flow.\"\"\"
        orchestrator, session_id, mock_intent = test_session"""
    
    new_cancel = """    @pytest.mark.asyncio
    async def test_cancellation_flow(self, test_session):
        \"\"\"Test order cancellation flow.\"\"\"
        orchestrator, session_id = test_session"""
    
    content = content.replace(old_cancel, new_cancel)
    
    # Remove patch decorators that conflict with fixtures
    content = re.sub(r'with patch\(\'app\.utils\.agent_orchestration_async\.async_intent_detector\'\) as mock_detector:\n\s+mock_detector\.detect_intent = AsyncMock\(.*?\)\n', '', content, flags=re.DOTALL)
    
    # Simplify test_context_preservation
    old_context_test = """        # Process input
        with patch('app.utils.agent_orchestration_async.async_intent_detector') as mock_detector:
            mock_detector.detect_intent = AsyncMock(return_value=ConversationEvent.REQUEST_MENU_INFO)
            await orchestrator.process_voice_input(session_id, "Show menu")"""
    
    new_context_test = """        # Process input
        await orchestrator.process_voice_input(session_id, "Show menu")"""
    
    content = content.replace(old_context_test, new_context_test)
    
    # Fix test_cart_synchronization
    old_cart_sync = """        with patch('app.utils.agent_orchestration_async.async_intent_detector') as mock_detector:
            mock_detector.detect_intent = AsyncMock(return_value=ConversationEvent.ADD_ITEM)
            response = await orchestrator.process_voice_input(session_id, "Add tuna roll")"""
    
    new_cart_sync = """        response = await orchestrator.process_voice_input(session_id, "Add tuna roll")"""
    
    content = content.replace(old_cart_sync, new_cart_sync)
    
    # Fix test_conversation_history_tracking
    old_history = """        with patch('app.utils.agent_orchestration_async.async_intent_detector') as mock_detector:
            mock_detector.detect_intent = AsyncMock(return_value=ConversationEvent.REQUEST_MENU_INFO)
            
            for user_input in inputs:
                orchestrator.frontline_agent.process_voice_input = AsyncMock(return_value={
                    "text": f"Response to: {user_input}",
                    "agent": "frontline",
                    "handled": True
                })
                
                await orchestrator.process_voice_input(session_id, user_input)"""
    
    new_history = """        for user_input in inputs:
            orchestrator.frontline_agent.process_voice_input = AsyncMock(return_value={
                "text": f"Response to: {user_input}",
                "agent": "frontline",
                "handled": True
            })
            
            await orchestrator.process_voice_input(session_id, user_input)"""
    
    content = content.replace(old_history, new_history)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"Fixed remaining integration tests in {file_path}")
    return True

def main():
    """Fix the tests."""
    test_file = Path("/home/proxyie/MySoftware/RedBarSushiAI/tests/integration/test_agent_orchestration_comprehensive.py")
    
    if fix_tests(test_file):
        print("\nRemaining integration tests fixed successfully!")
    else:
        print("\nNo changes needed.")

if __name__ == "__main__":
    main()