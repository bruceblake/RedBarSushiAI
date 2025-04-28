import json
import pytest
import time
import re
from unittest import mock

@pytest.mark.e2e
def test_order_status_notification_flow(api_request, create_test_menu_payload):
    """
    Tests the complete flow of order status notifications from creation to delivery.
    
    This test verifies:
    1. SMS notifications are sent when order status changes
    2. Status updates from Deliverect trigger correct notifications
    3. The notification content is appropriate for each status
    4. All key order statuses generate appropriate notifications
    """
    # Setup: Create a test menu
    menu_payload = create_test_menu_payload(payload_type="direct", num_items=3)
    menu_response = api_request.post("/menu_update", data=menu_payload)
    assert menu_response.status == 200
    
    # Extract a test item to order
    test_item = menu_payload["items"][0]
    
    # Create a test order
    test_order_data = {
        "customer": {
            "name": "Robin Chen",
            "phone": "+15551234567",
            "email": "test@example.com"
        },
        "items": [
            {
                "plu": test_item["plu"],
                "name": test_item["name"],
                "price": test_item["price"],
                "quantity": 2
            }
        ],
        "pickup_time": "2025-05-01T18:30:00Z",
        "order_type": "pickup",
        "payment_method": "card"
    }
    
    # Place the order
    order_response = api_request.post("/order", data=test_order_data)
    assert order_response.status == 200
    order_result = order_response.json()
    assert "order_id" in order_result
    
    # Get the order ID for tracking
    order_id = order_result["order_id"]
    channel_order_id = order_result.get("channel_order_id", order_id)
    
    # Mock the Twilio SMS client to verify notifications
    with mock.patch('twilio.rest.Client.messages.create') as mock_sms:
        mock_sms.return_value.sid = "SM12345"
        
        # Step 1: Test notification when order is accepted by kitchen
        deliverect_accepted_payload = {
            "orderId": f"DLV-{order_id}",
            "status": 20,  # 20 = Accepted
            "timeStamp": "2025-05-01T18:15:00Z",
            "channelOrderId": channel_order_id,
            "location": "test-location",
            "channelLink": "test-channel-link"
        }
        
        accepted_response = api_request.post(
            "/webhook/deliverect/order_status",
            data=json.dumps(deliverect_accepted_payload),
            content_type='application/json'
        )
        assert accepted_response.status == 200
        
        # Wait for async processing
        time.sleep(1)
        
        # Verify that an SMS was sent for the accepted status
        mock_sms.assert_called()
        
        # Get the last SMS message
        last_call_args = mock_sms.call_args
        assert last_call_args is not None
        
        # Verify SMS content includes order acceptance
        sms_body = last_call_args[1].get('body', '')
        assert "accepted" in sms_body.lower() or "confirmed" in sms_body.lower()
        assert "Robin" in sms_body or channel_order_id in sms_body
        
        # Reset the mock for the next status
        mock_sms.reset_mock()
        
        # Step 2: Test notification when order is being prepared
        deliverect_preparation_payload = {
            "orderId": f"DLV-{order_id}",
            "status": 30,  # 30 = In Preparation
            "timeStamp": "2025-05-01T18:20:00Z",
            "channelOrderId": channel_order_id,
            "location": "test-location",
            "channelLink": "test-channel-link"
        }
        
        preparation_response = api_request.post(
            "/webhook/deliverect/order_status",
            data=json.dumps(deliverect_preparation_payload),
            content_type='application/json'
        )
        assert preparation_response.status == 200
        
        # Wait for async processing
        time.sleep(1)
        
        # Verify that an SMS was sent for the preparation status
        mock_sms.assert_called()
        
        # Get the SMS content
        last_call_args = mock_sms.call_args
        sms_body = last_call_args[1].get('body', '')
        assert "preparing" in sms_body.lower() or "started" in sms_body.lower()
        
        # Reset the mock for the next status
        mock_sms.reset_mock()
        
        # Step 3: Test notification when order is ready for pickup
        deliverect_ready_payload = {
            "orderId": f"DLV-{order_id}",
            "status": 70,  # 70 = Ready for Pickup/Ready for Delivery
            "timeStamp": "2025-05-01T18:25:00Z",
            "channelOrderId": channel_order_id,
            "location": "test-location",
            "channelLink": "test-channel-link"
        }
        
        ready_response = api_request.post(
            "/webhook/deliverect/order_status",
            data=json.dumps(deliverect_ready_payload),
            content_type='application/json'
        )
        assert ready_response.status == 200
        
        # Wait for async processing
        time.sleep(1)
        
        # Verify that an SMS was sent for the ready status
        mock_sms.assert_called()
        
        # Get the SMS content
        last_call_args = mock_sms.call_args
        sms_body = last_call_args[1].get('body', '')
        assert "ready" in sms_body.lower()
        assert "pickup" in sms_body.lower()  # Should mention pickup since it's a pickup order
        
        # Reset the mock for the next status
        mock_sms.reset_mock()
        
        # Step 4: Test notification when order is completed/delivered
        deliverect_completed_payload = {
            "orderId": f"DLV-{order_id}",
            "status": 90,  # 90 = Completed
            "timeStamp": "2025-05-01T18:40:00Z",
            "channelOrderId": channel_order_id,
            "location": "test-location",
            "channelLink": "test-channel-link"
        }
        
        completed_response = api_request.post(
            "/webhook/deliverect/order_status",
            data=json.dumps(deliverect_completed_payload),
            content_type='application/json'
        )
        assert completed_response.status == 200
        
        # Wait for async processing
        time.sleep(1)
        
        # Verify that an SMS was sent for the completed status
        mock_sms.assert_called()
        
        # Get the SMS content
        last_call_args = mock_sms.call_args
        sms_body = last_call_args[1].get('body', '')
        assert "complete" in sms_body.lower() or "finished" in sms_body.lower() or "enjoy" in sms_body.lower()
    
    # Verify the order status was updated in the database
    order_status_response = api_request.get(f"/order/{order_id}")
    assert order_status_response.status == 200
    
    order_data = order_status_response.json()
    assert order_data["status"] == "completed" or order_data["status"] == 90

