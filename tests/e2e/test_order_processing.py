"""
End-to-end tests for order processing in RedBarSushiAI.
These tests verify that orders flow correctly through the system,
from voice input to Deliverect submission and database storage.
"""

import pytest
import json
import os
import uuid
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import datetime

# Set environment to test mode
os.environ["TESTING"] = "True"
os.environ["FLASK_ENV"] = "testing"
os.environ["NO_X11"] = "1"  # Disable X11 requirement for headless testing
os.environ["OPENAI_REALTIME_NO_DISPLAY"] = "1"  # Disable display for OpenAI Realtime

# Import app components after setting test environment
from app import create_app
from app.models.menu import MenuItem, MenuModifier, MenuModifierGroup, MenuNameVariant
from app.models.order import Order, OrderItem, OrderItemModifier
from app.models.location import Location
from app.agents.fulfillment import process_order, submit_to_deliverect


@pytest.fixture
def app():
    """Create Flask app for testing with in-memory SQLite database"""
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    app.config["INITIALIZE_MENU_DATABASE"] = False  # Don't initialize DB automatically
    
    # Create all tables in the in-memory database
    with app.app_context():
        from app.db import db
        db.create_all()
        
        # Seed with test data
        _create_test_data(db)
    
    yield app


def _create_test_data(db):
    """Create test data for the database"""
    # Create a test location
    test_location = Location(
        id=1,
        name="Red Bar Sushi Test Location",
        address="123 Test St",
        city="Testville",
        state="NY",
        zip="10001",
        phone="555-123-1000",
        channelLinkId="test-channel-link-id",
        business_hours="9:00-22:00"
    )
    
    # Create test menu categories
    sushi_cat = MenuModifierGroup(
        id=1,
        deliverect_group_id="cat_sushi",
        name="Sushi Rolls",
        min_selection=0,
        max_selection=0
    )
    
    # Create test menu items
    cali_roll = MenuItem(
        id=1,
        name="California Roll",
        description="Crab, avocado, and cucumber",
        price=850,  # $8.50
        plu="CALI-ROLL",
        deliverect_item_id="item_cali_roll",
        is_available=True
    )
    
    spicy_tuna = MenuItem(
        id=2,
        name="Spicy Tuna Roll",
        price=950,  # $9.50
        plu="SPICY-TUNA",
        deliverect_item_id="item_spicy_tuna",
        description="Fresh tuna with spicy sauce",
        is_available=True
    )
    
    # Create test modifier groups
    sauce_group = MenuModifierGroup(
        id=101,
        deliverect_group_id="mod_gr_sauce",
        name="Sauce Options",
        min_selection=0,
        max_selection=3
    )
    
    # Create test modifiers
    extra_avo = MenuModifier(
        id=201,
        modifier_group_id=101,
        name="Extra Avocado",
        price_change=150,  # $1.50
        plu="MOD-EXTRA-AVO",
        deliverect_modifier_id="mod_extra_avo",
        is_available=True
    )
    
    spicy_sauce = MenuModifier(
        id=202,
        modifier_group_id=101,
        name="Spicy Mayo",
        price_change=100,  # $1.00
        plu="MOD-SPICY-MAYO",
        deliverect_modifier_id="mod_spicy_mayo",
        is_available=True
    )
    
    # Create name variants for natural language matching
    variants = [
        MenuNameVariant(variant_phrase="california roll", canonical_name="California Roll", target_plu="CALI-ROLL"),
        MenuNameVariant(variant_phrase="cali roll", canonical_name="California Roll", target_plu="CALI-ROLL"),
        MenuNameVariant(variant_phrase="spicy tuna", canonical_name="Spicy Tuna Roll", target_plu="SPICY-TUNA"),
        MenuNameVariant(variant_phrase="spicy tuna roll", canonical_name="Spicy Tuna Roll", target_plu="SPICY-TUNA"),
        MenuNameVariant(variant_phrase="extra avocado", canonical_name="Extra Avocado", target_plu="MOD-EXTRA-AVO"),
        MenuNameVariant(variant_phrase="spicy mayo", canonical_name="Spicy Mayo", target_plu="MOD-SPICY-MAYO"),
    ]
    
    # Add to database
    db.session.add_all([
        test_location, sushi_cat, cali_roll, spicy_tuna, sauce_group, 
        extra_avo, spicy_sauce, *variants
    ])
    db.session.commit()


