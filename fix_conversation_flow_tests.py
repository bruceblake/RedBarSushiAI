#!/usr/bin/env python3
"""Fix conversation flow tests to match actual implementation."""

import re
from pathlib import Path

def fix_conversation_flow_tests():
    """Fix the conversation flow tests."""
    test_file = Path("/home/proxyie/MySoftware/RedBarSushiAI/tests/integration/test_agent_orchestration_comprehensive.py")
    
    with open(test_file, 'r') as f:
        content = f.read()
    
    # The orchestrator returns FSM state in the response, not in session["fsm"]
    # Fix the test_complete_order_flow to check response["state"] instead of session["fsm"].current_state
    content = re.sub(
        r'# Verify FSM state\s*\n\s*session = orchestrator\.active_sessions\[session_id\]\s*\n\s*assert session\["fsm"\]\.current_state == expected_state',
        '''# Verify FSM state
            assert response.get("state") == expected_state.name''',
        content,
        flags=re.MULTILINE
    )
    
    # Fix test_error_recovery_flow - Get FSM from fsm_manager
    content = re.sub(
        r'session\["fsm"\]\.current_state = ConversationState\.ERROR\s*\n\s*session\["fsm"\]\.previous_state = ConversationState\.ORDERING',
        '''# Get FSM from manager
        fsm = await orchestrator.fsm_manager.get_fsm(session_id)
        fsm.current_state = ConversationState.ERROR
        fsm.previous_state = ConversationState.ORDERING
        await orchestrator.fsm_manager.save_fsm(session_id, fsm)''',
        content
    )
    
    # Fix the recovery check
    content = re.sub(
        r'# Should recover to previous state\s*\n\s*assert session\["fsm"\]\.current_state == ConversationState\.ORDERING',
        '''# Should recover to previous state
        fsm = await orchestrator.fsm_manager.get_fsm(session_id)
        assert fsm.current_state == ConversationState.ORDERING''',
        content
    )
    
    # Fix test_cancellation_flow
    content = re.sub(
        r'session\["fsm"\]\.current_state = ConversationState\.ORDERING',
        '''# Get and update FSM state
        fsm = await orchestrator.fsm_manager.get_fsm(session_id)
        fsm.current_state = ConversationState.ORDERING
        await orchestrator.fsm_manager.save_fsm(session_id, fsm)''',
        content
    )
    
    # Fix cancellation state checks
    content = re.sub(
        r'# Should enter cancellation pending\s*\n\s*assert session\["fsm"\]\.current_state == ConversationState\.CANCELLATION_PENDING',
        '''# Should enter cancellation pending
        fsm = await orchestrator.fsm_manager.get_fsm(session_id)
        assert fsm.current_state == ConversationState.CANCELLATION_PENDING''',
        content
    )
    
    content = re.sub(
        r'# Should return to ordering\s*\n\s*assert session\["fsm"\]\.current_state == ConversationState\.ORDERING',
        '''# Should return to ordering
        fsm = await orchestrator.fsm_manager.get_fsm(session_id)
        assert fsm.current_state == ConversationState.ORDERING''',
        content
    )
    
    # Fix cart synchronization test
    content = re.sub(
        r'session\["fsm"\]\.current_state = ConversationState\.ORDERING',
        '''# Set FSM state
        fsm = await orchestrator.fsm_manager.get_fsm(session_id)
        fsm.current_state = ConversationState.ORDERING
        await orchestrator.fsm_manager.save_fsm(session_id, fsm)''',
        content
    )
    
    # Fix global commands tests
    content = re.sub(
        r'session\["fsm"\]\.current_state = ConversationState\.ORDERING',
        '''# Set FSM state
        fsm = await orchestrator.fsm_manager.get_fsm(session_id)
        fsm.current_state = ConversationState.ORDERING
        await orchestrator.fsm_manager.save_fsm(session_id, fsm)''',
        content
    )
    
    content = re.sub(
        r'session\["fsm"\]\.previous_state = ConversationState\.MAIN_MENU',
        '''# Set previous state
        fsm = await orchestrator.fsm_manager.get_fsm(session_id)
        fsm.previous_state = ConversationState.MAIN_MENU
        await orchestrator.fsm_manager.save_fsm(session_id, fsm)''',
        content
    )
    
    # Fix state assertions in global commands
    content = re.sub(
        r'assert session\["fsm"\]\.current_state == ConversationState\.GREETING',
        '''fsm = await orchestrator.fsm_manager.get_fsm(session_id)
            assert fsm.current_state == ConversationState.GREETING''',
        content
    )
    
    content = re.sub(
        r'assert session\["fsm"\]\.current_state == ConversationState\.MAIN_MENU',
        '''fsm = await orchestrator.fsm_manager.get_fsm(session_id)
            assert fsm.current_state == ConversationState.MAIN_MENU''',
        content
    )
    
    # Fix error handling tests
    content = re.sub(
        r'assert session\["fsm"\]\.current_state == ConversationState\.ERROR',
        '''fsm = await orchestrator.fsm_manager.get_fsm(session_id)
        assert fsm.current_state == ConversationState.ERROR''',
        content
    )
    
    # Fix test_multiple_concurrent_sessions
    content = re.sub(
        r'orchestrator\.active_sessions\[sid\] = \{"fsm": await orchestrator\.get_fsm\(sid\), "context": \{\}\}',
        '''# Initialize session properly
            await orchestrator.start_new_conversation(sid, {"test": True})''',
        content
    )
    
    # Fix cleanup test
    content = re.sub(
        r'orchestrator\.active_sessions\[active_sid\] = \{"fsm": await orchestrator\.get_fsm\(active_sid\), "context": \{\}\}\s*\n\s*orchestrator\.active_sessions\[inactive_sid\] = \{"fsm": await orchestrator\.get_fsm\(inactive_sid\), "context": \{\}\}',
        '''# Initialize sessions properly
        await orchestrator.start_new_conversation(active_sid, {"test": True})
        await orchestrator.start_new_conversation(inactive_sid, {"test": True})''',
        content
    )
    
    # Fix rapid state changes test
    content = re.sub(
        r'assert session\["fsm"\]\.current_state in \[\s*ConversationState\.VALIDATION,\s*ConversationState\.CONFIRMATION\s*\]',
        '''fsm = await orchestrator.fsm_manager.get_fsm(session_id)
        assert fsm.current_state in [
            ConversationState.VALIDATION,
            ConversationState.CONFIRMATION
        ]''',
        content
    )
    
    # Fix missing context data test
    content = re.sub(
        r'session\["fsm"\]\.current_state = ConversationState\.ORDERING',
        '''# Set FSM state
        fsm = await orchestrator.fsm_manager.get_fsm(session_id)
        fsm.current_state = ConversationState.ORDERING
        await orchestrator.fsm_manager.save_fsm(session_id, fsm)''',
        content
    )
    
    with open(test_file, 'w') as f:
        f.write(content)
    
    print(f"Fixed conversation flow tests in {test_file}")
    return True

if __name__ == "__main__":
    if fix_conversation_flow_tests():
        print("\nConversation flow tests fixed successfully!")
    else:
        print("\nFailed to fix conversation flow tests.")