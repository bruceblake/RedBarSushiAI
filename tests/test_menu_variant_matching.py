"""
Test menu variant matching functionality.
"""
import pytest
from unittest.mock import patch

def test_menu_variant_matching(app, setup_test_menu):
    """Test that menu variant matching works correctly."""
    from app.utils.order_utils import find_menu_item
    
    # Create mock menu data with name variants
    mock_menu = {
        "items": [
            {
                "name": "Classic Burger",
                "id": "PROD-001",
                "reference_handler": "BRG-001",
                "price": 8.50,
                "available": True
            },
            {
                "name": "French Fries",
                "id": "PROD-002",
                "reference_handler": "FRS-001",
                "price": 3.50,
                "available": True
            },
            {
                "name": "Coca Cola",
                "id": "PROD-003",
                "reference_handler": "DRK-001",
                "price": 2.50,
                "available": True
            }
        ],
        "name_variants": {
            "hamburger": "Classic Burger",
            "burger": "Classic Burger",
            "fries": "French Fries",
            "coke": "Coca Cola",
            "soda": "Coca Cola",
            "coca cola": "Coca Cola"
        }
    }
    
    with patch('app.utils.menu_utils.load_menu_data', return_value=mock_menu):
        # Test standard variants
        item1, score1 = find_menu_item("Hamburger")
        assert item1 is not None
        assert item1["name"] == "Classic Burger"
        assert score1 == 0
        
        # Test fries variants
        item2, score2 = find_menu_item("Fries")
        assert item2 is not None
        assert item2["name"] == "French Fries"
        assert score2 == 0
        
        # Test drink variants
        item3, score3 = find_menu_item("Coke")
        assert item3 is not None
        assert item3["name"] == "Coca Cola"
        assert score3 == 0
        
        # Test drink variants - another form
        item4, score4 = find_menu_item("Soda")
        assert item4 is not None
        assert item4["name"] == "Coca Cola"
        assert score4 == 0
        
        # Test non-existent variant
        item5, score5 = find_menu_item("Pizza")
        assert item5 is None

def test_deliverect_menu_processing(app):
    """Test that Deliverect menu processing creates name variants correctly."""
    from app.utils.menu_utils import process_deliverect_menu
    
    # Sample Deliverect menu data with variety of menu items
    deliverect_data = {
        "categories": [
            {
                "id": "CAT-001",
                "name": "Main Dishes",
                "products": [
                    {
                        "id": "PROD-001",
                        "name": "Chicken Parmesan",
                        "price": 1595,
                        "description": "Breaded chicken with marinara and cheese",
                        "plu": "MAIN-001",
                        "available": True
                    },
                    {
                        "id": "PROD-002",
                        "name": "Vegetable Stir Fry",
                        "price": 1395,
                        "description": "Mixed vegetables in sauce",
                        "plu": "MAIN-002",
                        "available": True
                    }
                ]
            },
            {
                "id": "CAT-002",
                "name": "Sides",
                "products": [
                    {
                        "id": "PROD-003",
                        "name": "Garlic Bread",
                        "price": 595,
                        "description": "Toasted bread with garlic butter",
                        "plu": "SIDE-001",
                        "available": True
                    },
                    {
                        "id": "PROD-004",
                        "name": "Sweet Potato Fries",
                        "price": 495,
                        "description": "Crispy sweet potato fries",
                        "plu": "SIDE-002",
                        "available": True
                    }
                ]
            }
        ]
    }
    
    # Process the menu
    processed_menu = process_deliverect_menu(deliverect_data)
    
    # Verify name variants were created
    assert "name_variants" in processed_menu
    
    # Multi-word items should have full name and key words as variants
    assert "chicken parmesan" in processed_menu["name_variants"]
    assert "chicken" in processed_menu["name_variants"]
    assert "parmesan" in processed_menu["name_variants"]
    assert processed_menu["name_variants"]["chicken"] == "Chicken Parmesan"
    
    # Verify another multi-word item
    assert "vegetable stir fry" in processed_menu["name_variants"]
    assert "vegetable" in processed_menu["name_variants"]
    assert processed_menu["name_variants"]["vegetable"] == "Vegetable Stir Fry"
    
    # Side items should still work
    assert "garlic bread" in processed_menu["name_variants"]
    assert "garlic" in processed_menu["name_variants"]
    assert "bread" in processed_menu["name_variants"]
    assert processed_menu["name_variants"]["bread"] == "Garlic Bread"
    
    # Sweet potato fries should extract key terms
    assert "sweet potato fries" in processed_menu["name_variants"]
    assert "sweet" in processed_menu["name_variants"]
    assert "potato" in processed_menu["name_variants"]
    assert "fries" in processed_menu["name_variants"]
    assert processed_menu["name_variants"]["fries"] == "Sweet Potato Fries"
    
    # Item count should match
    assert len(processed_menu["items"]) == 4
    
    # Check total number of variants (should be more than just the item count)
    assert len(processed_menu["name_variants"]) > len(processed_menu["items"])