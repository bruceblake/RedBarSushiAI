"""
Tests for the guardrail and validation systems in RedBarSushiAI.
Focuses on validating business rules, menu constraints, and edge cases.
"""

import pytest
import os
import datetime
from unittest.mock import patch, MagicMock

# Set environment to test mode
os.environ["TESTING"] = "True"
os.environ["FLASK_ENV"] = "testing"

# Import app components
from app import create_app
from app.models.menu import MenuItem, MenuModifier, MenuModifierGroup, MenuNameVariant
from app.models.order import Order, OrderItem, OrderItemModifier


@pytest.fixture
def app():
    """Create Flask app for testing with in-memory SQLite database"""
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    app.config["INITIALIZE_MENU_DATABASE"] = False  # Don't initialize DB automatically
    
    # Create all tables in the in-memory database
    with app.app_context():
        from app.db import db
        db.create_all()
        
        # Seed with test data including complex validation scenarios
        _create_test_data(db)
    
    yield app


def _create_test_data(db):
    """Create test data for the database with complex validation rules"""
    # Create test menu categories
    sushi_cat = MenuModifierGroup(
        id=1,
        deliverect_group_id="cat_sushi",
        name="Sushi Rolls",
        min_selection=0,
        max_selection=0
    )
    
    # Create test menu items
    basic_roll = MenuItem(
        id=1,
        name="Basic Roll",
        description="Simple roll with no required modifiers",
        price=750,  # $7.50
        plu="BASIC-ROLL",
        deliverect_item_id="item_basic_roll",
        is_available=True
    )
    
    combo_roll = MenuItem(
        id=2,
        name="Combo Roll",
        description="Roll that is part of a combo",
        price=1250,  # $12.50
        plu="COMBO-ROLL",
        deliverect_item_id="item_combo_roll",
        is_available=True,
        is_combo=True
    )
    
    variant_roll = MenuItem(
        id=3,
        name="Variant Roll",
        description="Roll with size variants",
        price=950,  # $9.50 (base price)
        plu="VARIANT-ROLL",
        deliverect_item_id="item_variant_roll",
        is_available=True,
        is_variant=True
    )
    
    snoozed_roll = MenuItem(
        id=4,
        name="Snoozed Roll",
        description="Temporarily unavailable roll",
        price=850,  # $8.50
        plu="SNOOZED-ROLL",
        deliverect_item_id="item_snoozed_roll",
        is_available=True,
        snoozed_until=datetime.datetime.now() + datetime.timedelta(hours=2)  # Snoozed for 2 hours
    )
    
    unavailable_roll = MenuItem(
        id=5,
        name="Unavailable Roll",
        description="Permanently unavailable roll",
        price=850,  # $8.50
        plu="UNAVAIL-ROLL",
        deliverect_item_id="item_unavail_roll",
        is_available=False
    )
    
    # Create test modifier groups
    # Sauce group - optional
    sauce_group = MenuModifierGroup(
        id=101,
        deliverect_group_id="mod_gr_sauce",
        name="Sauce Options",
        min_selection=0,
        max_selection=3,
        plu="MOD-GR-SAUCE"
    )
    
    # Rice group - required minimum 1
    rice_group = MenuModifierGroup(
        id=102,
        deliverect_group_id="mod_gr_rice",
        name="Rice Options",
        min_selection=1,  # Required
        max_selection=1,  # Only one option
        plu="MOD-GR-RICE"
    )
    
    # Size group for variants
    size_group = MenuModifierGroup(
        id=103,
        deliverect_group_id="mod_gr_size",
        name="Size Options",
        min_selection=1,  # Required
        max_selection=1,  # Only one size
        plu="MOD-GR-SIZE",
        is_variant_group=True
    )
    
    # Create test modifiers
    soy_sauce = MenuModifier(
        id=201,
        modifier_group_id=101,  # Sauce group
        name="Soy Sauce",
        price_change=0,  # Free
        plu="MOD-SOY",
        deliverect_modifier_id="mod_soy",
        is_available=True
    )
    
    spicy_sauce = MenuModifier(
        id=202,
        modifier_group_id=101,  # Sauce group
        name="Spicy Mayo",
        price_change=100,  # $1.00
        plu="MOD-SPICY",
        deliverect_modifier_id="mod_spicy",
        is_available=True
    )
    
    eel_sauce = MenuModifier(
        id=203,
        modifier_group_id=101,  # Sauce group
        name="Eel Sauce",
        price_change=100,  # $1.00
        plu="MOD-EEL",
        deliverect_modifier_id="mod_eel",
        is_available=True
    )
    
    white_rice = MenuModifier(
        id=204,
        modifier_group_id=102,  # Rice group
        name="White Rice",
        price_change=0,  # Base price
        plu="MOD-WHITE-RICE",
        deliverect_modifier_id="mod_white_rice",
        is_available=True
    )
    
    brown_rice = MenuModifier(
        id=205,
        modifier_group_id=102,  # Rice group
        name="Brown Rice",
        price_change=100,  # $1.00 extra
        plu="MOD-BROWN-RICE",
        deliverect_modifier_id="mod_brown_rice",
        is_available=True
    )
    
    small_size = MenuModifier(
        id=206,
        modifier_group_id=103,  # Size group
        name="Small",
        price_change=-200,  # $2.00 less than base price
        plu="MOD-SMALL",
        deliverect_modifier_id="mod_small",
        is_available=True
    )
    
    medium_size = MenuModifier(
        id=207,
        modifier_group_id=103,  # Size group
        name="Medium",
        price_change=0,  # Base price
        plu="MOD-MEDIUM",
        deliverect_modifier_id="mod_medium",
        is_available=True
    )
    
    large_size = MenuModifier(
        id=208,
        modifier_group_id=103,  # Size group
        name="Large",
        price_change=300,  # $3.00 more than base price
        plu="MOD-LARGE",
        deliverect_modifier_id="mod_large",
        is_available=True
    )
    
    # Create item-modifier group associations
    basic_sauce_assoc = ItemModifierGroup(
        menu_item_id=1,  # Basic Roll
        modifier_group_id=101  # Sauce Group (optional)
    )
    
    combo_sauce_assoc = ItemModifierGroup(
        menu_item_id=2,  # Combo Roll
        modifier_group_id=101  # Sauce Group (optional)
    )
    
    combo_rice_assoc = ItemModifierGroup(
        menu_item_id=2,  # Combo Roll
        modifier_group_id=102  # Rice Group (required)
    )
    
    variant_size_assoc = ItemModifierGroup(
        menu_item_id=3,  # Variant Roll
        modifier_group_id=103  # Size Group (variant)
    )
    
    # Use the ItemModifierGroup model defined in the app
    from app.models.menu import ItemModifierGroup
    
    # Create name variants for natural language matching
    variants = [
        MenuNameVariant(variant_phrase="basic roll", canonical_name="Basic Roll", target_plu="BASIC-ROLL"),
        MenuNameVariant(variant_phrase="combo roll", canonical_name="Combo Roll", target_plu="COMBO-ROLL"),
        MenuNameVariant(variant_phrase="variant roll", canonical_name="Variant Roll", target_plu="VARIANT-ROLL"),
        MenuNameVariant(variant_phrase="snoozed roll", canonical_name="Snoozed Roll", target_plu="SNOOZED-ROLL"),
        MenuNameVariant(variant_phrase="unavailable roll", canonical_name="Unavailable Roll", target_plu="UNAVAIL-ROLL"),
        MenuNameVariant(variant_phrase="soy sauce", canonical_name="Soy Sauce", target_plu="MOD-SOY"),
        MenuNameVariant(variant_phrase="spicy mayo", canonical_name="Spicy Mayo", target_plu="MOD-SPICY"),
        MenuNameVariant(variant_phrase="spicy sauce", canonical_name="Spicy Mayo", target_plu="MOD-SPICY"),
        MenuNameVariant(variant_phrase="eel sauce", canonical_name="Eel Sauce", target_plu="MOD-EEL"),
        MenuNameVariant(variant_phrase="white rice", canonical_name="White Rice", target_plu="MOD-WHITE-RICE"),
        MenuNameVariant(variant_phrase="brown rice", canonical_name="Brown Rice", target_plu="MOD-BROWN-RICE"),
        MenuNameVariant(variant_phrase="small", canonical_name="Small", target_plu="MOD-SMALL"),
        MenuNameVariant(variant_phrase="medium", canonical_name="Medium", target_plu="MOD-MEDIUM"),
        MenuNameVariant(variant_phrase="large", canonical_name="Large", target_plu="MOD-LARGE"),
    ]
    
    # Add all entities to the database session
    db.session.add_all([
        sushi_cat, basic_roll, combo_roll, variant_roll, snoozed_roll, unavailable_roll,
        sauce_group, rice_group, size_group,
        soy_sauce, spicy_sauce, eel_sauce, white_rice, brown_rice,
        small_size, medium_size, large_size,
        basic_sauce_assoc, combo_sauce_assoc, combo_rice_assoc, variant_size_assoc,
        *variants
    ])
    db.session.commit()


