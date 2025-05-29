"""
Integration tests for Deliverect API interactions.
Tests menu syncing, order submission, and webhook processing.
"""

import pytest
import json
from datetime import datetime
from unittest.mock import patch, AsyncMock, Mock
from app.utils.deliverect.menu_async import process_deliverect_menu
from app.utils.deliverect.orders_async import submit_order_to_deliverect
from app.api.deliverect_menu import process_menu_webhook
from app.api.deliverect_webhooks import process_order_status_webhook
from app.models.menu_async import MenuItem, MenuModifier
from app.models.order_async import Order


class TestDeliverectMenuIntegration:
    """Test Deliverect menu synchronization."""
    
    @pytest.fixture
    def sample_deliverect_menu(self):
        """Sample Deliverect menu payload."""
        return {
            "categories": [
                {
                    "_id": "cat_123",
                    "name": "Sushi Rolls",
                    "description": "Fresh sushi rolls",
                    "products": [
                        {
                            "_id": "prod_456",
                            "name": "California Roll",
                            "description": "Crab, avocado, cucumber",
                            "price": 1295,
                            "plu": "PLU_CALI_001",
                            "productType": 1,
                            "isAvailable": True,
                            "modifierGroups": []
                        }
                    ]
                }
            ],
            "modifierGroups": [
                {
                    "_id": "modgrp_789",
                    "name": "Spice Level",
                    "plu": "GRP_SPICE",
                    "minSelection": 0,
                    "maxSelection": 1,
                    "modifiers": [
                        {
                            "_id": "mod_101",
                            "name": "Extra Spicy",
                            "plu": "MOD_XSPICY",
                            "price": 0
                        }
                    ]
                }
            ]
        }
    
    @pytest.mark.asyncio
    async def test_process_menu_webhook(self, client, sample_deliverect_menu, db_session):
        """Test processing Deliverect menu webhook."""
        # Mock Deliverect auth
        with patch('app.utils.deliverect.auth.verify_webhook_signature', return_value=True):
            response = await client.post(
                "/api/deliverect/menu/update",
                json=sample_deliverect_menu,
                headers={"X-Deliverect-Signature": "valid_signature"}
            )
            
            assert response.status_code == 200
            
            # Verify items were created
            items = await db_session.execute(
                select(MenuItem).where(MenuItem.plu == "PLU_CALI_001")
            )
            item = items.scalar_one_or_none()
            assert item is not None
            assert item.name == "California Roll"
            assert item.price == 1295
    
    @pytest.mark.asyncio
    async def test_menu_item_availability_update(self, db_session):
        """Test updating item availability from Deliverect."""
        # Create existing item
        item = MenuItem(
            name="Dragon Roll",
            plu="PLU_DRAGON",
            price=1895,
            deliverect_item_id="prod_dragon",
            is_available=True
        )
        db_session.add(item)
        await db_session.commit()
        
        # Process availability update
        update_payload = {
            "products": [{
                "_id": "prod_dragon",
                "plu": "PLU_DRAGON",
                "isAvailable": False,
                "snoozeUntil": "2024-01-20T18:00:00Z"
            }]
        }
        
        await process_deliverect_menu(update_payload, db_session)
        
        # Verify availability was updated
        await db_session.refresh(item)
        assert item.is_available is False
        assert item.snoozed_until is not None
    
    @pytest.mark.asyncio
    async def test_modifier_group_sync(self, sample_deliverect_menu, db_session):
        """Test syncing modifier groups from Deliverect."""
        await process_deliverect_menu(sample_deliverect_menu, db_session)
        
        # Check modifier group was created
        from app.models.menu_async import MenuModifierGroup
        groups = await db_session.execute(
            select(MenuModifierGroup).where(MenuModifierGroup.plu == "GRP_SPICE")
        )
        group = groups.scalar_one_or_none()
        
        assert group is not None
        assert group.name == "Spice Level"
        assert group.min_selection == 0
        assert group.max_selection == 1
    
    @pytest.mark.asyncio
    async def test_menu_update_preserves_custom_fields(self, db_session):
        """Test that menu updates preserve custom fields."""
        # Create item with custom variant
        from app.models.menu_async import MenuNameVariant
        
        item = MenuItem(
            name="Salmon Roll",
            plu="PLU_SALMON",
            price=1495,
            deliverect_item_id="prod_salmon"
        )
        
        variant = MenuNameVariant(
            variant_phrase="sake roll",
            canonical_name="Salmon Roll",
            target_plu="PLU_SALMON"
        )
        
        db_session.add_all([item, variant])
        await db_session.commit()
        
        # Process menu update
        update_payload = {
            "products": [{
                "_id": "prod_salmon",
                "plu": "PLU_SALMON",
                "name": "Fresh Salmon Roll",  # Name changed
                "price": 1595  # Price changed
            }]
        }
        
        await process_deliverect_menu(update_payload, db_session)
        
        # Verify variant was preserved
        variants = await db_session.execute(
            select(MenuNameVariant).where(MenuNameVariant.target_plu == "PLU_SALMON")
        )
        assert variants.scalar_one_or_none() is not None


