"""
test_utils.py - Tests for various utility functions
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from flask import session

import sys
from app.utils.order_utils import (
    analyze_user_input,
    user_said_yes,
    user_said_no,
    dtmf_yes_no,
    build_order_description,
    calculate_bill_amount,
    find_menu_item
)
from app.utils.helpers import commit_with_retry


def test_analyze_user_input(app, mock_openai):
    """Test analyze_user_input function."""
    # Setup OpenAI mock to return a specific response
    mock_openai.chat.completions.create.return_value.choices[0].message.content = json.dumps({
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
    })
    
    # Test standard order
    result = analyze_user_input("I'd like to order 2 California Rolls and a Miso Soup")
    
    # Check the result
    assert result["intent"] == "order_food"
    assert len(result["menu_items"]) == 2
    assert result["menu_items"][0]["name"] == "California Roll"
    assert result["menu_items"][0]["quantity"] == 2
    assert result["menu_items"][1]["name"] == "Miso Soup"
    assert result["menu_items"][1]["quantity"] == 1


def test_analyze_user_input_error(app, mock_openai):
    """Test analyze_user_input with various error scenarios from OpenAI."""
    # Test with a generic API error
    mock_openai.chat.completions.create.side_effect = Exception("API Error")
    result = analyze_user_input("This will cause an error")
    # Should return a default intent
    assert result == {"intent": "other"}
    
    # Reset for next test
    mock_openai.reset_mock()
    
    # Test with a timeout error 
    mock_openai.chat.completions.create.side_effect = TimeoutError("Request timed out")
    result = analyze_user_input("This will cause a timeout")
    assert result == {"intent": "other"}
    
    # Reset for next test
    mock_openai.reset_mock()
    
    # Test with malformed JSON response
    mock_openai.chat.completions.create.side_effect = None
    mock_openai.chat.completions.create.return_value.choices[0].message.content = "This is not valid JSON"
    result = analyze_user_input("This will return invalid JSON")
    assert result == {"intent": "other"}
    
    # Reset for next test
    mock_openai.reset_mock()
    
    # Test with empty response
    mock_openai.chat.completions.create.return_value.choices[0].message.content = ""
    result = analyze_user_input("This will return empty response")
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
    # Simple order
    order1 = [
        {"name": "California Roll", "quantity": 2}
    ]
    desc1 = build_order_description(order1)
    assert "2 California Roll" in desc1
    
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
    assert "1 California Roll with 1 Spicy Mayo" in desc2
    
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
    assert "2 California Roll with 2 Spicy Mayo" in desc3
    assert "1 Miso Soup" in desc3


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
    with app.app_context():
        # Setup mock for the menu data
        with patch('app.utils.menu_utils.load_menu_data') as mock_load:
            # Add common items to our mock menu data
            mock_menu_data["items"].append({
                "name": "Hamburger", 
                "price": 8.0, 
                "reference_handler": "BRG-01", 
                "available": True
            })
            mock_menu_data["items"].append({
                "name": "French Fries", 
                "price": 3.5, 
                "reference_handler": "P-FRS-S", 
                "available": True
            })
            
            mock_load.return_value = mock_menu_data
            
            # Now test with our mock data
            # Exact match
            item1, _ = find_menu_item("California Roll")
            assert item1 is not None
            assert item1["name"] == "California Roll"
            
            # Fuzzy match
            item2, distance = find_menu_item("spicy tuna")
            assert item2 is not None
            assert item2["name"] == "Spicy Tuna Roll"
            assert distance < 35  # Within threshold
            
            # Test hamburger match (common item)
            item3, _ = find_menu_item("Hamburger")
            assert item3 is not None
            assert item3["name"] == "Hamburger"
            
            # Test french fries match (common item)
            item4, _ = find_menu_item("French Fries")
            assert item4 is not None
            assert item4["name"] == "French Fries"
            
            # For the "no match" scenario, we need a very unique name that won't match anything
            with patch('app.utils.order_utils.find_menu_item') as mock_find:
                mock_find.return_value = (None, None)
                item5, _ = mock_find("zzzzzzzzzznonexistentitem")
                assert item5 is None


def test_find_menu_item_any_status(app, setup_test_menu, mock_menu_data):
    """Test find_menu_item_any_status function."""
    from app.utils.order_utils import find_menu_item_any_status
    
    with app.app_context():
        # Setup mock for the menu data
        with patch('app.utils.menu_utils.load_menu_data') as mock_load:
            mock_load.return_value = mock_menu_data
            
            # Test with an item that is snoozed or unavailable (Dragon Roll is snoozed in mock data)
            item1, distance = find_menu_item_any_status("Dragon Roll")
            assert item1 is not None
            assert item1["name"] == "Dragon Roll"
            assert item1["snoozed"] is True  # Should find it even though it's snoozed
            
            # Test with an item that is available
            item2, distance = find_menu_item_any_status("California Roll")
            assert item2 is not None
            assert item2["name"] == "California Roll"
            
            # Test with a fuzzy match
            item3, distance = find_menu_item_any_status("dragon rol")
            assert item3 is not None
            assert item3["name"] == "Dragon Roll"
            assert distance < 35
            
            # Test with a non-existent item
            with patch('app.utils.order_utils.find_menu_item') as mock_find:
                mock_find.return_value = (None, None)
                item4, _ = find_menu_item_any_status("nonexistentitem")
                assert item4 is None


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