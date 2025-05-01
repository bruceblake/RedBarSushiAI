import json
import pytest


@pytest.mark.integration
def test_modifier_structure_preservation(flask_client):
    """
    Test that modifier groups and options are correctly preserved when
    receiving menu updates from Deliverect.

    This test verifies:
    1. Modifier groups are correctly created and linked to items
    2. Modifier options are correctly assigned to their groups
    3. All modifier properties (price, min/max selections) are preserved
    """
    # Create a menu with modifier groups and options
    menu_with_modifiers = {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "type": "menu.updated",
        "data": {
            "categories": [{"id": "CAT-1", "name": "Main Dishes"}],
            "items": [
                {
                    "plu": "ITEM-1",
                    "name": "Pizza",
                    "price": 1299,
                    "categoryId": "CAT-1",
                    "available": True,
                    "modifierGroups": ["MOD-GRP-1", "MOD-GRP-2"],
                }
            ],
            "modifierGroups": [
                {
                    "id": "MOD-GRP-1",
                    "name": "Pizza Toppings",
                    "minSelection": 0,
                    "maxSelection": 5,
                    "modifiers": ["MOD-1", "MOD-2", "MOD-3"],
                },
                {
                    "id": "MOD-GRP-2",
                    "name": "Pizza Base",
                    "minSelection": 1,
                    "maxSelection": 1,
                    "modifiers": ["MOD-4", "MOD-5"],
                },
            ],
            "modifiers": [
                {"id": "MOD-1", "name": "Pepperoni", "price": 199},
                {"id": "MOD-2", "name": "Mushrooms", "price": 149},
                {"id": "MOD-3", "name": "Extra Cheese", "price": 249},
                {"id": "MOD-4", "name": "Thin Crust", "price": 0},
                {"id": "MOD-5", "name": "Deep Dish", "price": 299},
            ],
        },
    }

    # Submit the menu with modifiers
    response = flask_client.post(
        "/menu_update",
        data=json.dumps(menu_with_modifiers),
        content_type="application/json",
    )
    assert response.status_code == 200

    # Get the menu to verify modifier structure
    menu_response = flask_client.get("/menu")
    assert menu_response.status_code == 200
    menu_data = menu_response.json

    # Verify that all components exist
    assert "modifierGroups" in menu_data
    assert "modifiers" in menu_data

    # Check modifier groups
    modifier_groups = {group["id"]: group for group in menu_data["modifierGroups"]}
    assert "MOD-GRP-1" in modifier_groups
    assert "MOD-GRP-2" in modifier_groups

    # Check properties of the first modifier group
    toppings_group = modifier_groups["MOD-GRP-1"]
    assert toppings_group["name"] == "Pizza Toppings"
    assert toppings_group["minSelection"] == 0
    assert toppings_group["maxSelection"] == 5
    assert set(toppings_group["modifiers"]) == set(["MOD-1", "MOD-2", "MOD-3"])

    # Check properties of the second modifier group
    base_group = modifier_groups["MOD-GRP-2"]
    assert base_group["name"] == "Pizza Base"
    assert base_group["minSelection"] == 1
    assert base_group["maxSelection"] == 1
    assert set(base_group["modifiers"]) == set(["MOD-4", "MOD-5"])

    # Check modifiers
    modifiers = {mod["id"]: mod for mod in menu_data["modifiers"]}
    assert len(modifiers) == 5
    assert "MOD-1" in modifiers
    assert "MOD-2" in modifiers
    assert "MOD-3" in modifiers
    assert "MOD-4" in modifiers
    assert "MOD-5" in modifiers

    # Check properties of some modifiers
    assert modifiers["MOD-1"]["name"] == "Pepperoni"
    assert (
        modifiers["MOD-1"]["price"] == 199 or modifiers["MOD-1"]["price"] == 1.99
    )  # Depending on price format

    assert modifiers["MOD-4"]["name"] == "Thin Crust"
    assert modifiers["MOD-4"]["price"] == 0 or modifiers["MOD-4"]["price"] == 0.0

    # Check that the item has modifier groups
    items = {item["plu"]: item for item in menu_data["items"]}
    assert "ITEM-1" in items
    assert "modifierGroups" in items["ITEM-1"]
    assert set(items["ITEM-1"]["modifierGroups"]) == set(["MOD-GRP-1", "MOD-GRP-2"])