def test_availability_validation(app):
    """Test validation of item availability"""
    with app.app_context():
        from app.agents.guardrail import validate_item_availability
        
        # Test available item
        basic_roll = MenuItem.query.filter_by(plu="BASIC-ROLL").first()
        result = validate_item_availability(basic_roll)
        assert result["valid"] is True, "Available item should pass validation"
        
        # Test snoozed item
        snoozed_roll = MenuItem.query.filter_by(plu="SNOOZED-ROLL").first()
        result = validate_item_availability(snoozed_roll)
        assert result["valid"] is False, "Snoozed item should fail validation"
        assert "temporarily unavailable" in result["message"].lower(), "Should mention temporary unavailability"
        
        # Test permanently unavailable item
        unavail_roll = MenuItem.query.filter_by(plu="UNAVAIL-ROLL").first()
        result = validate_item_availability(unavail_roll)
        assert result["valid"] is False, "Unavailable item should fail validation"
        assert "not available" in result["message"].lower(), "Should mention unavailability"


def test_required_modifier_validation(app):
    """Test validation of required modifiers"""
    with app.app_context():
        from app.agents.guardrail import validate_modifiers_requirements
        
        # Test combo roll which requires rice selection
        combo_roll = MenuItem.query.filter_by(plu="COMBO-ROLL").first()
        
        # Case 1: No rice modifier selected
        modifiers = []
        result = validate_modifiers_requirements(combo_roll, modifiers)
        assert result["valid"] is False, "Missing required rice should fail validation"
        assert "rice" in result["message"].lower(), "Should mention missing rice selection"
        
        # Case 2: With rice modifier selected
        white_rice = MenuModifier.query.filter_by(plu="MOD-WHITE-RICE").first()
        modifiers = [{"modifier": white_rice, "quantity": 1}]
        result = validate_modifiers_requirements(combo_roll, modifiers)
        assert result["valid"] is True, "With required rice selected, should pass validation"
        
        # Test basic roll which has no required modifiers
        basic_roll = MenuItem.query.filter_by(plu="BASIC-ROLL").first()
        result = validate_modifiers_requirements(basic_roll, [])
        assert result["valid"] is True, "Item with no required modifiers should pass validation"


