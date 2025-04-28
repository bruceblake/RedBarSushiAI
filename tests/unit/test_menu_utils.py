import json
import pytest
import os
import tempfile
from unittest import mock

# Import the modules to be tested
from app.utils.menu_utils import load_menu, save_menu, update_menu_items, find_item_by_plu
from app.utils.menu_validator import validate_menu

@pytest.mark.unit
def test_load_menu():
    """
    Test the load_menu function.
    
    This tests that load_menu:
    1. Correctly loads menu data from a file
    2. Returns an empty menu structure if the file doesn't exist
    3. Properly handles invalid JSON 
    """
    # Test loading from a valid file
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp_file:
        file_path = tmp_file.name
        try:
            # Create a test menu file
            test_menu = {
                "items": [
                    {
                        "name": "Test Item",
                        "price": 10.99,
                        "plu": "TEST-1"
                    }
                ],
                "modifiers": [],
                "modifierGroups": []
            }
            
            with open(file_path, 'w') as f:
                json.dump(test_menu, f)
            
            # Test loading the menu
            loaded_menu = load_menu(file_path=file_path)
            
            # Verify the menu was loaded correctly
            assert loaded_menu is not None
            assert "items" in loaded_menu
            assert len(loaded_menu["items"]) == 1
            assert loaded_menu["items"][0]["name"] == "Test Item"
        finally:
            # Clean up
            if os.path.exists(file_path):
                os.remove(file_path)
    
    # Test loading a non-existent file
    non_existent_path = "/tmp/non_existent_menu_file.json"
    if os.path.exists(non_existent_path):
        os.remove(non_existent_path)
        
    # Should return empty menu structure
    empty_menu = load_menu(file_path=non_existent_path)
    assert empty_menu is not None
    assert "items" in empty_menu
    assert len(empty_menu["items"]) == 0
    assert "modifiers" in empty_menu
    assert "modifierGroups" in empty_menu
    
    # Test loading an invalid JSON file
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp_file:
        file_path = tmp_file.name
        try:
            # Create an invalid JSON file
            with open(file_path, 'w') as f:
                f.write("This is not valid JSON")
            
            # Should return empty menu structure
            invalid_menu = load_menu(file_path=file_path)
            assert invalid_menu is not None
            assert "items" in invalid_menu
            assert len(invalid_menu["items"]) == 0
        finally:
            # Clean up
            if os.path.exists(file_path):
                os.remove(file_path)

