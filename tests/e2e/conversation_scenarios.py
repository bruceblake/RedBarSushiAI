"""
E2E Conversation Scenarios for RedBarSushiAI.

This module defines complete conversation scenarios that test the entire system
from initial call to order completion, including all state transitions and
agent interactions.
"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import json


class ScenarioType(Enum):
    """Types of conversation scenarios."""
    HAPPY_PATH = "happy_path"
    ERROR_RECOVERY = "error_recovery"
    COMPLEX_ORDER = "complex_order"
    EDGE_CASES = "edge_cases"
    STRESS_TEST = "stress_test"


@dataclass
class ConversationTurn:
    """Single turn in a conversation."""
    speaker: str  # "user" or "system"
    message: str
    expected_state: Optional[str] = None
    expected_agent: Optional[str] = None
    expected_context: Optional[Dict[str, Any]] = None
    validation_function: Optional[Callable] = None
    wait_time: float = 0.5  # Seconds to wait before next turn


@dataclass
class ConversationScenario:
    """Complete conversation scenario."""
    id: str
    name: str
    description: str
    scenario_type: ScenarioType
    turns: List[ConversationTurn]
    initial_context: Dict[str, Any] = field(default_factory=dict)
    expected_outcome: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    timeout: float = 300.0  # 5 minutes default


class HappyPathScenarios:
    """Happy path conversation scenarios."""
    
    @staticmethod
    def simple_pickup_order() -> ConversationScenario:
        """Simple pickup order scenario."""
        return ConversationScenario(
            id="happy_path_001",
            name="Simple Pickup Order",
            description="Customer places a simple pickup order with no issues",
            scenario_type=ScenarioType.HAPPY_PATH,
            turns=[
                ConversationTurn(
                    speaker="system",
                    message="",  # Initial greeting
                    expected_state="GREETING",
                    expected_agent="frontline"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Hi, my name is John",
                    expected_state="MAIN_MENU",
                    expected_context={"customer_name": "John"}
                ),
                ConversationTurn(
                    speaker="user",
                    message="I'd like to place an order for pickup",
                    expected_state="ORDERING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="I'll have two California rolls please",
                    expected_agent="cart",
                    expected_context=lambda ctx: len(ctx.get("cart", [])) == 1
                ),
                ConversationTurn(
                    speaker="user",
                    message="That's all for now",
                    expected_state="VALIDATION"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Yes, that's correct",
                    expected_state="CONFIRMATION"
                ),
                ConversationTurn(
                    speaker="user",
                    message="I'll pay when I pick up",
                    expected_state="FULFILLMENT"
                ),
                ConversationTurn(
                    speaker="user",
                    message="My phone number is 555-1234",
                    expected_state="COMPLETED"
                )
            ],
            expected_outcome={
                "order_placed": True,
                "order_type": "pickup",
                "items_count": 1,
                "customer_phone": "555-1234"
            },
            tags=["pickup", "simple", "happy_path"]
        )
    
    @staticmethod
    def order_with_menu_questions() -> ConversationScenario:
        """Order with menu inquiries."""
        return ConversationScenario(
            id="happy_path_002",
            name="Order with Menu Questions",
            description="Customer asks about menu before ordering",
            scenario_type=ScenarioType.HAPPY_PATH,
            turns=[
                ConversationTurn(
                    speaker="system",
                    message="",
                    expected_state="GREETING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Hello, I'm Sarah",
                    expected_state="MAIN_MENU"
                ),
                ConversationTurn(
                    speaker="user",
                    message="What vegetarian options do you have?",
                    expected_state="MAIN_MENU",  # Should stay in main menu
                    expected_agent="menu"
                ),
                ConversationTurn(
                    speaker="user",
                    message="How much is the vegetable roll?",
                    expected_agent="menu"
                ),
                ConversationTurn(
                    speaker="user",
                    message="I'd like to order the vegetable roll",
                    expected_state="ORDERING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Make it 3 rolls please",
                    expected_context=lambda ctx: (
                        ctx.get("cart") and 
                        ctx["cart"][0].get("quantity") == 3
                    )
                ),
                ConversationTurn(
                    speaker="user",
                    message="That's everything",
                    expected_state="VALIDATION"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Perfect, confirm the order",
                    expected_state="CONFIRMATION"
                )
            ],
            expected_outcome={
                "order_placed": True,
                "dietary_preference": "vegetarian",
                "menu_questions_asked": True
            },
            tags=["menu_inquiry", "vegetarian", "happy_path"]
        )


class ErrorRecoveryScenarios:
    """Error recovery conversation scenarios."""
    
    @staticmethod
    def item_not_available() -> ConversationScenario:
        """Handle unavailable item scenario."""
        return ConversationScenario(
            id="error_recovery_001",
            name="Item Not Available",
            description="Customer tries to order unavailable item",
            scenario_type=ScenarioType.ERROR_RECOVERY,
            turns=[
                ConversationTurn(
                    speaker="system",
                    message="",
                    expected_state="GREETING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Hi, I'm Mike",
                    expected_state="MAIN_MENU"
                ),
                ConversationTurn(
                    speaker="user",
                    message="I want to order",
                    expected_state="ORDERING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="I'd like the lobster roll",  # Not on menu
                    validation_function=lambda resp: (
                        "not available" in resp.lower() or
                        "don't have" in resp.lower()
                    )
                ),
                ConversationTurn(
                    speaker="user",
                    message="Oh, then I'll have the spicy tuna roll instead",
                    expected_context=lambda ctx: len(ctx.get("cart", [])) == 1
                ),
                ConversationTurn(
                    speaker="user",
                    message="That's all",
                    expected_state="VALIDATION"
                )
            ],
            expected_outcome={
                "error_recovered": True,
                "unavailable_item_handled": True
            },
            tags=["error_recovery", "unavailable_item"]
        )
    
    @staticmethod
    def connection_issues() -> ConversationScenario:
        """Handle connection/understanding issues."""
        return ConversationScenario(
            id="error_recovery_002",
            name="Connection Issues",
            description="Poor connection with repeated requests",
            scenario_type=ScenarioType.ERROR_RECOVERY,
            turns=[
                ConversationTurn(
                    speaker="system",
                    message="",
                    expected_state="GREETING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="...",  # Unclear audio
                    validation_function=lambda resp: (
                        "didn't catch" in resp.lower() or
                        "repeat" in resp.lower()
                    )
                ),
                ConversationTurn(
                    speaker="user",
                    message="My name is Emma",
                    expected_state="MAIN_MENU"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Can you repeat that?",  # Global command
                    validation_function=lambda resp: len(resp) > 0
                ),
                ConversationTurn(
                    speaker="user",
                    message="I want to order food",
                    expected_state="ORDERING"
                )
            ],
            expected_outcome={
                "global_commands_used": ["REPEAT"],
                "unclear_input_handled": True
            },
            tags=["error_recovery", "connection_issues", "global_commands"]
        )


class ComplexOrderScenarios:
    """Complex order conversation scenarios."""
    
    @staticmethod
    def large_group_order() -> ConversationScenario:
        """Large group order with modifications."""
        return ConversationScenario(
            id="complex_order_001",
            name="Large Group Order",
            description="Complex order for a group with modifications",
            scenario_type=ScenarioType.COMPLEX_ORDER,
            turns=[
                ConversationTurn(
                    speaker="system",
                    message="",
                    expected_state="GREETING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Hi, this is David",
                    expected_state="MAIN_MENU"
                ),
                ConversationTurn(
                    speaker="user",
                    message="I need to place a large order for pickup",
                    expected_state="ORDERING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Start with 5 California rolls",
                    expected_context=lambda ctx: (
                        ctx.get("cart") and
                        any(item.get("quantity") == 5 for item in ctx["cart"])
                    )
                ),
                ConversationTurn(
                    speaker="user",
                    message="Add 3 spicy tuna rolls, but make 2 of them without spicy mayo",
                    expected_context=lambda ctx: len(ctx.get("cart", [])) >= 2
                ),
                ConversationTurn(
                    speaker="user",
                    message="Also add 4 orders of edamame",
                    expected_context=lambda ctx: len(ctx.get("cart", [])) >= 3
                ),
                ConversationTurn(
                    speaker="user",
                    message="And 2 miso soups",
                    expected_context=lambda ctx: len(ctx.get("cart", [])) >= 4
                ),
                ConversationTurn(
                    speaker="user",
                    message="Actually, change the California rolls to 6",
                    validation_function=lambda resp: (
                        "changed" in resp.lower() or
                        "updated" in resp.lower()
                    )
                ),
                ConversationTurn(
                    speaker="user",
                    message="That's everything",
                    expected_state="VALIDATION"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Can you repeat my order?",
                    validation_function=lambda resp: (
                        "6" in resp and "california" in resp.lower()
                    )
                ),
                ConversationTurn(
                    speaker="user",
                    message="Yes, that's correct",
                    expected_state="CONFIRMATION"
                )
            ],
            expected_outcome={
                "order_complexity": "high",
                "modifications_made": True,
                "total_items": 4,
                "quantity_changed": True
            },
            tags=["complex_order", "modifications", "large_order"]
        )
    
    @staticmethod
    def order_with_cancellation() -> ConversationScenario:
        """Order that gets partially cancelled."""
        return ConversationScenario(
            id="complex_order_002",
            name="Order with Partial Cancellation",
            description="Customer cancels part of order",
            scenario_type=ScenarioType.COMPLEX_ORDER,
            turns=[
                ConversationTurn(
                    speaker="system",
                    message="",
                    expected_state="GREETING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Lisa here",
                    expected_state="MAIN_MENU"
                ),
                ConversationTurn(
                    speaker="user",
                    message="I want to order",
                    expected_state="ORDERING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Two salmon rolls and one tuna roll",
                    expected_context=lambda ctx: len(ctx.get("cart", [])) >= 2
                ),
                ConversationTurn(
                    speaker="user",
                    message="Actually, cancel the tuna roll",
                    validation_function=lambda resp: (
                        "removed" in resp.lower() or
                        "cancelled" in resp.lower()
                    )
                ),
                ConversationTurn(
                    speaker="user",
                    message="Just the salmon rolls then",
                    expected_state="VALIDATION"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Wait, I changed my mind, cancel everything",
                    expected_state="CANCELLATION_PENDING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="No, actually keep the order",
                    expected_state="ORDERING",
                    validation_function=lambda resp: "salmon" in resp.lower()
                ),
                ConversationTurn(
                    speaker="user",
                    message="That's final",
                    expected_state="VALIDATION"
                )
            ],
            expected_outcome={
                "cancellation_attempted": True,
                "cancellation_declined": True,
                "final_order_placed": True
            },
            tags=["complex_order", "cancellation", "state_changes"]
        )


class EdgeCaseScenarios:
    """Edge case conversation scenarios."""
    
    @staticmethod
    def rapid_state_changes() -> ConversationScenario:
        """Rapid state changes and context switches."""
        return ConversationScenario(
            id="edge_cases_001",
            name="Rapid Context Switches",
            description="Customer rapidly switches context",
            scenario_type=ScenarioType.EDGE_CASES,
            turns=[
                ConversationTurn(
                    speaker="system",
                    message="",
                    expected_state="GREETING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Tom",
                    expected_state="MAIN_MENU"
                ),
                ConversationTurn(
                    speaker="user",
                    message="What's your address?",
                    expected_agent="frontline"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Never mind, I want to order",
                    expected_state="ORDERING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Actually, what time do you close?",
                    validation_function=lambda resp: (
                        "close" in resp.lower() or
                        "hours" in resp.lower()
                    )
                ),
                ConversationTurn(
                    speaker="user",
                    message="OK add a California roll",
                    expected_context=lambda ctx: len(ctx.get("cart", [])) == 1
                ),
                ConversationTurn(
                    speaker="user",
                    message="Go back",  # Global command
                    expected_state="MAIN_MENU"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Start over",  # Global command
                    expected_state="GREETING",
                    expected_context=lambda ctx: (
                        not ctx.get("cart") or len(ctx["cart"]) == 0
                    )
                )
            ],
            expected_outcome={
                "handled_context_switches": True,
                "global_commands_used": ["GO_BACK", "START_OVER"],
                "state_reset": True
            },
            tags=["edge_cases", "context_switches", "global_commands"]
        )
    
    @staticmethod
    def ambiguous_requests() -> ConversationScenario:
        """Handle ambiguous and unclear requests."""
        return ConversationScenario(
            id="edge_cases_002",
            name="Ambiguous Requests",
            description="Customer makes ambiguous requests",
            scenario_type=ScenarioType.EDGE_CASES,
            turns=[
                ConversationTurn(
                    speaker="system",
                    message="",
                    expected_state="GREETING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Hey",  # No name provided
                    expected_state="MAIN_MENU",
                    expected_context=lambda ctx: not ctx.get("customer_name")
                ),
                ConversationTurn(
                    speaker="user",
                    message="I want the usual",  # Ambiguous
                    validation_function=lambda resp: (
                        "what" in resp.lower() or
                        "which" in resp.lower() or
                        "help" in resp.lower()
                    )
                ),
                ConversationTurn(
                    speaker="user",
                    message="The $12.95 one",  # Price-based disambiguation
                    validation_function=lambda resp: (
                        "which" in resp.lower() or
                        len(resp) > 50  # Listing options
                    )
                ),
                ConversationTurn(
                    speaker="user",
                    message="The first one you mentioned",
                    expected_context=lambda ctx: len(ctx.get("cart", [])) >= 1
                ),
                ConversationTurn(
                    speaker="user",
                    message="Something spicy",  # Vague request
                    validation_function=lambda resp: (
                        "spicy" in resp.lower() and
                        ("which" in resp.lower() or "have" in resp.lower())
                    )
                ),
                ConversationTurn(
                    speaker="user",
                    message="The spicy tuna",
                    expected_context=lambda ctx: len(ctx.get("cart", [])) >= 2
                )
            ],
            expected_outcome={
                "disambiguation_handled": True,
                "ambiguous_requests_resolved": True
            },
            tags=["edge_cases", "disambiguation", "ambiguous"]
        )


class StressTestScenarios:
    """Stress test conversation scenarios."""
    
    @staticmethod
    def maximum_length_conversation() -> ConversationScenario:
        """Very long conversation with many interactions."""
        turns = [
            ConversationTurn(
                speaker="system",
                message="",
                expected_state="GREETING"
            ),
            ConversationTurn(
                speaker="user",
                message="Hi, I'm Alex",
                expected_state="MAIN_MENU"
            )
        ]
        
        # Add many menu questions
        menu_questions = [
            "What's in the California roll?",
            "Is the spicy tuna very spicy?",
            "Do you have brown rice option?",
            "What's the most popular item?",
            "Any lunch specials?",
            "What comes with the bento box?",
            "Is the salmon fresh?",
            "Do you have gluten-free soy sauce?"
        ]
        
        for question in menu_questions:
            turns.append(ConversationTurn(
                speaker="user",
                message=question,
                wait_time=0.3
            ))
        
        # Start ordering
        turns.append(ConversationTurn(
            speaker="user",
            message="OK I'm ready to order",
            expected_state="ORDERING"
        ))
        
        # Add many items with modifications
        orders = [
            "One California roll with extra avocado",
            "Two spicy tuna rolls",
            "One salmon sashimi",
            "Three pieces of tamago",
            "One miso soup",
            "Actually make that two miso soups",
            "One green tea ice cream"
        ]
        
        for order in orders:
            turns.append(ConversationTurn(
                speaker="user",
                message=order,
                wait_time=0.5
            ))
        
        # Complete order
        turns.extend([
            ConversationTurn(
                speaker="user",
                message="That's all",
                expected_state="VALIDATION"
            ),
            ConversationTurn(
                speaker="user",
                message="Yes, confirm it",
                expected_state="CONFIRMATION"
            )
        ])
        
        return ConversationScenario(
            id="stress_test_001",
            name="Maximum Length Conversation",
            description="Very long conversation testing system limits",
            scenario_type=ScenarioType.STRESS_TEST,
            turns=turns,
            expected_outcome={
                "conversation_length": len(turns),
                "handled_many_questions": True,
                "context_maintained": True
            },
            tags=["stress_test", "long_conversation"],
            timeout=600.0  # 10 minutes
        )


def get_all_scenarios() -> List[ConversationScenario]:
    """Get all defined conversation scenarios."""
    scenarios = []
    
    # Happy path scenarios
    scenarios.append(HappyPathScenarios.simple_pickup_order())
    scenarios.append(HappyPathScenarios.order_with_menu_questions())
    
    # Error recovery scenarios
    scenarios.append(ErrorRecoveryScenarios.item_not_available())
    scenarios.append(ErrorRecoveryScenarios.connection_issues())
    
    # Complex order scenarios
    scenarios.append(ComplexOrderScenarios.large_group_order())
    scenarios.append(ComplexOrderScenarios.order_with_cancellation())
    
    # Edge case scenarios
    scenarios.append(EdgeCaseScenarios.rapid_state_changes())
    scenarios.append(EdgeCaseScenarios.ambiguous_requests())
    
    # Stress test scenarios
    scenarios.append(StressTestScenarios.maximum_length_conversation())
    
    return scenarios


def get_scenarios_by_type(scenario_type: ScenarioType) -> List[ConversationScenario]:
    """Get scenarios of a specific type."""
    all_scenarios = get_all_scenarios()
    return [s for s in all_scenarios if s.scenario_type == scenario_type]


def get_scenarios_by_tags(tags: List[str]) -> List[ConversationScenario]:
    """Get scenarios matching any of the specified tags."""
    all_scenarios = get_all_scenarios()
    return [
        s for s in all_scenarios
        if any(tag in s.tags for tag in tags)
    ]