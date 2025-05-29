"""
Integration tests for database operations.
Tests CRUD operations with real test database.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.models.menu_async import MenuItem, MenuCategory, MenuModifier, MenuModifierGroup, MenuNameVariant
from app.models.order_async import Order, OrderItem, OrderItemModifier
from app.db.crud_menu_async import (
    create_category, create_item, create_modifier, create_modifier_group,
    get_item_by_plu, get_all_available_items, link_item_to_modifier_group
)
from app.schemas.menu import MenuCategoryCreate, MenuItemCreate, MenuModifierCreate, MenuModifierGroupCreate


@pytest.mark.integration
class TestMenuDatabaseOperations:
    """Test menu-related database operations."""
    
    @pytest.fixture
    async def db_session(self, setup_database):
        """Get test database session."""
        from tests.e2e.conftest import TestSessionLocal
        async with TestSessionLocal() as session:
            yield session
            # Clean up after each test
            await session.execute(delete(OrderItemModifier))
            await session.execute(delete(OrderItem))
            await session.execute(delete(Order))
            await session.execute(delete(MenuItem))
            await session.execute(delete(MenuModifier))
            await session.execute(delete(MenuModifierGroup))
            await session.execute(delete(MenuCategory))
            await session.execute(delete(MenuNameVariant))
            await session.commit()
    
    @pytest.mark.asyncio
    async def test_create_menu_category(self, db_session):
        """Test creating a menu category."""
        category_data = MenuCategoryCreate(
            name="Test Rolls",
            description="Test sushi rolls",
            deliverect_category_id="CAT_TEST_001"
        )
        
        category = await create_category(db_session, category_data)
        
        assert category.id is not None
        assert category.name == "Test Rolls"
        assert category.description == "Test sushi rolls"
        assert category.deliverect_category_id == "CAT_TEST_001"
    
    @pytest.mark.asyncio
    async def test_create_menu_item_with_category(self, db_session):
        """Test creating a menu item with category."""
        # Create category first
        category = await create_category(
            db_session,
            MenuCategoryCreate(name="Rolls", deliverect_category_id="CAT_ROLLS")
        )
        
        # Create item
        item_data = MenuItemCreate(
            name="Test California Roll",
            category_id=category.id,
            price=1200,
            description="Test roll with crab and avocado",
            plu="PLU_TEST_CALI",
            deliverect_item_id="ITEM_TEST_001",
            is_available=True
        )
        
        item = await create_item(db_session, item_data)
        
        assert item.id is not None
        assert item.name == "Test California Roll"
        assert item.plu == "PLU_TEST_CALI"
        assert item.price == 1200
        assert item.category_id == category.id
        assert item.is_available is True
    
    @pytest.mark.asyncio
    async def test_create_modifier_group_with_modifiers(self, db_session):
        """Test creating modifier groups with modifiers."""
        # Create modifier group
        group_data = MenuModifierGroupCreate(
            name="Spice Level",
            min_selection=0,
            max_selection=1,
            deliverect_group_id="MG_SPICE",
            plu="PLU_MG_SPICE"
        )
        
        group = await create_modifier_group(db_session, group_data)
        
        # Create modifiers
        modifiers = []
        for name, plu, price in [("Mild", "MOD_MILD", 0), ("Spicy", "MOD_SPICY", 0), ("Extra Spicy", "MOD_EXTRA", 100)]:
            mod = await create_modifier(
                db_session,
                MenuModifierCreate(
                    name=name,
                    price_change=price,
                    plu=plu,
                    deliverect_modifier_id=f"MOD_{plu}"
                )
            )
            modifiers.append(mod)
            
            # Link to group
            from app.db.crud_menu_async import link_modifier_to_group
            await link_modifier_to_group(db_session, mod.id, group.id)
        
        # Verify relationships
        await db_session.refresh(group)
        assert len(group.modifiers) == 3
        assert any(m.name == "Spicy" for m in group.modifiers)
    
    @pytest.mark.asyncio
    async def test_get_item_by_plu(self, db_session):
        """Test retrieving item by PLU."""
        # Create test item
        item = await create_item(
            db_session,
            MenuItemCreate(
                name="PLU Test Item",
                plu="PLU_UNIQUE_TEST",
                price=800
            )
        )
        
        # Retrieve by PLU
        retrieved = await get_item_by_plu(db_session, "PLU_UNIQUE_TEST")
        
        assert retrieved is not None
        assert retrieved.id == item.id
        assert retrieved.name == "PLU Test Item"
    
    @pytest.mark.asyncio
    async def test_get_all_available_items(self, db_session):
        """Test retrieving only available items."""
        # Create mix of available and unavailable items
        available_item = await create_item(
            db_session,
            MenuItemCreate(name="Available Item", plu="PLU_AVAIL", price=1000, is_available=True)
        )
        
        unavailable_item = await create_item(
            db_session,
            MenuItemCreate(name="Unavailable Item", plu="PLU_UNAVAIL", price=1000, is_available=False)
        )
        
        snoozed_item = await create_item(
            db_session,
            MenuItemCreate(
                name="Snoozed Item",
                plu="PLU_SNOOZED",
                price=1000,
                is_available=False,
                snoozed_until=datetime.utcnow() + timedelta(hours=2)
            )
        )
        
        # Get available items
        available_items = await get_all_available_items(db_session)
        available_pluts = [item.plu for item in available_items]
        
        assert "PLU_AVAIL" in available_pluts
        assert "PLU_UNAVAIL" not in available_pluts
        assert "PLU_SNOOZED" not in available_pluts
    
    @pytest.mark.asyncio
    async def test_menu_name_variants(self, db_session):
        """Test natural language variant mapping."""
        # Create item
        item = await create_item(
            db_session,
            MenuItemCreate(name="California Roll", plu="PLU_CALIFORNIA", price=1200)
        )
        
        # Create variants
        variants = [
            MenuNameVariant(variant_phrase="cali roll", canonical_name="California Roll", target_plu="PLU_CALIFORNIA"),
            MenuNameVariant(variant_phrase="california", canonical_name="California Roll", target_plu="PLU_CALIFORNIA"),
            MenuNameVariant(variant_phrase="cali", canonical_name="California Roll", target_plu="PLU_CALIFORNIA")
        ]
        
        db_session.add_all(variants)
        await db_session.commit()
        
        # Test variant lookup
        result = await db_session.scalar(
            select(MenuNameVariant).where(MenuNameVariant.variant_phrase == "cali roll")
        )
        
        assert result is not None
        assert result.target_plu == "PLU_CALIFORNIA"
        assert result.canonical_name == "California Roll"
    
    @pytest.mark.asyncio
    async def test_item_with_multiple_modifier_groups(self, db_session):
        """Test item with multiple modifier groups."""
        # Create item
        item = await create_item(
            db_session,
            MenuItemCreate(name="Custom Roll", plu="PLU_CUSTOM", price=1500)
        )
        
        # Create multiple modifier groups
        spice_group = await create_modifier_group(
            db_session,
            MenuModifierGroupCreate(name="Spice Level", plu="MG_SPICE_2")
        )
        
        addon_group = await create_modifier_group(
            db_session,
            MenuModifierGroupCreate(name="Add-ons", plu="MG_ADDONS", max_selection=3)
        )
        
        # Link both groups to item
        await link_item_to_modifier_group(db_session, item.id, spice_group.id)
        await link_item_to_modifier_group(db_session, item.id, addon_group.id)
        
        # Verify relationships
        await db_session.refresh(item)
        assert len(item.modifier_groups) == 2
        group_names = [g.name for g in item.modifier_groups]
        assert "Spice Level" in group_names
        assert "Add-ons" in group_names


@pytest.mark.integration
class TestOrderDatabaseOperations:
    """Test order-related database operations."""
    
    @pytest.fixture
    async def db_session(self, setup_database):
        """Get test database session."""
        from tests.e2e.conftest import TestSessionLocal
        async with TestSessionLocal() as session:
            yield session
            # Clean up
            await session.execute(delete(OrderItemModifier))
            await session.execute(delete(OrderItem))
            await session.execute(delete(Order))
            await session.commit()
    
    @pytest.fixture
    async def sample_menu_items(self, db_session):
        """Create sample menu items for orders."""
        category = await create_category(
            db_session,
            MenuCategoryCreate(name="Test Category")
        )
        
        items = []
        for name, plu, price in [
            ("Test Roll 1", "PLU_TEST_1", 1000),
            ("Test Roll 2", "PLU_TEST_2", 1200)
        ]:
            item = await create_item(
                db_session,
                MenuItemCreate(
                    name=name,
                    plu=plu,
                    price=price,
                    category_id=category.id
                )
            )
            items.append(item)
        
        return items
    
    @pytest.mark.asyncio
    async def test_create_order_with_items(self, db_session, sample_menu_items):
        """Test creating order with items."""
        # Create order
        order = Order(
            deliverect_channel_order_id="TEST_ORDER_001",
            customer_phone="+1234567890",
            customer_name="Test Customer",
            order_type="pickup",
            status="pending",
            total_price=2200
        )
        db_session.add(order)
        await db_session.flush()
        
        # Add order items
        for item, quantity in zip(sample_menu_items, [1, 1]):
            order_item = OrderItem(
                order_id=order.id,
                menu_item_plu=item.plu,
                quantity=quantity,
                price=item.price * quantity
            )
            db_session.add(order_item)
        
        await db_session.commit()
        
        # Verify order
        await db_session.refresh(order)
        assert order.id is not None
        assert len(order.items) == 2
        assert order.total_price == 2200
    
    @pytest.mark.asyncio
    async def test_order_with_modifiers(self, db_session, sample_menu_items):
        """Test order items with modifiers."""
        # Create modifiers
        modifier = await create_modifier(
            db_session,
            MenuModifierCreate(
                name="Extra Sauce",
                plu="MOD_EXTRA_SAUCE",
                price_change=50
            )
        )
        
        # Create order
        order = Order(
            deliverect_channel_order_id="TEST_ORDER_002",
            customer_phone="+1234567890",
            order_type="delivery",
            delivery_address="123 Test St"
        )
        db_session.add(order)
        await db_session.flush()
        
        # Add order item with modifier
        order_item = OrderItem(
            order_id=order.id,
            menu_item_plu=sample_menu_items[0].plu,
            quantity=1,
            price=sample_menu_items[0].price
        )
        db_session.add(order_item)
        await db_session.flush()
        
        # Add modifier to order item
        item_modifier = OrderItemModifier(
            order_item_id=order_item.id,
            modifier_plu=modifier.plu,
            price=modifier.price_change
        )
        db_session.add(item_modifier)
        
        await db_session.commit()
        
        # Verify
        await db_session.refresh(order_item)
        assert len(order_item.modifiers) == 1
        assert order_item.modifiers[0].modifier_plu == "MOD_EXTRA_SAUCE"
    
    @pytest.mark.asyncio
    async def test_order_status_updates(self, db_session):
        """Test updating order status."""
        # Create order
        order = Order(
            deliverect_channel_order_id="TEST_ORDER_003",
            customer_phone="+1234567890",
            status="pending"
        )
        db_session.add(order)
        await db_session.commit()
        
        # Update status
        order.status = "confirmed"
        order.estimated_time = datetime.utcnow() + timedelta(minutes=30)
        await db_session.commit()
        
        # Verify update
        updated_order = await db_session.get(Order, order.id)
        assert updated_order.status == "confirmed"
        assert updated_order.estimated_time is not None
    
    @pytest.mark.asyncio
    async def test_concurrent_order_creation(self, db_session):
        """Test creating multiple orders concurrently."""
        async def create_test_order(order_id: str):
            order = Order(
                deliverect_channel_order_id=order_id,
                customer_phone="+1234567890",
                status="pending"
            )
            db_session.add(order)
            return order
        
        # Create multiple orders
        order_ids = [f"CONCURRENT_{i}" for i in range(5)]
        orders = [create_test_order(oid) for oid in order_ids]
        
        await db_session.commit()
        
        # Verify all created
        result = await db_session.scalars(
            select(Order).where(Order.deliverect_channel_order_id.like("CONCURRENT_%"))
        )
        created_orders = result.all()
        
        assert len(created_orders) == 5