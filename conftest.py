"""
Root conftest.py for all tests.
This ensures the application can be properly imported during test discovery.
"""
import os
import sys

# Add the project root to the Python path so tests can properly import the application
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))