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



