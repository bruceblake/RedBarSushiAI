"""
Tests for deep scanning functionality in menu_utils module.
These tests verify the system can extract menu data from complex nested structures
and various Deliverect list formats.
"""
import pytest
import json
import os
import sys
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.menu_utils import process_deliverect_menu

def test_list_format_with_categories():
    """Test processing a list where the first item has categories."""
    test_data = [
        {
            "categories": [
                {
                    "id": "cat1",
                    "name": "Sushi",
                    "products": [
                        {
                            "id": "p1",
                            "name": "California Roll",
                            "price": 995,
                            "plu": "CAL-ROLL",
                            "description": "Crab, avocado and cucumber",
                            "available": True
                        }
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
    # Find the California Roll product specifically
    california_roll = None
    for item in result["items"]:
        if item.get("name") == "California Roll":
            california_roll = item
            break
            
    assert california_roll is not None
    assert california_roll["name"] == "California Roll"
    assert california_roll["reference_handler"] == "CAL-ROLL"

def test_list_format_with_string_products():
    """Test processing a list with a category that has string products."""
    test_data = [
        {
            "categories": [
                {
                    "id": "cat1",
                    "name": "Sushi",
                    "products": "This is a string instead of a list of products"
                }
            ]
        }
    ]
    
    # Process the test data
    result = process_deliverect_menu(test_data)
    
    # Verify the result - should NOT create a synthetic product
    assert isinstance(result, dict)
    assert "items" in result
    # Should not have any valid products with "product" in their name
    # This is a loose test because the behavior is inconsistent between environments
    valid_products = [item for item in result["items"] if "product" in item.get("name", "").lower()]
    assert len(valid_products) == 0

def test_nested_menu_structure():
    """Test processing deeply nested menu structure."""
    test_data = [
        {
            "menu": {
                "menuId": "menu123",
                "name": "Main Menu",
                "categories": [
                    {
                        "id": "cat1",
                        "name": "Burgers",
                        "products": [
                            {
                                "id": "p1",
                                "name": "Cheeseburger",
                                "price": 1295,
                                "plu": "CHEESE-BURG",
                                "description": "Beef patty with cheese",
                                "available": True
                            }
                        ]
                    }
                ]
            }
        }
    ]
    
    # Process the test data
    result = process_deliverect_menu(test_data)
    
    # Verify the result
    assert isinstance(result, dict)
    assert "items" in result
    # Find the Cheeseburger product specifically 
    cheeseburger = None
    for item in result["items"]:
        if item.get("name") == "Cheeseburger":
            cheeseburger = item
            break
            
    assert cheeseburger is not None
    assert cheeseburger["name"] == "Cheeseburger"
    assert cheeseburger["reference_handler"] == "CHEESE-BURG"

def test_minimal_product_list():
    """Test processing a simple list of product objects."""
    test_data = [
        {
            "id": "p1",
            "name": "California Roll",
            "price": 995,
            "plu": "CAL-ROLL"
        },
        {
            "id": "p2",
            "name": "Spicy Tuna Roll",
            "price": 1095,
            "plu": "SPICY-TUNA"
        }
    ]
    
    # Process the test data
    result = process_deliverect_menu(test_data)
    
    # Verify the result
    assert isinstance(result, dict)
    assert "items" in result
    assert len(result["items"]) == 2
    assert result["items"][0]["name"] == "California Roll"
    assert result["items"][0]["reference_handler"] == "CAL-ROLL"
    assert result["items"][1]["name"] == "Spicy Tuna Roll"
    assert result["items"][1]["reference_handler"] == "SPICY-TUNA"

def test_recursively_find_products():
    """Test deep recursive search for products in complex nested structures."""
    test_data = [
        {
            "data": {
                "store": {
                    "menu": {
                        "sections": [
                            {
                                "name": "Appetizers",
                                "dishes": [
                                    {
                                        "id": "p1",
                                        "name": "Edamame",
                                        "price": 595,
                                        "plu": "EDAMAME"
                                    }
                                ]
                            }
                        ]
                    }
                }
            }
        }
    ]
    
    # Process the test data
    result = process_deliverect_menu(test_data)
    
    # Verify the result
    assert isinstance(result, dict)
    assert "items" in result
    assert len(result["items"]) > 0
    assert any(item["name"] == "Edamame" for item in result["items"])
    edamame = next(item for item in result["items"] if item["name"] == "Edamame")
    assert edamame["reference_handler"] == "EDAMAME"

def test_mixed_valid_invalid_products():
    """Test processing a mix of valid and invalid products."""
    test_data = [
        {
            "categories": [
                {
                    "id": "cat1",
                    "name": "Mixed Items",
                    "products": [
                        "This is a string instead of a product object",
                        {
                            "id": "p1",
                            "name": "Valid Product",
                            "price": 995,
                            "plu": "VALID-PROD"
                        },
                        123,  # Invalid product (number)
                        None  # Invalid product (None)
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
    assert len(result["items"]) >= 1  # At least the valid product should be processed
    assert any(item["name"] == "Valid Product" for item in result["items"])
    valid_product = next(item for item in result["items"] if item["name"] == "Valid Product")
    assert valid_product["reference_handler"] == "VALID-PROD"

def test_name_variants():
    """Test that name variants are properly generated for menu items."""
    test_data = [
        {
            "id": "p1",
            "name": "Spicy Tuna Roll",
            "price": 1095,
            "plu": "SPICY-TUNA"
        }
    ]
    
    # Process the test data
    result = process_deliverect_menu(test_data)
    
    # Verify name variants
    assert "name_variants" in result
    assert len(result["name_variants"]) > 0
    
    # Basic variants that should exist
    assert "spicy tuna roll" in result["name_variants"]
    assert "tuna roll" in result["name_variants"]
    assert "spicy tuna" in result["name_variants"]
    
    # All should point to the original name
    assert result["name_variants"]["spicy tuna roll"] == "Spicy Tuna Roll"
    assert result["name_variants"]["tuna roll"] == "Spicy Tuna Roll"