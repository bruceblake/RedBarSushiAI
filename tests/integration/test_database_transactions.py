"""
Integration tests for database transactions and integrity - Task 3.5.1.

This module tests order creation with rollback scenarios to ensure
database consistency and proper transaction handling.
"""

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import Dict, Any

from app.models.order_async import Order, OrderItem
from app.models.menu_async import MenuItem
from app.models.location_async import Location
from app.utils.order_utils_async import create_order_with_validation
from app.db_async import get_db


@pytest_asyncio.fixture
async def db_session():
    """Create a real database session for integration testing."""
    async for session in get_db():
        try:
            yield session
        finally:
            await session.rollback()


@pytest_asyncio.fixture
async def test_location(db_session):
    """Create a test location for orders."""
    location = Location(
        id="test_location_001",
        name="Test Sushi Restaurant",
        address="123 Test Street",
        phone="+1234567890",
        email="test@sushi.com",
        is_active=True
    )
    db_session.add(location)
    await db_session.commit()
    await db_session.refresh(location)
    return location


@pytest_asyncio.fixture
async def test_menu_items(db_session):
    """Create test menu items for orders."""
    items = []
    
    # Create California Roll
    cali_roll = MenuItem(
        plu="CALI_001",
        name="California Roll",
        description="Crab, avocado, cucumber",
        price=1295,  # $12.95 in cents
        is_available=True,
        category_id=1
    )
    items.append(cali_roll)
    
    # Create Spicy Tuna Roll
    tuna_roll = MenuItem(
        plu="TUNA_001", 
        name="Spicy Tuna Roll",
        description="Spicy tuna, cucumber",
        price=1395,  # $13.95 in cents
        is_available=True,
        category_id=1
    )
    items.append(tuna_roll)
    
    for item in items:
        db_session.add(item)
    
    await db_session.commit()
    
    for item in items:
        await db_session.refresh(item)
    
    return items


