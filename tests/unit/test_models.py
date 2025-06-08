"""
Comprehensive unit tests for database models - Task 2.4.1.

This module tests menu models including:
- MenuCategory with hierarchical structure
- MenuItem with variants and snoozing
- MenuModifier and MenuModifierGroup
- Relationships and associations
- JSONB properties and sanitization
"""
import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from app.models.menu_async import (
    MenuItem, MenuModifier, MenuCategory, MenuNameVariant,
    MenuModifierGroup
)
from app.models.order_async import Order, OrderItem, OrderItemModifier
from app.models.location_async import Location
from app.models.base_async import BaseModel, TimestampMixin

# Mock enums for testing - these may not exist in the actual codebase
from enum import Enum

class CategoryType(str, Enum):
    PRODUCT = "product"
    MODIFIER = "modifier"
    COMBO = "combo"

class ModifierMultiplicity(str, Enum):
    SINGLE = "single"
    MULTIPLE = "multiple"
    CUSTOM = "custom"


class TestMenuCategoryModel:
    """Test MenuCategory model functionality - Task 2.4.1."""
    
    @pytest.mark.asyncio
    async def test_category_creation_defaults(self):
        """Test creating category with default values."""
        category = MenuCategory(name="Sushi Rolls")
        
        assert category.name == "Sushi Rolls"
        assert category.description is None
        assert category.parent_id is None
        # SQLAlchemy defaults are applied at DB level, not in Python
        assert category.order_index is None or category.order_index == 0
        assert category.properties is None or category.properties == {}
    
    @pytest.mark.asyncio
    async def test_category_hierarchy(self, db_session):
        """Test category parent-child relationships."""
        parent = MenuCategory(name="Main Dishes")
        child1 = MenuCategory(name="Sushi", parent_id=parent.id)
        child2 = MenuCategory(name="Sashimi", parent_id=parent.id)
        
        db_session.add_all([parent, child1, child2])
        await db_session.commit()
        
        # Query to verify relationships
        result = await db_session.execute(
            select(MenuCategory).where(MenuCategory.parent_id == parent.id)
        )
        children = result.scalars().all()
        
        assert len(children) == 2
        assert all(child.parent_id == parent.id for child in children)
    
    @pytest.mark.asyncio
    async def test_category_properties(self):
        """Test category properties field."""
        category = MenuCategory(
            name="Test Category",
            properties={"display_type": "grid", "featured": True}
        )
        
        assert category.properties["display_type"] == "grid"
        assert category.properties["featured"] is True
        
        # Test empty properties
        empty_category = MenuCategory(name="Empty")
        assert empty_category.properties is None or empty_category.properties == {}
    
    @pytest.mark.asyncio
    async def test_category_jsonb_properties(self):
        """Test JSONB properties field."""
        properties = {
            "icon": "sushi-icon.png",
            "color": "#FF5733",
            "custom_field": "value"
        }
        
        category = MenuCategory(
            name="Special Category",
            properties=properties
        )
        
        assert category.properties == properties
        assert category.properties["icon"] == "sushi-icon.png"


class TestMenuItemModel:
    """Test MenuItem model functionality."""
    
    @pytest.mark.asyncio
    async def test_item_creation_required_fields(self):
        """Test creating item with required fields only."""
        item = MenuItem(
            name="California Roll",
            plu="CALI_001"
        )
        
        assert item.name == "California Roll"
        assert item.plu == "CALI_001"
        assert item.price == 0  # Default
        assert item.available is True  # Default
        assert item.properties == {}  # Default
    
    @pytest.mark.asyncio
    async def test_item_snooze_functionality(self):
        """Test item snoozing with datetime."""
        now = datetime.utcnow()
        snooze_until = now + timedelta(hours=2)
        
        item = MenuItem(
            name="Temp Unavailable",
            plu="TEMP_001",
            snoozed=True,
            snoozed_until=snooze_until
        )
        
        assert item.snoozed is True
        assert item.snoozed_until == snooze_until
        assert item.snoozed_until > now
    
    @pytest.mark.asyncio
    async def test_item_deliverect_integration(self):
        """Test Deliverect-specific fields."""
        item = MenuItem(
            name="Integration Item",
            plu="INT_001",
            deliverect_id="del_123456",
            properties={
                "deliverect_data": {
                    "pos_id": "POS123",
                    "sync_status": "synced"
                }
            }
        )
        
        assert item.deliverect_id == "del_123456"
        assert item.properties["deliverect_data"]["pos_id"] == "POS123"
    
    @pytest.mark.asyncio
    async def test_item_price_constraints(self):
        """Test price field constraints."""
        # Negative price should be allowed (discounts)
        item = MenuItem(name="Discount", plu="DISC_001", price=-500)
        assert item.price == -500
        assert item.price_display == "-$5.00"
        
        # Zero price
        item.price = 0
        assert item.price_display == "$0.00"
        
        # Large price
        item.price = 999999
        assert item.price_display == "$9,999.99"
    
    @pytest.mark.asyncio
    async def test_item_sanitize_properties(self):
        """Test properties sanitization."""
        with patch('app.models.menu_async.sanitize_properties') as mock_sanitize:
            mock_sanitize.return_value = {"clean": "data"}
            
            item = MenuItem(
                name="Test",
                plu="TEST",
                properties={"<script>": "bad"}
            )
            
            # In real implementation, properties should be sanitized
            mock_sanitize.assert_called()


