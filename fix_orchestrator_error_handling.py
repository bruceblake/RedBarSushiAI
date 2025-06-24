#!/usr/bin/env python3
"""Fix error handling in orchestrator to catch agent processing errors."""

import re
from pathlib import Path

def fix_orchestrator_error_handling():
    """Add error handling to agent processing."""
    orchestrator_file = Path("/home/proxyie/MySoftware/RedBarSushiAI/app/utils/agent_orchestration_async.py")
    
    with open(orchestrator_file, 'r') as f:
        content = f.read()
    
    # Find the line with agent processing and wrap it in try-except
    # Look for the pattern around line 198
    pattern = r'(agent, response = await self\._process_with_appropriate_agent\(fsm, input_text, context\))'
    
    replacement = '''try:
            agent, response = await self._process_with_appropriate_agent(fsm, input_text, context)
        except Exception as e:
            logger.error(f"Agent processing error: {str(e)}", exc_info=True)
            # Transition to ERROR state
            await fsm.trigger(ConversationEvent.ERROR_OCCURRED)
            # Return error response
            return {
                "text": "I'm sorry, I encountered an error processing your request. Please try again or ask for assistance.",
                "handled": True,
                "agent": "ErrorHandler",
                "error": str(e),
                "state": ConversationState.ERROR.name
            }'''
    
    # Replace the line
    content = re.sub(pattern, replacement, content)
    
    with open(orchestrator_file, 'w') as f:
        f.write(content)
    
    print(f"Fixed error handling in {orchestrator_file}")
    return True

if __name__ == "__main__":
    if fix_orchestrator_error_handling():
        print("\nError handling fixed successfully!")
    else:
        print("\nFailed to fix error handling.")