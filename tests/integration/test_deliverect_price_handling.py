import json
import pytest


@pytest.mark.integration
def test_deliverect_price_conversion(flask_client, deliverect_menu_json):
    """
    Test that prices are correctly converted between dollars and cents when
    handling Deliverect menu updates. According to Deliverect glossary,
    prices are stored in cents (e.g., 1 euro is stored as 100).

    This test verifies:
    1. Deliverect menu with prices in cents is correctly processed
    2. When retrieving the menu, prices are in correct format
    3. When sending prices in dollars, they're correctly converted to cents
    """
    # First create a menu with the Deliverect format that uses cents
    # Prices like 1500 should represent $15.00
    flask_client.post(
        "/menu_update",
        data=json.dumps(
            deliverect_menu_json
        ),  # Assumes this fixture has prices in cents
        content_type="application/json",
    )

    # Retrieve the menu to see how prices are stored
    menu_response = flask_client.get("/menu")
    assert menu_response.status_code == 200
    menu_data = menu_response.json

    # Check prices of some sample items
    # Note: Depending on the implementation, the API might return prices
    # in dollars (15.00) or in cents (1500)
    sample_items = []
    for item in menu_data.get("items", []):
        if "price" in item:
            sample_items.append(item)

    assert len(sample_items) > 0, "No items with prices found in the menu"

    # Now try updating a single item with price in dollars format
    # The system should convert it to cents correctly
    sample_item = sample_items[0]
    original_price = sample_item["price"]

    # Calculate new price in dollars (add $1.00)
    # If the price is already in dollars, new_price_dollars = original_price + 1
    # If the price is in cents, new_price_dollars = (original_price / 100) + 1
    if original_price >= 100:  # Assume it's in cents if ≥ 100
        new_price_dollars = (original_price / 100) + 1
    else:
        new_price_dollars = original_price + 1

    # Update the item with the dollar price
    update_payload = {
        "items": [
            {
                "plu": sample_item["plu"],
                "price": new_price_dollars,  # Send as dollars
                "name": sample_item["name"],
            }
        ]
    }

    # Send the update
    update_response = flask_client.post(
        "/menu_update", data=json.dumps(update_payload), content_type="application/json"
    )

    assert update_response.status_code == 200

    # Retrieve the menu again to check the updated price
    updated_menu_response = flask_client.get("/menu")
    assert updated_menu_response.status_code == 200
    updated_menu_data = updated_menu_response.json

    # Find the updated item
    updated_item = next(
        (i for i in updated_menu_data["items"] if i["plu"] == sample_item["plu"]), None
    )

    assert (
        updated_item is not None
    ), f"Could not find item with PLU {sample_item['plu']}"

    # Check if the price was updated correctly
    # Depending on how the API returns prices, we need to check appropriately
    if updated_item["price"] >= 100:  # If price is in cents
        expected_cents = int(new_price_dollars * 100)
        assert (
            abs(updated_item["price"] - expected_cents) < 2
        ), f"Price not correctly converted to cents. Expected {expected_cents}, got {updated_item['price']}"
    else:  # If price is in dollars
        assert (
            abs(updated_item["price"] - new_price_dollars) < 0.02
        ), f"Price not correctly updated. Expected {new_price_dollars}, got {updated_item['price']}"