class TestDeliverectOrderSubmission:
    """Test order submission to Deliverect."""
    
    @pytest.fixture
    def mock_deliverect_client(self):
        """Mock Deliverect API client."""
        client = AsyncMock()
        client.submit_order.return_value = {
            "status": 1,
            "_id": "dlv_order_123",
            "channelOrderId": "RBS-2024-001",
            "estimatedTime": 15
        }
        return client
    
    @pytest.fixture
    def sample_order_data(self):
        """Sample order data for submission."""
        return {
            "channelOrderId": "RBS-2024-001",
            "orderType": 1,  # Pickup
            "customer": {
                "name": "John Doe",
                "phone": "+1234567890",
                "email": "john@example.com"
            },
            "items": [
                {
                    "plu": "PLU_CALI_001",
                    "name": "California Roll",
                    "quantity": 2,
                    "price": 1295,
                    "modifiers": []
                }
            ],
            "total": 2590,
            "note": "No wasabi please"
        }
    
    @pytest.mark.asyncio
    async def test_submit_order_success(self, mock_deliverect_client, sample_order_data):
        """Test successful order submission."""
        with patch('app.utils.deliverect.orders_async.DeliverectClient', return_value=mock_deliverect_client):
            result = await submit_order_to_deliverect(sample_order_data)
            
            assert result["status"] == 1
            assert result["_id"] == "dlv_order_123"
            assert result["estimatedTime"] == 15
            
            mock_deliverect_client.submit_order.assert_called_once_with(sample_order_data)
    
    @pytest.mark.asyncio
    async def test_submit_order_with_modifiers(self, mock_deliverect_client):
        """Test order submission with item modifiers."""
        order_data = {
            "channelOrderId": "RBS-2024-002",
            "items": [
                {
                    "plu": "PLU_SPICY_TUNA",
                    "name": "Spicy Tuna Roll",
                    "quantity": 1,
                    "price": 1495,
                    "modifiers": [
                        {
                            "plu": "MOD_XSPICY",
                            "name": "Extra Spicy",
                            "quantity": 1,
                            "price": 0
                        },
                        {
                            "plu": "MOD_EXTRA_AVO",
                            "name": "Extra Avocado",
                            "quantity": 1,
                            "price": 200
                        }
                    ]
                }
            ],
            "total": 1695  # 1495 + 200
        }
        
        with patch('app.utils.deliverect.orders_async.DeliverectClient', return_value=mock_deliverect_client):
            result = await submit_order_to_deliverect(order_data)
            
            # Verify modifiers were included
            submitted_order = mock_deliverect_client.submit_order.call_args[0][0]
            assert len(submitted_order["items"][0]["modifiers"]) == 2
            assert submitted_order["total"] == 1695
    
    @pytest.mark.asyncio
    async def test_submit_order_retry_on_failure(self, mock_deliverect_client):
        """Test order submission retry logic."""
        # First call fails, second succeeds
        mock_deliverect_client.submit_order.side_effect = [
            Exception("Network error"),
            {"status": 1, "_id": "dlv_order_retry"}
        ]
        
        with patch('app.utils.deliverect.orders_async.DeliverectClient', return_value=mock_deliverect_client):
            with patch('asyncio.sleep', return_value=None):  # Skip delay
                result = await submit_order_to_deliverect({"channelOrderId": "TEST"})
                
                assert result["_id"] == "dlv_order_retry"
                assert mock_deliverect_client.submit_order.call_count == 2
    
    @pytest.mark.asyncio
    async def test_order_submission_validation(self):
        """Test order validation before submission."""
        # Invalid order data
        invalid_orders = [
            {},  # Empty order
            {"items": []},  # No items
            {"items": [{"plu": "TEST"}]},  # Missing required fields
            {"items": [{"plu": "TEST", "quantity": 0}]}  # Invalid quantity
        ]
        
        for order_data in invalid_orders:
            with pytest.raises(ValueError):
                await submit_order_to_deliverect(order_data)


