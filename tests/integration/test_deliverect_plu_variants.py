import json
import pytest

@pytest.mark.integration
def test_plu_variant_handling(flask_client):
    """
    Test that PLUs with special formats like ### are correctly handled.
    In Deliverect, PLUs containing ### are variants or linked products.
    
    This test verifies:
    1. Products with PLUs containing ### can be correctly processed
    2. The base PLU (without ###) is extracted correctly
    3. Reference pricing works properly for variant products
    """
    # Create a menu with base products and variant products
    variant_menu = {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "type": "menu.updated",
        "data": {
            "categories": [
                {
                    "id": "BURG-CAT",
                    "name": "Burgers",
                    "description": "Burger options"
                }
            ],
            "items": [
                # Base products with prices
                {
                    "plu": "P-BURG-CHK",
                    "name": "Chicken Burger",
                    "price": 899,  # $8.99 in cents
                    "categoryId": "BURG-CAT",
                    "available": True
                },
                {
                    "plu": "P-BURG-CHE",
                    "name": "Cheeseburger",
                    "price": 949,  # $9.49 in cents
                    "categoryId": "BURG-CAT",
                    "available": True
                },
                # Variant products with ### format - these should inherit pricing from base products
                {
                    "plu": "P-BURG-CHK###PRNT",
                    "referenceId": "P-BURG-CHK",  # Reference to base product
                    "name": "Chicken Burger Combo",
                    "categoryId": "BURG-CAT",
                    "available": True
                },
                {
                    "plu": "P-BURG-CHE###PRNT",
                    "referenceId": "P-BURG-CHE",  # Reference to base product
                    "name": "Cheeseburger Combo",
                    "categoryId": "BURG-CAT",
                    "available": True
                }
            ]
        }
    }
    
    # Submit the menu with variant PLUs
    response = flask_client.post(
        '/menu_update',
        data=json.dumps(variant_menu),
        content_type='application/json'
    )
    
    assert response.status_code == 200
    
    # Retrieve the processed menu
    menu_response = flask_client.get('/menu')
    assert menu_response.status_code == 200
    menu_data = menu_response.json
    
    # Get the items by PLU
    items = {item.get('plu', ''): item for item in menu_data.get('items', [])}
    
    # Check that all PLUs are present in the menu
    assert 'P-BURG-CHK' in items, "Base PLU 'P-BURG-CHK' not found in menu"
    assert 'P-BURG-CHE' in items, "Base PLU 'P-BURG-CHE' not found in menu"
    
    # Check pricing for base products
    assert items['P-BURG-CHK']['price'] == 8.99, f"Expected base product price 8.99, got {items['P-BURG-CHK']['price']}"
    assert items['P-BURG-CHE']['price'] == 9.49, f"Expected base product price 9.49, got {items['P-BURG-CHE']['price']}"
    
    # Verify the variant products - may be represented differently depending on implementation
    chicken_variant = None
    cheese_variant = None
    
    # Try to find the variant products by name
    for item in menu_data.get('items', []):
        if "Chicken Burger Combo" in item.get('name', ''):
            chicken_variant = item
        elif "Cheeseburger Combo" in item.get('name', ''):
            cheese_variant = item
            
    # Check that variants were found
    assert chicken_variant is not None, "Chicken Burger variant not found in menu"
    assert cheese_variant is not None, "Cheeseburger variant not found in menu"
    
    # Verify the variant products have valid prices (either own price or reference price)
    assert chicken_variant['price'] > 0, f"Chicken Burger variant has invalid price: {chicken_variant['price']}"
    assert cheese_variant['price'] > 0, f"Cheeseburger variant has invalid price: {cheese_variant['price']}"
    
    # Test updating a variant price
    update_payload = {
        "items": [
            {
                "plu": chicken_variant['plu'],
                "price": 1099,  # $10.99 in cents
                "name": chicken_variant['name']
            }
        ]
    }
    
    # Submit the price update
    update_response = flask_client.post(
        '/menu_update',
        data=json.dumps(update_payload),
        content_type='application/json'
    )
    
    assert update_response.status_code == 200
    
    # Retrieve the menu again to confirm the price update
    updated_menu = flask_client.get('/menu')
    assert updated_menu.status_code == 200
    updated_data = updated_menu.json
    
    # Find the updated variant
    updated_chicken_variant = None
    for item in updated_data.get('items', []):
        if item.get('plu') == chicken_variant['plu']:
            updated_chicken_variant = item
            break
    
    assert updated_chicken_variant is not None, "Couldn't find updated Chicken Burger variant"
    assert updated_chicken_variant['price'] == 10.99, f"Expected updated price 10.99, got {updated_chicken_variant['price']}"

