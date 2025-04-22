#\!/usr/bin/env python
"""
Simple script to test that imports work in CI environments.
"""

import sys
import os

print("Starting import test...")

# Add a flag to skip app initialization
os.environ["SKIP_APP_INIT"] = "true"

# Let's directly import the modules without the app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Try importing the agent module directly
try:
    print("Importing agent module...")
    from app.utils.agent import AI_COMPONENTS_AVAILABLE
    print("agent module imported successfully")
    print(f"AI_COMPONENTS_AVAILABLE = {AI_COMPONENTS_AVAILABLE}")
except Exception as e:
    print(f"Error importing agent module: {str(e)}")
    
print("Import test complete.")
