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
    """Hierarchical state definitions for the conversation HSM."""
    
    # Root states
    INITIAL = "INITIAL"
    ACTIVE = "ACTIVE"
    COMPLETION = "COMPLETION"
    ERROR_RECOVERY = "ERROR_RECOVERY"
    
    # ACTIVE substates - Main conversation flow
    GREETING = "ACTIVE.GREETING"
    MAIN_MENU = "ACTIVE.MAIN_MENU"
    ORDERING = "ACTIVE.ORDERING"
    VALIDATION = "ACTIVE.VALIDATION"
    CONFIRMATION = "ACTIVE.CONFIRMATION"
    FULFILLMENT = "ACTIVE.FULFILLMENT"
    FOLLOW_UP = "ACTIVE.FOLLOW_UP"
    ESCALATION = "ACTIVE.ESCALATION"
    
    # ORDERING substates - Hierarchical ordering process
    ORDERING_BROWSING = "ACTIVE.ORDERING.BROWSING"
    ORDERING_MENU_INQUIRY = "ACTIVE.ORDERING.MENU_INQUIRY"
    ORDERING_ITEM_CUSTOMIZATION = "ACTIVE.ORDERING.ITEM_CUSTOMIZATION"
    ORDERING_CART_REVIEW = "ACTIVE.ORDERING.CART_REVIEW"
    ORDERING_VALIDATION = "ACTIVE.ORDERING.VALIDATION"
    
    # CONFIRMATION substates
    CONFIRMATION_REVIEW = "ACTIVE.CONFIRMATION.REVIEW"
    CONFIRMATION_MODIFY = "ACTIVE.CONFIRMATION.MODIFY"
    CONFIRMATION_PAYMENT = "ACTIVE.CONFIRMATION.PAYMENT"
    CONFIRMATION_DELIVERY = "ACTIVE.CONFIRMATION.DELIVERY"
    
    # FULFILLMENT substates
    FULFILLMENT_PROCESSING = "ACTIVE.FULFILLMENT.PROCESSING"
    FULFILLMENT_TRACKING = "ACTIVE.FULFILLMENT.TRACKING"
    FULFILLMENT_DELIVERY = "ACTIVE.FULFILLMENT.DELIVERY"
    
    # Global superstates (can be entered from any state)
    GLOBAL_INQUIRY = "GLOBAL_INQUIRY"
    GLOBAL_HELP = "GLOBAL_HELP"
    GLOBAL_CANCELLATION = "GLOBAL_CANCELLATION"
    
    # GLOBAL_INQUIRY substates
    INQUIRY_HOURS = "GLOBAL_INQUIRY.HOURS"
    INQUIRY_LOCATION = "GLOBAL_INQUIRY.LOCATION"
    INQUIRY_POLICIES = "GLOBAL_INQUIRY.POLICIES"
    INQUIRY_MENU = "GLOBAL_INQUIRY.MENU"
    
    # GLOBAL_CANCELLATION substates
    CANCELLATION_PENDING = "GLOBAL_CANCELLATION.PENDING"
    CANCELLATION_CONFIRMED = "GLOBAL_CANCELLATION.CONFIRMED"
    
    # ERROR_RECOVERY substates
    ERROR_RETRY = "ERROR_RECOVERY.RETRY"
    ERROR_FALLBACK = "ERROR_RECOVERY.FALLBACK"
    ERROR_ESCALATION = "ERROR_RECOVERY.ESCALATION"


