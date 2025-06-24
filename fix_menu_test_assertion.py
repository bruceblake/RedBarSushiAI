#!/usr/bin/env python3
"""
Fix the menu test assertion to check for the actual response structure.
"""

import re
from pathlib import Path

def fix_tests(file_path):
    """Fix the menu test assertion."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix the menu test assertion
    old_assertion = """        # Verify menu-related response
        assert response is not None
        assert "menu" in response.get("text", "").lower() or response.get("delegated_to") == "menu\""""
    
    new_assertion = """        # Verify menu-related response
        assert response is not None
        assert "menu" in response.get("text", "").lower()\""""
    
    content = content.replace(old_assertion, new_assertion)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"Fixed menu test assertion in {file_path}")
    return True

def main():
    """Fix the tests."""
    test_file = Path("/home/proxyie/MySoftware/RedBarSushiAI/tests/integration/test_agent_orchestration_comprehensive.py")
    
    if fix_tests(test_file):
        print("\nMenu test assertion fixed successfully!")
    else:
        print("\nNo changes needed.")

if __name__ == "__main__":
    main()