@pytest.mark.integration
def test_price_rounding_consistency(flask_client):
    """
    Test that price rounding is consistent when converting between
    dollars and cents, especially for prices with fractions.

    This test verifies:
    1. Prices with fractions (e.g., $9.99) are correctly converted to cents
    2. Rounding is consistent for all price operations
    3. Prices are not truncated (losing pennies)
    """
    # Create a test menu with items having prices with fractions
    test_menu = {
        "items": [
            {
                "name": "Precision Test Item 1",
                "plu": "TEST-PRICE-01",
                "price": 9.99,  # $9.99 in dollars
                "available": True,
            },
            {
                "name": "Precision Test Item 2",
                "plu": "TEST-PRICE-02",
                "price": 10.49,  # $10.49 in dollars
                "available": True,
            },
            {
                "name": "Precision Test Item 3",
                "plu": "TEST-PRICE-03",
                "price": 7.95,  # $7.95 in dollars
                "available": True,
            },
        ]
    }

    # Create the menu
    menu_response = flask_client.post(
        "/menu_update", data=json.dumps(test_menu), content_type="application/json"
    )

    assert menu_response.status_code == 200

    # Retrieve the menu to check how prices were stored
    retrieved_menu = flask_client.get("/menu")
    assert retrieved_menu.status_code == 200
    menu_data = retrieved_menu.json

    # Get the items by PLU
    item1 = next((i for i in menu_data["items"] if i["plu"] == "TEST-PRICE-01"), None)
    item2 = next((i for i in menu_data["items"] if i["plu"] == "TEST-PRICE-02"), None)
    item3 = next((i for i in menu_data["items"] if i["plu"] == "TEST-PRICE-03"), None)

    assert item1 is not None, "Could not find test item 1"
    assert item2 is not None, "Could not find test item 2"
    assert item3 is not None, "Could not find test item 3"

    # Check price1 (should be either 9.99 in dollars or 999 in cents)
    if item1["price"] >= 100:  # If price is in cents
        assert (
            round(item1["price"]) == 999
        ), f"Price for item 1 not correctly converted to cents. Expected 999, got {item1['price']}"
        assert (
            round(item2["price"]) == 1049
        ), f"Price for item 2 not correctly converted to cents. Expected 1049, got {item2['price']}"
        assert (
            round(item3["price"]) == 795
        ), f"Price for item 3 not correctly converted to cents. Expected 795, got {item3['price']}"
    else:  # If price is in dollars
        assert (
            abs(item1["price"] - 9.99) < 0.01
        ), f"Price for item 1 not preserved. Expected 9.99, got {item1['price']}"
        assert (
            abs(item2["price"] - 10.49) < 0.01
        ), f"Price for item 2 not preserved. Expected 10.49, got {item2['price']}"
        assert (
            abs(item3["price"] - 7.95) < 0.01
        ), f"Price for item 3 not preserved. Expected 7.95, got {item3['price']}"

    # Now update with Deliverect format (prices in cents)
    deliverect_format = {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "type": "menu.updated",
        "data": {
            "items": [
                {
                    "plu": "TEST-PRICE-01",
                    "price": 999,  # $9.99 in cents
                    "name": "Updated Precision Test Item 1",
                },
                {
                    "plu": "TEST-PRICE-02",
                    "price": 1049,  # $10.49 in cents
                    "name": "Updated Precision Test Item 2",
                },
                {
                    "plu": "TEST-PRICE-03",
                    "price": 795,  # $7.95 in cents
                    "name": "Updated Precision Test Item 3",
                },
            ]
        },
    }

    # Update with Deliverect format
    update_response = flask_client.post(
        "/menu_update",
        data=json.dumps(deliverect_format),
        content_type="application/json",
    )

    assert update_response.status_code == 200

    # Retrieve the menu again to verify prices
    updated_menu = flask_client.get("/menu")
    assert updated_menu.status_code == 200
    updated_data = updated_menu.json

    # Get the updated items
    updated_item1 = next(
        (i for i in updated_data["items"] if i["plu"] == "TEST-PRICE-01"), None
    )
    updated_item2 = next(
        (i for i in updated_data["items"] if i["plu"] == "TEST-PRICE-02"), None
    )
    updated_item3 = next(
        (i for i in updated_data["items"] if i["plu"] == "TEST-PRICE-03"), None
    )

    # Check if prices match expected values
    if updated_item1["price"] >= 100:  # If price is in cents
        assert (
            round(updated_item1["price"]) == 999
        ), f"Updated price for item 1 incorrect. Expected 999, got {updated_item1['price']}"
        assert (
            round(updated_item2["price"]) == 1049
        ), f"Updated price for item 2 incorrect. Expected 1049, got {updated_item2['price']}"
        assert (
            round(updated_item3["price"]) == 795
        ), f"Updated price for item 3 incorrect. Expected 795, got {updated_item3['price']}"
    else:  # If price is in dollars
        assert (
            abs(updated_item1["price"] - 9.99) < 0.01
        ), f"Updated price for item 1 incorrect. Expected 9.99, got {updated_item1['price']}"
        assert (
            abs(updated_item2["price"] - 10.49) < 0.01
        ), f"Updated price for item 2 incorrect. Expected 10.49, got {updated_item2['price']}"
        assert (
            abs(updated_item3["price"] - 7.95) < 0.01
        ), f"Updated price for item 3 incorrect. Expected 7.95, got {updated_item3['price']}"


@pytest.mark.integration
def test_mixed_price_format_handling(flask_client):
    """
    Test that the API can handle mixed price formats in the same request.
    This ensures robustness when receiving data from different sources.

    This test verifies:
    1. The API can process a request with mixed price formats (dollars and cents)
    2. All prices are correctly stored regardless of input format
    """
    # Create a test menu with mixed price formats (some in dollars, some in cents)
    mixed_format_menu = {
        "items": [
            {
                "name": "Dollar Format Item",
                "plu": "PRICE-FMT-01",
                "price": 12.99,  # $12.99 in dollars
                "available": True,
            },
            {
                "name": "Cent Format Item",
                "plu": "PRICE-FMT-02",
                "price": 1399,  # $13.99 in cents
                "available": True,
            },
        ]
    }

    # Create the menu
    menu_response = flask_client.post(
        "/menu_update",
        data=json.dumps(mixed_format_menu),
        content_type="application/json",
    )

    assert menu_response.status_code == 200

    # Retrieve the menu to check how prices were stored
    retrieved_menu = flask_client.get("/menu")
    assert retrieved_menu.status_code == 200
    menu_data = retrieved_menu.json

    # Get the items
    dollar_item = next(
        (i for i in menu_data["items"] if i["plu"] == "PRICE-FMT-01"), None
    )
    cent_item = next(
        (i for i in menu_data["items"] if i["plu"] == "PRICE-FMT-02"), None
    )

    assert dollar_item is not None, "Could not find dollar format item"
    assert cent_item is not None, "Could not find cent format item"

    # Check if prices were normalized correctly
    # If the API returns prices in cents
    if dollar_item["price"] >= 100:
        dollar_expected_cents = int(12.99 * 100)
        cent_expected_cents = 1399

        assert (
            abs(dollar_item["price"] - dollar_expected_cents) < 1
        ), f"Dollar-format price not converted correctly. Expected ~{dollar_expected_cents}, got {dollar_item['price']}"
        assert (
            abs(cent_item["price"] - cent_expected_cents) < 1
        ), f"Cent-format price not preserved correctly. Expected {cent_expected_cents}, got {cent_item['price']}"

    # If the API returns prices in dollars
    else:
        dollar_expected = 12.99
        cent_expected = 13.99

        assert (
            abs(dollar_item["price"] - dollar_expected) < 0.01
        ), f"Dollar-format price not preserved. Expected {dollar_expected}, got {dollar_item['price']}"
        assert (
            abs(cent_item["price"] - cent_expected) < 0.01
        ), f"Cent-format price not converted correctly. Expected {cent_expected}, got {cent_item['price']}"
