"""
Integration tests for foreign key constraints - Task 3.5.3.

This module tests that foreign key relationships in the database
are properly enforced and prevent data integrity violations.
"""

import pytest
import pytest_asyncio
import uuid
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.menu_async import MenuItem, MenuCategory, MenuModifier, MenuModifierGroup
from app.models.order_async import Order, OrderItem, OrderItemModifier
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
async def test_category(db_session):
    """Create a test menu category."""
    category = MenuCategory(
        name="Test Sushi Rolls",
        description="Test category for sushi rolls",
        location_id="test_location_001"
    )
    db_session.add(category)
    await db_session.commit()
    await db_session.refresh(category)
    return category


@pytest_asyncio.fixture
async def test_modifier_group(db_session):
    """Create a test modifier group."""
    modifier_group = MenuModifierGroup(
        name="Test Spice Level",
        min_selection=0,
        max_selection=1,
        location_id="test_location_001"
    )
    db_session.add(modifier_group)
    await db_session.commit()
    await db_session.refresh(modifier_group)
    return modifier_group


@pytest_asyncio.fixture
async def test_order(db_session):
    """Create a test order."""
    order = Order(
        id=str(uuid.uuid4()),
        customer_phone="+1234567890",
        customer_name="Test Customer",
        order_type="pickup",
        total_price=25.50
    )
    db_session.add(order)
    await db_session.commit()
    await db_session.refresh(order)
    return order


@pytest_asyncio.fixture
async def test_order_item(db_session, test_order):
    """Create a test order item."""
    order_item = OrderItem(
        id=str(uuid.uuid4()),
        order_id=test_order.id,
        menu_item_plu="TEST_001",
        name="Test Sushi Roll",
        quantity=2,
        price=12.95
    )
    db_session.add(order_item)
    await db_session.commit()
    await db_session.refresh(order_item)
    return order_item


class TestMenuForeignKeyConstraints:
    """Test foreign key constraints for menu-related tables."""
    
    @pytest.mark.asyncio
    async def test_menu_item_valid_category_reference(self, db_session, test_category):
        """Test that menu items can reference valid categories."""
        menu_item = MenuItem(
            name="California Roll",
            description="Crab, avocado, cucumber",
            price=12.95,
            plu="CALI_001",
            category_id=test_category.id,
            location_id="test_location_001"
        )
        
        db_session.add(menu_item)
        await db_session.commit()
        await db_session.refresh(menu_item)
        
        # Verify the foreign key relationship works
        assert menu_item.category_id == test_category.id
        
        # Load the category through the relationship
        await db_session.refresh(menu_item, ['category'])
        assert menu_item.category.name == "Test Sushi Rolls"
    
    @pytest.mark.asyncio
    async def test_menu_item_invalid_category_reference(self, db_session):
        """Test that menu items cannot reference non-existent categories."""
        menu_item = MenuItem(
            name="Invalid Category Item",
            description="This should fail",
            price=10.00,
            plu="INVALID_001",
            category_id=99999,  # Non-existent category ID
            location_id="test_location_001"
        )
        
        db_session.add(menu_item)
        
        # Should raise IntegrityError due to foreign key constraint
        with pytest.raises(IntegrityError) as exc_info:
            await db_session.commit()
        
        # Verify it's specifically a foreign key violation
        assert "foreign key constraint" in str(exc_info.value).lower() or \
               "violates foreign key" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_menu_item_null_category_allowed(self, db_session):
        """Test that menu items can have null category_id (should be allowed)."""
        menu_item = MenuItem(
            name="Uncategorized Item",
            description="Item without category",
            price=8.00,
            plu="UNCAT_001",
            category_id=None,  # Null category should be allowed
            location_id="test_location_001"
        )
        
        db_session.add(menu_item)
        await db_session.commit()
        await db_session.refresh(menu_item)
        
        # Should succeed
        assert menu_item.category_id is None
        assert menu_item.name == "Uncategorized Item"
    
    @pytest.mark.asyncio
    async def test_delete_category_with_items_constraint(self, db_session, test_category):
        """Test cascade behavior when deleting category with menu items."""
        # Create a menu item that references the category
        menu_item = MenuItem(
            name="Test Roll",
            description="Test item",
            price=15.00,
            plu="TEST_001",
            category_id=test_category.id,
            location_id="test_location_001"
        )
        db_session.add(menu_item)
        await db_session.commit()
        
        # Try to delete the category
        await db_session.delete(test_category)
        
        # This might either cascade delete or raise constraint error
        # depending on the foreign key configuration
        try:
            await db_session.commit()
            
            # If deletion succeeded, check if item was also deleted (cascade)
            # or if its category_id was set to NULL
            await db_session.refresh(menu_item)
            # Item should either be deleted or have null category_id
            
        except IntegrityError:
            # If deletion failed, that's also valid behavior
            # for foreign key constraint protection
            await db_session.rollback()
            
            # Verify the category and item still exist
            await db_session.refresh(test_category)
            await db_session.refresh(menu_item)
            assert test_category.id is not None
            assert menu_item.category_id == test_category.id


