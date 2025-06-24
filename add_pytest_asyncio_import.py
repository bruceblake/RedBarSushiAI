#!/usr/bin/env python3
"""
Script to add pytest_asyncio import to test files that use @pytest_asyncio.fixture
"""

import re
from pathlib import Path

def add_import_if_needed(file_path):
    """Add pytest_asyncio import if file uses @pytest_asyncio.fixture."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check if file uses @pytest_asyncio.fixture
    if '@pytest_asyncio.fixture' not in content:
        return False
    
    # Check if already imports pytest_asyncio
    if 'import pytest_asyncio' in content:
        return False
    
    # Find the import section and add pytest_asyncio
    lines = content.split('\n')
    import_added = False
    
    for i, line in enumerate(lines):
        if line.startswith('import pytest'):
            # Add pytest_asyncio import after pytest import
            lines.insert(i + 1, 'import pytest_asyncio')
            import_added = True
            break
    
    if not import_added:
        # If no pytest import found, add at the beginning of imports
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                lines.insert(i, 'import pytest_asyncio')
                break
    
    # Write back
    with open(file_path, 'w') as f:
        f.write('\n'.join(lines))
    
    print(f"Added pytest_asyncio import to {file_path}")
    return True

def main():
    """Add pytest_asyncio imports to all test files that need it."""
    test_dir = Path("/home/proxyie/MySoftware/RedBarSushiAI/tests/integration")
    fixed_count = 0
    
    for test_file in test_dir.glob("test_*.py"):
        if add_import_if_needed(test_file):
            fixed_count += 1
    
    print(f"\nTotal files fixed: {fixed_count}")

if __name__ == "__main__":
    main()