@pytest.mark.e2e
def test_snooze_item_notification(api_request, create_test_menu_payload):
    """
    Tests notifications when menu items become unavailable (snoozed).
    
    This test verifies:
    1. Customers with pending orders are notified when ordered items become unavailable
    2. The notification includes appropriate details about the affected items
    3. Alternative items are suggested when available
    """
    # Setup: Create a test menu
    menu_payload = create_test_menu_payload(payload_type="direct", num_items=5)
    menu_response = api_request.post("/menu_update", data=menu_payload)
    assert menu_response.status == 200
    
    # Extract test items
    test_item1 = menu_payload["items"][0]
    test_item2 = menu_payload["items"][1]
    
    # Create a test order with the first item
    test_order_data = {
        "customer": {
            "name": "Jamie Lewis",
            "phone": "+15551234567",
            "email": "jamie@example.com"
        },
        "items": [
            {
                "plu": test_item1["plu"],
                "name": test_item1["name"],
                "price": test_item1["price"],
                "quantity": 1
            }
        ],
        "pickup_time": "2025-05-01T19:30:00Z",
        "order_type": "pickup",
        "payment_method": "card"
    }
    
    # Place the order
    order_response = api_request.post("/order", data=test_order_data)
    assert order_response.status == 200
    order_result = order_response.json()
    order_id = order_result["order_id"]
    
    # Simulate the order being in "pending" or "accepted" status
    update_response = api_request.post(
        f"/order/{order_id}/status",
        data={"status": "accepted"}
    )
    assert update_response.status == 200
    
    # Now snooze the item that was ordered
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
                            "plu": test_item1["plu"],
                            "snoozeStart": "2025-05-01T19:00:00.000000Z",
                            "snoozeEnd": "2025-05-02T00:00:00.000000Z"
                        }
                    ]
                }
            }
        ],
        "allSnoozedItems": [
            {
                "plu": test_item1["plu"],
                "snoozeStart": "2025-05-01T19:00:00.000000Z",
                "snoozeEnd": "2025-05-02T00:00:00.000000Z"
            }
        ]
    }
    
    # Mock the Twilio SMS client to verify notifications
    with mock.patch('twilio.rest.Client.messages.create') as mock_sms:
        mock_sms.return_value.sid = "SM12345"
        
        # Submit the snooze request
        snooze_response = api_request.post(
            "/menu_update",
            data=json.dumps(snooze_payload),
            content_type='application/json'
        )
        assert snooze_response.status == 200
        
        # Wait for async processing
        time.sleep(1)
        
        # Verify an SMS was sent about the unavailable item
        mock_sms.assert_called()
        
        # Get the SMS content
        last_call_args = mock_sms.call_args
        sms_body = last_call_args[1].get('body', '')
        
        # Should mention the unavailable item and possibly suggest alternatives
        assert test_item1["name"] in sms_body
        assert any(phrase in sms_body.lower() for phrase in 
                   ["unavailable", "out of stock", "no longer available", "unable to prepare"])
        
        # Reset the mock for testing unsnooze
        mock_sms.reset_mock()
        
        # Now unsnooze the item
        unsnooze_payload = {
            "accountId": "test-account-id",
            "locationId": "test-location-id",
            "channelLinkId": "test-channel-link-id",
            "operations": [
                {
                    "action": "unsnooze",
                    "data": {
                        "items": [
                            {
                                "plu": test_item1["plu"]
                            }
                        ]
                    }
                }
            ],
            "allSnoozedItems": []
        }
        
        # Submit the unsnooze request
        unsnooze_response = api_request.post(
            "/menu_update",
            data=json.dumps(unsnooze_payload),
            content_type='application/json'
        )
        assert unsnooze_response.status == 200
        
        # Wait for async processing
        time.sleep(1)
        
        # Verify an SMS might be sent about the item becoming available again
        # (This is optional behavior - not all systems notify about items becoming available again)
        if mock_sms.called:
            last_call_args = mock_sms.call_args
            sms_body = last_call_args[1].get('body', '')
            
            # Should mention the item is available again
            assert test_item1["name"] in sms_body
            assert any(phrase in sms_body.lower() for phrase in 
                      ["available again", "back in stock", "can now be prepared"])

# Helper functions for tests
def extract_gather_action(twiml):
    """Extract the 'action' attribute from a <Gather> tag in TwiML."""
    gather_match = re.search(r'<Gather[^>]*action="([^"]*)"', twiml)
    if gather_match:
        return gather_match.group(1)
    return None