def test_modifier_max_selection_validation(app):
    """Test validation of maximum modifier selections"""
    with app.app_context():
        from app.agents.guardrail import validate_modifiers_requirements
        
        # Test sauce group which allows up to 3 sauces
        basic_roll = MenuItem.query.filter_by(plu="BASIC-ROLL").first()
        
        # Case 1: Valid number of sauces (3)
        soy_sauce = MenuModifier.query.filter_by(plu="MOD-SOY").first()
        spicy_sauce = MenuModifier.query.filter_by(plu="MOD-SPICY").first()
        eel_sauce = MenuModifier.query.filter_by(plu="MOD-EEL").first()
        
        modifiers = [
            {"modifier": soy_sauce, "quantity": 1},
            {"modifier": spicy_sauce, "quantity": 1},
            {"modifier": eel_sauce, "quantity": 1}
        ]
        
        result = validate_modifiers_requirements(basic_roll, modifiers)
        assert result["valid"] is True, "3 sauces should be valid (max=3)"
        
        # Case 2: Too many sauces (4) by increasing quantity
        modifiers = [
            {"modifier": soy_sauce, "quantity": 2},
            {"modifier": spicy_sauce, "quantity": 1},
            {"modifier": eel_sauce, "quantity": 1}
        ]
        
        result = validate_modifiers_requirements(basic_roll, modifiers)
        assert result["valid"] is False, "4 sauces should be invalid (max=3)"
        assert "maximum" in result["message"].lower(), "Should mention maximum limit"


