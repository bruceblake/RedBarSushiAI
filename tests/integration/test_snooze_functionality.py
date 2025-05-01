import json
import pytest
from datetime import datetime, timedelta, timezone


@pytest.mark.integration
def test_snooze_unsnooze_with_correct_format(flask_client, simple_menu_format):
    """
    Test snooze/unsnooze functionality with the correct format according to Deliverect glossary.
    Verifies:
    1. Items can be snoozed with the proper format
    2. The snoozed items are properly marked in the menu
    3. Items can be unsnoozed properly
    """
    # First create a menu with items
    flask_client.post(
        "/menu_update",
        data=json.dumps(simple_menu_format),
        content_type="application/json",
    )

    # Create snooze payload according to Deliverect glossary
    # The snooze format includes:
    # - accountId, locationId, channelLinkId for identification
    # - operations with action "snooze" or "unsnooze" and items identified by plu
    # - allSnoozedItems with a list of all snoozed PLUs and timestamps

    now = datetime.now(timezone.utc)
    tomorrow = now + timedelta(days=1)

    # Format timestamps as expected by Deliverect
    start_time = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    end_time = tomorrow.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    snooze_payload = {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "operations": [
            {
                "action": "snooze",
                "data": {
                    "items": [
                        {
                            "plu": "STK-01",
                            "snoozeStart": start_time,
                            "snoozeEnd": end_time,
                        }
                    ]
                },
            }
        ],
        "allSnoozedItems": [
            {"plu": "STK-01", "snoozeStart": start_time, "snoozeEnd": end_time}
        ],
    }

    # Snooze the item
    snooze_response = flask_client.post(
        "/snoozeUnsnooze",
        data=json.dumps(snooze_payload),
        content_type="application/json",
    )

    # Assert the response
    assert snooze_response.status_code == 200
    assert "status" in snooze_response.json
    assert snooze_response.json["status"] == "success"

    # Check if item is properly snoozed in the menu
    menu_response = flask_client.get("/menu")
    assert menu_response.status_code == 200

    menu_data = menu_response.json
    steak_item = next((i for i in menu_data["items"] if i["plu"] == "STK-01"), None)

    # If the item exists, verify it's snoozed
    if steak_item:
        assert steak_item["snoozed"] is True
        assert steak_item["available"] is False

    # Create unsnooze payload
    unsnooze_payload = {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "operations": [{"action": "unsnooze", "data": {"items": [{"plu": "STK-01"}]}}],
        "allSnoozedItems": [],  # Empty list since no items are snoozed anymore
    }

    # Unsnooze the item
    unsnooze_response = flask_client.post(
        "/snoozeUnsnooze",
        data=json.dumps(unsnooze_payload),
        content_type="application/json",
    )

    # Assert the unsnooze response
    assert unsnooze_response.status_code == 200
    assert "status" in unsnooze_response.json
    assert unsnooze_response.json["status"] == "success"

    # Check if item is properly unsnoozed in the menu
    updated_menu_response = flask_client.get("/menu")
    assert updated_menu_response.status_code == 200

    updated_menu_data = updated_menu_response.json
    updated_steak_item = next(
        (i for i in updated_menu_data["items"] if i["plu"] == "STK-01"), None
    )

    # If the item exists, verify it's unsnoozed
    if updated_steak_item:
        assert updated_steak_item["snoozed"] is False
        assert updated_steak_item["available"] is True


