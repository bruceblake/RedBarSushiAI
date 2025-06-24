"""
Comprehensive test fixtures for RedBarSushi testing.
Provides consistent test data across all test suites.
"""
import pytest
from datetime import datetime
from typing import Dict, List, Any


@pytest.fixture
def sample_menu_items():
    """Sample menu items for testing."""
    return [
        {
            "plu": "SUSHI001",
            "name": "California Roll",
            "price": 12.95,
            "category": "Sushi Rolls",
            "description": "Crab, avocado, cucumber",
            "available": True,
            "modifierGroups": ["MOD_GROUP_001"]
        },
        {
            "plu": "SUSHI002",
            "name": "Spicy Tuna Roll",
            "price": 14.95,
            "category": "Sushi Rolls",
            "description": "Spicy tuna, cucumber",
            "available": True,
            "modifierGroups": ["MOD_GROUP_001"]
        },
        {
            "plu": "SUSHI003",
            "name": "Salmon Roll",
            "price": 13.95,
            "category": "Sushi Rolls",
            "description": "Fresh salmon",
            "available": True,
            "modifierGroups": ["MOD_GROUP_001"]
        },
        {
            "plu": "APP001",
            "name": "Edamame",
            "price": 5.95,
            "category": "Appetizers",
            "description": "Steamed soybeans",
            "available": True,
            "modifierGroups": []
        },
        {
            "plu": "APP002",
            "name": "Miso Soup",
            "price": 3.95,
            "category": "Appetizers",
            "description": "Traditional soybean soup",
            "available": True,
            "modifierGroups": []
        },
        {
            "plu": "VEGGIE001",
            "name": "Avocado Roll",
            "price": 8.95,
            "category": "Vegetarian",
            "description": "Fresh avocado",
            "available": True,
            "modifierGroups": ["MOD_GROUP_001"]
        },
        {
            "plu": "VEGGIE002",
            "name": "Cucumber Roll",
            "price": 7.95,
            "category": "Vegetarian",
            "description": "Crisp cucumber",
            "available": True,
            "modifierGroups": ["MOD_GROUP_001"]
        }
    ]


@pytest.fixture
def sample_modifiers():
    """Sample modifiers for testing."""
    return {
        "MOD_GROUP_001": {
            "id": "MOD_GROUP_001",
            "name": "Roll Options",
            "minAllowed": 0,
            "maxAllowed": 3,
            "modifierIds": ["MOD001", "MOD002", "MOD003"]
        },
        "modifiers": [
            {
                "id": "MOD001",
                "plu": "MOD001",
                "name": "Extra Wasabi",
                "price": 0,
                "available": True
            },
            {
                "id": "MOD002",
                "plu": "MOD002",
                "name": "No Wasabi",
                "price": 0,
                "available": True
            },
            {
                "id": "MOD003",
                "plu": "MOD003",
                "name": "Extra Ginger",
                "price": 0.50,
                "available": True
            }
        ]
    }


@pytest.fixture
def sample_cart_states():
    """Sample cart states for testing."""
    return {
        "empty": {
            "items": [],
            "total_price": 0
        },
        "single_item": {
            "items": [{
                "plu": "SUSHI001",
                "name": "California Roll",
                "price": 12.95,
                "quantity": 1,
                "modifiers": [],
                "special_instructions": None
            }],
            "total_price": 12.95
        },
        "multiple_items": {
            "items": [
                {
                    "plu": "SUSHI001",
                    "name": "California Roll",
                    "price": 12.95,
                    "quantity": 2,
                    "modifiers": [],
                    "special_instructions": None
                },
                {
                    "plu": "SUSHI002",
                    "name": "Spicy Tuna Roll",
                    "price": 14.95,
                    "quantity": 1,
                    "modifiers": [],
                    "special_instructions": None
                },
                {
                    "plu": "APP001",
                    "name": "Edamame",
                    "price": 5.95,
                    "quantity": 1,
                    "modifiers": [],
                    "special_instructions": None
                }
            ],
            "total_price": 46.80
        },
        "with_modifiers": {
            "items": [{
                "plu": "SUSHI001",
                "name": "California Roll",
                "price": 12.95,
                "quantity": 1,
                "modifiers": [
                    {
                        "plu": "MOD003",
                        "name": "Extra Ginger",
                        "quantity": 1,
                        "price_change": 0.50
                    }
                ],
                "special_instructions": "Extra spicy please"
            }],
            "total_price": 13.45
        }
    }


