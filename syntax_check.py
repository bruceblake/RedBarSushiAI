#!/usr/bin/env python3
"""
Minimal script to check syntax of realtime_audio.py without importing it
"""

import py_compile
import sys
import os

# Path to the file we want to check
file_path = os.path.join('app', 'utils', 'realtime_audio.py')

print(f"Checking syntax of {file_path}...")
try:
    # Try to compile the file to check for syntax errors
    py_compile.compile(file_path, doraise=True)
    print(f"✅ No syntax errors found in {file_path}")
    sys.exit(0)
except py_compile.PyCompileError as e:
    print(f"❌ Syntax error in {file_path}: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Error checking {file_path}: {e}")
    sys.exit(1)