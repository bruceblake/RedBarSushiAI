"""
Test cases for LLM prompt evaluation.

This module contains test cases for evaluating the quality and accuracy
of LLM prompts used throughout the RedBarSushiAI system.
"""

from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


class TestCategory(Enum):
    """Categories of prompt tests."""
    INTENT_DETECTION = "intent_detection"
    AGENT_RESPONSE = "agent_response"
    FUNCTION_CALLING = "function_calling"
    ERROR_HANDLING = "error_handling"
    DISAMBIGUATION = "disambiguation"
    GLOBAL_COMMANDS = "global_commands"


@dataclass
class PromptTestCase:
    """Individual test case for prompt evaluation."""
    id: str
    category: TestCategory
    description: str
    system_prompt: str
    user_input: str
    context: Dict[str, Any]
    expected_outputs: List[str]  # Multiple acceptable outputs
    expected_intent: str = None  # For intent detection tests
    expected_function: str = None  # For function calling tests
    should_fail: bool = False
    tags: List[str] = field(default_factory=list)


class IntentDetectionTestCases:
    """Test cases for intent detection prompts."""
    
    @staticmethod
    def get_test_cases() -> List[PromptTestCase]:
        """Get all intent detection test cases."""
        return [
            # GREETING State Tests
            PromptTestCase(
                id="intent_greeting_001",
                category=TestCategory.INTENT_DETECTION,
                description="User provides name clearly",
                system_prompt="",  # Will be filled by intent detector
                user_input="My name is John",
                context={"state": "GREETING"},
                expected_outputs=["PROVIDE_NAME"],
                expected_intent="PROVIDE_NAME",
                tags=["greeting", "name"]
            ),
            PromptTestCase(
                id="intent_greeting_002",
                category=TestCategory.INTENT_DETECTION,
                description="User provides just first name",
                system_prompt="",
                user_input="Sarah",
                context={"state": "GREETING"},
                expected_outputs=["PROVIDE_NAME"],
                expected_intent="PROVIDE_NAME",
                tags=["greeting", "name"]
            ),
            PromptTestCase(
                id="intent_greeting_003",
                category=TestCategory.INTENT_DETECTION,
                description="User wants to skip name",
                system_prompt="",
                user_input="I don't want to give my name",
                context={"state": "GREETING"},
                expected_outputs=["SKIP_NAME"],
                expected_intent="SKIP_NAME",
                tags=["greeting", "skip"]
            ),
            PromptTestCase(
                id="intent_greeting_004",
                category=TestCategory.INTENT_DETECTION,
                description="User confused in greeting",
                system_prompt="",
                user_input="What? I don't understand",
                context={"state": "GREETING"},
                expected_outputs=["REQUEST_ESCALATION"],
                expected_intent="REQUEST_ESCALATION",
                tags=["greeting", "confusion"]
            ),
            
            # MAIN_MENU State Tests
            PromptTestCase(
                id="intent_menu_001",
                category=TestCategory.INTENT_DETECTION,
                description="User wants to start ordering",
                system_prompt="",
                user_input="I'd like to place an order",
                context={"state": "MAIN_MENU"},
                expected_outputs=["START_ORDER"],
                expected_intent="START_ORDER",
                tags=["menu", "order"]
            ),
            PromptTestCase(
                id="intent_menu_002",
                category=TestCategory.INTENT_DETECTION,
                description="User asks about menu",
                system_prompt="",
                user_input="What sushi rolls do you have?",
                context={"state": "MAIN_MENU"},
                expected_outputs=["REQUEST_MENU"],
                expected_intent="REQUEST_MENU",
                tags=["menu", "inquiry"]
            ),
            PromptTestCase(
                id="intent_menu_003",
                category=TestCategory.INTENT_DETECTION,
                description="User asks about hours",
                system_prompt="",
                user_input="Are you open until 10pm?",
                context={"state": "MAIN_MENU"},
                expected_outputs=["REQUEST_HOURS"],
                expected_intent="REQUEST_HOURS",
                tags=["menu", "hours"]
            ),
            
            # ORDERING State Tests
            PromptTestCase(
                id="intent_ordering_001",
                category=TestCategory.INTENT_DETECTION,
                description="User adds item to order",
                system_prompt="",
                user_input="Add two California rolls",
                context={"state": "ORDERING"},
                expected_outputs=["ADD_ITEM"],
                expected_intent="ADD_ITEM",
                tags=["ordering", "add"]
            ),
            PromptTestCase(
                id="intent_ordering_002",
                category=TestCategory.INTENT_DETECTION,
                description="User completes order",
                system_prompt="",
                user_input="That's all for now",
                context={"state": "ORDERING"},
                expected_outputs=["COMPLETE_ORDER"],
                expected_intent="COMPLETE_ORDER",
                tags=["ordering", "complete"]
            ),
            PromptTestCase(
                id="intent_ordering_003",
                category=TestCategory.INTENT_DETECTION,
                description="User requests cancellation",
                system_prompt="",
                user_input="Actually, I want to cancel this order",
                context={"state": "ORDERING"},
                expected_outputs=["REQUEST_CANCELLATION"],
                expected_intent="REQUEST_CANCELLATION",
                tags=["ordering", "cancel"]
            ),
            
            # VALIDATION State Tests
            PromptTestCase(
                id="intent_validation_001",
                category=TestCategory.INTENT_DETECTION,
                description="User confirms order",
                system_prompt="",
                user_input="Yes, that's correct",
                context={"state": "VALIDATION"},
                expected_outputs=["CONFIRM"],
                expected_intent="CONFIRM",
                tags=["validation", "confirm"]
            ),
            PromptTestCase(
                id="intent_validation_002",
                category=TestCategory.INTENT_DETECTION,
                description="User wants to add more",
                system_prompt="",
                user_input="Can I add one more thing?",
                context={"state": "VALIDATION"},
                expected_outputs=["REQUEST_ADD_MORE"],
                expected_intent="REQUEST_ADD_MORE",
                tags=["validation", "modify"]
            ),
            
            # Edge Cases
            PromptTestCase(
                id="intent_edge_001",
                category=TestCategory.INTENT_DETECTION,
                description="Ambiguous input in ordering",
                system_prompt="",
                user_input="Actually, never mind",
                context={"state": "ORDERING"},
                expected_outputs=["CANCEL_ORDER", "REQUEST_CANCELLATION"],
                expected_intent="REQUEST_CANCELLATION",
                tags=["edge", "ambiguous"]
            ),
            PromptTestCase(
                id="intent_edge_002",
                category=TestCategory.INTENT_DETECTION,
                description="Multiple intents in one message",
                system_prompt="",
                user_input="Add a tuna roll and that's all",
                context={"state": "ORDERING"},
                expected_outputs=["ADD_ITEM", "COMPLETE_ORDER"],
                expected_intent="ADD_ITEM",  # Should prioritize first action
                tags=["edge", "multiple"]
            )
        ]