@pytest.fixture
def mock_deliverect_api():
    """Mock the Deliverect API for testing"""
    # Create a mock response for the create order endpoint
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "orderId": "test-order-id-123",
        "status": 10,  # Initial received status
        "channelOrderId": "RBS-TEST-123"
    }
    
    # Patch the requests library or specific deliverect function
    with patch('app.utils.deliverect.orders.create_order', return_value=mock_response):
        yield mock_response


def test_create_order_in_database(app):
    """Test that an order is properly created in the database"""
    with app.app_context():
        from app.db import db
        from app.utils.order_utils import create_order
        
        # Create test order data
        order_data = {
            "customer_name": "Test Customer",
            "customer_phone": "555-123-4567",
            "order_type": 1,  # Pickup
            "items": [
                {
                    "plu": "CALI-ROLL",
                    "quantity": 2,
                    "modifiers": [
                        {"plu": "MOD-EXTRA-AVO", "quantity": 1}
                    ]
                },
                {
                    "plu": "SPICY-TUNA",
                    "quantity": 1,
                    "modifiers": []
                }
            ]
        }
        
        # Create the order
        order_id = create_order(order_data)
        
        # Get the created order
        order = Order.query.get(order_id)
        
        # Verify order details
        assert order is not None, "Order should be created"
        assert order.customer_phone == "555-123-4567", "Order should have correct phone"
        assert order.order_type == 1, "Order should have correct type"
        
        # Check order items
        assert len(order.items) == 2, "Order should have 2 items"
        
        # Check for California Roll with modifier
        cali_roll_items = [item for item in order.items if item.menu_item_plu == "CALI-ROLL"]
        assert len(cali_roll_items) == 1, "Should have California Roll item"
        assert cali_roll_items[0].quantity == 2, "Should have 2 California Rolls"
        
        # Check modifiers
        cali_modifiers = [mod for mod in cali_roll_items[0].modifiers if mod.modifier_plu == "MOD-EXTRA-AVO"]
        assert len(cali_modifiers) == 1, "Should have Extra Avocado modifier"
        assert cali_modifiers[0].quantity == 1, "Should have 1 Extra Avocado"
        
        # Check for Spicy Tuna Roll
        spicy_tuna_items = [item for item in order.items if item.menu_item_plu == "SPICY-TUNA"]
        assert len(spicy_tuna_items) == 1, "Should have Spicy Tuna Roll item"
        assert spicy_tuna_items[0].quantity == 1, "Should have 1 Spicy Tuna Roll"
        assert len(spicy_tuna_items[0].modifiers) == 0, "Should have no modifiers"


@pytest.mark.asyncio
async def test_process_order_to_deliverect(app, mock_deliverect_api):
    """Test that an order is properly processed and submitted to Deliverect"""
    with app.app_context():
        from app.db import db
        from app.agents.fulfillment import process_order
        
        # Set up cart data
        cart_data = {
            "items": [
                {
                    "plu": "CALI-ROLL",
                    "name": "California Roll",
                    "price": 850,
                    "quantity": 1,
                    "modifiers": [
                        {
                            "plu": "MOD-EXTRA-AVO",
                            "name": "Extra Avocado",
                            "price_change": 150,
                            "quantity": 1
                        }
                    ]
                }
            ],
            "total_price": 1000  # $10.00
        }
        
        # Process the order
        result = await process_order(
            cart_data,
            customer_name="Test Customer",
            customer_phone="555-123-4567",
            order_type=1,  # Pickup
            notes="Test order"
        )
        
        # Verify result
        assert result.get("success") is True, "Order processing should succeed"
        assert "order_id" in result, "Result should include order_id"
        
        # Check database for the order
        order_id = result["order_id"]
        order = Order.query.get(order_id)
        
        assert order is not None, "Order should exist in database"
        assert order.deliverect_channel_order_id is not None, "Order should have Deliverect ID"
        assert order.total_price == 1000, "Order should have correct price"
        
        # Verify Deliverect API was called
        assert mock_deliverect_api.json.called, "Deliverect API should be called"