def test_variant_group_validation(app):
    """Test validation of variant groups like sizes"""
    with app.app_context():
        from app.agents.guardrail import validate_modifiers_requirements
        
        # Test variant roll which requires exactly one size selection
        variant_roll = MenuItem.query.filter_by(plu="VARIANT-ROLL").first()
        
        # Case 1: No size selected
        modifiers = []
        result = validate_modifiers_requirements(variant_roll, modifiers)
        assert result["valid"] is False, "Missing size selection should fail validation"
        assert "size" in result["message"].lower(), "Should mention missing size selection"
        
        # Case 2: One size selected (valid)
        medium_size = MenuModifier.query.filter_by(plu="MOD-MEDIUM").first()
        modifiers = [{"modifier": medium_size, "quantity": 1}]
        result = validate_modifiers_requirements(variant_roll, modifiers)
        assert result["valid"] is True, "One size selection should pass validation"
        
        # Case 3: Multiple sizes selected (invalid)
        small_size = MenuModifier.query.filter_by(plu="MOD-SMALL").first()
        large_size = MenuModifier.query.filter_by(plu="MOD-LARGE").first()
        modifiers = [
            {"modifier": small_size, "quantity": 1},
            {"modifier": large_size, "quantity": 1}
        ]
        result = validate_modifiers_requirements(variant_roll, modifiers)
        assert result["valid"] is False, "Multiple sizes should fail validation"
        assert "only one" in result["message"].lower(), "Should mention only one selection allowed"


def test_price_calculation_with_modifiers(app):
    """Test that price is correctly calculated with modifiers"""
    with app.app_context():
        from app.agents.guardrail import calculate_price_with_modifiers
        
        # Calculate price for basic roll with spicy sauce
        basic_roll = MenuItem.query.filter_by(plu="BASIC-ROLL").first()
        spicy_sauce = MenuModifier.query.filter_by(plu="MOD-SPICY").first()
        
        modifiers = [{"modifier": spicy_sauce, "quantity": 1}]
        price = calculate_price_with_modifiers(basic_roll, modifiers)
        
        # Base price: $7.50 + Spicy Sauce: $1.00 = $8.50
        expected_price = 750 + 100  # In cents
        assert price == expected_price, f"Price should be {expected_price} cents, got {price}"
        
        # Calculate price for variant roll with size modifier
        variant_roll = MenuItem.query.filter_by(plu="VARIANT-ROLL").first()
        large_size = MenuModifier.query.filter_by(plu="MOD-LARGE").first()
        
        modifiers = [{"modifier": large_size, "quantity": 1}]
        price = calculate_price_with_modifiers(variant_roll, modifiers)
        
        # Base price: $9.50 + Large size: $3.00 = $12.50
        expected_price = 950 + 300  # In cents
        assert price == expected_price, f"Price should be {expected_price} cents, got {price}"
        
        # Calculate price for combo roll with brown rice
        combo_roll = MenuItem.query.filter_by(plu="COMBO-ROLL").first()
        brown_rice = MenuModifier.query.filter_by(plu="MOD-BROWN-RICE").first()
        
        modifiers = [{"modifier": brown_rice, "quantity": 1}]
        price = calculate_price_with_modifiers(combo_roll, modifiers)
        
        # Base price: $12.50 + Brown rice: $1.00 = $13.50
        expected_price = 1250 + 100  # In cents
        assert price == expected_price, f"Price should be {expected_price} cents, got {price}"