class AgentResponseTestCases:
    """Test cases for agent response generation."""
    
    @staticmethod
    def get_test_cases() -> List[PromptTestCase]:
        """Get agent response test cases."""
        return [
            # Frontline Agent Tests
            PromptTestCase(
                id="agent_frontline_001",
                category=TestCategory.AGENT_RESPONSE,
                description="Greeting a new customer",
                system_prompt="You are a friendly restaurant host for Red Bar Sushi.",
                user_input="",  # Initial call
                context={"initial_call": True},
                expected_outputs=[
                    "Welcome to Red Bar Sushi",
                    "Hello! Thank you for calling Red Bar Sushi",
                    "Good evening, welcome to Red Bar Sushi"
                ],
                tags=["frontline", "greeting"]
            ),
            PromptTestCase(
                id="agent_frontline_002",
                category=TestCategory.AGENT_RESPONSE,
                description="Responding to name provision",
                system_prompt="You are a friendly restaurant host. The customer just provided their name.",
                user_input="My name is Alice",
                context={"customer_name": "Alice"},
                expected_outputs=[
                    "Nice to meet you, Alice",
                    "Thank you, Alice",
                    "Hello Alice, how can I help you today"
                ],
                tags=["frontline", "name_response"]
            ),
            
            # Menu Agent Tests
            PromptTestCase(
                id="agent_menu_001",
                category=TestCategory.AGENT_RESPONSE,
                description="Describing menu items",
                system_prompt="You are a menu expert. Describe sushi rolls available.",
                user_input="What rolls do you have?",
                context={"menu_items": ["California Roll", "Spicy Tuna Roll"]},
                expected_outputs=[
                    "California Roll",
                    "Spicy Tuna Roll",
                    "We have California Roll and Spicy Tuna Roll"
                ],
                tags=["menu", "description"]
            ),
            
            # Cart Agent Tests
            PromptTestCase(
                id="agent_cart_001",
                category=TestCategory.AGENT_RESPONSE,
                description="Confirming item addition",
                system_prompt="You are managing the customer's order. Confirm adding items.",
                user_input="Add 2 California rolls",
                context={"cart": []},
                expected_outputs=[
                    "added 2 California rolls",
                    "I've added 2 California rolls to your order",
                    "2 California rolls have been added"
                ],
                tags=["cart", "confirmation"]
            ),
            
            # Error Response Tests
            PromptTestCase(
                id="agent_error_001",
                category=TestCategory.ERROR_HANDLING,
                description="Handling unavailable item",
                system_prompt="The requested item is not available.",
                user_input="I want the Dragon roll",
                context={"unavailable_item": "Dragon roll"},
                expected_outputs=[
                    "sorry",
                    "not available",
                    "don't have",
                    "unavailable"
                ],
                tags=["error", "unavailable"]
            )
        ]