@pytest.mark.integration
def test_missing_price_handling(flask_client):
    """
    Test that products with missing prices are handled correctly,
    particularly for products with PLUs containing ###.
    
    This test verifies:
    1. Products with missing prices but valid referenceId get prices from referenced products
    2. Products with missing prices and no valid references are rejected
    """
    # Create a menu with base product first to ensure database is not empty
    base_menu = {
        "items": [
            {
                "plu": "BASE-PROD",
                "name": "Base Product",
                "price": 1299,  # $12.99 in cents
                "available": True
            }
        ]
    }
    
    # Submit base menu
    response = flask_client.post(
        '/menu_update',
        data=json.dumps(base_menu),
        content_type='application/json'
    )
    
    assert response.status_code == 200
    
    # Now test each scenario:
    
    # 1. Valid reference - should use reference price
    valid_reference = {
        "items": [
            {
                "plu": "REF-PROD###PRNT",
                "referenceId": "BASE-PROD",  # Valid reference
                "name": "Referenced Product",
                "price": 0,  # Zero price - should use reference price
                "available": True
            }
        ]
    }
    
    response1 = flask_client.post(
        '/menu_update',
        data=json.dumps(valid_reference),
        content_type='application/json'
    )
    
    assert response1.status_code == 200, "Failed to add product with valid referenceId"
    
    # 2. Invalid reference but ### format - should extract base PLU
    extracted_base = {
        "items": [
            {
                "plu": "BASE-PROD###PRNT",  # Contains BASE-PROD as base PLU
                "name": "Base PLU Extracted",
                "price": 0,  # Zero price - should extract base PLU
                "available": True
            }
        ]
    }
    
    response2 = flask_client.post(
        '/menu_update',
        data=json.dumps(extracted_base),
        content_type='application/json'
    )
    
    assert response2.status_code == 200, "Failed to add product with extractable base PLU"
    
    # 3. Missing price with no reference - should be rejected
    missing_price = {
        "items": [
            {
                "plu": "MISSING-PRICE",
                "name": "Missing Price Product",
                "price": 0,  # Zero price and no reference - should be rejected
                "available": True
            }
        ]
    }
    
    response3 = flask_client.post(
        '/menu_update',
        data=json.dumps(missing_price),
        content_type='application/json'
    )
    
    assert response3.status_code == 400, "Should reject product with missing price and no reference"
    
    # Verify the menu to ensure the first two products were added successfully
    menu_response = flask_client.get('/menu')
    assert menu_response.status_code == 200
    menu_data = menu_response.json
    
    # Find products by name (more reliable than PLU which might be transformed)
    referenced_product = None
    extracted_product = None
    
    for item in menu_data.get('items', []):
        if item.get('name') == "Referenced Product":
            referenced_product = item
        elif item.get('name') == "Base PLU Extracted":
            extracted_product = item
    
    # Verify referenced product pricing worked
    assert referenced_product is not None, "Referenced product not found in menu"
    assert referenced_product['price'] == 12.99, \
        f"Referenced product has incorrect price. Expected 12.99, got {referenced_product['price']}"
    
    # Verify base PLU extraction worked
    assert extracted_product is not None, "Extracted base product not found in menu"
    assert extracted_product['price'] == 12.99, \
        f"Extracted base product has incorrect price. Expected 12.99, got {extracted_product['price']}"

