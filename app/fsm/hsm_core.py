"""
Hierarchical State Machine (HSM) implementation for RedBarSushiAI.

This module provides HSM support with nested states, state stacks, and 
hierarchical event handling for more fluid conversation management.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Callable, Union, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from abc import ABC, abstractmethod

from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class HSMError(Exception):
    """Base exception for HSM-related errors."""
    pass


@dataclass
class HSMStateDefinition:
    """
    Definition of a hierarchical state.
    
    Attributes:
        name: Unique name of the state
        parent_state_name: Name of the parent state (None for root states)
        initial_substate_name: Default substate to enter when this state is entered
        on_enter: Callback when entering the state
        on_exit: Callback when exiting the state
        handle_event: Event handler for this state
    """
    name: str
    parent_state_name: Optional[str] = None
    initial_substate_name: Optional[str] = None
    on_enter: Optional[Callable] = None
    on_exit: Optional[Callable] = None
    handle_event: Optional[Callable] = None
    
    # Runtime tracking (not part of definition)
    substates: List[str] = field(default_factory=list)
    
    def add_substate(self, substate_name: str) -> None:
        """Add a substate to this state."""
        if substate_name not in self.substates:
            self.substates.append(substate_name)
    
    def is_parent_of(self, state_name: str, all_states: Dict[str, 'HSMStateDefinition']) -> bool:
        """Check if this state is a parent of the given state."""
        if state_name in self.substates:
            return True
        # Check nested substates
        for substate_name in self.substates:
            substate = all_states.get(substate_name)
            if substate and substate.is_parent_of(state_name, all_states):
                return True
        return False


class HSMEvent:
    """Base class for HSM events."""
    
    def __init__(self, name: str, data: Optional[Dict[str, Any]] = None):
        self.name = name
        self.data = data or {}
    
    def __str__(self):
        return f"HSMEvent({self.name})"


class HSMStateHandler(ABC):
    """
    Abstract base class for HSM state handlers.
    
    Provides template methods for state lifecycle and event handling.
    """
    
    def __init__(self, state_name: str):
        self.state_name = state_name
        self.logger = get_logger(f"{__name__}.{state_name}")
    
    async def on_enter(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """
        Called when entering this state.
        
        Args:
            context: The conversation context
            event: The event that triggered entry (if any)
        """
        self.logger.info(f"Entering state: {self.state_name}")
    
    async def on_exit(self, context: Dict[str, Any], event: Optional[HSMEvent] = None) -> None:
        """
        Called when exiting this state.
        
        Args:
            context: The conversation context  
            event: The event that triggered exit (if any)
        """
        self.logger.info(f"Exiting state: {self.state_name}")
    
    @abstractmethod
    async def handle_event(self, event: HSMEvent, context: Dict[str, Any]) -> Optional[str]:
        """
        Handle an event in this state.
        
        Args:
            event: The event to handle
            context: The conversation context
            
        Returns:
            Target state name if a transition should occur, None otherwise
        """
        pass


class ConversationHSMStates:
    """Hierarchical state definitions for the conversation FSM."""
    
    # Root states
    INITIAL = "INITIAL"
    ACTIVE = "ACTIVE"
    COMPLETION = "COMPLETION"
    ERROR_RECOVERY = "ERROR_RECOVERY"
    
    # ACTIVE substates
    GREETING = "GREETING"
    MAIN_MENU = "MAIN_MENU"
    ORDERING = "ORDERING"
    CONFIRMATION = "CONFIRMATION"
    FULFILLMENT = "FULFILLMENT"
    
    # ORDERING substates
    ORDERING_BROWSING = "ORDERING.BROWSING"
    ORDERING_MENU_INQUIRY = "ORDERING.MENU_INQUIRY"
    ORDERING_ITEM_CUSTOMIZATION = "ORDERING.ITEM_CUSTOMIZATION"
    ORDERING_CART_REVIEW = "ORDERING.CART_REVIEW"
    
    # CONFIRMATION substates
    CONFIRMATION_REVIEW = "CONFIRMATION.REVIEW"
    CONFIRMATION_MODIFY = "CONFIRMATION.MODIFY"
    CONFIRMATION_PAYMENT = "CONFIRMATION.PAYMENT"
    
    # Global superstates (can be entered from any state)
    GLOBAL_INQUIRY = "GLOBAL_INQUIRY"
    GLOBAL_HELP = "GLOBAL_HELP"
    
    # GLOBAL_INQUIRY substates
    ASKING_HOURS = "GLOBAL_INQUIRY.ASKING_HOURS"
    ASKING_LOCATION = "GLOBAL_INQUIRY.ASKING_LOCATION"
    ASKING_POLICIES = "GLOBAL_INQUIRY.ASKING_POLICIES"


def create_conversation_hsm_states() -> Dict[str, HSMStateDefinition]:
    """Create the hierarchical state definitions for conversation."""
    states = {}
    
    # Root states
    states[ConversationHSMStates.INITIAL] = HSMStateDefinition(
        name=ConversationHSMStates.INITIAL
    )
    
    states[ConversationHSMStates.ACTIVE] = HSMStateDefinition(
        name=ConversationHSMStates.ACTIVE,
        initial_substate_name=ConversationHSMStates.GREETING
    )
    
    states[ConversationHSMStates.COMPLETION] = HSMStateDefinition(
        name=ConversationHSMStates.COMPLETION
    )
    
    states[ConversationHSMStates.ERROR_RECOVERY] = HSMStateDefinition(
        name=ConversationHSMStates.ERROR_RECOVERY
    )
    
    # ACTIVE substates
    states[ConversationHSMStates.GREETING] = HSMStateDefinition(
        name=ConversationHSMStates.GREETING,
        parent_state_name=ConversationHSMStates.ACTIVE
    )
    
    states[ConversationHSMStates.MAIN_MENU] = HSMStateDefinition(
        name=ConversationHSMStates.MAIN_MENU,
        parent_state_name=ConversationHSMStates.ACTIVE
    )
    
    states[ConversationHSMStates.ORDERING] = HSMStateDefinition(
        name=ConversationHSMStates.ORDERING,
        parent_state_name=ConversationHSMStates.ACTIVE,
        initial_substate_name=ConversationHSMStates.ORDERING_BROWSING
    )
    
    states[ConversationHSMStates.CONFIRMATION] = HSMStateDefinition(
        name=ConversationHSMStates.CONFIRMATION,
        parent_state_name=ConversationHSMStates.ACTIVE,
        initial_substate_name=ConversationHSMStates.CONFIRMATION_REVIEW
    )
    
    states[ConversationHSMStates.FULFILLMENT] = HSMStateDefinition(
        name=ConversationHSMStates.FULFILLMENT,
        parent_state_name=ConversationHSMStates.ACTIVE
    )
    
    # ORDERING substates
    states[ConversationHSMStates.ORDERING_BROWSING] = HSMStateDefinition(
        name=ConversationHSMStates.ORDERING_BROWSING,
        parent_state_name=ConversationHSMStates.ORDERING
    )
    
    states[ConversationHSMStates.ORDERING_MENU_INQUIRY] = HSMStateDefinition(
        name=ConversationHSMStates.ORDERING_MENU_INQUIRY,
        parent_state_name=ConversationHSMStates.ORDERING
    )
    
    states[ConversationHSMStates.ORDERING_ITEM_CUSTOMIZATION] = HSMStateDefinition(
        name=ConversationHSMStates.ORDERING_ITEM_CUSTOMIZATION,
        parent_state_name=ConversationHSMStates.ORDERING
    )
    
    states[ConversationHSMStates.ORDERING_CART_REVIEW] = HSMStateDefinition(
        name=ConversationHSMStates.ORDERING_CART_REVIEW,
        parent_state_name=ConversationHSMStates.ORDERING
    )
    
    # CONFIRMATION substates
    states[ConversationHSMStates.CONFIRMATION_REVIEW] = HSMStateDefinition(
        name=ConversationHSMStates.CONFIRMATION_REVIEW,
        parent_state_name=ConversationHSMStates.CONFIRMATION
    )
    
    states[ConversationHSMStates.CONFIRMATION_MODIFY] = HSMStateDefinition(
        name=ConversationHSMStates.CONFIRMATION_MODIFY,
        parent_state_name=ConversationHSMStates.CONFIRMATION
    )
    
    states[ConversationHSMStates.CONFIRMATION_PAYMENT] = HSMStateDefinition(
        name=ConversationHSMStates.CONFIRMATION_PAYMENT,
        parent_state_name=ConversationHSMStates.CONFIRMATION
    )
    
    # Global superstates
    states[ConversationHSMStates.GLOBAL_INQUIRY] = HSMStateDefinition(
        name=ConversationHSMStates.GLOBAL_INQUIRY,
        initial_substate_name=ConversationHSMStates.ASKING_HOURS
    )
    
    states[ConversationHSMStates.GLOBAL_HELP] = HSMStateDefinition(
        name=ConversationHSMStates.GLOBAL_HELP
    )
    
    # GLOBAL_INQUIRY substates
    states[ConversationHSMStates.ASKING_HOURS] = HSMStateDefinition(
        name=ConversationHSMStates.ASKING_HOURS,
        parent_state_name=ConversationHSMStates.GLOBAL_INQUIRY
    )
    
    states[ConversationHSMStates.ASKING_LOCATION] = HSMStateDefinition(
        name=ConversationHSMStates.ASKING_LOCATION,
        parent_state_name=ConversationHSMStates.GLOBAL_INQUIRY
    )
    
    states[ConversationHSMStates.ASKING_POLICIES] = HSMStateDefinition(
        name=ConversationHSMStates.ASKING_POLICIES,
        parent_state_name=ConversationHSMStates.GLOBAL_INQUIRY
    )
    
    # Build parent-child relationships
    for state_name, state_def in states.items():
        if state_def.parent_state_name:
            parent = states.get(state_def.parent_state_name)
            if parent:
                parent.add_substate(state_name)
    
    return states


class HSMTransitionType(Enum):
    """Types of transitions in the HSM."""
    EXTERNAL = auto()  # Exit source, enter target
    INTERNAL = auto()  # Stay in current state
    LOCAL = auto()     # Transition within same parent


@dataclass
class HSMTransition:
    """Definition of a state transition."""
    source_state: str
    event_name: str
    target_state: Optional[str]
    transition_type: HSMTransitionType = HSMTransitionType.EXTERNAL
    guard: Optional[Callable] = None
    action: Optional[Callable] = None