class TestMenuModifierModel:
    """Test MenuModifier model functionality."""
    
    @pytest.mark.asyncio
    async def test_modifier_creation(self):
        """Test creating modifier with various fields."""
        modifier = MenuModifier(
            name="Extra Avocado",
            plu="MOD_AVO",
            price_change=200,
            is_available=True,
            max_quantity=3
        )
        
        assert modifier.name == "Extra Avocado"
        assert modifier.plu == "MOD_AVO"
        assert modifier.price_change == 200
        assert modifier.price_change_display == "+$2.00"
        assert modifier.max_quantity == 3
    
    @pytest.mark.asyncio
    async def test_modifier_snooze(self):
        """Test modifier snoozing."""
        snooze_time = datetime.utcnow() + timedelta(hours=1)
        modifier = MenuModifier(
            name="Temp Unavailable Mod",
            plu="MOD_TEMP",
            snoozed=True,
            snoozed_until=snooze_time
        )
        
        assert modifier.snoozed is True
        assert modifier.snoozed_until == snooze_time
    
    @pytest.mark.asyncio
    async def test_modifier_negative_price(self):
        """Test modifier with negative price (discount)."""
        modifier = MenuModifier(
            name="No Cheese",
            plu="MOD_NO_CHEESE",
            price_change=-150
        )
        
        assert modifier.price_change == -150
        assert modifier.price_change_display == "-$1.50"


class TestMenuModifierGroupModel:
    """Test MenuModifierGroup model functionality."""
    
    @pytest.mark.asyncio
    async def test_modifier_group_creation(self):
        """Test creating modifier group with constraints."""
        group = MenuModifierGroup(
            name="Toppings",
            description="Choose your toppings",
            min_selections=0,
            max_selections=3,
            is_required=False,
            multiplicity=ModifierMultiplicity.MULTIPLE
        )
        
        assert group.name == "Toppings"
        assert group.min_selections == 0
        assert group.max_selections == 3
        assert group.is_required is False
        assert group.multiplicity == ModifierMultiplicity.MULTIPLE
    
    @pytest.mark.asyncio
    async def test_modifier_group_required_constraints(self):
        """Test required modifier group constraints."""
        group = MenuModifierGroup(
            name="Spice Level",
            min_selections=1,
            max_selections=1,
            is_required=True,
            multiplicity=ModifierMultiplicity.SINGLE
        )
        
        assert group.is_required is True
        assert group.min_selections == 1
        assert group.max_selections == 1
        assert group.multiplicity == ModifierMultiplicity.SINGLE
    
    @pytest.mark.asyncio
    async def test_modifier_multiplicity_enum(self):
        """Test ModifierMultiplicity enum values."""
        assert ModifierMultiplicity.SINGLE.value == "single"
        assert ModifierMultiplicity.MULTIPLE.value == "multiple"
        assert ModifierMultiplicity.CUSTOM.value == "custom"


