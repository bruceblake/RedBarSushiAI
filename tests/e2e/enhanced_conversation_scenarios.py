"""
Enhanced E2E Conversation Scenarios with comprehensive validations.

This module extends the base scenarios with the new priority scenarios
and enhanced validation functions.
"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from tests.e2e.conversation_scenarios import (
    ConversationScenario, ConversationTurn, ScenarioType,
    HappyPathScenarios, ErrorRecoveryScenarios, ComplexOrderScenarios,
    EdgeCaseScenarios, StressTestScenarios
)


class ValidationHelpers:
    """Helper functions for response validation."""
    
    @staticmethod
    def contains_all(phrases: List[str]) -> Callable:
        """Check if response contains all phrases."""
        def validator(response: str) -> bool:
            response_lower = response.lower()
            return all(phrase.lower() in response_lower for phrase in phrases)
        return validator
    
    @staticmethod
    def contains_any(phrases: List[str]) -> Callable:
        """Check if response contains any of the phrases."""
        def validator(response: str) -> bool:
            response_lower = response.lower()
            return any(phrase.lower() in response_lower for phrase in phrases)
        return validator
    
    @staticmethod
    def cart_item_validator(
        name: str = None,
        quantity: int = None,
        has_modifiers: bool = None,
        modifier_keys: List[str] = None
    ) -> Callable:
        """Validate cart item properties."""
        def validator(context: Dict[str, Any]) -> bool:
            cart = context.get("cart", [])
            if not cart:
                return False
            
            # Find matching item
            for item in cart:
                matches = True
                
                if name and name.lower() not in item.get("name", "").lower():
                    matches = False
                
                if quantity is not None and item.get("quantity") != quantity:
                    matches = False
                
                if has_modifiers is not None:
                    item_has_mods = bool(item.get("modifiers"))
                    if has_modifiers != item_has_mods:
                        matches = False
                
                if modifier_keys:
                    item_mods = item.get("modifiers", {})
                    if not all(key in item_mods for key in modifier_keys):
                        matches = False
                
                if matches:
                    return True
            
            return False
        return validator


class ModifierScenarios:
    """Scenarios specifically testing modifier selection."""
    
    @staticmethod
    def poke_bowl_with_modifiers() -> ConversationScenario:
        """Comprehensive poke bowl ordering with multiple modifiers."""
        return ConversationScenario(
            id="modifier_001",
            name="Poke Bowl with Complex Modifiers",
            description="Customer orders poke bowl with size, protein, and topping selections",
            scenario_type=ScenarioType.HAPPY_PATH,
            turns=[
                ConversationTurn(
                    speaker="system",
                    message="",
                    expected_state="GREETING",
                    expected_agent="frontline"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Hi, I'm Jennifer and I'd like to order for pickup",
                    expected_state="ORDERING",
                    expected_context={"customer_name": "Jennifer", "order_type": "pickup"},
                    validation_function=ValidationHelpers.contains_any([
                        "what would you like",
                        "what can I get",
                        "ready to take your order"
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="I want a poke bowl",
                    expected_agent="menu",
                    validation_function=ValidationHelpers.contains_any([
                        "what size",
                        "regular or large",
                        "size would you"
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="Large please",
                    validation_function=ValidationHelpers.contains_any([
                        "protein",
                        "what kind of fish",
                        "tuna",
                        "salmon"
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="I'll have salmon and spicy tuna",
                    expected_agent="cart",
                    validation_function=ValidationHelpers.contains_all([
                        "salmon",
                        "spicy tuna"
                    ]),
                    expected_context=ValidationHelpers.cart_item_validator(
                        name="poke bowl",
                        quantity=1,
                        has_modifiers=True,
                        modifier_keys=["size", "proteins"]
                    )
                ),
                ConversationTurn(
                    speaker="user",
                    message="Add extra avocado, seaweed salad, and spicy mayo on the side",
                    validation_function=ValidationHelpers.contains_any([
                        "extra avocado",
                        "anything else",
                        "added"
                    ]),
                    expected_context=lambda ctx: (
                        ctx.get("cart") and
                        "avocado" in str(ctx["cart"][0].get("modifiers", {})).lower()
                    )
                ),
                ConversationTurn(
                    speaker="user",
                    message="That's it for now",
                    expected_state="VALIDATION",
                    validation_function=ValidationHelpers.contains_all([
                        "large poke bowl",
                        "salmon",
                        "spicy tuna",
                        "extra avocado"
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="Yes, that's correct",
                    expected_state="CONFIRMATION",
                    validation_function=ValidationHelpers.contains_any([
                        "ready in",
                        "pickup time",
                        "minutes"
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="I'll pay when I arrive",
                    expected_state="FULFILLMENT"
                ),
                ConversationTurn(
                    speaker="user",
                    message="My number is 415-555-1234",
                    expected_state="COMPLETED",
                    expected_context={"customer_phone": "415-555-1234"},
                    validation_function=ValidationHelpers.contains_any([
                        "order number",
                        "confirmation",
                        "see you soon"
                    ])
                )
            ],
            expected_outcome={
                "order_placed": True,
                "order_type": "pickup",
                "items_count": 1,
                "modifiers_selected": True,
                "modifier_categories": ["size", "proteins", "extras"],
                "final_cart_validation": lambda cart: (
                    len(cart) == 1 and
                    cart[0]["name"].lower() == "poke bowl" and
                    cart[0].get("modifiers", {}).get("size") == "large" and
                    len(cart[0].get("modifiers", {}).get("proteins", [])) == 2
                )
            },
            tags=["modifiers", "poke_bowl", "pickup", "complex_order"]
        )
    
    @staticmethod
    def sushi_roll_spice_level() -> ConversationScenario:
        """Test spice level modifier selection."""
        return ConversationScenario(
            id="modifier_002",
            name="Sushi Roll with Spice Level",
            description="Customer orders rolls with specific spice preferences",
            scenario_type=ScenarioType.HAPPY_PATH,
            turns=[
                ConversationTurn(
                    speaker="system",
                    message="",
                    expected_state="GREETING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Mark here, I want to order",
                    expected_state="ORDERING",
                    expected_context={"customer_name": "Mark"}
                ),
                ConversationTurn(
                    speaker="user",
                    message="I'd like a spicy tuna roll",
                    expected_agent="menu",
                    validation_function=ValidationHelpers.contains_any([
                        "how spicy",
                        "spice level",
                        "mild, medium, or hot"
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="Make it extra spicy",
                    expected_agent="cart",
                    expected_context=lambda ctx: (
                        ctx.get("cart") and
                        ctx["cart"][0].get("modifiers", {}).get("spice_level") in ["hot", "extra_spicy"]
                    ),
                    validation_function=ValidationHelpers.contains_all([
                        "extra spicy",
                        "spicy tuna"
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="Also add a salmon roll, not spicy at all",
                    expected_context=lambda ctx: len(ctx.get("cart", [])) == 2,
                    validation_function=ValidationHelpers.contains_any([
                        "salmon roll",
                        "no spice",
                        "not spicy"
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="That's all",
                    expected_state="VALIDATION",
                    validation_function=lambda resp: (
                        "extra spicy" in resp.lower() and
                        "salmon roll" in resp.lower() and
                        resp.lower().count("roll") >= 2
                    )
                )
            ],
            expected_outcome={
                "order_placed": True,
                "items_with_spice_modifier": 1,
                "spice_levels_used": ["extra_spicy", "none"]
            },
            tags=["modifiers", "spice_level", "preferences"]
        )


class EnhancedHappyPathScenarios(HappyPathScenarios):
    """Enhanced versions of happy path scenarios with better validations."""
    
    @staticmethod
    def enhanced_simple_pickup_order() -> ConversationScenario:
        """Enhanced simple pickup order with comprehensive validations."""
        base_scenario = HappyPathScenarios.simple_pickup_order()
        
        # Enhance turns with better validations
        enhanced_turns = []
        for turn in base_scenario.turns:
            enhanced_turn = ConversationTurn(
                speaker=turn.speaker,
                message=turn.message,
                expected_state=turn.expected_state,
                expected_agent=turn.expected_agent,
                expected_context=turn.expected_context,
                wait_time=turn.wait_time
            )
            
            # Add specific validations based on the turn
            if "place an order" in turn.message:
                enhanced_turn.validation_function = ValidationHelpers.contains_any([
                    "what would you like",
                    "what can I get",
                    "ready to take"
                ])
            elif "California rolls" in turn.message:
                enhanced_turn.validation_function = ValidationHelpers.contains_all([
                    "california roll",
                    "2",
                    "added"
                ])
                enhanced_turn.expected_context = ValidationHelpers.cart_item_validator(
                    name="california roll",
                    quantity=2
                )
            elif "That's all" in turn.message:
                enhanced_turn.validation_function = lambda resp: all([
                    "order" in resp.lower(),
                    "california roll" in resp.lower(),
                    "2" in resp or "two" in resp.lower(),
                    any(word in resp.lower() for word in ["total", "confirm", "correct"])
                ])
            elif "Yes, that's correct" in turn.message:
                enhanced_turn.validation_function = ValidationHelpers.contains_any([
                    "payment",
                    "how would you",
                    "pay"
                ])
            elif "phone number" in turn.message:
                enhanced_turn.validation_function = ValidationHelpers.contains_any([
                    "order number",
                    "confirmation",
                    "ready in",
                    "minutes"
                ])
            
            enhanced_turns.append(enhanced_turn)
        
        base_scenario.turns = enhanced_turns
        
        # Enhance expected outcome
        base_scenario.expected_outcome.update({
            "final_cart_validation": lambda cart: (
                len(cart) == 1 and
                cart[0]["quantity"] == 2 and
                "california" in cart[0]["name"].lower() and
                cart[0].get("unit_price", 0) > 0 and
                cart[0].get("plu") is not None
            ),
            "pos_payload_validation": lambda payload: all([
                payload.get("items") is not None,
                len(payload["items"]) == 1,
                payload.get("order_type") == "pickup",
                payload.get("customer", {}).get("phone") == "555-1234"
            ])
        })
        
        return base_scenario


class DeliveryScenarios:
    """Scenarios for delivery orders."""
    
    @staticmethod
    def complete_delivery_order() -> ConversationScenario:
        """Complete delivery order with address and payment."""
        return ConversationScenario(
            id="delivery_001",
            name="Full Delivery Order Flow",
            description="Customer completes delivery order with address verification",
            scenario_type=ScenarioType.HAPPY_PATH,
            turns=[
                ConversationTurn(
                    speaker="system",
                    message="",
                    expected_state="GREETING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Hello, I'm Robert and I'd like delivery please",
                    expected_state="ORDERING",
                    expected_context={
                        "customer_name": "Robert",
                        "order_type": "delivery"
                    },
                    validation_function=ValidationHelpers.contains_any([
                        "delivery",
                        "what would you like",
                        "address"
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="First, do you deliver to downtown?",
                    validation_function=ValidationHelpers.contains_any([
                        "deliver",
                        "area",
                        "yes",
                        "address"
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="Great! I'll have a salmon teriyaki bento box",
                    expected_agent="cart",
                    expected_context=lambda ctx: (
                        ctx.get("order_type") == "delivery" and
                        len(ctx.get("cart", [])) == 1
                    ),
                    validation_function=ValidationHelpers.contains_all([
                        "salmon teriyaki",
                        "bento"
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="Add miso soup and a green tea",
                    expected_context=lambda ctx: len(ctx.get("cart", [])) == 3,
                    validation_function=ValidationHelpers.contains_all([
                        "miso soup",
                        "green tea"
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="That's everything",
                    expected_state="VALIDATION",
                    validation_function=lambda resp: all([
                        "salmon teriyaki bento" in resp.lower(),
                        "miso soup" in resp.lower(),
                        "green tea" in resp.lower(),
                        any(word in resp.lower() for word in ["total", "order", "confirm"])
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="Yes, that's right",
                    expected_state="CONFIRMATION",
                    validation_function=ValidationHelpers.contains_any([
                        "delivery address",
                        "where should",
                        "deliver to"
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="123 Main Street, Apartment 4B",
                    validation_function=ValidationHelpers.contains_any([
                        "city",
                        "zip",
                        "postal code",
                        "cross street"
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="San Francisco, 94105. Near Market Street",
                    expected_context=lambda ctx: all([
                        "123 Main" in ctx.get("delivery_address", ""),
                        "94105" in ctx.get("delivery_address", ""),
                        "San Francisco" in ctx.get("delivery_address", "")
                    ]),
                    validation_function=ValidationHelpers.contains_any([
                        "confirm",
                        "correct address",
                        "123 Main"
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="Yes, that's correct",
                    validation_function=ValidationHelpers.contains_any([
                        "payment",
                        "pay",
                        "card or cash"
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="Credit card",
                    expected_state="FULFILLMENT",
                    expected_context={"payment_method": "credit_card"},
                    validation_function=ValidationHelpers.contains_any([
                        "driver",
                        "terminal",
                        "card reader"
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="Sounds good. My phone is 415-555-9876",
                    expected_state="COMPLETED",
                    expected_context={"customer_phone": "415-555-9876"},
                    validation_function=ValidationHelpers.contains_all([
                        "order",
                        "delivery",
                        "minutes"
                    ])
                )
            ],
            expected_outcome={
                "order_placed": True,
                "order_type": "delivery",
                "address_collected": True,
                "payment_method": "credit_card",
                "delivery_validation": lambda ctx: all([
                    ctx.get("delivery_address") is not None,
                    "123 Main" in ctx["delivery_address"],
                    "94105" in ctx["delivery_address"]
                ])
            },
            tags=["delivery", "address", "payment", "complete_flow"]
        )


def get_enhanced_scenarios() -> List[ConversationScenario]:
    """Get all enhanced scenarios including new ones."""
    scenarios = []
    
    # Add new modifier scenarios
    scenarios.append(ModifierScenarios.poke_bowl_with_modifiers())
    scenarios.append(ModifierScenarios.sushi_roll_spice_level())
    
    # Add enhanced versions of existing scenarios
    scenarios.append(EnhancedHappyPathScenarios.enhanced_simple_pickup_order())
    
    # Add delivery scenario
    scenarios.append(DeliveryScenarios.complete_delivery_order())
    
    # Include all original scenarios (they still have value)
    from tests.e2e.conversation_scenarios import get_all_scenarios
    scenarios.extend(get_all_scenarios())
    
    return scenarios