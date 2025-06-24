#!/usr/bin/env python3
"""Add debug output to error test."""

import re
from pathlib import Path

def fix_error_test():
    """Add debug output to error test."""
    test_file = Path("/home/proxyie/MySoftware/RedBarSushiAI/tests/integration/test_agent_orchestration_comprehensive.py")
    
    with open(test_file, 'r') as f:
        content = f.read()
    
    # Find and update the test_agent_process_error
    pattern = r'(response = await orchestrator\.process_voice_input\(session_id, "Show menu"\)\s*\n\s*\n\s*# Should handle error gracefully)'
    
    replacement = '''response = await orchestrator.process_voice_input(session_id, "Show menu")
        
        # Debug output
        print(f"\\nDEBUG: Response = {response}")
        print(f"DEBUG: 'error' in response = {'error' in response}")
        print(f"DEBUG: response.get('text') = {response.get('text')}")
        print(f"DEBUG: 'Error' in response['text'] = {'Error' in response.get('text', '')}")
        
        # Should handle error gracefully'''
    
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    with open(test_file, 'w') as f:
        f.write(content)
    
    print(f"Added debug output to {test_file}")
    return True

if __name__ == "__main__":
    if fix_error_test():
        print("\nDebug output added successfully!")
    else:
        print("\nFailed to add debug output.")