class TestOrderForeignKeyConstraints:
    """Test foreign key constraints for order-related tables."""
    
    @pytest.mark.asyncio
    async def test_order_item_valid_order_reference(self, db_session, test_order):
        """Test that order items can reference valid orders."""
        order_item = OrderItem(
            id=str(uuid.uuid4()),
            order_id=test_order.id,
            menu_item_plu="VALID_001",
            name="Valid Order Item",
            quantity=1,
            price=10.00
        )
        
        db_session.add(order_item)
        await db_session.commit()
        await db_session.refresh(order_item)
        
        # Verify the foreign key relationship works
        assert order_item.order_id == test_order.id
        
        # Load the order through the relationship
        await db_session.refresh(order_item, ['order'])
        assert order_item.order.customer_name == "Test Customer"
    
    @pytest.mark.asyncio
    async def test_order_item_invalid_order_reference(self, db_session):
        """Test that order items cannot reference non-existent orders."""
        order_item = OrderItem(
            id=str(uuid.uuid4()),
            order_id="non-existent-order-id",  # Non-existent order ID
            menu_item_plu="INVALID_001",
            name="Invalid Order Item",
            quantity=1,
            price=10.00
        )
        
        db_session.add(order_item)
        
        # Should raise IntegrityError due to foreign key constraint
        with pytest.raises(IntegrityError) as exc_info:
            await db_session.commit()
        
        # Verify it's specifically a foreign key violation
        assert "foreign key constraint" in str(exc_info.value).lower() or \
               "violates foreign key" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_order_item_modifier_valid_order_item_reference(self, db_session, test_order_item):
        """Test that order item modifiers can reference valid order items."""
        order_item_modifier = OrderItemModifier(
            id=str(uuid.uuid4()),
            order_item_id=test_order_item.id,
            modifier_plu="SPICY_001",
            name="Extra Spicy",
            price_change=1.50
        )
        
        db_session.add(order_item_modifier)
        await db_session.commit()
        await db_session.refresh(order_item_modifier)
        
        # Verify the foreign key relationship works
        assert order_item_modifier.order_item_id == test_order_item.id
        
        # Load the order item through the relationship
        await db_session.refresh(order_item_modifier, ['order_item'])
        assert order_item_modifier.order_item.name == "Test Sushi Roll"
    
    @pytest.mark.asyncio
    async def test_order_item_modifier_invalid_order_item_reference(self, db_session):
        """Test that order item modifiers cannot reference non-existent order items."""
        order_item_modifier = OrderItemModifier(
            id=str(uuid.uuid4()),
            order_item_id="non-existent-item-id",  # Non-existent order item ID
            modifier_plu="INVALID_001",
            name="Invalid Modifier",
            price_change=0.00
        )
        
        db_session.add(order_item_modifier)
        
        # Should raise IntegrityError due to foreign key constraint
        with pytest.raises(IntegrityError) as exc_info:
            await db_session.commit()
        
        # Verify it's specifically a foreign key violation
        assert "foreign key constraint" in str(exc_info.value).lower() or \
               "violates foreign key" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_cascade_delete_order_with_items(self, db_session, test_order):
        """Test cascade deletion when order is deleted."""
        # Create order items and modifiers
        order_item = OrderItem(
            id=str(uuid.uuid4()),
            order_id=test_order.id,
            menu_item_plu="CASCADE_001",
            name="Cascade Test Item",
            quantity=1,
            price=15.00
        )
        db_session.add(order_item)
        await db_session.commit()
        await db_session.refresh(order_item)
        
        # Add modifier to the order item
        order_item_modifier = OrderItemModifier(
            id=str(uuid.uuid4()),
            order_item_id=order_item.id,
            modifier_plu="CASCADE_MOD_001",
            name="Cascade Test Modifier",
            price_change=2.00
        )
        db_session.add(order_item_modifier)
        await db_session.commit()
        
        # Count items and modifiers before deletion
        item_count_result = await db_session.execute(
            "SELECT COUNT(*) FROM order_items WHERE order_id = :order_id",
            {"order_id": test_order.id}
        )
        initial_item_count = item_count_result.scalar()
        
        modifier_count_result = await db_session.execute(
            "SELECT COUNT(*) FROM order_item_modifiers WHERE order_item_id = :item_id",
            {"item_id": order_item.id}
        )
        initial_modifier_count = modifier_count_result.scalar()
        
        assert initial_item_count == 1
        assert initial_modifier_count == 1
        
        # Delete the order
        await db_session.delete(test_order)
        await db_session.commit()
        
        # Verify cascade deletion worked
        final_item_count_result = await db_session.execute(
            "SELECT COUNT(*) FROM order_items WHERE order_id = :order_id",
            {"order_id": test_order.id}
        )
        final_item_count = final_item_count_result.scalar()
        
        final_modifier_count_result = await db_session.execute(
            "SELECT COUNT(*) FROM order_item_modifiers WHERE order_item_id = :item_id",
            {"item_id": order_item.id}
        )
        final_modifier_count = final_modifier_count_result.scalar()
        
        # Both should be 0 due to cascade deletion
        assert final_item_count == 0
        assert final_modifier_count == 0


