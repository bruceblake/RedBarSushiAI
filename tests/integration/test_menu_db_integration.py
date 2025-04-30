"""
Test the menu database integration functionality.
These tests verify that menu data can be properly stored and retrieved from the database.
"""
import pytest
import json
import os
from flask import current_app

from app.utils.menu_db_store import menu_db_store
from app.utils.menu_utils_db import (
    load_menu_data,
    write_menu_file,
    update_menu_item,
    process_product_changes
)
from app.utils.menu_migration import migrate_menu_to_database, verify_menu_migration
from app.models.menu import MenuItem, MenuModifier, MenuModifierGroup


@pytest.fixture
def test_menu_data():
    """Create test menu data for the database tests."""
    return {
        "items": [
            {
                "name": "Test Sushi Roll",
                "price": 12.99,
                "description": "A delicious test sushi roll",
                "category": "Sushi Rolls",
                "available": True,
                "reference_handler": "test-sushi-roll"
            },
            {
                "name": "Spicy Tuna",
                "price": 14.99,
                "description": "Spicy tuna roll with special sauce",
                "category": "Sushi Rolls",
                "available": True,
                "reference_handler": "spicy-tuna-roll"
            }
        ],
        "modifiers": [
            {
                "name": "Extra Wasabi",
                "price": 0.50,
                "available": True,
                "reference_handler": "extra-wasabi"
            },
            {
                "name": "Extra Ginger",
                "price": 0.50,
                "available": True,
                "reference_handler": "extra-ginger"
            }
        ],
        "modifierGroups": [
            {
                "name": "Add Extras",
                "min": 0,
                "max": 5,
                "multiMax": 2,
                "reference_handler": "extras-group",
                "subProducts": ["extra-wasabi", "extra-ginger"]
            }
        ]
    }


@pytest.fixture
def app_with_db(app):
    """Set up the app with an initialized database."""
    with app.app_context():
        # Create tables if they don't exist
        from app import db
        from app.models.menu import MenuItem, MenuModifier, MenuModifierGroup
        db.create_all()
        
        # Clear existing data
        MenuModifierGroup.query.delete()
        MenuModifier.query.delete()
        MenuItem.query.delete()
        db.session.commit()
        
        yield app
        
        # Clean up after tests
        MenuModifierGroup.query.delete()
        MenuModifier.query.delete()
        MenuItem.query.delete()
        db.session.commit()


def test_menu_db_store_initialization(app_with_db):
    """Test that the menu_db_store initializes correctly."""
    with app_with_db.app_context():
        # Force re-initialization
        menu_db_store._initialize_redis()
        assert menu_db_store.initialized is True


def test_migrate_menu_to_database(app_with_db, test_menu_data):
    """Test migrating menu data to the database."""
    with app_with_db.app_context():
        # Write test data to a temporary file
        temp_file = "/tmp/test_menu_data.json"
        with open(temp_file, "w") as f:
            json.dump(test_menu_data, f)
        
        try:
            # Migrate menu data from file to database
            result = migrate_menu_to_database(file_path=temp_file, force=True)
            
            # Verify migration result
            assert result["success"] is True
            assert result["items_count"] == len(test_menu_data["items"])
            assert result["modifiers_count"] == len(test_menu_data["modifiers"])
            assert result["modifier_groups_count"] == len(test_menu_data["modifierGroups"])
            
            # Verify data in database
            items = MenuItem.query.all()
            modifiers = MenuModifier.query.all()
            modifier_groups = MenuModifierGroup.query.all()
            
            assert len(items) == len(test_menu_data["items"])
            assert len(modifiers) == len(test_menu_data["modifiers"])
            assert len(modifier_groups) == len(test_menu_data["modifierGroups"])
            
            # Check if item names match
            item_names = [item.name for item in items]
            expected_names = [item["name"] for item in test_menu_data["items"]]
            assert sorted(item_names) == sorted(expected_names)
            
        finally:
            # Clean up
            if os.path.exists(temp_file):
                os.remove(temp_file)


