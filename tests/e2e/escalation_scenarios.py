"""
Help and Escalation E2E scenarios for RedBarSushiAI.

This module contains comprehensive scenarios for testing help requests,
human escalation, and various support paths.
"""

from typing import List
from tests.e2e.conversation_scenarios import ConversationScenario, ConversationTurn, ScenarioType
from tests.e2e.test_helpers import ResponseAssertions


class HelpEscalationScenarios:
    """Scenarios for help requests and human escalation."""
    
    @staticmethod
    def immediate_help_request() -> ConversationScenario:
        """Customer requests help immediately."""
        return ConversationScenario(
            id="help_001",
            name="Immediate Help Request",
            description="Customer asks for help at the beginning of call",
            scenario_type=ScenarioType.ERROR_RECOVERY,
            turns=[
                ConversationTurn(
                    speaker="system",
                    message="",
                    expected_state="GREETING",
                    expected_agent="frontline"
                ),
                ConversationTurn(
                    speaker="user",
                    message="I need help",
                    validation_function=lambda resp: any([
                        "help" in resp.lower(),
                        "assist" in resp.lower(),
                        "what can i" in resp.lower(),
                        "happy to help" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="What can you help me with?",
                    validation_function=lambda resp: any([
                        "order" in resp.lower(),
                        "menu" in resp.lower(),
                        "delivery" in resp.lower(),
                        "pickup" in resp.lower(),
                        "help you with" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="How does ordering work?",
                    validation_function=lambda resp: all([
                        any(word in resp.lower() for word in ["tell", "ask", "name", "order"]),
                        len(resp) > 50  # Should be a helpful explanation
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="OK, my name is Susan, I'll try ordering",
                    expected_state="ORDERING",
                    expected_context={"customer_name": "Susan"}
                ),
                ConversationTurn(
                    speaker="user",
                    message="One California roll please",
                    expected_context=lambda ctx: len(ctx.get("cart", [])) == 1
                )
            ],
            expected_outcome={
                "help_provided": True,
                "proceeded_to_order": True,
                "help_type": "ordering_instructions"
            },
            tags=["help", "instruction", "recovery"]
        )
    
    @staticmethod
    def manager_escalation() -> ConversationScenario:
        """Customer explicitly requests to speak to a manager."""
        return ConversationScenario(
            id="escalation_001",
            name="Manager Escalation Request",
            description="Customer wants to speak to a human manager",
            scenario_type=ScenarioType.ERROR_RECOVERY,
            turns=[
                ConversationTurn(
                    speaker="system",
                    message="",
                    expected_state="GREETING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Hi, I'm Karen",
                    expected_state="MAIN_MENU",
                    expected_context={"customer_name": "Karen"}
                ),
                ConversationTurn(
                    speaker="user",
                    message="I have a complaint about my last order",
                    validation_function=lambda resp: any([
                        "sorry" in resp.lower(),
                        "help" in resp.lower(),
                        "assist" in resp.lower(),
                        "understand" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="I want to speak to a manager",
                    expected_state="ESCALATION",
                    expected_agent="escalation",
                    validation_function=lambda resp: any([
                        "transfer" in resp.lower(),
                        "connect" in resp.lower(),
                        "manager" in resp.lower(),
                        "someone will" in resp.lower(),
                        "representative" in resp.lower(),
                        "human" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="Yes, please connect me",
                    validation_function=lambda resp: any([
                        "transfer" in resp.lower(),
                        "moment" in resp.lower(),
                        "shortly" in resp.lower(),
                        "hold" in resp.lower()
                    ]),
                    expected_context=lambda ctx: ctx.get("escalation_requested") == True
                )
            ],
            expected_outcome={
                "escalation_completed": True,
                "escalation_reason": "manager_request",
                "reached_terminal_state": True
            },
            tags=["escalation", "manager", "complaint"]
        )
    
    @staticmethod
    def escalation_then_continue() -> ConversationScenario:
        """Customer requests escalation but then decides to continue."""
        return ConversationScenario(
            id="escalation_002",
            name="Escalation Request Then Continue",
            description="Customer changes mind about human escalation",
            scenario_type=ScenarioType.ERROR_RECOVERY,
            turns=[
                ConversationTurn(
                    speaker="system",
                    message="",
                    expected_state="GREETING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Hello, I'm David",
                    expected_state="MAIN_MENU"
                ),
                ConversationTurn(
                    speaker="user",
                    message="I need to place a complicated order",
                    expected_state="ORDERING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Actually, can I speak to a person?",
                    validation_function=lambda resp: any([
                        "help" in resp.lower(),
                        "transfer" in resp.lower(),
                        "what" in resp.lower() and "help" in resp.lower(),
                        "assist" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="Never mind, I'll try ordering with you",
                    expected_state="ORDERING",
                    validation_function=lambda resp: any([
                        "help" in resp.lower(),
                        "order" in resp.lower(),
                        "what would you" in resp.lower(),
                        "ready" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="Two salmon rolls and one spicy tuna",
                    expected_context=lambda ctx: len(ctx.get("cart", [])) >= 2,
                    validation_function=lambda resp: all([
                        "salmon" in resp.lower(),
                        "spicy tuna" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="That's all",
                    expected_state="VALIDATION"
                )
            ],
            expected_outcome={
                "escalation_requested": True,
                "escalation_cancelled": True,
                "order_completed": True
            },
            tags=["escalation", "cancelled", "recovery"]
        )
    
    @staticmethod
    def help_with_menu_allergies() -> ConversationScenario:
        """Customer needs help with allergies and dietary restrictions."""
        return ConversationScenario(
            id="help_002",
            name="Help with Allergies",
            description="Customer needs detailed help about ingredients",
            scenario_type=ScenarioType.HAPPY_PATH,
            turns=[
                ConversationTurn(
                    speaker="system",
                    message="",
                    expected_state="GREETING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Hi, I need help with allergies",
                    validation_function=lambda resp: any([
                        "help" in resp.lower(),
                        "allerg" in resp.lower(),
                        "assist" in resp.lower(),
                        "dietary" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="I'm Maria and I'm allergic to shellfish",
                    expected_state="MAIN_MENU",
                    expected_context={"customer_name": "Maria"},
                    validation_function=lambda resp: any([
                        "shellfish" in resp.lower(),
                        "avoid" in resp.lower(),
                        "options" in resp.lower(),
                        "safe" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="What rolls are safe for me?",
                    expected_agent="menu",
                    validation_function=lambda resp: all([
                        len(resp) > 100,  # Should list multiple options
                        any(word in resp.lower() for word in ["california", "vegetable", "cucumber"]),
                        "shellfish" not in resp.lower() or "no shellfish" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="Great, I'll have the vegetable roll",
                    expected_state="ORDERING",
                    expected_context=lambda ctx: (
                        len(ctx.get("cart", [])) == 1 and
                        "vegetable" in ctx["cart"][0].get("name", "").lower()
                    )
                ),
                ConversationTurn(
                    speaker="user",
                    message="Can you confirm there's no cross-contamination?",
                    validation_function=lambda resp: any([
                        "separate" in resp.lower(),
                        "careful" in resp.lower(),
                        "kitchen" in resp.lower(),
                        "precaution" in resp.lower(),
                        "safe" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="Thank you, that's all I need",
                    expected_state="VALIDATION"
                )
            ],
            expected_outcome={
                "help_provided": True,
                "help_type": "allergy_assistance",
                "safe_order_placed": True,
                "dietary_restriction": "shellfish_allergy"
            },
            tags=["help", "allergies", "dietary", "safety"]
        )
    
    @staticmethod
    def frustrated_customer_escalation() -> ConversationScenario:
        """Customer becomes frustrated and needs human help."""
        return ConversationScenario(
            id="escalation_003",
            name="Frustrated Customer Escalation",
            description="Customer frustration triggers escalation need",
            scenario_type=ScenarioType.ERROR_RECOVERY,
            turns=[
                ConversationTurn(
                    speaker="system",
                    message="",
                    expected_state="GREETING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Hello",
                    expected_state="MAIN_MENU"
                ),
                ConversationTurn(
                    speaker="user",
                    message="I want... uh... the thing with rice",
                    validation_function=lambda resp: any([
                        "which" in resp.lower(),
                        "what" in resp.lower(),
                        "help" in resp.lower(),
                        "describe" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="I don't know what it's called!",
                    validation_function=lambda resp: any([
                        "help" in resp.lower(),
                        "describe" in resp.lower(),
                        "ask" in resp.lower(),
                        "worry" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="This is too difficult, I need a person!",
                    expected_agent="escalation",
                    validation_function=lambda resp: any([
                        "understand" in resp.lower(),
                        "transfer" in resp.lower(),
                        "help" in resp.lower(),
                        "connect" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="Yes, transfer me please",
                    expected_state="ESCALATION",
                    expected_context=lambda ctx: (
                        ctx.get("escalation_reason") in ["customer_frustration", "difficulty", "request"]
                    )
                )
            ],
            expected_outcome={
                "escalation_completed": True,
                "escalation_trigger": "customer_frustration",
                "attempted_help_first": True
            },
            tags=["escalation", "frustration", "difficulty"]
        )
    
    @staticmethod
    def technical_help_request() -> ConversationScenario:
        """Customer needs technical help with the system."""
        return ConversationScenario(
            id="help_003",
            name="Technical Help Request",
            description="Customer has technical questions about ordering",
            scenario_type=ScenarioType.ERROR_RECOVERY,
            turns=[
                ConversationTurn(
                    speaker="system",
                    message="",
                    expected_state="GREETING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Hi, I'm having trouble with this system",
                    validation_function=lambda resp: any([
                        "help" in resp.lower(),
                        "trouble" in resp.lower(),
                        "assist" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="I'm Tom, how do I remove items from my order?",
                    expected_state="MAIN_MENU",
                    expected_context={"customer_name": "Tom"},
                    validation_function=lambda resp: any([
                        "remove" in resp.lower(),
                        "delete" in resp.lower(),
                        "change" in resp.lower(),
                        "tell me" in resp.lower()
                    ])
                ),
                ConversationTurn(
                    speaker="user",
                    message="OK let me try. I want to order",
                    expected_state="ORDERING"
                ),
                ConversationTurn(
                    speaker="user",
                    message="Add three California rolls",
                    expected_context=lambda ctx: (
                        len(ctx.get("cart", [])) == 1 and
                        ctx["cart"][0].get("quantity") == 3
                    )
                ),
                ConversationTurn(
                    speaker="user",
                    message="Actually remove one California roll",
                    validation_function=lambda resp: any([
                        "remove" in resp.lower(),
                        "now have 2" in resp.lower(),
                        "changed" in resp.lower(),
                        "updated" in resp.lower()
                    ]),
                    expected_context=lambda ctx: (
                        ctx["cart"][0].get("quantity") == 2
                    )
                ),
                ConversationTurn(
                    speaker="user",
                    message="Perfect! That worked. I'm done",
                    expected_state="VALIDATION"
                )
            ],
            expected_outcome={
                "help_provided": True,
                "help_type": "technical_guidance",
                "issue_resolved": True,
                "learned_feature": "item_removal"
            },
            tags=["help", "technical", "guidance", "learning"]
        )


def get_help_escalation_scenarios() -> List[ConversationScenario]:
    """Get all help and escalation scenarios."""
    return [
        HelpEscalationScenarios.immediate_help_request(),
        HelpEscalationScenarios.manager_escalation(),
        HelpEscalationScenarios.escalation_then_continue(),
        HelpEscalationScenarios.help_with_menu_allergies(),
        HelpEscalationScenarios.frustrated_customer_escalation(),
        HelpEscalationScenarios.technical_help_request()
    ]