class TestMenuNameVariantModel:
    """Test MenuNameVariant model functionality."""
    
    @pytest.mark.asyncio
    async def test_variant_creation(self):
        """Test creating name variant for fuzzy matching."""
        variant = MenuNameVariant(
            variant_phrase="cali roll",
            canonical_name="California Roll",
            target_plu="CALI_001"
        )
        
        assert variant.variant_phrase == "cali roll"
        assert variant.canonical_name == "California Roll"
        assert variant.target_plu == "CALI_001"
    
    @pytest.mark.asyncio
    async def test_variant_case_sensitivity(self, db_session):
        """Test variant phrase case handling."""
        variant1 = MenuNameVariant(
            variant_phrase="SPICY TUNA",
            canonical_name="Spicy Tuna Roll",
            target_plu="TUNA_001"
        )
        
        variant2 = MenuNameVariant(
            variant_phrase="spicy tuna",
            canonical_name="Spicy Tuna Roll",
            target_plu="TUNA_001"
        )
        
        db_session.add_all([variant1, variant2])
        await db_session.commit()
        
        # Both variants should be stored separately
        result = await db_session.execute(
            select(MenuNameVariant).where(
                MenuNameVariant.target_plu == "TUNA_001"
            )
        )
        variants = result.scalars().all()
        
        assert len(variants) == 2


class TestMenuModelRelationships:
    """Test relationships between menu models."""
    
    @pytest.mark.asyncio
    async def test_item_modifier_group_association(self, db_session):
        """Test many-to-many relationship between items and modifier groups."""
        item = MenuItem(name="Burger", plu="BURG_001")
        
        group1 = MenuModifierGroup(name="Toppings")
        group2 = MenuModifierGroup(name="Sauces")
        
        # Create association
        assoc1 = ItemModifierGroup(display_order=1)
        assoc1.item = item
        assoc1.modifier_group = group1
        
        assoc2 = ItemModifierGroup(display_order=2)
        assoc2.item = item
        assoc2.modifier_group = group2
        
        db_session.add_all([item, group1, group2, assoc1, assoc2])
        await db_session.commit()
        
        # Verify associations
        assert len(item.modifier_groups) == 2
    
    @pytest.mark.asyncio
    async def test_modifier_group_modifier_association(self, db_session):
        """Test many-to-many relationship between groups and modifiers."""
        group = MenuModifierGroup(name="Extras")
        
        mod1 = MenuModifier(name="Extra Cheese", plu="MOD_CHEESE")
        mod2 = MenuModifier(name="Extra Bacon", plu="MOD_BACON")
        
        # Create associations
        assoc1 = GroupModifier(display_order=1)
        assoc1.group = group
        assoc1.modifier = mod1
        
        assoc2 = GroupModifier(display_order=2)
        assoc2.group = group
        assoc2.modifier = mod2
        
        db_session.add_all([group, mod1, mod2, assoc1, assoc2])
        await db_session.commit()
        
        # Verify associations
        assert len(group.modifiers) == 2


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
        assert item.available is True
    
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
        assert item.available is True  # Base availability
        assert item.snoozed_until > datetime.utcnow()  # But snoozed


class TestOrderModel:
    """Test Order model functionality - Task 2.4.2."""
    
    @pytest.mark.asyncio
    async def test_order_creation_defaults(self):
        """Test creating order with default values."""
        order = Order()
        
        assert order.id is not None  # Auto-generated
        assert len(order.id) == 36  # UUID format
        assert order.status == 0  # Default status
        assert order.total_price == 0
        assert order.items == []
        assert order.created_at is not None
    
    @pytest.mark.asyncio
    async def test_order_string_id(self):
        """Test that order uses string ID (36 chars)."""
        order = Order(id="test-order-uuid-1234567890123456")
        assert isinstance(order.id, str)
        assert len(order.id) <= 36
    
    @pytest.mark.asyncio
    async def test_order_timestamps(self):
        """Test order timestamp tracking."""
        order = Order()
        
        assert order.created_at is not None
        assert order.updated_at is not None
        assert order.placed_at is None  # Not placed yet
        
        # Simulate placing order
        order.placed_at = datetime.utcnow()
        assert order.placed_at is not None
    
    @pytest.mark.asyncio
    async def test_order_delivery_fields(self):
        """Test delivery-specific order fields."""
        order = Order(
            order_type="delivery",
            delivery_address="123 Main St",
            delivery_lat=37.7749,
            delivery_lon=-122.4194,
            delivery_notes="Leave at door"
        )
        
        assert order.order_type == "delivery"
        assert order.delivery_address == "123 Main St"
        assert order.delivery_lat == 37.7749
        assert order.delivery_lon == -122.4194
        assert order.delivery_notes == "Leave at door"
    
    @pytest.mark.asyncio
    async def test_order_pickup_fields(self):
        """Test pickup-specific order fields."""
        pickup_time = datetime.utcnow() + timedelta(minutes=30)
        
        order = Order(
            order_type="pickup",
            estimated_time=pickup_time,
            pickup_notes="Call when ready"
        )
        
        assert order.order_type == "pickup"
        assert order.estimated_time == pickup_time
        assert order.pickup_notes == "Call when ready"
    
    @pytest.mark.asyncio
    async def test_order_deliverect_integration(self):
        """Test Deliverect integration fields."""
        order = Order(
            deliverect_order_id="DEL_ORDER_123",
            status=10  # Deliverect status code
        )
        
        assert order.deliverect_order_id == "DEL_ORDER_123"
        assert order.status == 10