def test_load_menu_data(app_with_db, test_menu_data):
    """Test loading menu data from the database."""
    with app_with_db.app_context():
        # Store menu data
        menu_db_store.store_menu_data(test_menu_data)
        
        # Load menu data using the function under test
        loaded_data = load_menu_data(force_refresh=True)
        
        # Verify loaded data
        assert len(loaded_data["items"]) == len(test_menu_data["items"])
        assert len(loaded_data["modifiers"]) == len(test_menu_data["modifiers"])
        assert len(loaded_data["modifierGroups"]) == len(test_menu_data["modifierGroups"])
        
        # Check if specific items are present
        item_names = [item["name"] for item in loaded_data["items"]]
        for expected_item in test_menu_data["items"]:
            assert expected_item["name"] in item_names


def test_write_menu_file(app_with_db, test_menu_data):
    """Test writing menu data to both database and file."""
    with app_with_db.app_context():
        # Temporary file path for testing
        temp_file = "/tmp/test_output_menu.json"
        
        try:
            # Write menu data using the function under test
            result = write_menu_file(test_menu_data, file_path=temp_file)
            
            # Verify the result
            assert result is True
            
            # Verify the file was created
            assert os.path.exists(temp_file)
            
            # Read the file to check contents
            with open(temp_file, "r") as f:
                file_data = json.load(f)
                
            assert len(file_data["items"]) == len(test_menu_data["items"])
            
            # Verify data in database
            items = MenuItem.query.all()
            assert len(items) == len(test_menu_data["items"])
            
        finally:
            # Clean up
            if os.path.exists(temp_file):
                os.remove(temp_file)


def test_update_menu_item(app_with_db, test_menu_data):
    """Test updating a menu item in the database."""
    with app_with_db.app_context():
        # Store initial menu data
        menu_db_store.store_menu_data(test_menu_data)
        
        # Update an item
        test_item = test_menu_data["items"][0].copy()
        test_item["price"] = 15.99
        test_item["description"] = "Updated description"
        
        # Update the item using the function under test
        result = update_menu_item(test_item)
        
        # Verify the result
        assert result is True
        
        # Verify the update in the database
        item = MenuItem.query.filter_by(reference_handler=test_item["reference_handler"]).first()
        assert item is not None
        assert item.price == 15.99
        assert item.description == "Updated description"
        
        # Load menu data to verify the update is reflected there
        loaded_data = load_menu_data(force_refresh=True)
        updated_item = next((item for item in loaded_data["items"] 
                            if item["reference_handler"] == test_item["reference_handler"]), None)
        
        assert updated_item is not None
        assert updated_item["price"] == 15.99
        assert updated_item["description"] == "Updated description"


def test_process_product_changes(app_with_db, test_menu_data):
    """Test processing product changes from Deliverect."""
    with app_with_db.app_context():
        # Store initial menu data
        menu_db_store.store_menu_data(test_menu_data)
        
        # Define product changes
        product_id = test_menu_data["items"][0]["reference_handler"]
        change_data = {
            "name": test_menu_data["items"][0]["name"],
            "price": 16.99,
            "available": False,
            "description": "Changed through Deliverect"
        }
        
        # Process the changes
        result = process_product_changes(product_id, change_data)
        
        # Verify the result
        assert result is True
        
        # Verify changes in the database
        item = MenuItem.query.filter_by(reference_handler=product_id).first()
        assert item is not None
        assert item.price == 16.99
        assert item.available is False
        assert item.description == "Changed through Deliverect"
        
        # Load menu data to verify changes are reflected
        loaded_data = load_menu_data(force_refresh=True)
        updated_item = next((item for item in loaded_data["items"] 
                            if item["reference_handler"] == product_id), None)
        
        assert updated_item is not None
        assert updated_item["price"] == 16.99
        assert updated_item["available"] is False
        assert updated_item["description"] == "Changed through Deliverect"


def test_menu_update_endpoint(app_with_db, client, test_menu_data):
    """Test the menu update endpoint using database storage."""
    with app_with_db.app_context():
        # Test the menu update endpoint
        response = client.post('/menu_update', json=test_menu_data)
        
        # Verify the response
        assert response.status_code == 200
        
        # Verify data in database
        items = MenuItem.query.all()
        modifiers = MenuModifier.query.all()
        modifier_groups = MenuModifierGroup.query.all()
        
        assert len(items) == len(test_menu_data["items"])
        assert len(modifiers) == len(test_menu_data["modifiers"])
        assert len(modifier_groups) == len(test_menu_data["modifierGroups"])
        
        # Verify menu data can be loaded from database
        loaded_data = load_menu_data(force_refresh=True)
        assert len(loaded_data["items"]) == len(test_menu_data["items"])