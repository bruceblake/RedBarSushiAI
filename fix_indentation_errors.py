#!/usr/bin/env python3
"""Fix indentation errors in the test file."""

import re
from pathlib import Path

def fix_indentation(file_path):
    """Fix indentation errors."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix the indentation errors by removing extra spaces
    content = re.sub(r'^                    ', '        ', content, flags=re.MULTILINE)
    
    # Fix incomplete lines
    content = re.sub(r'^\s+\)\n', '', content, flags=re.MULTILINE)
    
    # Remove the "No newline at end of file" text
    content = content.replace(' No newline at end of file', '')
    
    # Ensure file ends with newline
    if not content.endswith('\n'):
        content += '\n'
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"Fixed indentation in {file_path}")
    return True

def main():
    """Fix the indentation."""
    test_file = Path("/home/proxyie/MySoftware/RedBarSushiAI/tests/integration/test_agent_orchestration_comprehensive.py")
    
    if fix_indentation(test_file):
        print("\nIndentation fixed successfully!")
    else:
        print("\nNo changes needed.")

if __name__ == "__main__":
    main()