class ConversationHSMEvents:
    """Events that can trigger state transitions in the HSM."""
    
    # Lifecycle events
    START_CONVERSATION = "START_CONVERSATION"
    END_CONVERSATION = "END_CONVERSATION"
    
    # User interaction events
    USER_PROVIDES_NAME = "USER_PROVIDES_NAME"
    USER_GREETS = "USER_GREETS"
    USER_SAYS_GOODBYE = "USER_SAYS_GOODBYE"
    
    # Menu and ordering events
    REQUEST_MENU_INFO = "REQUEST_MENU_INFO"
    START_ORDER = "START_ORDER"
    ADD_ITEM = "ADD_ITEM"
    REMOVE_ITEM = "REMOVE_ITEM"
    MODIFY_ITEM = "MODIFY_ITEM"
    SELECT_ITEM = "SELECT_ITEM"
    ASK_ABOUT_ITEM = "ASK_ABOUT_ITEM"
    REQUEST_RECOMMENDATIONS = "REQUEST_RECOMMENDATIONS"
    
    # Cart and customization events
    VIEW_CART = "VIEW_CART"
    CLEAR_CART = "CLEAR_CART"
    ADD_MODIFICATION = "ADD_MODIFICATION"
    SET_QUANTITY = "SET_QUANTITY"
    CONFIRM_ITEM = "CONFIRM_ITEM"
    CANCEL_ITEM = "CANCEL_ITEM"
    
    # Order flow events
    COMPLETE_ORDER = "COMPLETE_ORDER"
    VALIDATE_ORDER = "VALIDATE_ORDER"
    ORDER_VALID = "ORDER_VALID"
    ORDER_INVALID = "ORDER_INVALID"
    MODIFY_ORDER = "MODIFY_ORDER"
    CONFIRM_ORDER = "CONFIRM_ORDER"
    REJECT_ORDER = "REJECT_ORDER"
    
    # Fulfillment events
    FULFILL_ORDER = "FULFILL_ORDER"
    PROVIDE_DELIVERY_INFO = "PROVIDE_DELIVERY_INFO"
    CHOOSE_PICKUP = "CHOOSE_PICKUP"
    COMPLETE_INTERACTION = "COMPLETE_INTERACTION"
    
    # Global commands
    REQUEST_FOLLOW_UP = "REQUEST_FOLLOW_UP"
    REQUEST_ESCALATION = "REQUEST_ESCALATION"
    REQUEST_HELP = "REQUEST_HELP"
    
    # Cancellation events
    USER_REQUESTS_CANCELLATION = "USER_REQUESTS_CANCELLATION"
    CONFIRM_CANCELLATION = "CONFIRM_CANCELLATION"
    DECLINE_CANCELLATION = "DECLINE_CANCELLATION"
    
    # Error handling events
    ERROR_OCCURRED = "ERROR_OCCURRED"
    RETRY_LAST_ACTION = "RETRY_LAST_ACTION"
    ESCALATE_DUE_TO_ERROR = "ESCALATE_DUE_TO_ERROR"
    FALLBACK_TO_MAIN_MENU = "FALLBACK_TO_MAIN_MENU"
    
    # Navigation events
    GO_BACK = "GO_BACK"
    START_OVER = "START_OVER"
    REPEAT = "REPEAT"
    
    # Inquiry resolution
    INQUIRY_COMPLETE = "INQUIRY_COMPLETE"
    INQUIRY_RESOLVED = "INQUIRY_RESOLVED"


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
        name=ConversationHSMStates.ERROR_RECOVERY,
        initial_substate_name=ConversationHSMStates.ERROR_RETRY
    )
    
    # ACTIVE substates - Main conversation flow
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
    
    states[ConversationHSMStates.VALIDATION] = HSMStateDefinition(
        name=ConversationHSMStates.VALIDATION,
        parent_state_name=ConversationHSMStates.ACTIVE
    )
    
    states[ConversationHSMStates.CONFIRMATION] = HSMStateDefinition(
        name=ConversationHSMStates.CONFIRMATION,
        parent_state_name=ConversationHSMStates.ACTIVE,
        initial_substate_name=ConversationHSMStates.CONFIRMATION_REVIEW
    )
    
    states[ConversationHSMStates.FULFILLMENT] = HSMStateDefinition(
        name=ConversationHSMStates.FULFILLMENT,
        parent_state_name=ConversationHSMStates.ACTIVE,
        initial_substate_name=ConversationHSMStates.FULFILLMENT_PROCESSING
    )
    
    states[ConversationHSMStates.FOLLOW_UP] = HSMStateDefinition(
        name=ConversationHSMStates.FOLLOW_UP,
        parent_state_name=ConversationHSMStates.ACTIVE
    )
    
    states[ConversationHSMStates.ESCALATION] = HSMStateDefinition(
        name=ConversationHSMStates.ESCALATION,
        parent_state_name=ConversationHSMStates.ACTIVE
    )
    
    # ORDERING substates - Hierarchical ordering process
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
    
    states[ConversationHSMStates.ORDERING_VALIDATION] = HSMStateDefinition(
        name=ConversationHSMStates.ORDERING_VALIDATION,
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
    
    states[ConversationHSMStates.CONFIRMATION_DELIVERY] = HSMStateDefinition(
        name=ConversationHSMStates.CONFIRMATION_DELIVERY,
        parent_state_name=ConversationHSMStates.CONFIRMATION
    )
    
    # FULFILLMENT substates
    states[ConversationHSMStates.FULFILLMENT_PROCESSING] = HSMStateDefinition(
        name=ConversationHSMStates.FULFILLMENT_PROCESSING,
        parent_state_name=ConversationHSMStates.FULFILLMENT
    )
    
    states[ConversationHSMStates.FULFILLMENT_TRACKING] = HSMStateDefinition(
        name=ConversationHSMStates.FULFILLMENT_TRACKING,
        parent_state_name=ConversationHSMStates.FULFILLMENT
    )
    
    states[ConversationHSMStates.FULFILLMENT_DELIVERY] = HSMStateDefinition(
        name=ConversationHSMStates.FULFILLMENT_DELIVERY,
        parent_state_name=ConversationHSMStates.FULFILLMENT
    )
    
    # Global superstates (can be entered from any state)
    states[ConversationHSMStates.GLOBAL_INQUIRY] = HSMStateDefinition(
        name=ConversationHSMStates.GLOBAL_INQUIRY,
        initial_substate_name=ConversationHSMStates.INQUIRY_MENU
    )
    
    states[ConversationHSMStates.GLOBAL_HELP] = HSMStateDefinition(
        name=ConversationHSMStates.GLOBAL_HELP
    )
    
    states[ConversationHSMStates.GLOBAL_CANCELLATION] = HSMStateDefinition(
        name=ConversationHSMStates.GLOBAL_CANCELLATION,
        initial_substate_name=ConversationHSMStates.CANCELLATION_PENDING
    )
    
    # GLOBAL_INQUIRY substates
    states[ConversationHSMStates.INQUIRY_HOURS] = HSMStateDefinition(
        name=ConversationHSMStates.INQUIRY_HOURS,
        parent_state_name=ConversationHSMStates.GLOBAL_INQUIRY
    )
    
    states[ConversationHSMStates.INQUIRY_LOCATION] = HSMStateDefinition(
        name=ConversationHSMStates.INQUIRY_LOCATION,
        parent_state_name=ConversationHSMStates.GLOBAL_INQUIRY
    )
    
    states[ConversationHSMStates.INQUIRY_POLICIES] = HSMStateDefinition(
        name=ConversationHSMStates.INQUIRY_POLICIES,
        parent_state_name=ConversationHSMStates.GLOBAL_INQUIRY
    )
    
    states[ConversationHSMStates.INQUIRY_MENU] = HSMStateDefinition(
        name=ConversationHSMStates.INQUIRY_MENU,
        parent_state_name=ConversationHSMStates.GLOBAL_INQUIRY
    )
    
    # GLOBAL_CANCELLATION substates
    states[ConversationHSMStates.CANCELLATION_PENDING] = HSMStateDefinition(
        name=ConversationHSMStates.CANCELLATION_PENDING,
        parent_state_name=ConversationHSMStates.GLOBAL_CANCELLATION
    )
    
    states[ConversationHSMStates.CANCELLATION_CONFIRMED] = HSMStateDefinition(
        name=ConversationHSMStates.CANCELLATION_CONFIRMED,
        parent_state_name=ConversationHSMStates.GLOBAL_CANCELLATION
    )
    
    # ERROR_RECOVERY substates
    states[ConversationHSMStates.ERROR_RETRY] = HSMStateDefinition(
        name=ConversationHSMStates.ERROR_RETRY,
        parent_state_name=ConversationHSMStates.ERROR_RECOVERY
    )
    
    states[ConversationHSMStates.ERROR_FALLBACK] = HSMStateDefinition(
        name=ConversationHSMStates.ERROR_FALLBACK,
        parent_state_name=ConversationHSMStates.ERROR_RECOVERY
    )
    
    states[ConversationHSMStates.ERROR_ESCALATION] = HSMStateDefinition(
        name=ConversationHSMStates.ERROR_ESCALATION,
        parent_state_name=ConversationHSMStates.ERROR_RECOVERY
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