@pytest.mark.integration
def test_empty_database_handling(flask_client):
    """
    Test that the system handles the case when the database is empty.
    
    The test validates:
    1. The validator correctly rejects items with missing prices when database is empty
    2. Error message is informative about the empty database condition
    """
    # First clear any existing menu data (this depends on your app having an endpoint to do this)
    # If your app doesn't have such an endpoint, you'll need to directly clear the database tables
    try:
        clear_resp = flask_client.post('/clear_menu_data', content_type='application/json')
        assert clear_resp.status_code in [200, 204], "Failed to clear menu data"
    except:
        # If no clear endpoint exists, this test may be skipped or alternative setup used
        pytest.skip("No way to clear menu data for empty database test")
    
    # Now try to add an item with missing price to empty database
    empty_db_menu = {
        "items": [
            {
                "plu": "P-BURG-CHE",
                "name": "Cheeseburger",
                "price": 0,  # Invalid price
                "available": True
            }
        ]
    }
    
    # This should be rejected with a 400 error
    response = flask_client.post(
        '/menu_update',
        data=json.dumps(empty_db_menu),
        content_type='application/json'
    )
    
    # Check that the request was rejected
    assert response.status_code == 400, "Should reject item with invalid price when database is empty"
    
    # Check that error message mentions empty database
    assert "database is empty" in response.data.decode('utf-8').lower(), \
        "Error message should mention empty database"

@pytest.mark.integration
def test_variant_product_handling(flask_client):
    """
    Test that variant products with zero prices are properly handled.
    
    Per Deliverect documentation, variant products can have zero price with
    their variant options having the actual prices.
    
    This test verifies:
    1. A parent variant product can have a zero price
    2. Variant group with variant options are processed correctly
    """
    # Create a menu with variant products (following Deliverect variant structure)
    variant_menu = {
        "items": [
            # Parent variant product - zero price is valid
            {
                "plu": "VAR-PROD-1",
                "name": "Chicken Tenders",
                "price": 0,  # Zero price is valid for variant products
                "available": True,
                "isVariant": True,
                "subProducts": ["MG-VAR-1"]  # Reference to variant group
            },
            # Variant group (modifier group)
            {
                "plu": "MG-VAR-1",
                "name": "How many pieces?",
                "productType": 3,  # Modifier group type
                "isVariantGroup": True,
                "min": 1,
                "max": 1,
                "subProducts": ["VAR-1", "VAR-2", "VAR-3"]  # Variant options
            },
            # Variant options with their own prices
            {
                "plu": "VAR-1",
                "name": "3 Pieces",
                "price": 800,  # $8.00
                "available": True
            },
            {
                "plu": "VAR-2",
                "name": "6 Pieces", 
                "price": 1100,  # $11.00
                "available": True
            },
            {
                "plu": "VAR-3",
                "name": "9 Pieces",
                "price": 1350,  # $13.50
                "available": True
            }
        ]
    }
    
    # Submit variant menu
    response = flask_client.post(
        '/menu_update',
        data=json.dumps(variant_menu),
        content_type='application/json'
    )
    
    # Should succeed despite parent product having zero price
    assert response.status_code == 200, "Failed to accept variant product with zero price"
    
    # Retrieve the menu to verify
    menu_response = flask_client.get('/menu')
    assert menu_response.status_code == 200
    menu_data = menu_response.json
    
    # Find the parent variant product
    parent_variant = None
    for item in menu_data.get('items', []):
        if item.get('name') == "Chicken Tenders":
            parent_variant = item
            break
    
    # Verify the parent variant has zero price and is marked as variant
    assert parent_variant is not None, "Parent variant product not found in menu"
    assert parent_variant['price'] == 0, f"Parent variant product should have zero price, got {parent_variant['price']}"
    assert parent_variant.get('is_variant') == True, "Parent product should be marked as variant"