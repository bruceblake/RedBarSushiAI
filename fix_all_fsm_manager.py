#!/usr/bin/env python3
"""Fix all fsm_manager references in tests."""

import re
from pathlib import Path

def fix_all_fsm_manager():
    """Fix all fsm_manager references."""
    test_file = Path("/home/proxyie/MySoftware/RedBarSushiAI/tests/integration/test_agent_orchestration_comprehensive.py")
    
    with open(test_file, 'r') as f:
        content = f.read()
    
    # Replace all orchestrator.fsm_manager with async_fsm_manager
    content = re.sub(r'orchestrator\.fsm_manager\.', 'async_fsm_manager.', content)
    
    # Add import at the top of TestGlobalCommands class if not already there
    content = re.sub(
        r'(class TestGlobalCommands:.*?\n.*?\n.*?\n.*?async def orchestrator_with_commands\(self\):)',
        r'\1\n        from app.fsm.core import async_fsm_manager',
        content,
        flags=re.DOTALL
    )
    
    # Add import at the top of other test methods that use it
    content = re.sub(
        r'(# Get FSM from manager\s*\n\s*)fsm = await async_fsm_manager',
        r'\1from app.fsm.core import async_fsm_manager\n        fsm = await async_fsm_manager',
        content
    )
    
    # Add import for test_error_recovery_flow
    content = re.sub(
        r'(# Set up error state\s*\n\s*session = orchestrator\.active_sessions\[session_id\]\s*\n\s*# Get FSM from manager\s*\n\s*)from app\.fsm\.core import async_fsm_manager',
        r'\1from app.fsm.core import async_fsm_manager',
        content
    )
    
    # Add import for test_rapid_state_changes
    content = re.sub(
        r'(# Verify FSM handled all transitions\s*\n\s*session = orchestrator\.active_sessions\[session_id\]\s*\n\s*)fsm = await async_fsm_manager',
        r'\1from app.fsm.core import async_fsm_manager\n        fsm = await async_fsm_manager',
        content
    )
    
    with open(test_file, 'w') as f:
        f.write(content)
    
    print(f"Fixed all fsm_manager references in {test_file}")
    return True

if __name__ == "__main__":
    if fix_all_fsm_manager():
        print("\nAll fsm_manager references fixed successfully!")
    else:
        print("\nFailed to fix fsm_manager references.")