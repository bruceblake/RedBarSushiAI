"""
Unit tests for database models.
Tests model validation, relationships, and business logic.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from app.models.menu_async import MenuItem, MenuModifier, MenuModifierGroup, MenuNameVariant
from app.models.order_async import Order, OrderItem, OrderItemModifier
from app.models.location_async import Location


class TestMenuItemModel:
    """Test MenuItem model functionality."""
    
    @pytest.mark.asyncio
    async def test_menu_item_creation(self, db_session):
        """Test creating a menu item with required fields."""
        item = MenuItem(
            name="California Roll",
            plu="PLU_CALI_001",
            price=1295,  # $12.95 in cents
            description="Crab, avocado, cucumber",
            is_available=True
        )
        db_session.add(item)
        await db_session.commit()
        
        assert item.id is not None
        assert item.name == "California Roll"
        assert item.plu == "PLU_CALI_001"
        assert item.price == 1295
    
    @pytest.mark.asyncio
    async def test_plu_uniqueness(self, db_session):
        """Test PLU must be unique."""
        item1 = MenuItem(name="Item 1", plu="UNIQUE_PLU", price=1000)
        item2 = MenuItem(name="Item 2", plu="UNIQUE_PLU", price=2000)
        
        db_session.add(item1)
        await db_session.commit()
        
        db_session.add(item2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_snooze_functionality(self, db_session):
        """Test item snooze until specific time."""
        future_time = datetime.utcnow() + timedelta(hours=2)
        item = MenuItem(
            name="Limited Item",
            plu="PLU_LIMITED",
            price=1500,
            is_available=True,
            snoozed_until=future_time
        )
        db_session.add(item)
        await db_session.commit()
        
        # Item should be considered unavailable if snoozed
        assert item.snoozed_until > datetime.utcnow()
        assert item.is_effectively_available() is False
    
    @pytest.mark.asyncio
    async def test_price_display_formatting(self):
        """Test price formatting for display."""
        item = MenuItem(name="Test", plu="TEST", price=1295)
        assert item.formatted_price == "$12.95"
        
        item_no_cents = MenuItem(name="Test2", plu="TEST2", price=1000)
        assert item_no_cents.formatted_price == "$10.00"


class TestMenuModifierModel:
    """Test MenuModifier model functionality."""
    
    @pytest.mark.asyncio
    async def test_modifier_price_changes(self, db_session):
        """Test modifiers can add or subtract from price."""
        add_modifier = MenuModifier(
            name="Extra Avocado",
            plu="MOD_EXTRA_AVO",
            price_change=200  # +$2.00
        )
        
        remove_modifier = MenuModifier(
            name="No Wasabi",
            plu="MOD_NO_WASABI",
            price_change=0  # No charge
        )
        
        discount_modifier = MenuModifier(
            name="Light Rice",
            plu="MOD_LIGHT_RICE",
            price_change=-50  # -$0.50
        )
        
        db_session.add_all([add_modifier, remove_modifier, discount_modifier])
        await db_session.commit()
        
        assert add_modifier.price_change == 200
        assert remove_modifier.price_change == 0
        assert discount_modifier.price_change == -50
    
    @pytest.mark.asyncio
    async def test_modifier_group_constraints(self, db_session):
        """Test modifier group selection constraints."""
        group = MenuModifierGroup(
            name="Spice Level",
            plu="GRP_SPICE",
            min_selection=0,
            max_selection=1  # Can only choose one
        )
        
        mild = MenuModifier(name="Mild", plu="MOD_MILD", modifier_group_id=group.id)
        medium = MenuModifier(name="Medium", plu="MOD_MEDIUM", modifier_group_id=group.id)
        hot = MenuModifier(name="Hot", plu="MOD_HOT", modifier_group_id=group.id)
        
        db_session.add_all([group, mild, medium, hot])
        await db_session.commit()
        
        assert len(group.modifiers) == 3
        assert group.is_required is False  # min_selection = 0
        assert group.allows_multiple is False  # max_selection = 1


class TestMenuNameVariantModel:
    """Test MenuNameVariant model for natural language mapping."""
    
    @pytest.mark.asyncio
    async def test_variant_creation(self, db_session):
        """Test creating name variants for menu items."""
        variants = [
            MenuNameVariant(
                variant_phrase="cali roll",
                canonical_name="California Roll",
                target_plu="PLU_CALI_001"
            ),
            MenuNameVariant(
                variant_phrase="california",
                canonical_name="California Roll",
                target_plu="PLU_CALI_001"
            ),
            MenuNameVariant(
                variant_phrase="cali",
                canonical_name="California Roll",
                target_plu="PLU_CALI_001"
            )
        ]
        
        db_session.add_all(variants)
        await db_session.commit()
        
        # All variants should point to same PLU
        for variant in variants:
            assert variant.target_plu == "PLU_CALI_001"
    
    @pytest.mark.asyncio
    async def test_variant_normalization(self):
        """Test variant phrases are normalized."""
        variant = MenuNameVariant(
            variant_phrase="SPICY TUNA!!!",
            canonical_name="Spicy Tuna Roll",
            target_plu="PLU_SPICY_TUNA"
        )
        
        # Should normalize to lowercase
        assert variant.normalized_phrase == "spicy tuna"


class TestOrderModel:
    """Test Order model functionality."""
    
    @pytest.mark.asyncio
    async def test_order_creation(self, db_session):
        """Test creating an order with required fields."""
        order = Order(
            customer_phone="+1234567890",
            customer_name="John Doe",
            order_type="pickup",
            status="pending",
            total_price=2495  # $24.95
        )
        db_session.add(order)
        await db_session.commit()
        
        assert order.id is not None
        assert order.placed_at is not None
        assert order.order_number is not None  # Auto-generated
    
    @pytest.mark.asyncio
    async def test_order_channel_id_generation(self, db_session):
        """Test Deliverect channel order ID generation."""
        order = Order(
            customer_phone="+1234567890",
            order_type="delivery"
        )
        db_session.add(order)
        await db_session.commit()
        
        # Should generate unique channel order ID
        assert order.deliverect_channel_order_id is not None
        assert order.deliverect_channel_order_id.startswith("RBS-")
    
    @pytest.mark.asyncio
    async def test_order_status_transitions(self):
        """Test valid order status values."""
        valid_statuses = [
            "pending", "confirmed", "preparing", 
            "ready", "delivered", "cancelled"
        ]
        
        for status in valid_statuses:
            order = Order(
                customer_phone="+1234567890",
                status=status
            )
            assert order.status == status


class TestOrderItemModel:
    """Test OrderItem model functionality."""
    
    @pytest.mark.asyncio
    async def test_order_item_with_modifiers(self, db_session):
        """Test order item with modifiers."""
        # Create order and item
        order = Order(customer_phone="+1234567890")
        order_item = OrderItem(
            order_id=order.id,
            menu_item_plu="PLU_CALI_001",
            menu_item_name="California Roll",
            quantity=2,
            unit_price=1295,
            total_price=2590  # 2 * 1295
        )
        
        # Add modifiers
        modifier1 = OrderItemModifier(
            order_item_id=order_item.id,
            modifier_plu="MOD_EXTRA_AVO",
            modifier_name="Extra Avocado",
            price_change=200
        )
        
        db_session.add_all([order, order_item, modifier1])
        await db_session.commit()
        
        assert len(order.items) == 1
        assert len(order_item.modifiers) == 1
        assert order_item.total_with_modifiers == 2990  # (1295 + 200) * 2
    
    @pytest.mark.asyncio
    async def test_order_total_calculation(self, db_session):
        """Test calculating order total from items."""
        order = Order(customer_phone="+1234567890")
        
        item1 = OrderItem(
            order_id=order.id,
            menu_item_plu="PLU_CALI",
            menu_item_name="California Roll",
            quantity=2,
            unit_price=1295,
            total_price=2590
        )
        
        item2 = OrderItem(
            order_id=order.id,
            menu_item_plu="PLU_EDAMAME",
            menu_item_name="Edamame",
            quantity=1,
            unit_price=595,
            total_price=595
        )
        
        db_session.add_all([order, item1, item2])
        await db_session.commit()
        
        # Order should calculate total from items
        assert order.calculated_total == 3185  # 2590 + 595


class TestLocationModel:
    """Test Location model functionality."""
    
    @pytest.mark.asyncio
    async def test_location_business_hours(self, db_session):
        """Test location business hours storage."""
        location = Location(
            name="Red Bar Sushi Main",
            address="123 Sushi St",
            phone="+1234567890",
            deliverect_location_id="LOC123",
            deliverect_channel_link_id="LINK123",
            business_hours={
                "monday": {"open": "11:00", "close": "22:00"},
                "tuesday": {"open": "11:00", "close": "22:00"},
                "wednesday": {"open": "11:00", "close": "22:00"},
                "thursday": {"open": "11:00", "close": "22:00"},
                "friday": {"open": "11:00", "close": "23:00"},
                "saturday": {"open": "12:00", "close": "23:00"},
                "sunday": {"open": "12:00", "close": "21:00"}
            }
        )
        
        db_session.add(location)
        await db_session.commit()
        
        assert location.id is not None
        assert location.business_hours["friday"]["close"] == "23:00"
    
    @pytest.mark.asyncio
    async def test_location_is_open_check(self):
        """Test checking if location is currently open."""
        location = Location(
            name="Test Location",
            business_hours={
                "monday": {"open": "09:00", "close": "17:00"}
            }
        )
        
        # Mock current time to Monday 2pm
        import datetime
        mock_time = datetime.datetime(2024, 1, 15, 14, 0)  # Monday 2pm
        
        # Would need to implement is_open() method
        # assert location.is_open(mock_time) is True
        
        # Mock current time to Monday 8pm
        mock_time_closed = datetime.datetime(2024, 1, 15, 20, 0)
        # assert location.is_open(mock_time_closed) is False


class TestModelRelationships:
    """Test relationships between models."""
    
    @pytest.mark.asyncio
    async def test_cascade_delete_order_items(self, db_session):
        """Test deleting order cascades to items."""
        order = Order(customer_phone="+1234567890")
        item = OrderItem(
            order_id=order.id,
            menu_item_plu="PLU_TEST",
            quantity=1,
            unit_price=1000
        )
        
        db_session.add_all([order, item])
        await db_session.commit()
        
        # Delete order
        await db_session.delete(order)
        await db_session.commit()
        
        # Item should be deleted too
        items = await db_session.execute(
            select(OrderItem).where(OrderItem.order_id == order.id)
        )
        assert len(items.scalars().all()) == 0
    
    @pytest.mark.asyncio
    async def test_menu_item_modifier_groups(self, db_session):
        """Test many-to-many relationship between items and modifier groups."""
        item = MenuItem(name="Sushi Combo", plu="PLU_COMBO", price=2495)
        
        group1 = MenuModifierGroup(name="Protein", plu="GRP_PROTEIN")
        group2 = MenuModifierGroup(name="Sides", plu="GRP_SIDES")
        
        item.modifier_groups.append(group1)
        item.modifier_groups.append(group2)
        
        db_session.add_all([item, group1, group2])
        await db_session.commit()
        
        assert len(item.modifier_groups) == 2
        assert group1 in item.modifier_groups
        assert group2 in item.modifier_groups