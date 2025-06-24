"""
E2E Conversation Flow Tests for RedBarSushiAI.

This module provides end-to-end testing capabilities for validating
complete conversation flows through the system.
"""

from .conversation_scenarios import (
    ConversationScenario,
    ConversationTurn,
    ScenarioType,
    get_all_scenarios,
    get_scenarios_by_type,
    get_scenarios_by_tags
)

from .e2e_test_runner import (
    E2ETestRunner,
    ScenarioResult,
    TurnResult,
    run_e2e_tests
)

from .websocket_mock_server import (
    MockWebSocketServer,
    MockConversationHandler,
    start_mock_server
)

__all__ = [
    # Scenarios
    'ConversationScenario',
    'ConversationTurn',
    'ScenarioType',
    'get_all_scenarios',
    'get_scenarios_by_type',
    'get_scenarios_by_tags',
    
    # Runner
    'E2ETestRunner',
    'ScenarioResult',
    'TurnResult',
    'run_e2e_tests',
    
    # Mock Server
    'MockWebSocketServer',
    'MockConversationHandler',
    'start_mock_server'
]
