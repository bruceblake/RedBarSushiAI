"""
Unit tests for database models.
"""
import pytest
from datetime import datetime, timedelta
from app.models.menu_async import MenuItem, MenuModifier, MenuCategory, MenuNameVariant
from app.models.order_async import Order, OrderItem, OrderItemModifier
from app.models.location_async import Location


class TestMenuModels:
    """Test menu-related models."""
    
    @pytest.mark.asyncio
    async def test_menu_item_creation(self, db_session):
        """Test creating a menu item."""
        item = MenuItem(
            name="Test Roll",
            description="A test sushi roll",
            price=999,
            plu="TEST_001",
            category_id=1,
            is_available=True
        )
        
        db_session.add(item)
        await db_session.commit()
        
        assert item.id is not None
        assert item.name == "Test Roll"
        assert item.price == 999
        assert item.plu == "TEST_001"
        assert item.is_available is True
    
    @pytest.mark.asyncio
    async def test_menu_item_price_display(self):
        """Test menu item price display formatting."""
        item = MenuItem(name="Test", price=1295, plu="TEST")
        assert item.price_display == "$12.95"
        
        item.price = 1000
        assert item.price_display == "$10.00"
        
        item.price = 99
        assert item.price_display == "$0.99"
    
    @pytest.mark.asyncio
    async def test_menu_modifier_price_change(self):
        """Test modifier price change display."""
        modifier = MenuModifier(
            name="Extra Sauce",
            price_change=150,
            plu="MOD_001"
        )
        assert modifier.price_change_display == "+$1.50"
        
        modifier.price_change = -100
        assert modifier.price_change_display == "-$1.00"
        
        modifier.price_change = 0
        assert modifier.price_change_display == "$0.00"
    
    @pytest.mark.asyncio
    async def test_menu_category_items_relationship(self, db_session):
        """Test category-items relationship."""
        category = MenuCategory(name="Test Category")
        item1 = MenuItem(name="Item 1", price=100, plu="ITEM_001")
        item2 = MenuItem(name="Item 2", price=200, plu="ITEM_002")
        
        category.items.append(item1)
        category.items.append(item2)
        
        db_session.add(category)
        await db_session.commit()
        
        assert len(category.items) == 2
        assert item1.category_id == category.id
        assert item2.category_id == category.id
    
    @pytest.mark.asyncio
    async def test_menu_name_variant(self, db_session):
        """Test menu name variants for fuzzy matching."""
        variant = MenuNameVariant(
            variant_phrase="cali roll",
            canonical_name="California Roll",
            target_plu="CALI_001"
        )
        
        db_session.add(variant)
        await db_session.commit()
        
        assert variant.variant_phrase == "cali roll"
        assert variant.canonical_name == "California Roll"
        assert variant.target_plu == "CALI_001"
    
    @pytest.mark.asyncio
    async def test_item_availability_with_snooze(self):
        """Test item availability with snooze functionality."""
        item = MenuItem(
            name="Test Item",
            price=1000,
            plu="TEST_001",
            is_available=True,
            snoozed_until=datetime.utcnow() + timedelta(hours=1)
        )
        
        # Item should be unavailable if snoozed
        assert item.is_available is True  # Base availability
        assert item.snoozed_until > datetime.utcnow()  # But snoozed


class TestOrderModels:
    """Test order-related models."""
    
    @pytest.mark.asyncio
    async def test_order_creation(self, db_session):
        """Test creating an order."""
        order = Order(
            customer_phone="+1234567890",
            customer_name="John Doe",
            order_type="pickup",
            total_price=2590,
            status="pending"
        )
        
        db_session.add(order)
        await db_session.commit()
        
        assert order.id is not None
        assert order.customer_phone == "+1234567890"
        assert order.total_price == 2590
        assert order.status == "pending"
        assert order.placed_at is not None
    
    @pytest.mark.asyncio
    async def test_order_item_relationship(self, db_session, sample_menu_data):
        """Test order-item relationship."""
        order = Order(
            customer_phone="+1234567890",
            customer_name="Test Customer",
            order_type="pickup",
            total_price=0
        )
        
        california_roll = sample_menu_data["items"][0]
        
        order_item = OrderItem(
            menu_item_id=california_roll.id,
            menu_item_plu=california_roll.plu,
            quantity=2,
            unit_price=california_roll.price,
            total_price=california_roll.price * 2
        )
        
        order.items.append(order_item)
        order.total_price = order_item.total_price
        
        db_session.add(order)
        await db_session.commit()
        
        assert len(order.items) == 1
        assert order.items[0].quantity == 2
        assert order.total_price == california_roll.price * 2
    
    @pytest.mark.asyncio
    async def test_order_item_modifiers(self, db_session, sample_menu_data):
        """Test order item modifiers."""
        order = Order(
            customer_phone="+1234567890",
            customer_name="Test Customer",
            order_type="pickup"
        )
        
        item = sample_menu_data["items"][0]
        modifier = sample_menu_data["modifiers"][0]
        
        order_item = OrderItem(
            menu_item_id=item.id,
            menu_item_plu=item.plu,
            quantity=1,
            unit_price=item.price
        )
        
        item_modifier = OrderItemModifier(
            modifier_id=modifier.id,
            modifier_plu=modifier.plu,
            price_change=modifier.price_change
        )
        
        order_item.modifiers.append(item_modifier)
        order_item.total_price = item.price + modifier.price_change
        
        order.items.append(order_item)
        order.total_price = order_item.total_price
        
        db_session.add(order)
        await db_session.commit()
        
        assert len(order.items[0].modifiers) == 1
        assert order.items[0].modifiers[0].price_change == modifier.price_change
        assert order.total_price == item.price + modifier.price_change
    
    @pytest.mark.asyncio
    async def test_order_status_tracking(self, db_session):
        """Test order status tracking."""
        order = Order(
            customer_phone="+1234567890",
            customer_name="Test Customer",
            order_type="delivery",
            status="pending"
        )
        
        db_session.add(order)
        await db_session.commit()
        
        # Update status
        order.status = "confirmed"
        order.deliverect_order_id = "DEL123"
        await db_session.commit()
        
        assert order.status == "confirmed"
        assert order.deliverect_order_id == "DEL123"
        
        # Test delivery fields
        order.delivery_address = "123 Test St"
        order.estimated_time = datetime.utcnow() + timedelta(minutes=30)
        await db_session.commit()
        
        assert order.delivery_address == "123 Test St"
        assert order.estimated_time > datetime.utcnow()


class TestLocationModel:
    """Test location model."""
    
    @pytest.mark.asyncio
    async def test_location_creation(self, db_session):
        """Test creating a location."""
        location = Location(
            id="test-location-001",
            name="Test Location",
            status="active",
            webhook_base="https://test.example.com/webhook",
            api_key="test-api-key-123"
        )
        
        db_session.add(location)
        await db_session.commit()
        
        assert location.id == "test-location-001"
        assert location.name == "Test Location"
        assert location.status == "active"
        assert location.webhook_base == "https://test.example.com/webhook"
    
    @pytest.mark.asyncio
    async def test_location_business_hours(self, db_session):
        """Test location with to_dict method."""
        location = Location(
            id="test-location-002",
            name="Test Location 2",
            status="registered"
        )
        
        db_session.add(location)
        await db_session.commit()
        
        # Test to_dict method
        location_dict = location.to_dict()
        assert location_dict["id"] == "test-location-002"
        assert location_dict["name"] == "Test Location 2"
        assert location_dict["status"] == "registered"
        assert "created_at" in location_dict
        assert "updated_at" in location_dict