def test_order_validation_with_guardrail(app):
    """Test that the guardrail agent properly validates orders"""
    with app.app_context():
        from app.db import db
        from app.agents.guardrail import validate_order
        
        # 1. Test a valid order
        valid_cart = {
            "items": [
                {
                    "plu": "CALI-ROLL",
                    "name": "California Roll",
                    "price": 850,
                    "quantity": 1,
                    "modifiers": []
                }
            ]
        }
        
        result = validate_order(valid_cart)
        assert result["valid"] is True, "Valid order should pass validation"
        assert result["errors"] == [], "Valid order should have no errors"
        
        # 2. Test an order with unavailable item
        # Make the California Roll unavailable
        cali_roll = MenuItem.query.filter_by(plu="CALI-ROLL").first()
        cali_roll.is_available = False
        db.session.commit()
        
        result = validate_order(valid_cart)
        assert result["valid"] is False, "Order with unavailable item should fail validation"
        assert len(result["errors"]) > 0, "Should have validation errors"
        assert any("unavailable" in error.lower() for error in result["errors"]), "Should mention unavailability"
        
        # Reset availability
        cali_roll.is_available = True
        db.session.commit()
        
        # 3. Test an order with snoozed item
        # Snooze the California Roll
        cali_roll.snoozed_until = datetime.datetime.now() + datetime.timedelta(hours=1)
        db.session.commit()
        
        result = validate_order(valid_cart)
        assert result["valid"] is False, "Order with snoozed item should fail validation"
        assert any("temporarily unavailable" in error.lower() for error in result["errors"]), "Should mention snooze"
        
        # Reset snooze
        cali_roll.snoozed_until = None
        db.session.commit()
        
        # 4. Test an order with missing required modifier
        # Make the sauce group required
        sauce_group = MenuModifierGroup.query.filter_by(id=101).first()
        sauce_group.min_selection = 1
        db.session.commit()
        
        result = validate_order(valid_cart)
        assert result["valid"] is False, "Order missing required modifier should fail validation"
        assert any("required" in error.lower() for error in result["errors"]), "Should mention required modifier"
        
        # Reset modifier group
        sauce_group.min_selection = 0
        db.session.commit()


@pytest.mark.asyncio
async def test_end_to_end_order_flow(app, mock_deliverect_api):
    """Test the complete order flow from cart to Deliverect submission"""
    with app.app_context():
        from app.db import db
        from app.agents.cart import Cart
        from app.agents.fulfillment import process_order
        
        # Create a session ID
        session_id = str(uuid.uuid4())
        
        # Create a cart and add items
        cart = Cart(session_id)
        
        # Add items to cart
        await cart.add_item(
            plu="CALI-ROLL",
            quantity=2,
            modifiers=[
                {"plu": "MOD-EXTRA-AVO", "quantity": 1}
            ]
        )
        
        await cart.add_item(
            plu="SPICY-TUNA",
            quantity=1,
            modifiers=[]
        )
        
        # Get cart contents
        cart_contents = await cart.get_contents()
        
        # Process the order
        result = await process_order(
            cart_contents,
            customer_name="End to End Test",
            customer_phone="555-987-6543",
            order_type=1  # Pickup
        )
        
        # Verify order was created
        assert result.get("success") is True, "Order processing should succeed"
        assert "order_id" in result, "Result should include order_id"
        
        # Check database
        order_id = result["order_id"]
        order = Order.query.get(order_id)
        
        assert order is not None, "Order should exist in database"
        assert order.total_price > 0, "Order should have a price"
        assert len(order.items) == 2, "Order should have 2 items"
        
        # Verify items and modifiers
        cali_items = [item for item in order.items if item.menu_item_plu == "CALI-ROLL"]
        assert len(cali_items) == 1, "Should have California Roll"
        assert cali_items[0].quantity == 2, "Should have 2 California Rolls"
        
        # Check for modifier
        has_extra_avo = any(
            mod.modifier_plu == "MOD-EXTRA-AVO" 
            for mod in cali_items[0].modifiers
        )
        assert has_extra_avo, "Should have Extra Avocado modifier"
        
        # Verify Deliverect API call
        assert mock_deliverect_api.json.called, "Deliverect API should be called"


