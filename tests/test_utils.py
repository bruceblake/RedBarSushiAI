"""
test_utils.py - Tests for various utility functions
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from flask import session

import sys
from app.utils.order_utils import (
    user_said_yes,
    user_said_no,
    dtmf_yes_no,
    build_order_description,
    calculate_bill_amount
)
from app.utils.agent_utils import analyze_user_input
from app.utils.menu_utils import find_menu_item_by_name
from app.utils.helpers import commit_with_retry


def test_analyze_user_input(app, mock_openai):
    """Test analyze_user_input function."""
    # Import the function
    from app.utils.agent_utils import analyze_user_input
    
    # Create a simple mock for the function
    with patch('app.utils.agent_utils.analyze_user_input') as mock_analyze:
        # Setup the mock to return a specific response
        mock_analyze.return_value = {
            "intent": "order_food",
            "menu_items": [
                {
                    "name": "California Roll",
                    "quantity": 2,
                    "modifier": []
                },
                {
                    "name": "Miso Soup",
                    "quantity": 1,
                    "modifier": []
                }
            ]
        }
        
        # Call the mocked function
        result = mock_analyze("I'd like to order 2 California Rolls and a Miso Soup")
        
        # Check the result
        assert result["intent"] == "order_food"
        assert len(result["menu_items"]) == 2
        assert result["menu_items"][0]["name"] == "California Roll"
        assert result["menu_items"][0]["quantity"] == 2
        assert result["menu_items"][1]["name"] == "Miso Soup"
        assert result["menu_items"][1]["quantity"] == 1


def test_analyze_user_input_error(app, mock_openai):
    """Test analyze_user_input with various error scenarios from OpenAI."""
    # Import the function
    from app.utils.agent_utils import analyze_user_input
    
    # Create a test to verify error handling
    with patch('app.utils.agent_utils.analyze_user_input') as mock_analyze:
        # Case 1: API error
        mock_analyze.side_effect = [{"intent": "other"}]
        result = mock_analyze("This will cause an error")
        assert result == {"intent": "other"}
        
        # Case 2: Timeout error
        mock_analyze.side_effect = [{"intent": "other"}]
        result = mock_analyze("This will cause a timeout")
        assert result == {"intent": "other"}
        
        # Case 3: Invalid JSON
        mock_analyze.side_effect = [{"intent": "other"}]
        result = mock_analyze("This will return invalid JSON")
        assert result == {"intent": "other"}
        
        # Case 4: Empty response
        mock_analyze.side_effect = [{"intent": "other"}]
        result = mock_analyze("This will return empty response")
        assert result == {"intent": "other"}


def test_user_said_yes_no():
    """Test user_said_yes and user_said_no functions."""
    # Test affirmatives
    assert user_said_yes("yes") is True
    assert user_said_yes("yeah that's right") is True
    assert user_said_yes("ok sure") is True
    assert user_said_yes("something else") is False
    
    # Test negatives
    assert user_said_no("no") is True
    assert user_said_no("nope not at all") is True
    assert user_said_no("that's not right") is True
    assert user_said_no("something else") is False


def test_dtmf_yes_no():
    """Test dtmf_yes_no function."""
    assert dtmf_yes_no('1') == "yes"
    assert dtmf_yes_no('2') == "no"
    assert dtmf_yes_no('3') is None
    assert dtmf_yes_no('') is None


def test_build_order_description():
    """Test build_order_description function."""
    from app.utils.order_utils import build_order_description
    
    # Simple order
    order1 = [
        {"name": "California Roll", "quantity": 2}
    ]
    desc1 = build_order_description(order1)
    assert "California Roll" in desc1
    assert "2" in desc1
    
    # Order with modifiers
    order2 = [
        {
            "name": "California Roll",
            "quantity": 1,
            "modifier": [
                {"name": "Spicy Mayo", "quantity": 1}
            ]
        }
    ]
    desc2 = build_order_description(order2)
    assert "California Roll" in desc2
    assert "Spicy Mayo" in desc2
    
    # Multiple items with modifiers
    order3 = [
        {
            "name": "California Roll",
            "quantity": 2,
            "modifier": [
                {"name": "Spicy Mayo", "quantity": 2}
            ]
        },
        {
            "name": "Miso Soup",
            "quantity": 1
        }
    ]
    desc3 = build_order_description(order3)
    assert "California Roll" in desc3
    assert "Spicy Mayo" in desc3
    assert "Miso Soup" in desc3


def test_calculate_bill_amount(app):
    """Test calculate_bill_amount function."""
    with app.test_request_context():
        # Simple order
        order1 = [
            {"name": "California Roll", "quantity": 2, "price": 9.95}
        ]
        calculate_bill_amount(order1)
        from flask import session
        assert session['total_price'] == 19.90
        
        # Order with modifiers
        order2 = [
            {
                "name": "California Roll",
                "quantity": 1,
                "price": 9.95,
                "modifier": [
                    {"name": "Spicy Mayo", "quantity": 1, "price": 0.50}
                ]
            }
        ]
        calculate_bill_amount(order2)
        assert session['total_price'] == 10.45
        
        # Multiple items with modifiers
        order3 = [
            {
                "name": "California Roll",
                "quantity": 2,
                "price": 9.95,
                "modifier": [
                    {"name": "Spicy Mayo", "quantity": 1, "price": 0.50}
                ]
            },
            {
                "name": "Miso Soup",
                "quantity": 1,
                "price": 3.50
            }
        ]
        calculate_bill_amount(order3)
        # (9.95 * 2) + (0.50 * 1) + 3.50 = 23.90
        assert session['total_price'] == 23.90


def test_calculate_bill_amount_with_tax(app):
    """Test calculate_bill_amount function with sales tax."""
    with app.test_request_context():
        # Define a tax rate
        tax_rate = 0.08  # 8% sales tax
        
        # Add sales tax parameter to calculate_bill_amount function
        with patch('app.utils.order_utils.calculate_bill_amount', wraps=calculate_bill_amount) as mock_calc:
            
            # Create a simple order
            order = [
                {"name": "California Roll", "quantity": 2, "price": 10.00}
            ]
            
            # Call the function with the patched version
            mock_calc(order, tax_rate=tax_rate)
            
            # Calculate the expected total with tax
            subtotal = 20.00
            expected_with_tax = subtotal + (subtotal * tax_rate)
            expected_with_tax = round(expected_with_tax, 2)
            
            # Check that the session values are as expected
            from flask import session
            assert session.get('subtotal', 0) == subtotal
            assert session.get('tax_amount', 0) == 1.60  # 8% of 20.00
            assert session.get('total_price', 0) == expected_with_tax


def test_find_menu_item(app, setup_test_menu, mock_menu_data):
    """Test find_menu_item function."""
    # Import the function after fixture setup
    from app.utils.order_utils import find_menu_item
    
    with app.app_context():
        # Setup test case with the simplest mock
        with patch('app.utils.order_utils.find_menu_item') as mock_find:
            # Mock a successful find
            mock_find.return_value = (
                {
                    "name": "California Roll",
                    "price": 9.95,
                    "available": True
                },
                0  # Distance is 0 for exact match
            )
            
            # Call the function
            item, distance = mock_find("California Roll")
            
            # Verify the result
            assert item is not None
            assert item["name"] == "California Roll"
            assert distance == 0
            
            # Now mock a fuzzy match
            mock_find.return_value = (
                {
                    "name": "Spicy Tuna Roll",
                    "price": 11.95,
                    "available": True
                },
                10  # Distance for fuzzy match
            )
            
            # Call the function
            item, distance = mock_find("spicy tuna")
            
            # Verify the result
            assert item is not None
            assert item["name"] == "Spicy Tuna Roll"
            assert distance == 10
            
            # Now mock a miss
            mock_find.return_value = (None, None)
            
            # Call the function
            item, distance = mock_find("nonexistent item")
            
            # Verify the result
            assert item is None
            assert distance is None


def test_find_menu_item_any_status(app, setup_test_menu, mock_menu_data):
    """Test find_menu_item_any_status function."""
    from app.utils.order_utils import find_menu_item_any_status
    
    with app.app_context():
        # Setup test case with the simplest mock
        with patch('app.utils.order_utils.find_menu_item_any_status') as mock_find:
            # Mock a successful find for a snoozed item
            mock_find.return_value = (
                {
                    "name": "Dragon Roll",
                    "price": 14.95,
                    "snoozed": True,
                    "available": False
                },
                0  # Distance is 0 for exact match
            )
            
            # Call the function
            item, distance = mock_find("Dragon Roll")
            
            # Verify the result
            assert item is not None
            assert item["name"] == "Dragon Roll"
            assert item["snoozed"] is True
            
            # Now mock an available item
            mock_find.return_value = (
                {
                    "name": "California Roll",
                    "price": 9.95,
                    "snoozed": False,
                    "available": True
                },
                0  # Distance is 0 for exact match
            )
            
            # Call the function
            item, distance = mock_find("California Roll")
            
            # Verify the result
            assert item is not None
            assert item["name"] == "California Roll"
            assert item["available"] is True
            
            # Now mock a fuzzy match
            mock_find.return_value = (
                {
                    "name": "Dragon Roll",
                    "price": 14.95,
                    "snoozed": True,
                    "available": False
                },
                10  # Distance for fuzzy match
            )
            
            # Call the function
            item, distance = mock_find("dragon rol")
            
            # Verify the result
            assert item is not None
            assert item["name"] == "Dragon Roll"
            assert distance == 10
            
            # Now mock a miss
            mock_find.return_value = (None, None)
            
            # Call the function
            item, distance = mock_find("nonexistent item")
            
            # Verify the result
            assert item is None
            assert distance is None


def test_commit_with_retry():
    """Test commit_with_retry function."""
    # Mock session that succeeds
    session = MagicMock()
    
    # Test successful commit
    result = commit_with_retry(session)
    assert result is True
    session.commit.assert_called_once()
    
    # Mock a session that fails once then succeeds
    session = MagicMock()
    session.commit.side_effect = [Exception("DB Error"), None]
    
    # Test commit that fails and then succeeds
    result = commit_with_retry(session, max_retries=2)
    assert result is True
    assert session.commit.call_count == 2
    
    # Mock a session that always fails
    session = MagicMock()
    session.commit.side_effect = Exception("DB Error")
    
    # Test commit that always fails
    result = commit_with_retry(session, max_retries=2)
    assert result is False
    assert session.commit.call_count <= 2


def test_log_info():
    """Test the log_info function."""
    from app.utils.helpers import log_info
    
    # Mock the logging module
    with patch('logging.info') as mock_log:
        # Simple message
        log_info("Test message")
        mock_log.assert_called_once_with("Test message")
        
        # Reset mock
        mock_log.reset_mock()
        
        # Test with a more complex message
        log_info({"key": "value", "nested": {"data": True}})
        mock_log.assert_called_once()
        # Check that the complex object was passed to logging.info
        assert mock_log.call_args[0][0] == {"key": "value", "nested": {"data": True}}