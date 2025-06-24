#!/usr/bin/env python3
"""
Script to fix agent selection tests after commenting out _get_appropriate_agent.
These tests need to be rewritten to test agent selection indirectly.
"""

import re
from pathlib import Path

def fix_agent_selection_tests(file_path):
    """Fix the agent selection tests to work without _get_appropriate_agent."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix 1: Fix the state-based agent selection test
    # This whole test method needs to be rewritten
    old_test = '''    @pytest.mark.asyncio
    async def test_state_based_agent_selection(self, initialized_orchestrator):
        """Test correct agent selection for each state."""
        orchestrator = initialized_orchestrator
        
        # Test state-agent mapping
        state_agent_map = [
            (ConversationState.GREETING, "frontline_agent"),
            (ConversationState.MAIN_MENU, "frontline_agent"),
            (ConversationState.ORDERING, "cart_agent"),
            (ConversationState.VALIDATION, "guardrail_agent"),
            (ConversationState.CONFIRMATION, "frontline_agent"),
            (ConversationState.FULFILLMENT, "fulfillment_agent"),
            (ConversationState.ESCALATION, "escalation_agent"),
        ]
        
        for state, expected_agent in state_agent_map:
            # Mock FSM with specific state
            mock_fsm = AsyncMock()
            mock_fsm.current_state = state
            
            # Create session
            session_id = f"test_{state.name}"
            orchestrator.active_sessions[session_id] = {
                "fsm": mock_fsm,
                "context": {},
                "conversation_history": []
            }
            
            # Get appropriate agent
            context = {"conversation_state": state.name}
            # NOTE: _get_appropriate_agent method doesn't exist
            # The actual orchestrator uses _process_with_appropriate_agent internally
            # This is handled automatically by process_voice_input()
            #             agent = await orchestrator._get_appropriate_agent(state, context)
            # Test agent selection indirectly through process_voice_input
            agent = None  # Agent selection is internal to orchestrator
            
            # Verify correct agent selected
            assert agent is not None
            assert hasattr(orchestrator, expected_agent)'''
    
    new_test = '''    @pytest.mark.asyncio
    async def test_state_based_agent_selection(self, initialized_orchestrator):
        """Test correct agent selection for each state."""
        orchestrator = initialized_orchestrator
        
        # Test state-agent mapping - we'll verify by checking which agent processes the request
        state_agent_map = [
            (ConversationState.GREETING, "frontline_agent", "frontline"),
            (ConversationState.MAIN_MENU, "frontline_agent", "frontline"),
            (ConversationState.ORDERING, "cart_agent", "cart"),
            (ConversationState.VALIDATION, "guardrail_agent", "guardrail"),
            (ConversationState.CONFIRMATION, "frontline_agent", "frontline"),
            (ConversationState.FULFILLMENT, "fulfillment_agent", "fulfillment"),
            (ConversationState.ESCALATION, "escalation_agent", "escalation"),
        ]
        
        for state, expected_agent_attr, expected_agent_name in state_agent_map:
            # Create session and set state
            session_id = f"test_{state.name}"
            await orchestrator.start_new_conversation(session_id, {"test": True})
            
            # Set the FSM state
            session = orchestrator.active_sessions[session_id]
            session["fsm"].current_state = state
            
            # Mock all agents to track which one gets called
            for agent_attr in ["frontline_agent", "menu_agent", "cart_agent", 
                              "guardrail_agent", "fulfillment_agent", "escalation_agent"]:
                if hasattr(orchestrator, agent_attr):
                    agent = getattr(orchestrator, agent_attr)
                    agent.process_voice_input = AsyncMock(return_value={
                        "text": f"Response from {agent_attr}",
                        "agent": agent_attr.replace("_agent", ""),
                        "handled": True
                    })
                    agent.process_input = AsyncMock(return_value={
                        "text": f"Response from {agent_attr}",
                        "agent": agent_attr.replace("_agent", ""),
                        "handled": True
                    })
            
            # Process input and check which agent was used
            with patch('app.utils.agent_orchestration_async.intent_detector') as mock_detector:
                mock_detector.detect_event = AsyncMock(return_value=(ConversationEvent.REQUEST_MENU_INFO, 0.9))
                response = await orchestrator.process_voice_input(session_id, "test input")
            
            # Verify the expected agent was used
            assert response["agent"] == expected_agent_name'''
    
    content = content.replace(old_test, new_test)
    
    # Fix 2: Fix menu query substate test
    old_menu_test = '''    @pytest.mark.asyncio
    async def test_menu_query_substate_handling(self, initialized_orchestrator):
        """Test agent selection for menu query substate."""
        orchestrator = initialized_orchestrator
        
        # Menu query should use menu agent
        context = {"conversation_state": "MENU_QUERY_SUBSTATE"}
            # NOTE: _get_appropriate_agent method doesn't exist
            # The actual orchestrator uses _process_with_appropriate_agent internally
            # This is handled automatically by process_voice_input()
            #         agent = await orchestrator._get_appropriate_agent(
            # Test agent selection indirectly through process_voice_input
            agent = None  # Agent selection is internal to orchestrator
            ConversationState.MENU_QUERY_SUBSTATE, 
            context
        )
        
        assert agent.name == "MenuEnhanced"'''
    
    new_menu_test = '''    @pytest.mark.asyncio
    async def test_menu_query_substate_handling(self, initialized_orchestrator):
        """Test agent selection for menu query substate."""
        orchestrator = initialized_orchestrator
        
        # Create session
        session_id = "test_menu_query"
        await orchestrator.start_new_conversation(session_id, {"test": True})
        
        # Set FSM to MAIN_MENU with menu query context
        session = orchestrator.active_sessions[session_id]
        session["fsm"].current_state = ConversationState.MAIN_MENU
        session["fsm"].context["requesting_menu_info"] = True
        
        # Mock menu agent
        orchestrator.menu_agent.process_input = AsyncMock(return_value={
            "text": "Here are our menu items",
            "agent": "menu",
            "handled": True
        })
        
        # Mock frontline agent (shouldn't be called)
        orchestrator.frontline_agent.process_voice_input = AsyncMock(return_value={
            "text": "Frontline response",
            "agent": "frontline",
            "handled": True
        })
        
        # Process with menu query
        with patch('app.utils.agent_orchestration_async.intent_detector') as mock_detector:
            mock_detector.detect_event = AsyncMock(return_value=(ConversationEvent.REQUEST_MENU_INFO, 0.9))
            response = await orchestrator.process_voice_input(session_id, "What's on the menu?")
        
        # Should use menu agent
        assert response["agent"] == "menu"'''
    
    content = content.replace(old_menu_test, new_menu_test)
    
    # Fix 3: Fix error state fallback test
    old_error_test = '''    @pytest.mark.asyncio
    async def test_error_state_fallback(self, initialized_orchestrator):
        """Test fallback agent for error state."""
        orchestrator = initialized_orchestrator
        
        context = {"conversation_state": "ERROR"}
            # NOTE: _get_appropriate_agent method doesn't exist
            # The actual orchestrator uses _process_with_appropriate_agent internally
            # This is handled automatically by process_voice_input()
            #         agent = await orchestrator._get_appropriate_agent(
            # Test agent selection indirectly through process_voice_input
            agent = None  # Agent selection is internal to orchestrator
            ConversationState.ERROR,
            context
        )
        
        # Should use frontline agent as fallback
        assert agent == orchestrator.frontline_agent'''
    
    new_error_test = '''    @pytest.mark.asyncio
    async def test_error_state_fallback(self, initialized_orchestrator):
        """Test fallback agent for error state."""
        orchestrator = initialized_orchestrator
        
        # Create session  
        session_id = "test_error"
        await orchestrator.start_new_conversation(session_id, {"test": True})
        
        # Set FSM to ERROR state
        session = orchestrator.active_sessions[session_id]
        session["fsm"].current_state = ConversationState.ERROR
        
        # Mock frontline agent (should be used as fallback)
        orchestrator.frontline_agent.process_voice_input = AsyncMock(return_value={
            "text": "Let me help you recover from this error",
            "agent": "frontline",
            "handled": True
        })
        
        # Process in error state
        with patch('app.utils.agent_orchestration_async.intent_detector') as mock_detector:
            mock_detector.detect_event = AsyncMock(return_value=(ConversationEvent.REQUEST_MENU_INFO, 0.9))
            response = await orchestrator.process_voice_input(session_id, "help")
        
        # Should use frontline agent as fallback
        assert response["agent"] == "frontline"'''
    
    content = content.replace(old_error_test, new_error_test)
    
    # Fix 4: Fix the process method calls in frontline_agent
    # The frontline agent has process_voice_input, not process
    content = re.sub(
        r'orchestrator\.frontline_agent\.process\s*=\s*AsyncMock',
        'orchestrator.frontline_agent.process_voice_input = AsyncMock',
        content
    )
    
    # Fix 5: Fix conversation history access
    # The conversation history is likely in the conversation store, not the session
    pattern = r'session\["conversation_history"\]'
    replacement = 'await orchestrator.conversation_store.get_messages(session_id)'
    
    # Only replace in the conversation history test
    lines = content.split('\n')
    in_history_test = False
    new_lines = []
    
    for line in lines:
        if 'def test_conversation_history_tracking' in line:
            in_history_test = True
        elif in_history_test and 'def test_' in line:
            in_history_test = False
        
        if in_history_test and 'session["conversation_history"]' in line:
            # Replace with conversation store access
            line = line.replace('session["conversation_history"]', 
                               'await orchestrator.conversation_store.get_messages(session_id)')
        
        new_lines.append(line)
    
    content = '\n'.join(new_lines)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"Fixed agent selection tests in {file_path}")
    return True

def main():
    """Fix agent selection tests."""
    test_file = Path("/home/proxyie/MySoftware/RedBarSushiAI/tests/integration/test_agent_orchestration_comprehensive.py")
    
    if fix_agent_selection_tests(test_file):
        print("\nAgent selection tests updated successfully!")
    else:
        print("\nNo changes needed.")

if __name__ == "__main__":
    main()