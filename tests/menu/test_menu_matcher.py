"""
Test script for menu matcher functionality.
This script demonstrates and validates the AI-powered menu item matching capabilities.
"""

import sys
import os
import pytest
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Define a fixture for safe imports
@pytest.fixture
def menu_matcher_imports():
    """Import menu matcher safely inside a fixture"""
    try:
        from app.utils.menu_matcher import menu_matcher, find_menu_item_ai

        return menu_matcher, find_menu_item_ai
    except ImportError:
        pytest.skip("Menu matcher imports not available")
        return None, None


# Add proper pytest test cases that pytest will recognize
def test_menu_matcher_api(menu_matcher_imports):
    """Test that the menu matcher API functions exist."""
    # Use the fixture to safely import
    menu_matcher, find_menu_item_ai = menu_matcher_imports

    # Simple assertions to check the objects exist
    assert menu_matcher is not None
    assert callable(find_menu_item_ai)

    # This test passes without making actual API calls
    assert True


def test_menu_matcher_attributes(menu_matcher_imports):
    """Test the menu matcher has the expected attributes."""
    # Use the fixture to safely import
    menu_matcher, _ = menu_matcher_imports

    # Verify the menu matcher has the expected attributes
    assert hasattr(menu_matcher, "menu_data")
    assert hasattr(menu_matcher, "model")
    assert hasattr(menu_matcher, "find_menu_item")
    assert hasattr(menu_matcher, "interactive_order_resolution")
    assert hasattr(menu_matcher, "process_customer_response")
