#!/usr/bin/env python3
"""Fix syntax errors in comprehensive test file."""

import re
from pathlib import Path

def fix_syntax_errors():
    """Fix all syntax errors."""
    test_file = Path("/home/proxyie/MySoftware/RedBarSushiAI/tests/integration/test_agent_orchestration_comprehensive.py")
    
    with open(test_file, 'r') as f:
        content = f.read()
    
    # Fix missing parenthesis after Exception
    content = re.sub(
        r'side_effect=Exception\("Agent processing failed"\)\s*\n\s*\n\s*response = await',
        'side_effect=Exception("Agent processing failed")\n        )\n        \n        response = await',
        content
    )
    
    # Fix indentation for "response = await" lines that are incorrectly indented
    content = re.sub(
        r'^            response = await',
        '        response = await',
        content,
        flags=re.MULTILINE
    )
    
    # Fix indentation for "await orchestrator.process_voice_input" that's incorrectly indented
    lines = content.split('\n')
    fixed_lines = []
    
    for i, line in enumerate(lines):
        # Fix line 296 indentation issue
        if i == 295 and line.strip() == 'await orchestrator.process_voice_input(session_id, "Show menu")':
            fixed_lines.append('        await orchestrator.process_voice_input(session_id, "Show menu")')
        else:
            fixed_lines.append(line)
    
    content = '\n'.join(fixed_lines)
    
    # Fix the missing closing parenthesis in test_intent_detection_error
    content = re.sub(
        r'async def test_intent_detection_error\(self, orchestrator_with_errors\):\s*\n\s*"""Test handling of intent detection errors."""\s*\n\s*orchestrator, session_id = orchestrator_with_errors\s*\n\s*\n\s*# Mock frontline agent fallback',
        '''async def test_intent_detection_error(self, orchestrator_with_errors):
        """Test handling of intent detection errors."""
        orchestrator, session_id = orchestrator_with_errors
        
        # Mock frontline agent fallback''',
        content,
        flags=re.DOTALL
    )
    
    with open(test_file, 'w') as f:
        f.write(content)
    
    print(f"Fixed syntax errors in {test_file}")
    return True

if __name__ == "__main__":
    if fix_syntax_errors():
        print("\nSyntax errors fixed successfully!")
    else:
        print("\nFailed to fix syntax errors.")