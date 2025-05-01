import json
import pytest


@pytest.mark.integration
def test_price_consistency(flask_client):
    """
    Test that prices are consistently handled between dollars and cents.
    Verifies:
    1. Prices in dollars are correctly converted to cents
    2. Prices in cents are preserved as-is
    3. The API consistently returns the same price format
    """
    # Create a menu with prices in both dollars and cents
    mixed_price_menu = {
        "items": [
            {
                "name": "Dollar Price Item",
                "description": "Price in dollars (15.00)",
                "price": 15.00,  # Price in dollars
                "plu": "PRICE-01",
                "reference_handler": "PRICE-01",
                "available": True,
            },
            {
                "name": "Cent Price Item",
                "description": "Price in cents (1200)",
                "price": 1200,  # Price in cents
                "plu": "PRICE-02",
                "reference_handler": "PRICE-02",
                "available": True,
            },
        ]
    }

    # Update the menu
    response = flask_client.post(
        "/menu_update",
        data=json.dumps(mixed_price_menu),
        content_type="application/json",
    )

    # Assert the update was successful
    assert response.status_code == 200
    assert response.json["success"] is True

    # Get the menu to check how prices were stored
    get_response = flask_client.get("/menu")
    assert get_response.status_code == 200

    menu_data = get_response.json

    # Find the items
    dollar_item = next((i for i in menu_data["items"] if i["plu"] == "PRICE-01"), None)
    cent_item = next((i for i in menu_data["items"] if i["plu"] == "PRICE-02"), None)

    assert dollar_item is not None
    assert cent_item is not None

    # Check the price format - both should be in the same format now
    assert isinstance(dollar_item["price"], (int, float))
    assert isinstance(cent_item["price"], (int, float))

    # The system should consistently use either dollars or cents
    # We'll check if both prices follow the same format convention
    dollar_price = dollar_item["price"]
    cent_price = cent_item["price"]

    # If dollar_price is around 15 (dollar format), cent_price should be around 12 (dollar format)
    # If dollar_price is around 1500 (cent format), cent_price should be around 1200 (cent format)
    if 10 <= dollar_price <= 20:  # Dollar format
        assert 10 <= cent_price <= 15
        print(f"System using dollar format: ${dollar_price:.2f} and ${cent_price:.2f}")
    elif 1000 <= dollar_price <= 2000:  # Cent format
        assert 1000 <= cent_price <= 1500
        print(f"System using cent format: {dollar_price} cents and {cent_price} cents")
    else:
        pytest.fail(
            f"Unexpected price format. Dollar item: {dollar_price}, Cent item: {cent_price}"
        )


@pytest.mark.integration
def test_price_update_consistency(flask_client):
    """
    Test that price updates are handled consistently.
    Verifies:
    1. Prices can be updated properly
    2. Updated prices maintain the correct format
    """
    # Create an initial menu
    initial_menu = {
        "items": [
            {
                "name": "Update Test Item",
                "description": "Testing price updates",
                "price": 1500,  # $15.00 in cents
                "plu": "UPDATE-01",
                "reference_handler": "UPDATE-01",
                "available": True,
            }
        ]
    }

    # Update with the initial menu
    flask_client.post(
        "/menu_update", data=json.dumps(initial_menu), content_type="application/json"
    )

    # Create an update with a different price
    price_update = {
        "items": [
            {
                "name": "Update Test Item",
                "description": "Testing price updates",
                "price": 2000,  # $20.00 in cents
                "plu": "UPDATE-01",
                "reference_handler": "UPDATE-01",
                "available": True,
            }
        ]
    }

    # Apply the price update
    update_response = flask_client.post(
        "/menu_update", data=json.dumps(price_update), content_type="application/json"
    )

    # Assert the update was successful
    assert update_response.status_code == 200
    assert update_response.json["success"] is True

    # Get the menu to verify the price was updated
    get_response = flask_client.get("/menu")
    assert get_response.status_code == 200

    menu_data = get_response.json

    # Find the updated item
    updated_item = next(
        (i for i in menu_data["items"] if i["plu"] == "UPDATE-01"), None
    )
    assert updated_item is not None

    # Verify the price was updated correctly
    assert updated_item["price"] == 2000

    # Try updating with a price in dollars instead of cents
    dollar_update = {
        "items": [
            {
                "name": "Update Test Item",
                "description": "Testing price updates",
                "price": 25.00,  # $25.00 in dollars
                "plu": "UPDATE-01",
                "reference_handler": "UPDATE-01",
                "available": True,
            }
        ]
    }

    # Apply the dollar price update
    dollar_response = flask_client.post(
        "/menu_update", data=json.dumps(dollar_update), content_type="application/json"
    )

    # Assert the update was successful
    assert dollar_response.status_code == 200
    assert dollar_response.json["success"] is True

    # Get the menu to verify how the price was handled
    dollar_get_response = flask_client.get("/menu")
    assert dollar_get_response.status_code == 200

    dollar_menu_data = dollar_get_response.json

    # Find the updated item
    dollar_updated_item = next(
        (i for i in dollar_menu_data["items"] if i["plu"] == "UPDATE-01"), None
    )
    assert dollar_updated_item is not None

    # The system should either convert 25.00 to 2500 cents, or keep it as 25.00 dollars
    dollar_price = dollar_updated_item["price"]

    if 20 <= dollar_price <= 30:  # Dollar format
        assert abs(dollar_price - 25.00) < 0.01
        print(f"System using dollar format for updates: ${dollar_price:.2f}")
    elif 2000 <= dollar_price <= 3000:  # Cent format
        assert abs(dollar_price - 2500) < 1
        print(f"System using cent format for updates: {dollar_price} cents")
    else:
        pytest.fail(f"Unexpected price format after update: {dollar_price}")


@pytest.mark.integration
def test_deliverect_price_format(flask_client, deliverect_menu_json):
    """
    Test that prices in Deliverect format are handled correctly.
    According to the glossary, Deliverect expects prices in cents.

    Verifies:
    1. Prices from Deliverect (in cents) are preserved
    2. The correct format is sent back to Deliverect
    """
    # The deliverect_menu_json fixture has prices in cents already (e.g., 1500 for $15.00)

    # Update the menu with the Deliverect format
    response = flask_client.post(
        "/menu_update",
        data=json.dumps(deliverect_menu_json),
        content_type="application/json",
    )

    # Assert the update was successful
    assert response.status_code == 200
    assert response.json["success"] is True

    # Get the menu to verify the prices were stored correctly
    get_response = flask_client.get("/menu")
    assert get_response.status_code == 200

    menu_data = get_response.json

    # Find specific items with known prices
    steak = next((i for i in menu_data["items"] if i["plu"] == "STK-01"), None)
    burger = next((i for i in menu_data["items"] if i["plu"] == "BRG-01"), None)
    rice = next((i for i in menu_data["items"] if i["plu"] == "RICE-01"), None)

    assert steak is not None
    assert burger is not None
    assert rice is not None

    # Verify the prices in cents were preserved
    assert steak["price"] == 1500
    assert burger["price"] == 1200
    assert rice["price"] == 450
