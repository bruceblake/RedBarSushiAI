import pytest
from app import create_app
from flask import Flask
from unittest.mock import patch, MagicMock

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    return app.test_client()

def test_deliverect_deep_scan(client):
    """Test that menu_update endpoint can handle deeply nested menu data."""
    # Create a sample menu with deeply nested structure
    sample_menu = [
        {
            "menu": {
                "menuId": "12345",
                "name": "Main Menu",
                "categories": [
                    {
                        "id": "cat1",
                        "name": "Burgers",
                        "products": [
                            {
                                "id": "prod1",
                                "name": "Cheeseburger",
                                "price": 1095,  # in cents
                                "plu": "BURG-CHEESE",
                                "description": "Juicy beef patty with melted cheese",
                                "available": True
                            },
                            {
                                "id": "prod2",
                                "name": "Veggie Burger",
                                "price": 995,  # in cents
                                "plu": "BURG-VEGGIE",
                                "description": "Plant-based patty with toppings",
                                "available": True
                            }
                        ]
                    }
                ]
            }
        }
    ]
    
    # Send request to menu_update endpoint
    response = client.post('/menu_update', json=sample_menu)
    
    # Check response
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['items'] == 3  # Category + two items in this format
    
    # Get the processed menu
    from app.utils.menu_utils import load_menu_data
    menu_data = load_menu_data(force_refresh=True)
    
    # Print all items for debugging
    print("\nMENU ITEMS FROM DEEP SCAN:")
    for item in menu_data.get("items", []):
        print(f"  - {item.get('name')} -> {item.get('reference_handler')}")
    
    # Verify items
    items = menu_data.get("items", [])
    assert len(items) == 3  # Two products + category
    
    # Check specific items
    cheeseburger = next((item for item in items if item.get("name") == "Cheeseburger"), None)
    assert cheeseburger is not None
    assert cheeseburger.get("reference_handler") == "BURG-CHEESE"
    
    veggie_burger = next((item for item in items if item.get("name") == "Veggie Burger"), None)
    assert veggie_burger is not None
    assert veggie_burger.get("reference_handler") == "BURG-VEGGIE"

def test_deliverect_products_scan(client):
    """Test that menu_update endpoint can handle a list with nested products."""
    # Create a sample menu with products in a strange location
    sample_menu = [
        {
            "store": "12345",
            "menuItems": [
                {
                    "id": "prod1",
                    "name": "Cheeseburger",
                    "price": 1095,  # in cents
                    "plu": "BURG-CHEESE",
                    "description": "Juicy beef patty with melted cheese",
                    "available": True
                },
                {
                    "id": "prod2",
                    "name": "Veggie Burger",
                    "price": 995,  # in cents
                    "plu": "BURG-VEGGIE",
                    "description": "Plant-based patty with toppings",
                    "available": True
                }
            ]
        }
    ]
    
    # Send request to menu_update endpoint
    response = client.post('/menu_update', json=sample_menu)
    
    # Check response
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['items'] == 2  # Just two items without category in this format
    
    # Get the processed menu
    from app.utils.menu_utils import load_menu_data
    menu_data = load_menu_data(force_refresh=True)
    
    # Print all items for debugging
    print("\nMENU ITEMS FROM PRODUCTS SCAN:")
    for item in menu_data.get("items", []):
        print(f"  - {item.get('name')} -> {item.get('reference_handler')}")
    
    # Verify items - in this test only the two burgers are returned, no category 
    items = menu_data.get("items", [])
    assert len(items) == 2  # Just two products, no category in this format
    
    # Check specific items
    cheeseburger = next((item for item in items if item.get("name") == "Cheeseburger"), None)
    assert cheeseburger is not None
    assert cheeseburger.get("reference_handler") == "BURG-CHEESE"
    
    veggie_burger = next((item for item in items if item.get("name") == "Veggie Burger"), None)
    assert veggie_burger is not None
    assert veggie_burger.get("reference_handler") == "BURG-VEGGIE"