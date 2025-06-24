"""
OpenAI mocking fixtures for tests.

This module provides comprehensive mocks for OpenAI API calls to make tests
deterministic, fast, and free from external dependencies.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import json
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


# Default responses for different types of OpenAI calls
DEFAULT_CHAT_RESPONSE = {
    "id": "test-chat-completion",
    "object": "chat.completion",
    "created": 1234567890,
    "model": "gpt-4",
    "choices": [{
        "index": 0,
        "message": {
            "role": "assistant",
            "content": "I understand. How can I help you today?"
        },
        "finish_reason": "stop"
    }],
    "usage": {
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "total_tokens": 30
    }
}

INTENT_DETECTION_RESPONSE = {
    "id": "test-intent-detection",
    "object": "chat.completion",
    "created": 1234567890,
    "model": "gpt-4",
    "choices": [{
        "index": 0,
        "message": {
            "role": "assistant",
            "content": json.dumps({
                "intent": "USER_PROVIDES_NAME",
                "confidence": 0.95,
                "entities": {"name": "John"}
            })
        },
        "finish_reason": "stop"
    }]
}

MENU_MATCHING_RESPONSE = {
    "id": "test-menu-matching",
    "object": "chat.completion",
    "created": 1234567890,
    "model": "gpt-4",
    "choices": [{
        "index": 0,
        "message": {
            "role": "assistant",
            "content": json.dumps({
                "matches": [{
                    "plu": "ROLL_001",
                    "name": "California Roll",
                    "confidence": 0.98,
                    "quantity": 1
                }]
            })
        },
        "finish_reason": "stop"
    }]
}


@pytest.fixture(autouse=True)
def mock_openai_globally():
    """
    Globally mock OpenAI for all tests to prevent actual API calls.
    This is an autouse fixture that patches OpenAI at the source.
    """
    # Patch at multiple levels to ensure coverage
    patches = []
    
    # Patch the openai client initialization
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=MagicMock(**DEFAULT_CHAT_RESPONSE))
    mock_client.audio.speech.create = AsyncMock(return_value=MagicMock(content=b"mock audio data"))
    
    # Patch common import patterns
    import_patterns = [
        'app.utils.openai_pool.get_openai_client',
        'app.utils.openai_utils.get_openai_client',
        'app.services.openai_service.client',
        'app.utils.intent_detector_async.AsyncOpenAI',
        'app.agents.ai_mixin.AsyncOpenAI',
        'openai.AsyncOpenAI',
        'openai.OpenAI',
    ]
    
    for pattern in import_patterns:
        try:
            if 'get_openai_client' in pattern:
                p = patch(pattern, return_value=mock_client)
            else:
                p = patch(pattern, return_value=mock_client)
            patches.append(p)
            p.start()
        except Exception as e:
            logger.debug(f"Could not patch {pattern}: {e}")
    
    yield mock_client
    
    # Stop all patches
    for p in patches:
        try:
            p.stop()
        except Exception:
            pass


@pytest.fixture
def mock_openai_chat():
    """
    Fixture for mocking OpenAI chat completions with customizable responses.
    """
    def _mock_chat(response_content: str = "Mock response", **kwargs):
        """Create a mock chat completion with custom content."""
        response = DEFAULT_CHAT_RESPONSE.copy()
        response["choices"][0]["message"]["content"] = response_content
        # Update any additional fields
        for key, value in kwargs.items():
            if key in response:
                response[key] = value
        return MagicMock(**response)
    
    return _mock_chat


@pytest.fixture
def mock_openai_intent_detector():
    """
    Mock specifically for intent detection calls.
    """
    async def _mock_intent(intent: str = "USER_PROVIDES_NAME", confidence: float = 0.95, **entities):
        """Create a mock intent detection response."""
        content = {
            "intent": intent,
            "confidence": confidence,
            "entities": entities
        }
        response = INTENT_DETECTION_RESPONSE.copy()
        response["choices"][0]["message"]["content"] = json.dumps(content)
        return MagicMock(**response)
    
    return _mock_intent


@pytest.fixture
def mock_openai_menu_matcher():
    """
    Mock specifically for menu matching calls.
    """
    async def _mock_menu_match(items: List[Dict[str, Any]]):
        """Create a mock menu matching response."""
        content = {"matches": items}
        response = MENU_MATCHING_RESPONSE.copy()
        response["choices"][0]["message"]["content"] = json.dumps(content)
        return MagicMock(**response)
    
    return _mock_menu_match


@pytest_asyncio.fixture
async def mock_openai_streaming():
    """
    Mock for streaming OpenAI responses.
    """
    async def _mock_stream(chunks: List[str]):
        """Create a mock streaming response."""
        for i, chunk in enumerate(chunks):
            mock_chunk = MagicMock()
            mock_chunk.choices = [MagicMock()]
            mock_chunk.choices[0].delta = MagicMock()
            mock_chunk.choices[0].delta.content = chunk
            mock_chunk.choices[0].finish_reason = "stop" if i == len(chunks) - 1 else None
            yield mock_chunk
    
    return _mock_stream


@pytest.fixture
def mock_openai_with_function_calls():
    """
    Mock OpenAI responses that include function calls.
    """
    def _mock_function_call(function_name: str, arguments: Dict[str, Any]):
        """Create a mock response with function call."""
        response = DEFAULT_CHAT_RESPONSE.copy()
        response["choices"][0]["message"]["function_call"] = {
            "name": function_name,
            "arguments": json.dumps(arguments)
        }
        response["choices"][0]["message"]["content"] = None
        response["choices"][0]["finish_reason"] = "function_call"
        return MagicMock(**response)
    
    return _mock_function_call


# Specific mocks for common patterns in the codebase
@pytest.fixture
def mock_intent_detector_service():
    """
    Mock the entire intent detector service.
    """
    with patch('app.utils.intent_detector_async.intent_detector') as mock:
        mock.detect_intent = AsyncMock(return_value="USER_PROVIDES_NAME")
        mock.detect_global_command = AsyncMock(return_value=(None, 0.0))
        yield mock


@pytest.fixture
def mock_ai_mixin():
    """
    Mock the AI mixin functionality used by agents.
    """
    with patch('app.agents.ai_mixin.AIMixin.process_with_ai') as mock:
        mock.return_value = {
            "content": "Mock AI response",
            "usage": {"total_tokens": 100}
        }
        yield mock


def configure_openai_mock_for_test(mock_client, test_scenario: str):
    """
    Configure OpenAI mock for specific test scenarios.
    
    Args:
        mock_client: The mock OpenAI client
        test_scenario: Name of the test scenario to configure for
    """
    scenarios = {
        "greeting": {
            "content": "Hello! Welcome to Red Bar Sushi. What's your name?"
        },
        "menu_query": {
            "content": "We have California Rolls, Tuna Sashimi, and Salmon Rolls available today."
        },
        "order_confirmation": {
            "content": "I've added 2 California Rolls to your order. Anything else?"
        },
        "error": {
            "side_effect": Exception("OpenAI API Error")
        }
    }
    
    scenario_config = scenarios.get(test_scenario, {"content": "Default mock response"})
    
    if "side_effect" in scenario_config:
        mock_client.chat.completions.create.side_effect = scenario_config["side_effect"]
    else:
        response = DEFAULT_CHAT_RESPONSE.copy()
        response["choices"][0]["message"]["content"] = scenario_config["content"]
        mock_client.chat.completions.create.return_value = MagicMock(**response)