@pytest.mark.integration
def test_modifier_update(flask_client):
    """
    Test that modifier updates are correctly handled by the API.
    This includes updating prices, names, and group configurations.

    This test verifies:
    1. Modifier prices can be updated
    2. Modifier groups can be reconfigured
    3. Modifiers can be added/removed from groups
    """
    # Create initial menu with modifiers
    initial_menu = {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "type": "menu.updated",
        "data": {
            "items": [
                {
                    "plu": "BURGER-1",
                    "name": "Cheeseburger",
                    "price": 1099,
                    "available": True,
                    "modifierGroups": ["BURG-MOD-1"],
                }
            ],
            "modifierGroups": [
                {
                    "id": "BURG-MOD-1",
                    "name": "Burger Add-ons",
                    "minSelection": 0,
                    "maxSelection": 3,
                    "modifiers": ["BURG-OPT-1", "BURG-OPT-2", "BURG-OPT-3"],
                }
            ],
            "modifiers": [
                {"id": "BURG-OPT-1", "name": "Extra Cheese", "price": 199},
                {"id": "BURG-OPT-2", "name": "Bacon", "price": 249},
                {"id": "BURG-OPT-3", "name": "Avocado", "price": 299},
            ],
        },
    }

    # Submit the initial menu
    response = flask_client.post(
        "/menu_update", data=json.dumps(initial_menu), content_type="application/json"
    )
    assert response.status_code == 200

    # Update with modifier changes
    updated_menu = {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "type": "menu.updated",
        "data": {
            "items": [
                {
                    "plu": "BURGER-1",
                    "name": "Cheeseburger",
                    "price": 1099,
                    "available": True,
                    "modifierGroups": [
                        "BURG-MOD-1",
                        "BURG-MOD-2",
                    ],  # Added a new modifier group
                }
            ],
            "modifierGroups": [
                {
                    "id": "BURG-MOD-1",
                    "name": "Burger Add-ons",
                    "minSelection": 0,
                    "maxSelection": 5,  # Changed max selection
                    "modifiers": [
                        "BURG-OPT-1",
                        "BURG-OPT-2",
                        "BURG-OPT-3",
                        "BURG-OPT-4",
                    ],  # Added new modifier
                },
                {
                    "id": "BURG-MOD-2",
                    "name": "Cooking Preference",
                    "minSelection": 1,
                    "maxSelection": 1,
                    "modifiers": ["BURG-OPT-5", "BURG-OPT-6", "BURG-OPT-7"],
                },
            ],
            "modifiers": [
                {
                    "id": "BURG-OPT-1",
                    "name": "Extra Cheese",
                    "price": 249,  # Price increased
                },
                {"id": "BURG-OPT-2", "name": "Bacon", "price": 249},
                {"id": "BURG-OPT-3", "name": "Avocado", "price": 299},
                {"id": "BURG-OPT-4", "name": "Caramelized Onions", "price": 199},
                {"id": "BURG-OPT-5", "name": "Rare", "price": 0},
                {"id": "BURG-OPT-6", "name": "Medium", "price": 0},
                {"id": "BURG-OPT-7", "name": "Well Done", "price": 0},
            ],
        },
    }

    # Submit the updated menu
    update_response = flask_client.post(
        "/menu_update", data=json.dumps(updated_menu), content_type="application/json"
    )
    assert update_response.status_code == 200

    # Get the updated menu
    menu_response = flask_client.get("/menu")
    assert menu_response.status_code == 200
    menu_data = menu_response.json

    # Check updated modifier groups
    modifier_groups = {group["id"]: group for group in menu_data["modifierGroups"]}

    # Check that the first group was updated
    assert modifier_groups["BURG-MOD-1"]["maxSelection"] == 5
    assert "BURG-OPT-4" in modifier_groups["BURG-MOD-1"]["modifiers"]

    # Check that the new group was added
    assert "BURG-MOD-2" in modifier_groups
    assert modifier_groups["BURG-MOD-2"]["minSelection"] == 1
    assert modifier_groups["BURG-MOD-2"]["maxSelection"] == 1
    assert set(modifier_groups["BURG-MOD-2"]["modifiers"]) == set(
        ["BURG-OPT-5", "BURG-OPT-6", "BURG-OPT-7"]
    )

    # Check updated modifiers
    modifiers = {mod["id"]: mod for mod in menu_data["modifiers"]}

    # Check updated price
    if modifiers["BURG-OPT-1"]["price"] >= 100:  # If price is in cents
        assert modifiers["BURG-OPT-1"]["price"] == 249
    else:  # If price is in dollars
        assert abs(modifiers["BURG-OPT-1"]["price"] - 2.49) < 0.01

    # Check that the new modifiers were added
    assert "BURG-OPT-4" in modifiers
    assert modifiers["BURG-OPT-4"]["name"] == "Caramelized Onions"

    assert "BURG-OPT-5" in modifiers
    assert modifiers["BURG-OPT-5"]["name"] == "Rare"

    # Check that the item has both modifier groups
    items = {item["plu"]: item for item in menu_data["items"]}
    assert set(items["BURGER-1"]["modifierGroups"]) == set(["BURG-MOD-1", "BURG-MOD-2"])


