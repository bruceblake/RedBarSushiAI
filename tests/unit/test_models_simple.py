"""
Simple unit tests for models that work without database.
"""
import pytest
from app.models.menu_async import MenuItem, MenuModifier, MenuCategory
from app.models.order_async import Order, OrderItem
from app.models.location_async import Location


class TestModelCreation:
    """Test basic model instantiation."""
    
    def test_menu_item_creation(self):
        """Test creating a menu item instance."""
        item = MenuItem(
            name="Test Roll",
            description="A test sushi roll",
            price=999,
            plu="TEST_001",
            category_id=1,
            is_available=True
        )
        
        assert item.name == "Test Roll"
        assert item.price == 999
        assert item.plu == "TEST_001"
        assert item.available is True
    
    def test_menu_modifier_creation(self):
        """Test creating a modifier instance."""
        modifier = MenuModifier(
            name="Extra Sauce",
            price_change=150,
            plu="MOD_001"
        )
        
        assert modifier.name == "Extra Sauce"
        assert modifier.price_change == 150
        assert modifier.plu == "MOD_001"
    
    def test_order_creation(self):
        """Test creating an order instance."""
        order = Order(
            customer_phone="+1234567890",
            customer_name="John Doe",
            order_type="pickup",
            total_price=2590,
            status="pending"
        )
        
        assert order.customer_phone == "+1234567890"
        assert order.customer_name == "John Doe"
        assert order.total_price == 2590
        assert order.status == "pending"
    
    def test_location_creation(self):
        """Test creating a location instance."""
        location = Location(
            id="test-location-001",
            name="Test Location",
            status="active",
            webhook_base="https://test.example.com/webhook",
            api_key="test-api-key-123"
        )
        
        assert location.id == "test-location-001"
        assert location.name == "Test Location"
        assert location.status == "active"
    
    def test_location_to_dict(self):
        """Test location to_dict method."""
        location = Location(
            id="test-loc",
            name="Test",
            status="active"
        )
        
        result = location.to_dict()
        assert isinstance(result, dict)
        assert result["id"] == "test-loc"
        assert result["name"] == "Test"
        assert result["status"] == "active"