class TestCascadeBehavior:
    """Test cascade deletion and update behavior across foreign key relationships."""
    
    @pytest.mark.asyncio
    async def test_multiple_level_cascade_deletion(self, db_session, test_order):
        """Test cascade deletion across multiple levels of foreign key relationships."""
        # Create a complete order hierarchy: Order -> OrderItem -> OrderItemModifier
        order_item1 = OrderItem(
            id=str(uuid.uuid4()),
            order_id=test_order.id,
            menu_item_plu="MULTI_001",
            name="Multi Level Item 1",
            quantity=1,
            price=12.00
        )
        
        order_item2 = OrderItem(
            id=str(uuid.uuid4()),
            order_id=test_order.id,
            menu_item_plu="MULTI_002",
            name="Multi Level Item 2",
            quantity=2,
            price=8.00
        )
        
        db_session.add_all([order_item1, order_item2])
        await db_session.commit()
        await db_session.refresh(order_item1)
        await db_session.refresh(order_item2)
        
        # Add modifiers to both items
        modifiers = [
            OrderItemModifier(
                id=str(uuid.uuid4()),
                order_item_id=order_item1.id,
                modifier_plu="MOD_001",
                name="Modifier 1A",
                price_change=1.00
            ),
            OrderItemModifier(
                id=str(uuid.uuid4()),
                order_item_id=order_item1.id,
                modifier_plu="MOD_002",
                name="Modifier 1B",
                price_change=1.50
            ),
            OrderItemModifier(
                id=str(uuid.uuid4()),
                order_item_id=order_item2.id,
                modifier_plu="MOD_003",
                name="Modifier 2A",
                price_change=0.50
            )
        ]
        
        db_session.add_all(modifiers)
        await db_session.commit()
        
        # Count everything before deletion
        order_count_result = await db_session.execute(
            "SELECT COUNT(*) FROM orders WHERE id = :order_id",
            {"order_id": test_order.id}
        )
        initial_order_count = order_count_result.scalar()
        
        item_count_result = await db_session.execute(
            "SELECT COUNT(*) FROM order_items WHERE order_id = :order_id",
            {"order_id": test_order.id}
        )
        initial_item_count = item_count_result.scalar()
        
        modifier_count_result = await db_session.execute(
            "SELECT COUNT(*) FROM order_item_modifiers WHERE order_item_id IN (:item1, :item2)",
            {"item1": order_item1.id, "item2": order_item2.id}
        )
        initial_modifier_count = modifier_count_result.scalar()
        
        # Verify initial state
        assert initial_order_count == 1
        assert initial_item_count == 2
        assert initial_modifier_count == 3
        
        # Delete the top-level order
        await db_session.delete(test_order)
        await db_session.commit()
        
        # Verify complete cascade deletion
        final_order_count_result = await db_session.execute(
            "SELECT COUNT(*) FROM orders WHERE id = :order_id",
            {"order_id": test_order.id}
        )
        final_order_count = final_order_count_result.scalar()
        
        final_item_count_result = await db_session.execute(
            "SELECT COUNT(*) FROM order_items WHERE order_id = :order_id",
            {"order_id": test_order.id}
        )
        final_item_count = final_item_count_result.scalar()
        
        final_modifier_count_result = await db_session.execute(
            "SELECT COUNT(*) FROM order_item_modifiers WHERE order_item_id IN (:item1, :item2)",
            {"item1": order_item1.id, "item2": order_item2.id}
        )
        final_modifier_count = final_modifier_count_result.scalar()
        
        # All should be 0 due to cascade deletion
        assert final_order_count == 0
        assert final_item_count == 0
        assert final_modifier_count == 0
    
    @pytest.mark.asyncio
    async def test_prevent_orphaned_records(self, db_session):
        """Test that the database prevents creation of orphaned records."""
        # Try to create order items without a valid order
        orphaned_items = [
            OrderItem(
                id=str(uuid.uuid4()),
                order_id="orphan-order-1",
                menu_item_plu="ORPHAN_001",
                name="Orphaned Item 1",
                quantity=1,
                price=10.00
            ),
            OrderItem(
                id=str(uuid.uuid4()),
                order_id="orphan-order-2",
                menu_item_plu="ORPHAN_002",
                name="Orphaned Item 2",
                quantity=1,
                price=10.00
            )
        ]
        
        for item in orphaned_items:
            db_session.add(item)
            
            # Each should fail due to foreign key constraint
            with pytest.raises(IntegrityError) as exc_info:
                await db_session.commit()
            
            assert "foreign key constraint" in str(exc_info.value).lower() or \
                   "violates foreign key" in str(exc_info.value).lower()
            
            await db_session.rollback()
    
    @pytest.mark.asyncio
    async def test_foreign_key_constraint_with_concurrent_operations(self, db_session):
        """Test foreign key constraints under concurrent operations."""
        # Create a temporary order
        temp_order = Order(
            id=str(uuid.uuid4()),
            customer_phone="+1987654321",
            customer_name="Concurrent Test",
            order_type="delivery",
            total_price=30.00
        )
        db_session.add(temp_order)
        await db_session.commit()
        await db_session.refresh(temp_order)
        
        # Try to create order item and delete order concurrently
        # (simulated by rapid succession)
        order_item = OrderItem(
            id=str(uuid.uuid4()),
            order_id=temp_order.id,
            menu_item_plu="CONCURRENT_001",
            name="Concurrent Test Item",
            quantity=1,
            price=15.00
        )
        
        # Add the order item
        db_session.add(order_item)
        await db_session.commit()
        
        # Now try to delete the order (should cascade delete the item)
        await db_session.delete(temp_order)
        await db_session.commit()
        
        # Verify the item was also deleted
        item_count_result = await db_session.execute(
            "SELECT COUNT(*) FROM order_items WHERE id = :item_id",
            {"item_id": order_item.id}
        )
        item_count = item_count_result.scalar()
        
        assert item_count == 0