@pytest.fixture
def sample_customer_profiles():
    """Sample customer profiles for testing."""
    return [
        {
            "name": "John Smith",
            "phone": "+15551234567",
            "order_type": "pickup",
            "preferences": {
                "spice_level": "medium",
                "allergies": []
            }
        },
        {
            "name": "Sarah Johnson",
            "phone": "+15559876543",
            "order_type": "delivery",
            "address": "123 Main St, Anytown, CA 12345",
            "preferences": {
                "spice_level": "mild",
                "allergies": ["shellfish"]
            }
        },
        {
            "name": "Michael Chen",
            "phone": "+15555551234",
            "order_type": "pickup",
            "preferences": {
                "spice_level": "hot",
                "allergies": [],
                "vegetarian": True
            }
        }
    ]


@pytest.fixture
def sample_conversation_transcripts():
    """Sample conversation transcripts for testing."""
    return {
        "successful_order": [
            ("", "Hello and welcome to Red Bar Sushi! I'm Sarah, and I'm here to help you today. May I have your name, please?"),
            ("My name is John", "Nice to meet you, John! How can I help you today?"),
            ("I'd like to place an order", "What would you like to order?"),
            ("Two California rolls and one spicy tuna", "I've added 2 California Rolls and 1 Spicy Tuna Roll to your cart. Your total is $40.85. Would you like anything else?"),
            ("That's all", "Let me confirm your order: 2 California Rolls, 1 Spicy Tuna Roll. Your total is $40.85. Is this correct?"),
            ("Yes", "Great! Your order has been submitted. It will be ready in about 20 minutes."),
        ],
        "menu_inquiry": [
            ("", "Hello and welcome to Red Bar Sushi! I'm Sarah, and I'm here to help you today. May I have your name, please?"),
            ("Hi, I'm Lisa", "Nice to meet you, Lisa! How can I help you today?"),
            ("What vegetarian options do you have?", "We have several vegetarian options including Avocado Roll, Cucumber Roll, and Vegetable Tempura Roll."),
            ("I'll have two avocado rolls", "I've added 2 Avocado Rolls to your cart. Your total is $17.90. Would you like anything else?"),
        ],
        "error_recovery": [
            ("", "Hello and welcome to Red Bar Sushi! I'm Sarah, and I'm here to help you today. May I have your name, please?"),
            ("Umm", "I'm sorry, I didn't catch your name. Could you please tell me your name?"),
            ("Robert", "Nice to meet you, Robert! How can I help you today?"),
            ("I want the dragon roll", "I'm sorry, but I don't see a Dragon Roll on our menu. Would you like to try our California Roll or Spicy Tuna Roll instead?"),
        ]
    }


@pytest.fixture
def sample_fsm_contexts():
    """Sample FSM contexts for different states."""
    return {
        "greeting": {
            "call_sid": "CAtest123",
            "first_interaction": True,
            "greeting_sent": False
        },
        "main_menu": {
            "call_sid": "CAtest123",
            "customer_name": "John Smith",
            "greeting_sent": True,
            "main_menu_response": {"text": "How can I help you today?"}
        },
        "ordering": {
            "call_sid": "CAtest123",
            "customer_name": "John Smith",
            "cart": {
                "items": [{"name": "California Roll", "quantity": 1, "price": 12.95}],
                "total_price": 12.95
            }
        },
        "confirmation": {
            "call_sid": "CAtest123",
            "customer_name": "John Smith",
            "cart": {
                "items": [
                    {"name": "California Roll", "quantity": 2, "price": 12.95},
                    {"name": "Spicy Tuna Roll", "quantity": 1, "price": 14.95}
                ],
                "total_price": 40.85
            },
            "order_type": "pickup"
        }
    }


@pytest.fixture
def mock_api_responses():
    """Mock API responses for testing."""
    return {
        "openai_intent": {
            "choices": [{
                "message": {
                    "content": "USER_PROVIDES_NAME"
                }
            }]
        },
        "openai_chat": {
            "choices": [{
                "message": {
                    "content": "Nice to meet you! How can I help you today?",
                    "tool_calls": []
                }
            }]
        },
        "twilio_twiml": '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <ConversationRelay url="wss://example.com/api/conversation-relay" />
</Response>''',
        "deliverect_order": {
            "orderId": "DEL123456",
            "status": "accepted",
            "estimatedTime": 20
        }
    }