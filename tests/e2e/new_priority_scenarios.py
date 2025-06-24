"""
New priority E2E scenarios to improve test coverage.
"""

from typing import List
from dataclasses import dataclass
from tests.e2e.conversation_scenarios import ConversationScenario, ConversationTurn, ScenarioType


class NewPriorityScenarios:
    """New scenarios addressing coverage gaps."""
    
    @staticmethod
    def order_with_modifiers() -> ConversationScenario:
        """Test modifier selection flow."""
        return ConversationScenario(
            id="modifier_001",
            name="Order with Multiple Modifiers",
            description="Customer orders items requiring modifier selection",
            scenario_type=ScenarioType.HAPPY_PATH,
            turns=[
                ConversationTurn(
                    speaker="system",
                    message="",
                    expected_state="GREETING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Hi, I'm Jennifer",
                    expected_state="MAIN_MENU"
                ),
                ConversationTurn(
                    speaker="user",
                    message="I'd like to order for pickup",
                    expected_state="ORDERING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="I want a poke bowl",
                    validation_function=lambda resp: any([
                        "size" in resp.lower(),
                        "regular or large" in resp.lower(),
                        "what size" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="Large please",
                    validation_function=lambda resp: any([
                        "protein" in resp.lower(),
                        "tuna" in resp.lower() and "salmon" in resp.lower(),
                        "which" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="Salmon and tuna",
                    validation_function=lambda resp: any([
                        "toppings" in resp.lower(),
                        "anything else" in resp.lower(),
                        "added" in resp.lower()
                    ]),
                    expected_context=lambda ctx: (
                        ctx.get("cart") and
                        ctx["cart"][0].get("modifiers", {}).get("size") == "large" and
                        "salmon" in str(ctx["cart"][0].get("modifiers", {})).lower()
                    )
                ),
                ConversationTurn(
                    speaker="user",
                    message="Add extra avocado and spicy mayo",
                    expected_context=lambda ctx: (
                        "avocado" in str(ctx["cart"][0].get("modifiers", {})).lower()
                    )
                ),
                ConversationTurn(
                    speaker="user",
                    message="That's it for the poke bowl. Also add a green tea",
                    expected_context=lambda ctx: len(ctx.get("cart", [])) == 2
                ),
                ConversationTurn(
                    speaker="user",
                    message="That's everything",
                    expected_state="VALIDATION",
                    validation_function=lambda resp: all([
                        "large poke bowl" in resp.lower(),
                        "salmon" in resp.lower(),
                        "tuna" in resp.lower(),
                        "green tea" in resp.lower()
                    ])
                )
            ],
            expected_outcome={
                "order_placed": True,
                "modifiers_selected": True,
                "modifier_categories": ["size", "proteins", "extras"],
                "items_with_modifiers": 1
            },
            tags=["modifiers", "poke_bowl", "happy_path"]
        )
    
    @staticmethod
    def delivery_order_flow() -> ConversationScenario:
        """Test delivery order with address collection."""
        return ConversationScenario(
            id="delivery_001",
            name="Complete Delivery Order",
            description="Customer places delivery order with address",
            scenario_type=ScenarioType.HAPPY_PATH,
            turns=[
                ConversationTurn(
                    speaker="system",
                    message="",
                    expected_state="GREETING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Robert here",
                    expected_state="MAIN_MENU"
                ),
                ConversationTurn(
                    speaker="user",
                    message="I want delivery",
                    expected_state="ORDERING",
                    validation_function=lambda resp: "delivery" in resp.lower()
                ),
                ConversationTurn(
                    speaker="user",
                    message="One salmon teriyaki bento",
                    expected_context=lambda ctx: (
                        ctx.get("order_type") == "delivery" and
                        len(ctx.get("cart", [])) == 1
                    )
                ),
                ConversationTurn(
                    speaker="user",
                    message="That's all",
                    expected_state="VALIDATION"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Yes, correct",
                    expected_state="CONFIRMATION",
                    validation_function=lambda resp: any([
                        "address" in resp.lower(),
                        "deliver" in resp.lower(),
                        "where" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="123 Main Street, apartment 4B",
                    expected_context=lambda ctx: (
                        "123 Main" in ctx.get("delivery_address", "")
                    ),
                    validation_function=lambda resp: any([
                        "zip" in resp.lower(),
                        "postal" in resp.lower(),
                        "city" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="San Francisco, 94105",
                    expected_context=lambda ctx: (
                        "94105" in ctx.get("delivery_address", "")
                    )
                ),
                ConversationTurn(
                    speaker="user",
                    message="Pay with credit card",
                    expected_state="FULFILLMENT",
                    expected_context=lambda ctx: (
                        ctx.get("payment_method") == "credit_card"
                    )
                )
            ],
            expected_outcome={
                "order_placed": True,
                "order_type": "delivery",
                "address_collected": True,
                "payment_method": "credit_card"
            },
            tags=["delivery", "address", "payment"]
        )
    
    @staticmethod
    def help_and_escalation() -> ConversationScenario:
        """Test help requests and human escalation."""
        return ConversationScenario(
            id="escalation_001",
            name="Help and Human Escalation",
            description="Customer requests help and human assistance",
            scenario_type=ScenarioType.ERROR_RECOVERY,
            turns=[
                ConversationTurn(
                    speaker="system",
                    message="",
                    expected_state="GREETING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="I need help",
                    validation_function=lambda resp: any([
                        "help" in resp.lower(),
                        "assist" in resp.lower(),
                        "what can i" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="My name is Karen",
                    expected_state="MAIN_MENU"
                ),
                ConversationTurn(
                    speaker="user",
                    message="I have a complicated order",
                    expected_state="ORDERING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="I need to speak to a person",
                    expected_state="ESCALATION",
                    expected_agent="escalation",
                    validation_function=lambda resp: any([
                        "transfer" in resp.lower(),
                        "connect" in resp.lower(),
                        "someone will" in resp.lower(),
                        "representative" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="Never mind, I'll continue with you",
                    expected_state="ORDERING",
                    validation_function=lambda resp: any([
                        "help" in resp.lower(),
                        "order" in resp.lower(),
                        "what would you" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="Add two rainbow rolls",
                    expected_context=lambda ctx: len(ctx.get("cart", [])) == 1
                )
            ],
            expected_outcome={
                "escalation_requested": True,
                "escalation_cancelled": True,
                "returned_to_ordering": True
            },
            tags=["escalation", "help", "global_commands"]
        )
    
    @staticmethod
    def order_timing_questions() -> ConversationScenario:
        """Test questions about order timing and scheduling."""
        return ConversationScenario(
            id="timing_001",
            name="Order Timing and Scheduling",
            description="Customer asks about timing and schedules order",
            scenario_type=ScenarioType.HAPPY_PATH,
            turns=[
                ConversationTurn(
                    speaker="system",
                    message="",
                    expected_state="GREETING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Hi, Patricia here",
                    expected_state="MAIN_MENU"
                ),
                ConversationTurn(
                    speaker="user",
                    message="How long does pickup usually take?",
                    validation_function=lambda resp: any([
                        "minutes" in resp.lower(),
                        "ready" in resp.lower(),
                        "typically" in resp.lower(),
                        "usually" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="I'd like to place an order for pickup at 6:30 PM",
                    expected_state="ORDERING",
                    expected_context=lambda ctx: (
                        "6:30" in str(ctx.get("scheduled_time", "")) or
                        "18:30" in str(ctx.get("scheduled_time", ""))
                    )
                ),
                ConversationTurn(
                    speaker="user",
                    message="Three dragon rolls",
                    expected_context=lambda ctx: len(ctx.get("cart", [])) == 1
                ),
                ConversationTurn(
                    speaker="user",
                    message="When will this be ready?",
                    validation_function=lambda resp: (
                        "6:30" in resp or
                        "scheduled" in resp.lower()
                    )
                ),
                ConversationTurn(
                    speaker="user",
                    message="Perfect, that's all",
                    expected_state="VALIDATION"
                )
            ],
            expected_outcome={
                "order_placed": True,
                "scheduled_order": True,
                "timing_questions_asked": True
            },
            tags=["timing", "scheduling", "pickup"]
        )
    
    @staticmethod
    def pos_failure_recovery() -> ConversationScenario:
        """Test POS submission failure handling."""
        return ConversationScenario(
            id="pos_failure_001",
            name="POS Submission Failure",
            description="Handle POS system failure gracefully",
            scenario_type=ScenarioType.ERROR_RECOVERY,
            turns=[
                ConversationTurn(
                    speaker="system",
                    message="",
                    expected_state="GREETING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="George calling",
                    expected_state="MAIN_MENU"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Quick order - one California roll",
                    expected_state="ORDERING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="That's it",
                    expected_state="VALIDATION"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Yes confirm",
                    expected_state="CONFIRMATION"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Cash payment",
                    expected_state="FULFILLMENT",
                    # Simulate POS failure in test setup
                    validation_function=lambda resp: any([
                        "issue" in resp.lower(),
                        "problem" in resp.lower(),
                        "unable" in resp.lower(),
                        "try again" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="Yes, try again",
                    validation_function=lambda resp: any([
                        "success" in resp.lower(),
                        "placed" in resp.lower(),
                        "order number" in resp.lower()
                    ])
                )
            ],
            expected_outcome={
                "pos_failure_handled": True,
                "retry_successful": True,
                "order_eventually_placed": True
            },
            tags=["error_recovery", "pos_failure", "retry"]
        )


def get_new_priority_scenarios() -> List[ConversationScenario]:
    """Get all new priority scenarios."""
    return [
        NewPriorityScenarios.order_with_modifiers(),
        NewPriorityScenarios.delivery_order_flow(),
        NewPriorityScenarios.help_and_escalation(),
        NewPriorityScenarios.order_timing_questions(),
        NewPriorityScenarios.pos_failure_recovery()
    ]