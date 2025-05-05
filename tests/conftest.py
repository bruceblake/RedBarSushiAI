"""
Main conftest.py for all tests.
This file contains common fixtures and configurations for all test types.
"""

import pytest


# Define test markers
def pytest_configure(config):
    """
    Configure pytest with custom markers.
    """
    config.addinivalue_line("markers", "e2e: mark a test as an end-to-end test")


# Add additional common fixtures here if needed