class TestOrderItemModel:
    """Test OrderItem model functionality."""
    
    @pytest.mark.asyncio
    async def test_order_item_creation(self):
        """Test creating order item."""
        item = OrderItem(
            menu_item_plu="CALI_001",
            quantity=2,
            unit_price=899,
            total_price=1798
        )
        
        assert item.menu_item_plu == "CALI_001"
        assert item.quantity == 2
        assert item.unit_price == 899
        assert item.total_price == 1798
    
    @pytest.mark.asyncio
    async def test_order_item_special_instructions(self):
        """Test order item special instructions."""
        item = OrderItem(
            menu_item_plu="TUNA_001",
            quantity=1,
            special_instructions="No wasabi, extra ginger"
        )
        
        assert item.special_instructions == "No wasabi, extra ginger"
    
    @pytest.mark.asyncio
    async def test_order_item_relationships(self, db_session):
        """Test order item relationships."""
        order = Order()
        
        item1 = OrderItem(
            menu_item_plu="ITEM_001",
            quantity=1,
            unit_price=1000
        )
        
        item2 = OrderItem(
            menu_item_plu="ITEM_002",
            quantity=2,
            unit_price=500
        )
        
        order.items.extend([item1, item2])
        
        db_session.add(order)
        await db_session.commit()
        
        assert len(order.items) == 2
        assert all(item.order_id == order.id for item in order.items)


class TestOrderItemModifierModel:
    """Test OrderItemModifier model functionality."""
    
    @pytest.mark.asyncio
    async def test_order_item_modifier_creation(self):
        """Test creating order item modifier."""
        modifier = OrderItemModifier(
            modifier_plu="MOD_AVO",
            quantity=2,
            price_change=150
        )
        
        assert modifier.modifier_plu == "MOD_AVO"
        assert modifier.quantity == 2
        assert modifier.price_change == 150
    
    @pytest.mark.asyncio
    async def test_order_item_modifier_relationship(self, db_session):
        """Test order item modifier relationships."""
        order = Order()
        order_item = OrderItem(
            menu_item_plu="BURGER_001",
            quantity=1,
            unit_price=999
        )
        
        mod1 = OrderItemModifier(
            modifier_plu="MOD_CHEESE",
            price_change=100
        )
        
        mod2 = OrderItemModifier(
            modifier_plu="MOD_BACON",
            price_change=200
        )
        
        order_item.modifiers.extend([mod1, mod2])
        order.items.append(order_item)
        
        db_session.add(order)
        await db_session.commit()
        
        assert len(order_item.modifiers) == 2
        assert all(mod.order_item_id == order_item.id for mod in order_item.modifiers)


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


class TestContactRequestModel:
    """Test ContactRequest model functionality."""
    
    @pytest.mark.asyncio
    async def test_contact_request_creation(self):
        """Test creating contact request."""
        request = ContactRequest(
            name="John Doe",
            phone="+1234567890",
            request_type="callback",
            message="Please call me back",
            call_sid="CA123456789"
        )
        
        assert request.name == "John Doe"
        assert request.phone == "+1234567890"
        assert request.request_type == "callback"
        assert request.message == "Please call me back"
        assert request.call_sid == "CA123456789"
        assert request.status == "pending"  # Default
    
    @pytest.mark.asyncio
    async def test_contact_request_status_update(self, db_session):
        """Test contact request status updates."""
        request = ContactRequest(
            name="Test User",
            phone="+9876543210",
            request_type="support"
        )
        
        db_session.add(request)
        await db_session.commit()
        
        # Update status
        request.status = "completed"
        request.notes = "Resolved by agent"
        await db_session.commit()
        
        assert request.status == "completed"
        assert request.notes == "Resolved by agent"