def test_complete_order_validation(app):
    """Test complete order validation including all rules"""
    with app.app_context():
        from app.agents.guardrail import validate_order
        
        # Test 1: Valid order with all requirements met
        valid_cart = {
            "items": [
                {
                    "plu": "BASIC-ROLL",
                    "name": "Basic Roll",
                    "price": 750,
                    "quantity": 1,
                    "modifiers": []
                },
                {
                    "plu": "COMBO-ROLL",
                    "name": "Combo Roll",
                    "price": 1250,
                    "quantity": 1,
                    "modifiers": [
                        {
                            "plu": "MOD-WHITE-RICE",
                            "name": "White Rice",
                            "price_change": 0,
                            "quantity": 1
                        }
                    ]
                },
                {
                    "plu": "VARIANT-ROLL",
                    "name": "Variant Roll",
                    "price": 950,
                    "quantity": 1,
                    "modifiers": [
                        {
                            "plu": "MOD-MEDIUM",
                            "name": "Medium",
                            "price_change": 0,
                            "quantity": 1
                        }
                    ]
                }
            ]
        }
        
        result = validate_order(valid_cart)
        assert result["valid"] is True, "Valid order should pass validation"
        assert result["errors"] == [], "Valid order should have no errors"
        
        # Test 2: Invalid order with multiple issues
        invalid_cart = {
            "items": [
                {
                    "plu": "UNAVAIL-ROLL",  # Unavailable item
                    "name": "Unavailable Roll",
                    "price": 850,
                    "quantity": 1,
                    "modifiers": []
                },
                {
                    "plu": "COMBO-ROLL",  # Missing required rice modifier
                    "name": "Combo Roll",
                    "price": 1250,
                    "quantity": 1,
                    "modifiers": []
                },
                {
                    "plu": "VARIANT-ROLL",  # Multiple size modifiers
                    "name": "Variant Roll",
                    "price": 950,
                    "quantity": 1,
                    "modifiers": [
                        {
                            "plu": "MOD-SMALL",
                            "name": "Small",
                            "price_change": -200,
                            "quantity": 1
                        },
                        {
                            "plu": "MOD-LARGE",
                            "name": "Large",
                            "price_change": 300,
                            "quantity": 1
                        }
                    ]
                }
            ]
        }
        
        result = validate_order(invalid_cart)
        assert result["valid"] is False, "Invalid order should fail validation"
        assert len(result["errors"]) == 3, "Should have 3 distinct validation errors"


def test_snoozed_item_expiration(app):
    """Test that snoozed items become available after their snooze period"""
    with app.app_context():
        from app.db import db
        from app.agents.guardrail import validate_item_availability
        
        # Get the snoozed roll
        snoozed_roll = MenuItem.query.filter_by(plu="SNOOZED-ROLL").first()
        
        # It should be snoozed and unavailable at first
        result = validate_item_availability(snoozed_roll)
        assert result["valid"] is False, "Snoozed item should be unavailable"
        
        # Set the snooze time to the past
        snoozed_roll.snoozed_until = datetime.datetime.now() - datetime.timedelta(minutes=5)
        db.session.commit()
        
        # Now it should be available
        result = validate_item_availability(snoozed_roll)
        assert result["valid"] is True, "Item with expired snooze should be available"


def test_modifier_compatibility(app):
    """Test that incompatible modifiers are caught"""
    with app.app_context():
        from app.db import db
        from app.agents.guardrail import validate_modifier_compatibility
        
        # Create a test case with mismatched modifiers
        basic_roll = MenuItem.query.filter_by(plu="BASIC-ROLL").first()
        
        # Try to add a rice modifier which doesn't belong to basic roll
        brown_rice = MenuModifier.query.filter_by(plu="MOD-BROWN-RICE").first()
        
        # Should fail compatibility check
        result = validate_modifier_compatibility(basic_roll, brown_rice)
        assert result["valid"] is False, "Incompatible modifier should fail validation"
        assert "not valid" in result["message"].lower(), "Should mention incompatibility"
        
        # But a sauce modifier should be compatible
        spicy_sauce = MenuModifier.query.filter_by(plu="MOD-SPICY").first()
        result = validate_modifier_compatibility(basic_roll, spicy_sauce)
        assert result["valid"] is True, "Compatible modifier should pass validation"