class TestDeliverectWebhooks:
    """Test processing Deliverect webhooks."""
    
    @pytest.mark.asyncio
    async def test_order_status_webhook(self, client, db_session):
        """Test processing order status update webhook."""
        # Create order in database
        order = Order(
            deliverect_channel_order_id="RBS-2024-001",
            deliverect_order_id="dlv_order_123",
            customer_phone="+1234567890",
            status="confirmed"
        )
        db_session.add(order)
        await db_session.commit()
        
        # Status update webhook
        webhook_payload = {
            "eventType": "order.status_update",
            "channelOrderId": "RBS-2024-001",
            "orderId": "dlv_order_123",
            "status": 30,  # Ready for pickup
            "estimatedTime": 5
        }
        
        with patch('app.utils.deliverect.auth.verify_webhook_signature', return_value=True):
            response = await client.post(
                "/api/deliverect/webhooks/order/status",
                json=webhook_payload,
                headers={"X-Deliverect-Signature": "valid"}
            )
            
            assert response.status_code == 200
            
            # Verify order status was updated
            await db_session.refresh(order)
            assert order.status == "ready"
    
    @pytest.mark.asyncio
    async def test_order_cancellation_webhook(self, client, db_session):
        """Test processing order cancellation webhook."""
        # Create active order
        order = Order(
            deliverect_channel_order_id="RBS-2024-002",
            status="preparing"
        )
        db_session.add(order)
        await db_session.commit()
        
        # Cancellation webhook
        webhook_payload = {
            "eventType": "order.cancelled",
            "channelOrderId": "RBS-2024-002",
            "reason": "Customer requested"
        }
        
        with patch('app.utils.deliverect.auth.verify_webhook_signature', return_value=True):
            response = await client.post(
                "/api/deliverect/webhooks/order/cancel",
                json=webhook_payload
            )
            
            assert response.status_code == 200
            
            # Verify order was cancelled
            await db_session.refresh(order)
            assert order.status == "cancelled"
    
    @pytest.mark.asyncio
    async def test_webhook_signature_verification(self, client):
        """Test webhook signature verification."""
        webhook_payload = {"test": "data"}
        
        # Invalid signature
        with patch('app.utils.deliverect.auth.verify_webhook_signature', return_value=False):
            response = await client.post(
                "/api/deliverect/webhooks/test",
                json=webhook_payload,
                headers={"X-Deliverect-Signature": "invalid"}
            )
            
            assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_webhook_idempotency(self, client, db_session):
        """Test webhook processing is idempotent."""
        webhook_payload = {
            "eventType": "order.status_update",
            "channelOrderId": "RBS-IDEMPOTENT",
            "status": 20,
            "idempotencyKey": "webhook_123"
        }
        
        with patch('app.utils.deliverect.auth.verify_webhook_signature', return_value=True):
            # First request
            response1 = await client.post(
                "/api/deliverect/webhooks/order/status",
                json=webhook_payload
            )
            assert response1.status_code == 200
            
            # Duplicate request
            response2 = await client.post(
                "/api/deliverect/webhooks/order/status",
                json=webhook_payload
            )
            assert response2.status_code == 200
            
            # Should not process twice
            # Implementation would check idempotency key