class FunctionCallingTestCases:
    """Test cases for function calling accuracy."""
    
    @staticmethod
    def get_test_cases() -> List[PromptTestCase]:
        """Get function calling test cases."""
        return [
            # Cart Agent Function Calls
            PromptTestCase(
                id="function_cart_001",
                category=TestCategory.FUNCTION_CALLING,
                description="Add to cart function",
                system_prompt="You have access to add_to_cart function.",
                user_input="I want 3 California rolls",
                context={"available_functions": ["add_to_cart"]},
                expected_outputs=["add_to_cart"],
                expected_function="add_to_cart",
                tags=["cart", "function"]
            ),
            PromptTestCase(
                id="function_cart_002",
                category=TestCategory.FUNCTION_CALLING,
                description="Remove from cart function",
                system_prompt="You have access to remove_from_cart function.",
                user_input="Remove the tuna roll",
                context={"cart": [{"name": "Tuna Roll"}]},
                expected_outputs=["remove_from_cart"],
                expected_function="remove_from_cart",
                tags=["cart", "function"]
            ),
            
            # Menu Agent Function Calls
            PromptTestCase(
                id="function_menu_001",
                category=TestCategory.FUNCTION_CALLING,
                description="Search menu function",
                system_prompt="You have access to search_menu function.",
                user_input="Do you have anything vegetarian?",
                context={"available_functions": ["search_menu"]},
                expected_outputs=["search_menu"],
                expected_function="search_menu",
                tags=["menu", "function"]
            ),
            
            # Validation Tests
            PromptTestCase(
                id="function_validate_001",
                category=TestCategory.FUNCTION_CALLING,
                description="No function needed",
                system_prompt="You are having a conversation.",
                user_input="Thank you",
                context={},
                expected_outputs=[""],  # No function call
                expected_function=None,
                tags=["validation", "no_function"]
            )
        ]