@pytest.mark.asyncio
async def test_order_with_calculated_price(app):
    """Test that order price is correctly calculated including modifiers"""
    with app.app_context():
        from app.db import db
        from app.agents.cart import Cart
        
        # Create a session ID
        session_id = str(uuid.uuid4())
        
        # Create a cart
        cart = Cart(session_id)
        
        # Add California Roll with Extra Avocado
        await cart.add_item(
            plu="CALI-ROLL",
            quantity=1,
            modifiers=[
                {"plu": "MOD-EXTRA-AVO", "quantity": 1}
            ]
        )
        
        # Get cart contents
        cart_contents = await cart.get_contents()
        
        # Verify prices
        assert "total_price" in cart_contents, "Cart should have total price"
        
        # Calculate expected price
        # California Roll: $8.50
        # Extra Avocado: $1.50
        # Total: $10.00
        expected_price = 850 + 150  # In cents
        
        assert cart_contents["total_price"] == expected_price, \
            f"Cart total should be {expected_price} cents, got {cart_contents['total_price']}"
        
        # Check individual item price with modifier
        cali_roll_item = next(item for item in cart_contents["items"] if item["plu"] == "CALI-ROLL")
        assert cali_roll_item["price"] == 850, "Base price should be 850 cents"
        
        # Check modifier price
        extra_avo_mod = next(mod for mod in cali_roll_item["modifiers"] if mod["plu"] == "MOD-EXTRA-AVO")
        assert extra_avo_mod["price_change"] == 150, "Modifier price should be 150 cents"


@pytest.mark.asyncio
async def test_order_with_phone_number_from_caller(app, mock_deliverect_api):
    """Test that system uses caller's phone number for order"""
    with app.app_context():
        from app.db import db
        from app.agents.fulfillment import process_order
        from app.utils.agent_orchestration import SlotStore
        
        # Create a session ID
        session_id = str(uuid.uuid4())
        
        # Create a cart
        cart_data = {
            "items": [
                {
                    "plu": "CALI-ROLL",
                    "name": "California Roll",
                    "price": 850,
                    "quantity": 1,
                    "modifiers": []
                }
            ],
            "total_price": 850
        }
        
        # Mock the slot store to simulate caller phone number
        slot_store = SlotStore()
        caller_phone = "+15551234567"
        slot_store.set_slot(session_id, "phone_number", caller_phone)
        
        # Create the order using the caller's phone number
        with patch('app.agents.fulfillment.slot_store', slot_store):
            result = await process_order(
                cart_data,
                customer_name="Caller Test",
                # Deliberately omit phone_number to test auto-use of caller number
                order_type=1,  # Pickup
                session_id=session_id  # Important to include session ID
            )
        
        # Verify order was created
        assert result.get("success") is True, "Order processing should succeed"
        
        # Check that the caller's phone number was used
        order_id = result["order_id"]
        order = Order.query.get(order_id)
        
        assert order.customer_phone == caller_phone, \
            f"Order should use caller's phone number: {caller_phone}, got {order.customer_phone}"

# Run these tests with: pytest -v tests/e2e/test_order_processing.py