@pytest.mark.integration
def test_modifier_removal(flask_client):
    """
    Test that modifiers and modifier groups can be correctly removed.

    This test verifies:
    1. Modifier options can be removed from groups
    2. Entire modifier groups can be removed from items
    3. Removal of modifiers doesn't affect other menu elements
    """
    # Create initial menu with modifiers
    initial_menu = {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "type": "menu.updated",
        "data": {
            "items": [
                {
                    "plu": "SALAD-1",
                    "name": "Caesar Salad",
                    "price": 999,
                    "available": True,
                    "modifierGroups": ["SALAD-MOD-1", "SALAD-MOD-2"],
                }
            ],
            "modifierGroups": [
                {
                    "id": "SALAD-MOD-1",
                    "name": "Dressing",
                    "minSelection": 1,
                    "maxSelection": 1,
                    "modifiers": ["DRESS-1", "DRESS-2", "DRESS-3"],
                },
                {
                    "id": "SALAD-MOD-2",
                    "name": "Extra Toppings",
                    "minSelection": 0,
                    "maxSelection": 4,
                    "modifiers": ["TOP-1", "TOP-2", "TOP-3", "TOP-4"],
                },
            ],
            "modifiers": [
                {"id": "DRESS-1", "name": "Caesar Dressing", "price": 0},
                {"id": "DRESS-2", "name": "Ranch Dressing", "price": 0},
                {"id": "DRESS-3", "name": "Balsamic Vinaigrette", "price": 0},
                {"id": "TOP-1", "name": "Grilled Chicken", "price": 299},
                {"id": "TOP-2", "name": "Bacon Bits", "price": 149},
                {"id": "TOP-3", "name": "Croutons", "price": 99},
                {"id": "TOP-4", "name": "Parmesan", "price": 149},
            ],
        },
    }

    # Submit the initial menu
    response = flask_client.post(
        "/menu_update", data=json.dumps(initial_menu), content_type="application/json"
    )
    assert response.status_code == 200

    # Update with removals
    updated_menu = {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "type": "menu.updated",
        "data": {
            "items": [
                {
                    "plu": "SALAD-1",
                    "name": "Caesar Salad",
                    "price": 999,
                    "available": True,
                    "modifierGroups": ["SALAD-MOD-1"],  # Removed SALAD-MOD-2
                }
            ],
            "modifierGroups": [
                {
                    "id": "SALAD-MOD-1",
                    "name": "Dressing",
                    "minSelection": 1,
                    "maxSelection": 1,
                    "modifiers": ["DRESS-1", "DRESS-3"],  # Removed DRESS-2
                }
            ],
            "modifiers": [
                {"id": "DRESS-1", "name": "Caesar Dressing", "price": 0},
                {"id": "DRESS-3", "name": "Balsamic Vinaigrette", "price": 0},
            ],
        },
    }

    # Submit the update with removals
    update_response = flask_client.post(
        "/menu_update", data=json.dumps(updated_menu), content_type="application/json"
    )
    assert update_response.status_code == 200

    # Get the updated menu
    menu_response = flask_client.get("/menu")
    assert menu_response.status_code == 200
    menu_data = menu_response.json

    # Check that the item only has the remaining modifier group
    items = {item["plu"]: item for item in menu_data["items"]}
    assert "SALAD-1" in items
    assert "modifierGroups" in items["SALAD-1"]
    assert len(items["SALAD-1"]["modifierGroups"]) == 1
    assert items["SALAD-1"]["modifierGroups"][0] == "SALAD-MOD-1"

    # Check that only one modifier group remains
    modifier_groups = {group["id"]: group for group in menu_data["modifierGroups"]}
    assert "SALAD-MOD-1" in modifier_groups
    assert "SALAD-MOD-2" not in modifier_groups

    # Check that the remaining group has only the remaining modifiers
    dressing_group = modifier_groups["SALAD-MOD-1"]
    assert len(dressing_group["modifiers"]) == 2
    assert set(dressing_group["modifiers"]) == set(["DRESS-1", "DRESS-3"])

    # Check that only the remaining modifiers exist
    modifiers = {mod["id"]: mod for mod in menu_data["modifiers"]}
    assert "DRESS-1" in modifiers
    assert "DRESS-2" not in modifiers
    assert "DRESS-3" in modifiers
    assert "TOP-1" not in modifiers
    assert "TOP-2" not in modifiers
    assert "TOP-3" not in modifiers
    assert "TOP-4" not in modifiers

    # Verify the remaining modifiers are unchanged
    assert modifiers["DRESS-1"]["name"] == "Caesar Dressing"
    assert modifiers["DRESS-3"]["name"] == "Balsamic Vinaigrette"