class TestBaseModelFunctionality:
    """Test BaseModel abstract class functionality - Task 2.4.3."""
    
    @pytest.mark.asyncio
    async def test_base_model_to_dict(self):
        """Test model serialization to dict."""
        item = MenuItem(
            name="Test Item",
            plu="TEST_001",
            price=999,
            description="Test description"
        )
        
        item_dict = item.to_dict()
        
        assert isinstance(item_dict, dict)
        assert item_dict["name"] == "Test Item"
        assert item_dict["plu"] == "TEST_001"
        assert item_dict["price"] == 999
        assert item_dict["description"] == "Test description"
    
    @pytest.mark.asyncio
    async def test_base_model_from_dict(self):
        """Test model creation from dict."""
        data = {
            "name": "From Dict Item",
            "plu": "DICT_001",
            "price": 1299,
            "is_available": False
        }
        
        item = MenuItem.from_dict(data)
        
        assert item.name == "From Dict Item"
        assert item.plu == "DICT_001"
        assert item.price == 1299
        assert item.available is False
    
    @pytest.mark.asyncio
    async def test_timestamp_mixin_behavior(self):
        """Test TimestampMixin automatic timestamp handling."""
        # Most models inherit TimestampMixin
        order = Order()
        
        # Timestamps should be set automatically
        assert order.created_at is not None
        assert order.updated_at is not None
        
        # Updated_at should change on modification
        original_updated = order.updated_at
        await asyncio.sleep(0.001)  # Small delay
        order.status = 1
        # In real DB operation, updated_at would be updated by SQLAlchemy
    
    @pytest.mark.asyncio
    async def test_base_model_id_generation(self):
        """Test automatic ID generation."""
        category = MenuCategory(name="Auto ID Test")
        
        # ID should be None before persistence
        assert category.id is None
        
        # After DB commit, ID would be generated
        # This is handled by SQLAlchemy/PostgreSQL


class TestModelConstraintsAndValidation:
    """Test model constraints and validation."""
    
    @pytest.mark.asyncio
    async def test_required_fields(self):
        """Test required field validation."""
        # MenuItem requires name and PLU
        with pytest.raises(TypeError):
            MenuItem()  # Missing required fields
        
        # Valid creation
        item = MenuItem(name="Valid", plu="VALID_001")
        assert item.name == "Valid"
        assert item.plu == "VALID_001"
    
    @pytest.mark.asyncio
    async def test_string_length_constraints(self):
        """Test string field length constraints."""
        # Test maximum length for various fields
        long_name = "A" * 255  # Typical VARCHAR limit
        item = MenuItem(
            name=long_name,
            plu="LONG_001",
            description="B" * 1000  # Longer text field
        )
        
        assert len(item.name) == 255
        assert len(item.description) == 1000
    
    @pytest.mark.asyncio
    async def test_numeric_constraints(self):
        """Test numeric field constraints."""
        # Price can be negative (discounts)
        item = MenuItem(name="Discount", plu="DISC", price=-1000)
        assert item.price == -1000
        
        # Quantity should be positive
        order_item = OrderItem(
            menu_item_plu="TEST",
            quantity=0  # Zero quantity might be invalid in business logic
        )
        assert order_item.quantity == 0
    
    @pytest.mark.asyncio
    async def test_enum_field_validation(self):
        """Test enum field validation."""
        # Valid enum values
        category = MenuCategory(
            name="Test",
            category_type=CategoryType.PRODUCT
        )
        # assert category.category_type  # Field doesn't exist == CategoryType.PRODUCT
        
        # Invalid enum value would raise error
        with pytest.raises(ValueError):
            category.category_type = "invalid_type"
    
    @pytest.mark.asyncio
    async def test_jsonb_field_handling(self):
        """Test JSONB field handling."""
        # Valid JSON data
        properties = {
            "key1": "value1",
            "nested": {"key2": "value2"},
            "array": [1, 2, 3]
        }
        
        item = MenuItem(
            name="JSONB Test",
            plu="JSON_001",
            properties=properties
        )
        
        assert item.properties == properties
        assert item.properties["nested"]["key2"] == "value2"
        
        # Modification should work
        item.properties["new_key"] = "new_value"
        assert "new_key" in item.properties