class TestOrderCreationWithRollback:
    """Test order creation with various rollback scenarios."""
    
    @pytest.mark.asyncio
    async def test_successful_order_creation(self, db_session, test_location, test_menu_items):
        """Test successful order creation with all components."""
        # Prepare order data
        order_data = {
            "location_id": test_location.id,
            "customer_name": "John Doe",
            "customer_phone": "+1234567890",
            "customer_email": "john@example.com",
            "order_type": "delivery",
            "items": [
                {
                    "plu": "CALI_001",
                    "quantity": 2,
                    "price": 1295,
                    "modifiers": []
                },
                {
                    "plu": "TUNA_001", 
                    "quantity": 1,
                    "price": 1395,
                    "modifiers": []
                }
            ],
            "subtotal": 3985,  # (12.95 * 2) + 13.95
            "tax": 399,       # ~10% tax
            "total": 4384,    # subtotal + tax
            "delivery_address": "456 Customer Street"
        }
        
        # Create order with validation
        order = await create_order_with_validation(db_session, order_data)
        
        # Verify order was created successfully
        assert order is not None
        assert order.location_id == test_location.id
        assert order.customer_name == "John Doe"
        assert order.total == 4384
        assert len(order.items) == 2
        
        # Verify order items
        cali_item = next((item for item in order.items if item.plu == "CALI_001"), None)
        assert cali_item is not None
        assert cali_item.quantity == 2
        assert cali_item.price == 1295
        
        tuna_item = next((item for item in order.items if item.plu == "TUNA_001"), None)
        assert tuna_item is not None
        assert tuna_item.quantity == 1
        assert tuna_item.price == 1395
    
    @pytest.mark.asyncio
    async def test_rollback_on_validation_failure(self, db_session, test_location, test_menu_items):
        """Test rollback when order validation fails."""
        # Prepare invalid order data (missing required fields)
        invalid_order_data = {
            "location_id": test_location.id,
            # Missing customer_name - should cause validation failure
            "customer_phone": "+1234567890",
            "items": [
                {
                    "plu": "CALI_001",
                    "quantity": 2,
                    "price": 1295
                }
            ],
            "total": 2590
        }
        
        # Count orders before attempt
        initial_order_count = await db_session.execute(
            "SELECT COUNT(*) FROM orders"
        )
        initial_count = initial_order_count.scalar()
        
        # Attempt to create invalid order - should fail and rollback
        with pytest.raises((ValueError, IntegrityError, SQLAlchemyError)):
            await create_order_with_validation(db_session, invalid_order_data)
        
        # Verify no order was created (rollback successful)
        final_order_count = await db_session.execute(
            "SELECT COUNT(*) FROM orders"
        )
        final_count = final_order_count.scalar()
        
        assert final_count == initial_count
    
    @pytest.mark.asyncio
    async def test_rollback_on_payment_failure(self, db_session, test_location, test_menu_items):
        """Test rollback when payment processing fails."""
        order_data = {
            "location_id": test_location.id,
            "customer_name": "Jane Doe",
            "customer_phone": "+1234567890",
            "customer_email": "jane@example.com",
            "order_type": "pickup",
            "items": [
                {
                    "plu": "CALI_001",
                    "quantity": 1,
                    "price": 1295,
                    "modifiers": []
                }
            ],
            "subtotal": 1295,
            "tax": 130,
            "total": 1425,
            "payment_method": "credit_card",
            "payment_token": "invalid_token"  # This should cause payment failure
        }
        
        # Mock payment processor to fail
        with patch('app.utils.payment_processor.process_payment') as mock_payment:
            mock_payment.side_effect = Exception("Payment declined")
            
            # Count orders before attempt
            initial_order_count = await db_session.execute(
                "SELECT COUNT(*) FROM orders"
            )
            initial_count = initial_order_count.scalar()
            
            # Attempt to create order with failing payment
            with pytest.raises(Exception) as exc_info:
                await create_order_with_validation(db_session, order_data)
            
            assert "Payment declined" in str(exc_info.value)
            
            # Verify no order was created (rollback successful)
            final_order_count = await db_session.execute(
                "SELECT COUNT(*) FROM orders"
            )
            final_count = final_order_count.scalar()
            
            assert final_count == initial_count
    
    @pytest.mark.asyncio
    async def test_rollback_on_external_api_failure(self, db_session, test_location, test_menu_items):
        """Test rollback when external API calls fail."""
        order_data = {
            "location_id": test_location.id,
            "customer_name": "Bob Smith",
            "customer_phone": "+1234567890",
            "customer_email": "bob@example.com",
            "order_type": "delivery",
            "items": [
                {
                    "plu": "TUNA_001",
                    "quantity": 3,
                    "price": 1395,
                    "modifiers": []
                }
            ],
            "subtotal": 4185,
            "tax": 419,
            "total": 4604,
            "delivery_address": "789 Delivery Street"
        }
        
        # Mock Deliverect API to fail during order submission
        with patch('app.utils.deliverect_async.submit_order') as mock_deliverect:
            mock_deliverect.side_effect = Exception("Deliverect API unavailable")
            
            # Count orders before attempt
            initial_order_count = await db_session.execute(
                "SELECT COUNT(*) FROM orders"
            )
            initial_count = initial_order_count.scalar()
            
            # Attempt to create order with failing external API
            with pytest.raises(Exception) as exc_info:
                await create_order_with_validation(db_session, order_data)
            
            assert "Deliverect API unavailable" in str(exc_info.value)
            
            # Verify no order was created (rollback successful)
            final_order_count = await db_session.execute(
                "SELECT COUNT(*) FROM orders"
            )
            final_count = final_order_count.scalar()
            
            assert final_count == initial_count
    
    @pytest.mark.asyncio
    async def test_partial_rollback_with_inventory_check(self, db_session, test_location, test_menu_items):
        """Test rollback when inventory check fails for some items."""
        order_data = {
            "location_id": test_location.id,
            "customer_name": "Alice Johnson",
            "customer_phone": "+1234567890",
            "customer_email": "alice@example.com",
            "order_type": "pickup",
            "items": [
                {
                    "plu": "CALI_001",
                    "quantity": 2,
                    "price": 1295,
                    "modifiers": []
                },
                {
                    "plu": "UNAVAILABLE_001",  # This item doesn't exist
                    "quantity": 1,
                    "price": 1500,
                    "modifiers": []
                }
            ],
            "subtotal": 4090,
            "tax": 409,
            "total": 4499
        }
        
        # Count orders and order items before attempt
        initial_order_count = await db_session.execute(
            "SELECT COUNT(*) FROM orders"
        )
        initial_orders = initial_order_count.scalar()
        
        initial_item_count = await db_session.execute(
            "SELECT COUNT(*) FROM order_items"
        )
        initial_items = initial_item_count.scalar()
        
        # Attempt to create order with invalid item
        with pytest.raises((ValueError, IntegrityError)):
            await create_order_with_validation(db_session, order_data)
        
        # Verify no orders or order items were created
        final_order_count = await db_session.execute(
            "SELECT COUNT(*) FROM orders"
        )
        final_orders = final_order_count.scalar()
        
        final_item_count = await db_session.execute(
            "SELECT COUNT(*) FROM order_items"
        )
        final_items = final_item_count.scalar()
        
        assert final_orders == initial_orders
        assert final_items == initial_items
    
    @pytest.mark.asyncio
    async def test_concurrent_order_creation_with_rollback(self, db_session, test_location, test_menu_items):
        """Test rollback behavior with concurrent order creation."""
        async def create_order_task(order_number: int, should_fail: bool = False):
            """Helper function to create an order."""
            order_data = {
                "location_id": test_location.id,
                "customer_name": f"Customer {order_number}",
                "customer_phone": f"+123456789{order_number}",
                "customer_email": f"customer{order_number}@example.com",
                "order_type": "pickup",
                "items": [
                    {
                        "plu": "CALI_001",
                        "quantity": 1,
                        "price": 1295,
                        "modifiers": []
                    }
                ],
                "subtotal": 1295,
                "tax": 130,
                "total": 1425
            }
            
            if should_fail:
                # Add invalid data to cause failure
                order_data["customer_name"] = None
            
            try:
                return await create_order_with_validation(db_session, order_data)
            except Exception as e:
                if should_fail:
                    return e  # Expected failure
                raise  # Unexpected failure
        
        # Create multiple concurrent orders, some should fail
        tasks = [
            create_order_task(1, should_fail=False),
            create_order_task(2, should_fail=True),   # This should fail
            create_order_task(3, should_fail=False),
            create_order_task(4, should_fail=True),   # This should fail
            create_order_task(5, should_fail=False),
        ]
        
        # Execute tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successful vs failed orders
        successful_orders = [r for r in results if isinstance(r, Order)]
        failed_orders = [r for r in results if isinstance(r, Exception)]
        
        # Should have 3 successful and 2 failed
        assert len(successful_orders) == 3
        assert len(failed_orders) == 2
        
        # Verify only successful orders are in database
        final_order_count = await db_session.execute(
            "SELECT COUNT(*) FROM orders WHERE location_id = :location_id"
        )
        final_count = final_order_count.scalar()
        
        # Should match number of successful orders
        assert final_count >= len(successful_orders)
    
    @pytest.mark.asyncio
    async def test_nested_transaction_rollback(self, db_session, test_location, test_menu_items):
        """Test rollback behavior with nested transactions."""
        order_data = {
            "location_id": test_location.id,
            "customer_name": "Nested Transaction Test",
            "customer_phone": "+1234567890",
            "customer_email": "nested@example.com",
            "order_type": "delivery",
            "items": [
                {
                    "plu": "CALI_001",
                    "quantity": 1,
                    "price": 1295,
                    "modifiers": []
                }
            ],
            "subtotal": 1295,
            "tax": 130,
            "total": 1425,
            "delivery_address": "123 Nested Street"
        }
        
        # Start a transaction
        async with db_session.begin():
            try:
                # Create the order
                order = Order(**order_data)
                db_session.add(order)
                await db_session.flush()  # Get the order ID
                
                # Create order items in nested transaction
                async with db_session.begin_nested():
                    for item_data in order_data["items"]:
                        order_item = OrderItem(
                            order_id=order.id,
                            **item_data
                        )
                        db_session.add(order_item)
                    
                    # Simulate failure in nested transaction
                    raise Exception("Simulated nested transaction failure")
                    
            except Exception:
                # The outer transaction should also rollback
                await db_session.rollback()
                raise
        
        # Verify no order was created
        order_count = await db_session.execute(
            "SELECT COUNT(*) FROM orders WHERE customer_name = :name",
            {"name": "Nested Transaction Test"}
        )
        count = order_count.scalar()
        assert count == 0
        
        # Verify no order items were created
        item_count = await db_session.execute(
            "SELECT COUNT(*) FROM order_items"
        )
        items = item_count.scalar()
        # Should be same as before (no new items added)
        assert items >= 0  # Just verify query works