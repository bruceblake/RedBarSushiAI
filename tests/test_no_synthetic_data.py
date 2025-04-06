"""
Tests to verify no synthetic data is created from Deliverect input
"""
import pytest
from app.utils.menu_utils import process_deliverect_menu

def test_no_synthetic_names_with_bad_categories():
    """Test that no synthetic names are created even with problematic category data"""
    # Create test data with categories but no actual product data
    test_data = [
        {
            "categories": [
                {
                    "name": "Steak & Burgers",
                    "products": [] # Empty products list
                },
                {
                    "name": "Pizza",
                    "products": "This is a string, not a list" # String products
                },
                {
                    "name": "Sushi",
                    "products": [123, 456, 789] # Number IDs with no product mapping
                }
            ]
        }
    ]
    
    # Process the test data
    result = process_deliverect_menu(test_data)
    
    # Verify the result - should not have any synthetic names
    assert isinstance(result, dict)
    assert "items" in result
    
    # There should be no items since none of the products had valid data
    assert len(result["items"]) == 0

def test_no_synthetic_names_mixed_data():
    """Test that only real product names are used when some valid and some invalid data is present"""
    # Create test data with a mix of valid and invalid products
    test_data = [
        {
            "categories": [
                {
                    "name": "Mixed Items",
                    "products": [
                        {
                            "name": "Real Product",
                            "price": 1295,
                            "plu": "REAL-PROD"
                        },
                        "This is a string, not a product",
                        123, # Number, not a product
                        None, # None value
                        {} # Empty dict with no name
                    ]
                }
            ]
        }
    ]
    
    # Process the test data
    result = process_deliverect_menu(test_data)
    
    # Verify the result
    assert isinstance(result, dict)
    assert "items" in result
    assert len(result["items"]) == 1
    
    # Only the real product should be included
    assert result["items"][0]["name"] == "Real Product"
    assert result["items"][0]["reference_handler"] == "REAL-PROD"
    
    # No other items should be created
    assert not any(item["name"] != "Real Product" for item in result["items"])

def test_nested_data_no_synthetic():
    """Test that deeply nested data doesn't create synthetic names"""
    # Create test data with nested structure
    test_data = [
        {
            "data": {
                "nested": {
                    "categories": [
                        {
                            "name": "Deeply Nested",
                            "products": []
                        }
                    ]
                }
            }
        }
    ]
    
    # Process the test data
    result = process_deliverect_menu(test_data)
    
    # Should not create any synthetic items
    assert isinstance(result, dict)
    assert "items" in result
    assert len(result["items"]) == 0
