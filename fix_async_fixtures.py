#!/usr/bin/env python3
"""
Script to fix async fixtures in test files by replacing @pytest.fixture
with @pytest_asyncio.fixture for async fixtures.
"""

import re
import sys
from pathlib import Path

def fix_async_fixtures(file_path):
    """Fix async fixtures in a single file."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Pattern to find @pytest.fixture followed by async def
    pattern = r'(@pytest\.fixture)\s*\n(\s*)async def'
    replacement = r'@pytest_asyncio.fixture\n\2async def'
    
    # Replace all occurrences
    new_content = re.sub(pattern, replacement, content)
    
    # Count replacements
    replacements = len(re.findall(pattern, content))
    
    if replacements > 0:
        with open(file_path, 'w') as f:
            f.write(new_content)
        print(f"Fixed {replacements} async fixtures in {file_path}")
    else:
        print(f"No async fixtures to fix in {file_path}")
    
    return replacements

def main():
    """Fix async fixtures in all integration test files."""
    test_dir = Path("/home/proxyie/MySoftware/RedBarSushiAI/tests/integration")
    total_fixed = 0
    
    for test_file in test_dir.glob("test_*.py"):
        fixed = fix_async_fixtures(test_file)
        total_fixed += fixed
    
    print(f"\nTotal async fixtures fixed: {total_fixed}")

if __name__ == "__main__":
    main()