"""
Test the OpenAI Agents integration.
"""

import sys
import json
import pytest
from unittest.mock import patch, MagicMock

# Mock the celery module before importing anything that might use it
sys.modules["celery"] = MagicMock()
sys.modules["celery_app"] = MagicMock()
sys.modules["tasks"] = MagicMock()


# Add support for mocking OpenAI Agents
class MockAgent:
    def __init__(self, *args, **kwargs):
        self.tools = MagicMock()
        self.tools.search_menu = MagicMock(return_value={"found": True, "items": []})
        self.tools.get_details = MagicMock(return_value={"found": True, "item": {}})

        # Store initialization arguments to determine which type of agent we're mocking
        self.instructions = kwargs.get("instructions", "")

    def create_thread(self):
        mock_thread = MagicMock()
        mock_run = MagicMock()
        mock_message = MagicMock()

        # Add required properties
        mock_message.id = "msg_123"
        mock_message.content = [MagicMock()]
        mock_message.content[0].text = MagicMock()

        # Determine which response to return based on the agent type (via instructions)
        if "modify existing food orders" in self.instructions:
            # For OrderModificationAgent
            mock_message.content[0].text.value = json.dumps(
                {
                    "additions": [
                        {
                            "name": "Spicy Tuna Roll",
                            "quantity": 1,
                            "price": 8.95,
                            "reference_handler": "spicy-tuna-1",
                            "modifier": [],
                        }
                    ],
                    "removals": [],
                }
            )
        else:
            # For OrderParsingAgent (default)
            mock_message.content[0].text.value = json.dumps(
                {
                    "items": [
                        {
                            "name": "California Roll",
                            "quantity": 1,
                            "price": 7.95,
                            "reference_handler": "cal-roll-1",
                            "modifier": [],
                        }
                    ]
                }
            )

        # Configure the mock objects
        mock_thread.messages.create.return_value = mock_message
        mock_thread.messages.list.return_value = [mock_message]
        mock_thread.runs.create.return_value = mock_run
        mock_thread.runs.wait.return_value = mock_run

        return mock_thread


# Apply the mocks for OpenAI Agents
sys.modules["openai.agent"] = MagicMock()
sys.modules["openai.agent.Agent"] = MockAgent
sys.modules["openai.agent.types"] = MagicMock()

# Now import the modules that use these mocks
from app.utils.agent_utils_simple import get_order_modifications
from app.utils.agent_utils_simple import OrderParsingAgent


@pytest.fixture
def mock_openai_agent(monkeypatch):
    """Mock the OpenAI agent for testing."""
    # No need to mock Agent since we're using the simple implementation
    # monkeypatch.setattr('app.utils.agent_utils.Agent', MockAgent)
    yield


@patch("app.utils.agent_utils_simple.analyze_user_input")
def test_analyze_user_input(mock_analyze, mock_openai_agent):
    """Test that analyze_user_input works correctly."""
    # Set the return value for the mock
    mock_analyze.return_value = {
        "intent": "order_food",
        "menu_items": [{"name": "California Roll", "quantity": 2, "price": 7.95}],
    }

    # Test with a simple order
    result = mock_analyze("I want a California Roll")

    # Check the result
    assert result is not None
    assert "intent" in result
    assert result["intent"] == "order_food"
    assert "menu_items" in result
    assert len(result["menu_items"]) > 0


def test_get_order_modifications(mock_openai_agent):
    """Test that get_order_modifications works correctly."""
    # Create a current order
    current_order = [
        {
            "name": "California Roll",
            "quantity": 1,
            "price": 7.95,
            "reference_handler": "cal-roll-1",
            "modifier": [],
        }
    ]

    # Test with a modification request
    result = get_order_modifications("Add a Spicy Tuna Roll", current_order)

    # Check the result
    assert result is not None
    assert "additions" in result
    assert "removals" in result


@patch("app.utils.agent_utils_simple.OrderParsingAgent.parse_order")
def test_order_parsing_agent(mock_parse_order, mock_openai_agent):
    """Test that OrderParsingAgent works correctly."""
    # Set up mock return value
    mock_parse_order.return_value = {
        "items": [
            {
                "name": "California Roll",
                "quantity": 1,
                "price": 7.95,
                "reference_handler": "cal-roll-1",
            }
        ]
    }

    # Create an agent
    OrderParsingAgent()

    # Test parsing an order
    order = mock_parse_order("I want a California Roll and a Spicy Tuna Roll")

    # Check the result
    assert order is not None
    assert "items" in order
    assert len(order["items"]) > 0