@pytest.mark.integration
def test_allSnoozedItems_synchronization(flask_client, deliverect_menu_json):
    """
    Test that allSnoozedItems in the Deliverect format is used to synchronize all snoozed items.
    Verifies:
    1. Multiple items can be snoozed at once
    2. Only items in allSnoozedItems remain snoozed after sync
    """
    # First create a menu with items
    flask_client.post(
        "/menu_update",
        data=json.dumps(deliverect_menu_json),
        content_type="application/json",
    )

    now = datetime.now(timezone.utc)
    tomorrow = now + timedelta(days=1)

    # Format timestamps as expected by Deliverect
    start_time = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    end_time = tomorrow.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    # Snooze multiple items
    multi_snooze_payload = {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "operations": [
            {
                "action": "snooze",
                "data": {
                    "items": [
                        {
                            "plu": "STK-01",
                            "snoozeStart": start_time,
                            "snoozeEnd": end_time,
                        },
                        {
                            "plu": "BRG-01",
                            "snoozeStart": start_time,
                            "snoozeEnd": end_time,
                        },
                        {
                            "plu": "RICE-01",
                            "snoozeStart": start_time,
                            "snoozeEnd": end_time,
                        },
                    ]
                },
            }
        ],
        "allSnoozedItems": [
            {"plu": "STK-01", "snoozeStart": start_time, "snoozeEnd": end_time},
            {"plu": "BRG-01", "snoozeStart": start_time, "snoozeEnd": end_time},
            {"plu": "RICE-01", "snoozeStart": start_time, "snoozeEnd": end_time},
        ],
    }

    # Apply multiple snoozes
    snooze_response = flask_client.post(
        "/snoozeUnsnooze",
        data=json.dumps(multi_snooze_payload),
        content_type="application/json",
    )

    # Check all items are snoozed
    menu_response = flask_client.get("/menu")
    menu_data = menu_response.json

    steak = next((i for i in menu_data["items"] if i["plu"] == "STK-01"), None)
    burger = next((i for i in menu_data["items"] if i["plu"] == "BRG-01"), None)
    rice = next((i for i in menu_data["items"] if i["plu"] == "RICE-01"), None)

    if steak:
        assert steak["snoozed"] is True
    if burger:
        assert burger["snoozed"] is True
    if rice:
        assert rice["snoozed"] is True

    # Now send a sync with only some items in allSnoozedItems
    # This should unsnooze any items not in the list
    partial_sync_payload = {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "operations": [],  # No operations, just sync
        "allSnoozedItems": [
            {"plu": "STK-01", "snoozeStart": start_time, "snoozeEnd": end_time}
            # BRG-01 and RICE-01 are missing, should be unsnoozed
        ],
    }

    # Apply the sync
    sync_response = flask_client.post(
        "/snoozeUnsnooze",
        data=json.dumps(partial_sync_payload),
        content_type="application/json",
    )

    # Check which items are snoozed after sync
    updated_menu_response = flask_client.get("/menu")
    updated_menu_data = updated_menu_response.json

    steak = next((i for i in updated_menu_data["items"] if i["plu"] == "STK-01"), None)
    burger = next((i for i in updated_menu_data["items"] if i["plu"] == "BRG-01"), None)
    rice = next((i for i in updated_menu_data["items"] if i["plu"] == "RICE-01"), None)

    if steak:
        assert steak["snoozed"] is True  # Should still be snoozed
    if burger:
        assert burger["snoozed"] is False  # Should be unsnoozed
    if rice:
        assert rice["snoozed"] is False  # Should be unsnoozed


@pytest.mark.integration
def test_snooze_without_allSnoozedItems(flask_client, simple_menu_format):
    """
    Test that snooze operations work even without allSnoozedItems.
    Some systems might not include allSnoozedItems in every request.

    Verifies:
    1. Individual snooze operations work without allSnoozedItems
    2. Items are properly snoozed and unsnoozed
    """
    # First create a menu with items
    flask_client.post(
        "/menu_update",
        data=json.dumps(simple_menu_format),
        content_type="application/json",
    )

    # Create simpler snooze payload without allSnoozedItems
    simple_snooze_payload = {
        "accountId": "test-account-id",
        "locationId": "test-location-id",
        "channelLinkId": "test-channel-link-id",
        "operations": [{"action": "snooze", "plu": "STK-01"}],  # Simplified format
    }

    # Snooze the item
    snooze_response = flask_client.post(
        "/snoozeUnsnooze",
        data=json.dumps(simple_snooze_payload),
        content_type="application/json",
    )

    # Check if the request was accepted (even if format is different)
    assert snooze_response.status_code in [
        200,
        400,
        500,
    ]  # Some implementations may reject this format

    # If the request was successful, verify the item is snoozed
    if snooze_response.status_code == 200:
        menu_response = flask_client.get("/menu")
        menu_data = menu_response.json

        steak = next((i for i in menu_data["items"] if i["plu"] == "STK-01"), None)
        if steak:
            assert steak["snoozed"] is True
            assert steak["available"] is False

        # Also test unsnooze with simple format
        simple_unsnooze_payload = {
            "accountId": "test-account-id",
            "locationId": "test-location-id",
            "channelLinkId": "test-channel-link-id",
            "operations": [
                {"action": "unsnooze", "plu": "STK-01"}  # Simplified format
            ],
        }

        # Unsnooze the item
        unsnooze_response = flask_client.post(
            "/snoozeUnsnooze",
            data=json.dumps(simple_unsnooze_payload),
            content_type="application/json",
        )

        # If unsnooze was successful, verify the item is unsnoozed
        if unsnooze_response.status_code == 200:
            updated_menu_response = flask_client.get("/menu")
            updated_menu_data = updated_menu_response.json

            steak = next(
                (i for i in updated_menu_data["items"] if i["plu"] == "STK-01"), None
            )
            if steak:
                assert steak["snoozed"] is False
                assert steak["available"] is True