@pytest.mark.unit
def test_save_menu():
    """
    Test the save_menu function.
    
    This tests that save_menu:
    1. Correctly saves menu data to a file
    2. Creates the directory if it doesn't exist
    3. Handles errors gracefully
    """
    # Test saving to a file
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp_file:
        file_path = tmp_file.name
        try:
            # Create a test menu
            test_menu = {
                "items": [
                    {
                        "name": "Test Item",
                        "price": 10.99,
                        "plu": "TEST-1"
                    }
                ],
                "modifiers": [],
                "modifierGroups": []
            }
            
            # Save the menu
            save_menu(test_menu, file_path=file_path)
            
            # Verify the file was created
            assert os.path.exists(file_path)
            
            # Load the file and verify the contents
            with open(file_path, 'r') as f:
                saved_data = json.load(f)
            
            assert saved_data is not None
            assert "items" in saved_data
            assert len(saved_data["items"]) == 1
            assert saved_data["items"][0]["name"] == "Test Item"
        finally:
            # Clean up
            if os.path.exists(file_path):
                os.remove(file_path)
    
    # Test creating directory if it doesn't exist
    try:
        temp_dir = tempfile.mkdtemp()
        new_dir_path = os.path.join(temp_dir, "new_dir")
        file_path = os.path.join(new_dir_path, "menu.json")
        
        # Directory shouldn't exist yet
        assert not os.path.exists(new_dir_path)
        
        # Create a test menu
        test_menu = {
            "items": [
                {
                    "name": "New Test Item",
                    "price": 12.99,
                    "plu": "TEST-2"
                }
            ],
            "modifiers": [],
            "modifierGroups": []
        }
        
        # Save the menu - should create the directory
        save_menu(test_menu, file_path=file_path)
        
        # Verify the directory and file were created
        assert os.path.exists(new_dir_path)
        assert os.path.exists(file_path)
        
        # Load the file and verify the contents
        with open(file_path, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data is not None
        assert "items" in saved_data
        assert len(saved_data["items"]) == 1
        assert saved_data["items"][0]["name"] == "New Test Item"
    finally:
        # Clean up
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    # Test error handling (permission denied)
    with mock.patch('builtins.open', side_effect=PermissionError("Permission denied")):
        # Should not raise an exception
        save_menu({"items": []}, file_path="/tmp/test_menu.json")

@pytest.mark.unit
def test_update_menu_items():
    """
    Test the update_menu_items function.
    
    This tests that update_menu_items:
    1. Correctly updates existing items
    2. Adds new items if they don't exist
    3. Preserves existing fields not included in the update
    4. Handles PLU matching properly
    """
    # Create a base menu
    base_menu = {
        "items": [
            {
                "name": "Existing Item 1",
                "description": "Original description",
                "price": 10.99,
                "plu": "ITEM-1",
                "available": True,
                "category": "Category 1",
                "extra_field": "should be preserved"
            },
            {
                "name": "Existing Item 2",
                "description": "Another description",
                "price": 12.99,
                "plu": "ITEM-2",
                "available": True,
                "category": "Category 2"
            }
        ],
        "modifiers": [],
        "modifierGroups": []
    }
    
    # Create update data
    update_data = [
        {
            "name": "Updated Item 1",
            "price": 11.99,
            "plu": "ITEM-1"  # Matches existing item
        },
        {
            "name": "New Item",
            "description": "A new item",
            "price": 14.99,
            "plu": "ITEM-3"  # New item
        }
    ]
    
    # Update the menu
    updated_menu = update_menu_items(base_menu, update_data)
    
    # Verify the menu was updated correctly
    assert updated_menu is not None
    assert "items" in updated_menu
    assert len(updated_menu["items"]) == 3  # Should have 3 items now
    
    # Find the items by PLU
    item1 = next((i for i in updated_menu["items"] if i["plu"] == "ITEM-1"), None)
    item2 = next((i for i in updated_menu["items"] if i["plu"] == "ITEM-2"), None)
    item3 = next((i for i in updated_menu["items"] if i["plu"] == "ITEM-3"), None)
    
    # Verify item 1 was updated
    assert item1 is not None
    assert item1["name"] == "Updated Item 1"  # Name was updated
    assert item1["price"] == 11.99  # Price was updated
    assert item1["description"] == "Original description"  # Description was preserved
    assert item1["extra_field"] == "should be preserved"  # Extra field was preserved
    
    # Verify item 2 was untouched
    assert item2 is not None
    assert item2["name"] == "Existing Item 2"
    assert item2["price"] == 12.99
    
    # Verify item 3 was added
    assert item3 is not None
    assert item3["name"] == "New Item"
    assert item3["description"] == "A new item"
    assert item3["price"] == 14.99
    assert item3["plu"] == "ITEM-3"

@pytest.mark.unit
def test_find_item_by_plu():
    """
    Test the find_item_by_plu function.
    
    This tests that find_item_by_plu:
    1. Correctly finds items by PLU
    2. Returns None for non-existent PLUs
    3. Works with different PLU formats
    """
    # Create a test menu
    test_menu = {
        "items": [
            {
                "name": "Item 1",
                "plu": "ITEM-1",
                "price": 10.99
            },
            {
                "name": "Item 2",
                "plu": "ITEM-2",
                "price": 12.99
            },
            {
                "name": "Item with special PLU",
                "plu": "ITEM/3+",
                "price": 14.99
            }
        ],
        "modifiers": [
            {
                "name": "Modifier 1",
                "plu": "MOD-1",
                "price": 1.99
            }
        ],
        "modifierGroups": []
    }
    
    # Test finding existing items
    item1 = find_item_by_plu(test_menu, "ITEM-1")
    assert item1 is not None
    assert item1["name"] == "Item 1"
    
    item2 = find_item_by_plu(test_menu, "ITEM-2")
    assert item2 is not None
    assert item2["name"] == "Item 2"
    
    # Test finding item with special characters in PLU
    item3 = find_item_by_plu(test_menu, "ITEM/3+")
    assert item3 is not None
    assert item3["name"] == "Item with special PLU"
    
    # Test finding a modifier
    modifier1 = find_item_by_plu(test_menu, "MOD-1", item_type="modifier")
    assert modifier1 is not None
    assert modifier1["name"] == "Modifier 1"
    
    # Test non-existent PLU
    non_existent = find_item_by_plu(test_menu, "NON-EXISTENT")
    assert non_existent is None
    
    # Test finding a modifier as an item (should return None)
    modifier_as_item = find_item_by_plu(test_menu, "MOD-1")
    assert modifier_as_item is None
    
    # Test finding an item as a modifier (should return None)
    item_as_modifier = find_item_by_plu(test_menu, "ITEM-1", item_type="modifier")
    assert item_as_modifier is None

@pytest.mark.unit
def test_validate_menu():
    """
    Test the validate_menu function.
    
    This tests that validate_menu:
    1. Correctly identifies and fixes common issues
    2. Works with different menu formats
    3. Handles missing or invalid fields
    """
    # Create a problematic menu
    problematic_menu = {
        "items": [
            {
                "name": 123,  # Non-string name
                "description": None,  # None description
                "price": "10.99",  # String price
                "plu": "ITEM-1",
                "available": "true"  # String boolean
            },
            {
                # Missing name
                "description": "Item without name",
                "price": 12.99,
                "plu": "ITEM-2"
                # Missing available
            },
            {
                "name": "Item with invalid price",
                "description": "Item with non-numeric price",
                "price": "not a price",
                "plu": "ITEM-3",
                "available": True
            }
        ],
        "modifiers": [
            {
                "name": 456,  # Non-string name
                "price": "1.99",  # String price
                "plu": "MOD-1"
            }
        ],
        "modifierGroups": [
            {
                "id": "GROUP-1",
                "name": 789,  # Non-string name
                "minAllowed": "1",  # String number
                "maxAllowed": "2",  # String number
                "modifiers": ["MOD-1"]
            }
        ]
    }
    
    # Validate the menu
    validated_menu = validate_menu(problematic_menu)
    
    # Verify the menu was correctly validated
    assert validated_menu is not None
    assert "items" in validated_menu
    assert len(validated_menu["items"]) == 3
    
    # Check item 1
    item1 = next((i for i in validated_menu["items"] if i["plu"] == "ITEM-1"), None)
    assert item1 is not None
    assert isinstance(item1["name"], str)  # Name should be a string
    assert item1["name"] == "123"  # Converted to string
    assert item1["description"] == ""  # None converted to empty string
    assert isinstance(item1["price"], (int, float))  # Price should be a number
    assert abs(item1["price"] - 10.99) < 0.01  # Converted to number
    assert isinstance(item1["available"], bool)  # Available should be a boolean
    assert item1["available"] is True  # String "true" converted to boolean
    
    # Check item 2
    item2 = next((i for i in validated_menu["items"] if i["plu"] == "ITEM-2"), None)
    assert item2 is not None
    assert "name" in item2  # Should have a default name
    assert isinstance(item2["name"], str)
    assert "available" in item2  # Should have a default available value
    assert isinstance(item2["available"], bool)
    
    # Check item 3
    item3 = next((i for i in validated_menu["items"] if i["plu"] == "ITEM-3"), None)
    assert item3 is not None
    assert isinstance(item3["price"], (int, float))  # Invalid price should be converted to a default
    
    # Check modifier
    modifier1 = next((m for m in validated_menu["modifiers"] if m["plu"] == "MOD-1"), None)
    assert modifier1 is not None
    assert isinstance(modifier1["name"], str)  # Name should be a string
    assert modifier1["name"] == "456"  # Converted to string
    assert isinstance(modifier1["price"], (int, float))  # Price should be a number
    
    # Check modifier group
    group1 = next((g for g in validated_menu["modifierGroups"] if g["id"] == "GROUP-1"), None)
    assert group1 is not None
    assert isinstance(group1["name"], str)  # Name should be a string
    assert group1["name"] == "789"  # Converted to string
    assert isinstance(group1["minAllowed"], (int, float))  # minAllowed should be a number
    assert isinstance(group1["maxAllowed"], (int, float))  # maxAllowed should be a number