class DisambiguationTestCases:
    """Test cases for disambiguation scenarios."""
    
    @staticmethod
    def get_test_cases() -> List[PromptTestCase]:
        """Get disambiguation test cases."""
        return [
            PromptTestCase(
                id="disambig_001",
                category=TestCategory.DISAMBIGUATION,
                description="Price-based disambiguation",
                system_prompt="Multiple items found at same price. Ask for clarification.",
                user_input="I want the $12.95 roll",
                context={
                    "matches": [
                        {"name": "California Roll", "price": 12.95},
                        {"name": "Vegetable Roll", "price": 12.95}
                    ]
                },
                expected_outputs=[
                    "California Roll or Vegetable Roll",
                    "Which one would you like",
                    "both are $12.95"
                ],
                tags=["disambiguation", "price"]
            ),
            PromptTestCase(
                id="disambig_002",
                category=TestCategory.DISAMBIGUATION,
                description="Name similarity disambiguation",
                system_prompt="Multiple similar items found. Ask for clarification.",
                user_input="I want a spicy roll",
                context={
                    "matches": [
                        {"name": "Spicy Tuna Roll"},
                        {"name": "Spicy Salmon Roll"},
                        {"name": "Spicy Yellowtail Roll"}
                    ]
                },
                expected_outputs=[
                    "Spicy Tuna",
                    "Spicy Salmon",
                    "Spicy Yellowtail",
                    "Which spicy roll"
                ],
                tags=["disambiguation", "name"]
            )
        ]


class GlobalCommandTestCases:
    """Test cases for global command detection."""
    
    @staticmethod
    def get_test_cases() -> List[PromptTestCase]:
        """Get global command test cases."""
        return [
            PromptTestCase(
                id="global_001",
                category=TestCategory.GLOBAL_COMMANDS,
                description="Repeat command detection",
                system_prompt="",
                user_input="Can you repeat that?",
                context={},
                expected_outputs=["REPEAT"],
                expected_intent="REPEAT",
                tags=["global", "repeat"]
            ),
            PromptTestCase(
                id="global_002",
                category=TestCategory.GLOBAL_COMMANDS,
                description="Start over command",
                system_prompt="",
                user_input="Let's start over from the beginning",
                context={},
                expected_outputs=["START_OVER"],
                expected_intent="START_OVER",
                tags=["global", "start_over"]
            ),
            PromptTestCase(
                id="global_003",
                category=TestCategory.GLOBAL_COMMANDS,
                description="Go back command",
                system_prompt="",
                user_input="Wait, go back",
                context={},
                expected_outputs=["GO_BACK"],
                expected_intent="GO_BACK",
                tags=["global", "go_back"]
            ),
            PromptTestCase(
                id="global_004",
                category=TestCategory.GLOBAL_COMMANDS,
                description="Help command",
                system_prompt="",
                user_input="I need help",
                context={},
                expected_outputs=["HELP"],
                expected_intent="HELP",
                tags=["global", "help"]
            ),
            PromptTestCase(
                id="global_005",
                category=TestCategory.GLOBAL_COMMANDS,
                description="Not a global command",
                system_prompt="",
                user_input="I'll repeat my order: 2 California rolls",
                context={},
                expected_outputs=["NONE", ""],
                expected_intent=None,
                tags=["global", "false_positive"]
            )
        ]


def get_all_test_cases() -> List[PromptTestCase]:
    """Get all test cases across all categories."""
    all_cases = []
    all_cases.extend(IntentDetectionTestCases.get_test_cases())
    all_cases.extend(AgentResponseTestCases.get_test_cases())
    all_cases.extend(FunctionCallingTestCases.get_test_cases())
    all_cases.extend(DisambiguationTestCases.get_test_cases())
    all_cases.extend(GlobalCommandTestCases.get_test_cases())
    return all_cases


def get_test_cases_by_category(category: TestCategory) -> List[PromptTestCase]:
    """Get test cases for a specific category."""
    all_cases = get_all_test_cases()
    return [case for case in all_cases if case.category == category]


def get_test_cases_by_tags(tags: List[str]) -> List[PromptTestCase]:
    """Get test cases matching any of the specified tags."""
    all_cases = get_all_test_cases()
    return [
        case for case in all_cases 
        if any(tag in case.tags for tag in tags)
    ]