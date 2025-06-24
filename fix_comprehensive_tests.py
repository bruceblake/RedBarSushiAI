#!/usr/bin/env python3
"""Fix comprehensive integration tests to match current implementation."""

import re
from pathlib import Path

def fix_comprehensive_tests():
    """Fix all issues in comprehensive test file."""
    test_file = Path("/home/proxyie/MySoftware/RedBarSushiAI/tests/integration/test_agent_orchestration_comprehensive.py")
    
    with open(test_file, 'r') as f:
        content = f.read()
    
    # Fix the indentation issues
    lines = content.split('\n')
    fixed_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Fix broken for loops
        if 'for user_input in inputs:' in line and line.strip() == 'for user_input in inputs:':
            fixed_lines.append(line)
            i += 1
            continue
            
        # Fix lines with excessive indentation in agent loops
        if re.match(r'^\s{16,}agent = getattr\(orchestrator, agent_name\)', line):
            fixed_lines.append('                agent = getattr(orchestrator, agent_name)')
            i += 1
            continue
            
        if re.match(r'^\s{16,}agent\.process = AsyncMock', line):
            fixed_lines.append('                agent.process = AsyncMock(return_value=agent_response)')
            i += 1
            continue
            
        # Fix process method calls
        if 'agent.process(' in line and 'process_voice_input' not in line:
            line = line.replace('agent.process(', 'agent.process_voice_input(')
            
        # Fix the streaming test closing parenthesis
        if re.match(r'^\s+\)$', line):
            # Skip orphaned closing parentheses
            i += 1
            continue
            
        # Fix missing closing parenthesis for process_voice_input calls
        if 'stream_callback=chunk_callback' in line and not line.strip().endswith(')'):
            line = line + ')'
            
        # Fix missing closing parenthesis for datetime operations
        if 'datetime.now().timestamp() - 3700' in line and not line.strip().endswith(')'):
            line = line + ')'
            
        # Fix the rapid state changes test
        if 'for agent_attr in' in line and "'frontline_agent', 'cart_agent', 'guardrail_agent'" in line:
            fixed_lines.append(line)
            # Add proper indentation for the following lines
            i += 1
            while i < len(lines) and ('if hasattr' in lines[i] or 'agent = getattr' in lines[i] or 'agent.process' in lines[i]):
                if 'if hasattr' in lines[i]:
                    fixed_lines.append('                    if hasattr(orchestrator, agent_attr):')
                elif 'agent = getattr' in lines[i]:
                    fixed_lines.append('                        agent = getattr(orchestrator, agent_attr)')
                elif 'agent.process = AsyncMock' in lines[i]:
                    # Handle multi-line agent.process assignment
                    fixed_lines.append('                        agent.process_voice_input = AsyncMock(return_value={')
                    i += 1
                    while i < len(lines) and '})' not in lines[i]:
                        if 'text' in lines[i] or 'agent' in lines[i] or 'handled' in lines[i]:
                            fixed_lines.append('                            ' + lines[i].strip())
                        i += 1
                    fixed_lines.append('                        })')
                i += 1
            continue
            
        fixed_lines.append(line)
        i += 1
    
    # Join and make final fixes
    content = '\n'.join(fixed_lines)
    
    # Fix the conversation history test
    content = re.sub(
        r'for user_input in inputs:\s*\n\s*orchestrator\.frontline_agent\.process_voice_input = AsyncMock',
        '''for user_input in inputs:
            orchestrator.frontline_agent.process_voice_input = AsyncMock(return_value={
                "text": f"Response to: {user_input}",
                "agent": "frontline",
                "handled": True
            })
            
            await orchestrator.process_voice_input(session_id, user_input)''',
        content,
        flags=re.MULTILINE | re.DOTALL
    )
    
    # Fix process to process_voice_input everywhere
    content = re.sub(r'\.process\s*=\s*AsyncMock', '.process_voice_input = AsyncMock', content)
    content = re.sub(r'\.process\s*=\s*mock_streaming_process', '.process_voice_input = mock_streaming_process', content)
    
    # Fix orchestrator.process calls to process_voice_input
    content = re.sub(r'orchestrator\.process\(', 'orchestrator.process_voice_input(', content)
    
    # Fix missing async on mock functions
    content = re.sub(
        r'orchestrator\.frontline_agent\.process_voice_input = mock_streaming_process',
        'orchestrator.frontline_agent.process_voice_input = AsyncMock(side_effect=mock_streaming_process)',
        content
    )
    
    # Write the fixed content
    with open(test_file, 'w') as f:
        f.write(content)
    
    print(f"Fixed {test_file}")
    print("Key fixes:")
    print("- Fixed indentation issues")
    print("- Changed .process to .process_voice_input throughout")
    print("- Fixed broken for loops and missing parentheses")
    print("- Fixed agent method assignments")
    return True

if __name__ == "__main__":
    if fix_comprehensive_tests():
        print("\nComprehensive test file fixed successfully!")
    else:
        print("\nFailed to fix comprehensive test file.")