def test_cart_item_modification(app):
    """Test modifying items in the cart"""
    with app.app_context():
        from app.agents.cart import Cart
        import uuid
        import asyncio
        
        # Test modifying items in the cart
        async def test_cart_modifications():
            session_id = str(uuid.uuid4())
            cart = Cart(session_id)
            
            # Add an item to the cart
            await cart.add_item(
                plu="BASIC-ROLL",
                quantity=1,
                modifiers=[]
            )
            
            # Check initial cart contents
            contents = await cart.get_contents()
            assert len(contents["items"]) == 1, "Cart should have one item"
            assert contents["items"][0]["quantity"] == 1, "Quantity should be 1"
            
            # Increase quantity
            await cart.update_item_quantity(
                plu="BASIC-ROLL",
                quantity=2
            )
            
            # Check updated quantity
            contents = await cart.get_contents()
            assert contents["items"][0]["quantity"] == 2, "Quantity should be 2"
            
            # Add a modifier
            spicy_sauce = {"plu": "MOD-SPICY", "quantity": 1}
            await cart.add_modifier_to_item(
                item_plu="BASIC-ROLL",
                modifier=spicy_sauce
            )
            
            # Check if modifier was added
            contents = await cart.get_contents()
            assert len(contents["items"][0]["modifiers"]) == 1, "Should have one modifier"
            assert contents["items"][0]["modifiers"][0]["plu"] == "MOD-SPICY", "Should be spicy sauce"
            
            # Remove item
            await cart.remove_item(plu="BASIC-ROLL")
            
            # Check if item was removed
            contents = await cart.get_contents()
            assert len(contents["items"]) == 0, "Cart should be empty"
            
            return "Passed"
        
        # Run the async test
        result = asyncio.run(test_cart_modifications())
        assert result == "Passed", "Cart modification test should pass"


def test_full_guardrail_integration(app):
    """Test full integration of cart, guardrail, and order processing"""
    with app.app_context():
        from app.db import db
        from app.agents.cart import Cart
        from app.agents.guardrail import validate_order
        from app.agents.fulfillment import process_order
        from unittest.mock import patch, MagicMock
        import uuid
        import asyncio
        
        # Mock Deliverect API
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"orderId": "test-123"}
        
        async def run_integration_test():
            # Create a session
            session_id = str(uuid.uuid4())
            cart = Cart(session_id)
            
            # Add valid items to cart
            await cart.add_item(
                plu="BASIC-ROLL",
                quantity=1,
                modifiers=[{"plu": "MOD-SOY", "quantity": 1}]
            )
            
            await cart.add_item(
                plu="COMBO-ROLL",
                quantity=1,
                modifiers=[{"plu": "MOD-WHITE-RICE", "quantity": 1}]
            )
            
            # Get cart contents
            cart_contents = await cart.get_contents()
            
            # Validate the order
            validation_result = validate_order(cart_contents)
            assert validation_result["valid"] is True, "Order should pass validation"
            
            # Process the order with mocked Deliverect API
            with patch('app.utils.deliverect.orders.create_order', return_value=mock_response):
                order_result = await process_order(
                    cart_contents,
                    customer_name="Integration Test",
                    customer_phone="555-123-4567",
                    order_type=1  # Pickup
                )
            
            # Verify order was created
            assert order_result["success"] is True, "Order processing should succeed"
            assert "order_id" in order_result, "Result should include order_id"
            
            # Verify order in database
            from app.models.order import Order
            order = Order.query.get(order_result["order_id"])
            assert order is not None, "Order should exist in database"
            assert len(order.items) == 2, "Order should have 2 items"
            
            return "Integration test passed"
        
        # Run the async test
        result = asyncio.run(run_integration_test())
        assert result == "Integration test passed", "Full integration test should pass"


# Run these tests with: pytest -v tests/e2e/test_guardrails_and_validation.py