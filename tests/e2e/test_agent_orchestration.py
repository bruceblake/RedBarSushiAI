"""
End-to-end tests for the Agent Orchestration system.
These tests verify the functionality of the advanced agentic patterns including
sequential handoffs, background escalation, and state-machine slot filling.
"""

import json
import pytest
import time
import re
import os
import logging
import sys
import copy
import uuid
from unittest import mock

# Set up logging
log_format = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(
    level=logging.DEBUG,
    format=log_format,
    handlers=[
        logging.FileHandler("e2e_agent_orchestration_test_debug.log", mode="w"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("e2e_agent_orchestration_tests")

# Import the agent orchestration components
from app.utils.agent_orchestration_async import (
    AgentGraph, 
    FSMOrchestrator, 
    FSMPromptTemplate, 
    SlotStore, 
    FSMState,
    ModelEscalator
)

@pytest.fixture
def slot_store():
    """Create a SlotStore instance for testing."""
    # Use a memory-only SlotStore for testing
    return SlotStore()

@pytest.fixture
def fsm_orchestrator(slot_store):
    """Create an FSMOrchestrator instance for testing."""
    return FSMOrchestrator(slot_store=slot_store)

@pytest.fixture
def agent_graph():
    """Create an AgentGraph instance for testing."""
    graph = AgentGraph()
    
    # Add test nodes
    graph.add_node(
        name="TestFrontline",
        model="gpt-4.1-mini",
        description="Test frontline agent",
        confidence_threshold=0.7
    )
    
    graph.add_node(
        name="TestMenu",
        model="gpt-4.1-mini",
        description="Test menu agent",
        confidence_threshold=0.7
    )
    
    graph.add_node(
        name="TestEscalation",
        model="gpt-4o-mini",
        description="Test escalation agent",
        confidence_threshold=0.9
    )
    
    # Add transitions
    graph.add_transition(
        from_agent="TestFrontline", 
        to_agent="TestMenu",
        condition={
            "type": "tool_result",
            "tool": "intent_classifier",
            "field": "intent",
            "value": "menu_inquiry"
        },
        description="Route to Menu Agent for menu questions"
    )
    
    graph.add_transition(
        from_agent="TestFrontline", 
        to_agent="TestEscalation",
        condition={
            "type": "confidence",
            "value": 0.6,
            "comparison": "lt"
        },
        description="Escalate when confidence is low"
    )
    
    return graph

@pytest.fixture
def model_escalator():
    """Create a ModelEscalator instance for testing."""
    return ModelEscalator()

@pytest.mark.unit
def test_agent_graph_creation(agent_graph):
    """Test that an AgentGraph can be created with nodes and transitions."""
    # Check that the nodes were added
    assert "TestFrontline" in agent_graph.nodes
    assert "TestMenu" in agent_graph.nodes
    assert "TestEscalation" in agent_graph.nodes
    
    # Check that the transitions were added
    assert len(agent_graph.transitions) == 2
    
    # Check transition details
    frontline_to_menu = None
    frontline_to_escalation = None
    
    for transition in agent_graph.transitions:
        if transition['from_agent'] == "TestFrontline" and transition['to_agent'] == "TestMenu":
            frontline_to_menu = transition
        elif transition['from_agent'] == "TestFrontline" and transition['to_agent'] == "TestEscalation":
            frontline_to_escalation = transition
    
    assert frontline_to_menu is not None
    assert frontline_to_escalation is not None
    
    assert frontline_to_menu['condition']['type'] == "tool_result"
    assert frontline_to_menu['condition']['tool'] == "intent_classifier"
    
    assert frontline_to_escalation['condition']['type'] == "confidence"
    assert frontline_to_escalation['condition']['value'] == 0.6
    
    logger.info("Agent graph creation test passed")

@pytest.mark.unit
def test_agent_graph_next_agent(agent_graph):
    """Test that the agent graph correctly determines the next agent."""
    # Create a test state with a menu inquiry intent
    menu_state = {
        "tool_results": {
            "intent_classifier": {
                "intent": "menu_inquiry",
                "confidence": 0.85
            }
        }
    }
    
    # Test transition to menu agent
    next_agent = agent_graph.get_next_agent("TestFrontline", menu_state)
    assert next_agent == "TestMenu"
    
    # Create a test state with low confidence
    low_confidence_state = {
        "last_confidence": 0.5,
        "tool_results": {
            "intent_classifier": {
                "intent": "general",
                "confidence": 0.5
            }
        }
    }
    
    # Test transition to escalation agent
    next_agent = agent_graph.get_next_agent("TestFrontline", low_confidence_state)
    assert next_agent == "TestEscalation"
    
    # Create a test state with high confidence but no transition condition
    high_confidence_state = {
        "last_confidence": 0.9,
        "tool_results": {
            "intent_classifier": {
                "intent": "general",
                "confidence": 0.9
            }
        }
    }
    
    # Test no transition happens
    next_agent = agent_graph.get_next_agent("TestFrontline", high_confidence_state)
    assert next_agent is None
    
    logger.info("Agent graph next_agent determination test passed")

@pytest.mark.unit
def test_slot_store(slot_store):
    """Test the slot store functionality."""
    # Generate a test call SID
    call_sid = str(uuid.uuid4())
    
    # Test setting and getting a slot
    slot_store.set_slot(call_sid, "test_slot", "test_value")
    value = slot_store.get_slot(call_sid, "test_slot")
    assert value == "test_value"
    
    # Test setting and getting a complex value
    complex_value = {"name": "John", "age": 30, "items": ["item1", "item2"]}
    slot_store.set_slot(call_sid, "complex_slot", complex_value)
    retrieved_value = slot_store.get_slot(call_sid, "complex_slot")
    assert retrieved_value == complex_value
    
    # Test getting all slots
    all_slots = slot_store.get_all_slots(call_sid)
    assert "test_slot" in all_slots
    assert "complex_slot" in all_slots
    assert all_slots["test_slot"] == "test_value"
    assert all_slots["complex_slot"] == complex_value
    
    # Test clearing slots
    slot_store.clear_slots(call_sid)
    all_slots = slot_store.get_all_slots(call_sid)
    assert len(all_slots) == 0
    
    logger.info("SlotStore test passed")

@pytest.mark.unit
def test_fsm_orchestrator_basic(fsm_orchestrator):
    """Test basic FSM orchestrator functionality."""
    # Generate a test call SID
    call_sid = str(uuid.uuid4())
    
    # Check initial state
    current_state = fsm_orchestrator.get_current_state(call_sid)
    assert current_state == FSMState.INITIAL
    
    # Test state transition
    fsm_orchestrator.set_current_state(call_sid, FSMState.ASK_NAME)
    current_state = fsm_orchestrator.get_current_state(call_sid)
    assert current_state == FSMState.ASK_NAME
    
    # Test retry count
    retry_count = fsm_orchestrator.get_retry_count(call_sid, FSMState.ASK_NAME)
    assert retry_count == 1  # Should be 1 because set_current_state increments it
    
    # Set again to increment retry counter
    fsm_orchestrator.set_current_state(call_sid, FSMState.ASK_NAME)
    retry_count = fsm_orchestrator.get_retry_count(call_sid, FSMState.ASK_NAME)
    assert retry_count == 2
    
    logger.info("FSM orchestrator basic test passed")

@pytest.mark.unit
def test_fsm_orchestrator_processing(fsm_orchestrator):
    """Test FSM orchestrator processing of user input."""
    # Generate a test call SID
    call_sid = str(uuid.uuid4())
    
    # Set initial state
    fsm_orchestrator.set_current_state(call_sid, FSMState.ASK_NAME)
    
    # Process name input
    result = fsm_orchestrator.process_user_input(call_sid, "John Doe")
    
    # Verify the result
    assert result["state"] == FSMState.CONFIRM_NAME.value
    assert "John Doe" in result["system_prompt"] or "John Doe" in result["user_prompt"]
    
    # Check that slots were set correctly
    slots = fsm_orchestrator.slot_store.get_all_slots(call_sid)
    assert "name_raw" in slots
    assert slots["name_raw"] == "John Doe"
    
    # Confirm the name
    result = fsm_orchestrator.process_user_input(call_sid, "yes")
    
    # Verify the result
    assert result["state"] == FSMState.ASK_PHONE.value
    
    # Check that the name was confirmed
    slots = fsm_orchestrator.slot_store.get_all_slots(call_sid)
    assert "name" in slots
    assert slots["name"] == "John Doe"
    
    logger.info("FSM orchestrator processing test passed")

@pytest.mark.unit
def test_model_escalator(model_escalator):
    """Test model escalator functionality."""
    # Test determination of when to escalate
    assert model_escalator.should_escalate(0.5, "gpt-4.1-mini", False, 0.7) == True
    assert model_escalator.should_escalate(0.8, "gpt-4.1-mini", False, 0.7) == False
    
    # Test for critical operations (which have a higher threshold)
    assert model_escalator.should_escalate(0.7, "gpt-4.1-mini", True, 0.7) == True
    assert model_escalator.should_escalate(0.9, "gpt-4.1-mini", True, 0.7) == False
    
    # Test getting the next escalation model
    assert model_escalator.get_escalation_model("gpt-4.1-mini") == "gpt-4o"
    assert model_escalator.get_escalation_model("gpt-4o") == "gpt-4o-mini"
    
    # Test escalating a request
    original_request = {
        "model": "gpt-4.1-mini",
        "messages": [{"role": "user", "content": "Test message"}]
    }
    
    escalated_request = model_escalator.escalate_request(original_request, "gpt-4.1-mini")
    
    assert escalated_request["model"] == "gpt-4o"
    assert escalated_request["is_escalated"] == True
    assert escalated_request["original_model"] == "gpt-4.1-mini"
    assert escalated_request["messages"] == original_request["messages"]
    
    logger.info("Model escalator test passed")

@pytest.mark.integration
def test_fsm_prompt_templates():
    """Test FSM prompt templates with the actual default templates."""
    # First, create a temporary YAML file with test templates
    import tempfile
    import yaml
    
    # Use a subset of the default templates
    test_templates = {
        "initial": {
            "system": "You are an authentication assistant for testing.",
            "user": "Hello, I need to verify your identity before we proceed."
        },
        "ask_name": {
            "system": "You are an authentication assistant for testing with retry_count {retry_count}.",
            "user": "Please tell me your name, one word at a time."
        }
    }
    
    # Write the test templates to a temporary file
    with tempfile.NamedTemporaryFile('w', suffix='.yaml', delete=False) as f:
        yaml.dump(test_templates, f)
        template_path = f.name
    
    try:
        # Create a prompt template instance with the test file
        templates = FSMPromptTemplate(template_path)
        
        # Test getting a template
        template = templates.get_template("initial")
        assert template["system"] == "You are an authentication assistant for testing."
        assert template["user"] == "Hello, I need to verify your identity before we proceed."
        
        # Test applying a template with slots
        slots = {"retry_count": 2}
        applied = templates.apply_template("ask_name", slots)
        assert "retry_count 2" in applied["system"]
        
        logger.info("FSM prompt templates test passed")
    finally:
        # Clean up temporary file
        try:
            os.unlink(template_path)
        except:
            pass

@pytest.mark.integration
def test_full_orchestration_workflow():
    """Test the full orchestration workflow with all components."""
    # Create instances of all components
    slot_store = SlotStore()
    fsm = FSMOrchestrator(slot_store)
    graph = AgentGraph()
    
    # Add nodes to the graph
    graph.add_node(
        name="Frontline",
        model="gpt-4.1-mini",
        description="Frontline agent"
    )
    
    graph.add_node(
        name="Authentication",
        model="gpt-4.1-mini",
        description="Authentication agent"
    )
    
    graph.add_node(
        name="Menu",
        model="gpt-4.1-mini",
        description="Menu agent"
    )
    
    # Add transitions
    graph.add_transition(
        from_agent="Frontline",
        to_agent="Authentication",
        condition={
            "type": "slot_value",
            "slot": "authenticated",
            "value": False
        }
    )
    
    graph.add_transition(
        from_agent="Authentication",
        to_agent="Frontline",
        condition={
            "type": "slot_value",
            "slot": "authenticated",
            "value": True
        }
    )
    
    graph.add_transition(
        from_agent="Frontline",
        to_agent="Menu",
        condition={
            "type": "tool_result",
            "tool": "intent_classifier",
            "field": "intent",
            "value": "menu_inquiry"
        }
    )
    
    # Generate a test call SID
    call_sid = str(uuid.uuid4())
    
    # Start with non-authenticated state
    slot_store.set_slot(call_sid, "authenticated", False)
    
    # Create a state object
    state = {
        "slots": slot_store.get_all_slots(call_sid)
    }
    
    # Test transition to Authentication agent
    next_agent = graph.get_next_agent("Frontline", state)
    assert next_agent == "Authentication"
    
    logger.info("Transitioning to Authentication agent")
    
    # Simulate FSM processing for authentication
    fsm.set_current_state(call_sid, FSMState.ASK_NAME)
    result = fsm.process_user_input(call_sid, "Jane Smith")
    assert result["state"] == FSMState.CONFIRM_NAME.value
    
    result = fsm.process_user_input(call_sid, "yes")
    assert result["state"] == FSMState.ASK_PHONE.value
    
    result = fsm.process_user_input(call_sid, "555-123-4567")
    assert result["state"] == FSMState.CONFIRM_PHONE.value
    
    result = fsm.process_user_input(call_sid, "yes")
    assert result["state"] == FSMState.AUTHENTICATED.value
    
    # Verify authentication is complete
    slots = slot_store.get_all_slots(call_sid)
    assert slots["authenticated"] == True
    assert slots["name"] == "Jane Smith"
    assert slots["phone"] == "555-123-4567"
    
    # Update state object
    state = {
        "slots": slots
    }
    
    # Test transition back to Frontline agent
    next_agent = graph.get_next_agent("Authentication", state)
    assert next_agent == "Frontline"
    
    logger.info("Transitioning back to Frontline agent")
    
    # Simulate menu inquiry
    state["tool_results"] = {
        "intent_classifier": {
            "intent": "menu_inquiry",
            "confidence": 0.85
        }
    }
    
    # Test transition to Menu agent
    next_agent = graph.get_next_agent("Frontline", state)
    assert next_agent == "Menu"
    
    logger.info("Transitioning to Menu agent")
    
    logger.info("Full orchestration workflow test passed")

# Test the initialization function
@pytest.mark.unit
def test_initialize_orchestrators():
    """Test the initialization of orchestrators."""
    from app.utils.agent_orchestration_async import initialize_orchestrators
    
    # Mock Redis to ensure test doesn't depend on actual Redis connection
    with mock.patch('app.utils.agent_orchestration.Redis') as mock_redis:
        # Mock the successful Redis connection
        mock_redis_instance = mock.MagicMock()
        mock_redis.from_url.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        
        # Initialize orchestrators
        graph, slot_store, fsm, escalator = initialize_orchestrators()
        
        # Verify that we got all the components
        assert isinstance(graph, AgentGraph)
        assert isinstance(slot_store, SlotStore)
        assert isinstance(fsm, FSMOrchestrator)
        assert isinstance(escalator, ModelEscalator)
        
        # Check that the graph has the default nodes
        assert "Frontline" in graph.nodes
        assert "Menu" in graph.nodes
        assert "Cart" in graph.nodes
        assert "Fulfillment" in graph.nodes
        assert "Escalation" in graph.nodes
        
        # Check that there are transitions
        assert len(graph.transitions) > 0
        
        logger.info("Initialize orchestrators test passed with Redis")
    
    # Test without Redis (fall back to local store)
    with mock.patch('app.utils.agent_orchestration.Redis') as mock_redis:
        # Mock the failed Redis connection
        mock_redis.from_url.side_effect = Exception("Redis connection failed")
        
        # Initialize orchestrators
        graph, slot_store, fsm, escalator = initialize_orchestrators()
        
        # Verify that we got all the components
        assert isinstance(graph, AgentGraph)
        assert isinstance(slot_store, SlotStore)
        assert isinstance(fsm, FSMOrchestrator)
        assert isinstance(escalator, ModelEscalator)
        
        logger.info("Initialize orchestrators test passed without Redis")