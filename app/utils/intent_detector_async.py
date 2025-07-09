"""
LLM-based intent detection for HSM state transitions.

This module uses OpenAI to detect user intents from transcripts,
replacing keyword-based detection with intelligent understanding.
"""

import logging
from typing import Optional, Dict, Any, Tuple
from openai import AsyncOpenAI
from app.config import settings
from app.fsm.core import ConversationHSMStates, ConversationHSMEvents, HSMEvent
from app.utils.enhanced_logging import get_logger
from app.utils.global_commands import (
    GlobalCommand, global_command_detector, global_command_context
)

logger = get_logger(__name__)

class AsyncIntentDetector:
    """Detects user intents using LLM for HSM state transitions."""
    
    def __init__(self):
        """Initialize the intent detector with OpenAI client."""
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o-mini"  # Fast model for intent detection
        
    async def detect_intent(
        self, 
        transcript: str, 
        current_state: str,
        context: Dict[str, Any]
    ) -> Optional[HSMEvent]:
        """
        Detect user intent from transcript using LLM.
        
        Args:
            transcript: User's spoken text
            current_state: Current HSM state
            context: Conversation context
            
        Returns:
            HSMEvent to trigger, or None
        """
        if not transcript.strip():
            return None
            
        # First check for global commands
        global_cmd, confidence = global_command_detector.detect_command(transcript)
        if global_cmd != GlobalCommand.NONE and confidence >= 0.8:
            # Map global commands to events
            global_event = self._map_global_command_to_event(global_cmd)
            if global_event:
                logger.info(
                    f"Global command detected: {global_cmd.value}",
                    event=global_event.name,
                    confidence=confidence
                )
                return global_event
            
        # Build state-specific prompt
        system_prompt = self._build_system_prompt(current_state)
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": transcript}
                ],
                temperature=0.1,  # Low temperature for consistent intent detection
                max_tokens=50
            )
            
            intent = response.choices[0].message.content.strip().upper()
            logger.info(f"LLM Intent Detection - State: {current_state}, Transcript: '{transcript[:50]}...', Detected: {intent}")
            
            # Map HSM states to simplified state names for prompts
            state_mapping = {
                ConversationHSMStates.INITIAL: "GREETING",
                ConversationHSMStates.GREETING: "GREETING",
                ConversationHSMStates.MAIN_MENU: "MAIN_MENU",
                ConversationHSMStates.ORDERING: "ORDERING",
                ConversationHSMStates.VALIDATION: "VALIDATION",
                ConversationHSMStates.CONFIRMATION: "CONFIRMATION",
                ConversationHSMStates.FULFILLMENT: "FULFILLMENT",
                ConversationHSMStates.COMPLETION: "COMPLETION",
                ConversationHSMStates.FOLLOW_UP: "FOLLOW_UP",
                ConversationHSMStates.ESCALATION: "ESCALATION"
            }
            
            # Handle ordering substates
            if current_state.startswith("ACTIVE.ORDERING"):
                state_key = "ORDERING"
            elif current_state.startswith("ACTIVE.CONFIRMATION"):
                state_key = "CONFIRMATION"
            elif current_state.startswith("ACTIVE.FULFILLMENT"):
                state_key = "FULFILLMENT"
            else:
                state_key = state_mapping.get(current_state, "MAIN_MENU")
            
            # Map intent to event
            event = self._map_intent_to_event(intent, state_key)
            if event:
                logger.info(f"Intent '{intent}' mapped to event: {event.name}")
            else:
                logger.info(f"Intent '{intent}' has no event mapping in state {state_key}")
            
            return event
            
        except Exception as e:
            logger.error(f"Error detecting intent: {e}")
            logger.warning("AI is required for intent detection. Please ensure OpenAI API key is valid.")
            # Return None - no fallback logic as per requirement
            return None
    
    def _build_system_prompt(self, current_state: ConversationState) -> str:
        """Build state-specific system prompt for intent detection."""
        base_prompt = """You are an intent classifier for a restaurant phone ordering system.
Analyze the user's message and return ONLY ONE of the allowed intents listed below.
Do not explain or add any other text - just return the intent name.

Current conversation state: {state}

"""
        
        # Map HSM states to simplified state names for prompts
        state_mapping = {
            ConversationHSMStates.INITIAL: "GREETING",
            ConversationHSMStates.GREETING: "GREETING",
            ConversationHSMStates.MAIN_MENU: "MAIN_MENU",
            ConversationHSMStates.ORDERING: "ORDERING",
            ConversationHSMStates.VALIDATION: "VALIDATION",
            ConversationHSMStates.CONFIRMATION: "CONFIRMATION",
            ConversationHSMStates.FULFILLMENT: "FULFILLMENT",
            ConversationHSMStates.COMPLETION: "COMPLETION",
            ConversationHSMStates.FOLLOW_UP: "FOLLOW_UP",
            ConversationHSMStates.ESCALATION: "ESCALATION"
        }
        
        # Handle ordering substates
        if current_state.startswith("ACTIVE.ORDERING"):
            state_key = "ORDERING"
        elif current_state.startswith("ACTIVE.CONFIRMATION"):
            state_key = "CONFIRMATION"
        elif current_state.startswith("ACTIVE.FULFILLMENT"):
            state_key = "FULFILLMENT"
        else:
            state_key = state_mapping.get(current_state, "MAIN_MENU")
        
        state_prompts = {
            "GREETING": """
Allowed intents:
- USER_PROVIDES_NAME: User is giving their name or responding to name request
- START_ORDER: User wants to skip giving name and proceed to ordering
- REQUEST_ESCALATION: User is confused or asking for help

IMPORTANT: If user mentions ordering or menu in GREETING state, still return USER_PROVIDES_NAME if no name is detected, or START_ORDER if they're trying to proceed without giving name.

Examples:
"John" -> USER_PROVIDES_NAME
"My name is Sarah" -> USER_PROVIDES_NAME  
"I don't want to give my name" -> START_ORDER
"Can I order?" -> START_ORDER
"What do you have?" -> START_ORDER
"What?" -> REQUEST_ESCALATION
""",
            
            "MAIN_MENU": """
Allowed intents:
- START_ORDER: User wants to place an order or add items
- REQUEST_MENU_INFO: User wants to know about menu/items/prices
- REQUEST_ESCALATION: User wants to speak to a person or needs help
- REQUEST_FOLLOW_UP: User has a question not covered above

Examples:
"I'd like to order something" -> START_ORDER
"Can I get two items" -> START_ORDER
"What do you have on the menu?" -> REQUEST_MENU_INFO
"Are you open now?" -> REQUEST_FOLLOW_UP
"I need to speak to someone" -> REQUEST_ESCALATION
"Do you deliver?" -> REQUEST_FOLLOW_UP
""",
            
            "ORDERING": """
Allowed intents:
- ADD_ITEM: User is adding items to their order
- REMOVE_ITEM: User wants to remove something
- MODIFY_ITEM: User wants to change something (quantity, preparation)
- REQUEST_MENU_INFO: User asking about menu items while ordering
- COMPLETE_ORDER: User is done ordering
- USER_REQUESTS_CANCELLATION: User wants to cancel everything

Examples:
"Add an item" -> ADD_ITEM
"Remove that item" -> REMOVE_ITEM
"Make that 3 instead" -> MODIFY_ITEM
"What comes with that?" -> REQUEST_MENU_INFO
"That's all for now" -> COMPLETE_ORDER
"Never mind, cancel everything" -> USER_REQUESTS_CANCELLATION
"Actually, maybe I should cancel" -> USER_REQUESTS_CANCELLATION
"I want to cancel my order" -> USER_REQUESTS_CANCELLATION
""",
            
            "VALIDATION": """
Allowed intents:
- ORDER_VALID: User confirms the order is correct
- ORDER_INVALID: User wants to modify something
- REQUEST_ESCALATION: User needs assistance

Examples:
"Yes that's correct" -> ORDER_VALID
"Actually can you change..." -> ORDER_INVALID
"Can you repeat that?" -> ORDER_INVALID
"No, cancel it" -> ORDER_INVALID
"Can I add one more thing?" -> ORDER_INVALID
"I forgot to order something" -> ORDER_INVALID
""",
            
            "CONFIRMATION": """
Allowed intents:
- CONFIRM_ORDER: User confirms and wants to proceed
- MODIFY_ORDER: User wants to change something
- REJECT_ORDER: User wants to cancel
- REQUEST_ESCALATION: User has questions or needs help

Examples:
"Yes, place the order" -> CONFIRM_ORDER
"Actually can I add one more thing" -> MODIFY_ORDER
"Cancel the order" -> REJECT_ORDER
"How long will it take?" -> REQUEST_ESCALATION
""",
            
            "FULFILLMENT": """
Allowed intents:
- PROVIDE_DELIVERY_INFO: User providing delivery information
- CHOOSE_PICKUP: User wants pickup instead
- COMPLETE_INTERACTION: User is satisfied with service
- REQUEST_ESCALATION: User needs assistance

Examples:
"123 Main Street" -> PROVIDE_DELIVERY_INFO
"I'll pick it up" -> CHOOSE_PICKUP
"I'll pay with card" -> PROVIDE_PAYMENT
"I don't understand" -> REQUEST_ESCALATION
""",
            
        }
        
        state_prompt = state_prompts.get(
            state_key, 
            "Allowed intents: CONTINUE, REQUEST_ESCALATION, REQUEST_HUMAN"
        )
        
        return base_prompt.format(state=state_key) + state_prompt
    
    def _map_intent_to_event(self, intent: str, state_key: str) -> Optional[HSMEvent]:
        """Map detected intent to HSM event based on current state."""
        
        # State-specific intent mappings
        state_mappings = {
            "GREETING": {
                "USER_PROVIDES_NAME": ConversationHSMEvents.USER_PROVIDES_NAME,
                "START_ORDER": ConversationHSMEvents.START_ORDER,
                "REQUEST_ESCALATION": ConversationHSMEvents.REQUEST_ESCALATION
            },
            "MAIN_MENU": {
                "START_ORDER": ConversationHSMEvents.START_ORDER,
                "REQUEST_MENU_INFO": ConversationHSMEvents.REQUEST_MENU_INFO,
                "REQUEST_ESCALATION": ConversationHSMEvents.REQUEST_ESCALATION,
                "REQUEST_FOLLOW_UP": ConversationHSMEvents.REQUEST_FOLLOW_UP
            },
            "ORDERING": {
                "ADD_ITEM": ConversationHSMEvents.ADD_ITEM,
                "REMOVE_ITEM": ConversationHSMEvents.REMOVE_ITEM,
                "MODIFY_ITEM": ConversationHSMEvents.MODIFY_ITEM,
                "REQUEST_MENU_INFO": ConversationHSMEvents.REQUEST_MENU_INFO,
                "COMPLETE_ORDER": ConversationHSMEvents.COMPLETE_ORDER,
                "USER_REQUESTS_CANCELLATION": ConversationHSMEvents.USER_REQUESTS_CANCELLATION
            },
            "VALIDATION": {
                "ORDER_VALID": ConversationHSMEvents.ORDER_VALID,
                "ORDER_INVALID": ConversationHSMEvents.ORDER_INVALID,
                "REQUEST_ESCALATION": ConversationHSMEvents.REQUEST_ESCALATION
            },
            "CONFIRMATION": {
                "CONFIRM_ORDER": ConversationHSMEvents.CONFIRM_ORDER,
                "MODIFY_ORDER": ConversationHSMEvents.MODIFY_ORDER,
                "REJECT_ORDER": ConversationHSMEvents.REJECT_ORDER,
                "REQUEST_ESCALATION": ConversationHSMEvents.REQUEST_ESCALATION
            },
            "FULFILLMENT": {
                "PROVIDE_DELIVERY_INFO": ConversationHSMEvents.PROVIDE_DELIVERY_INFO,
                "CHOOSE_PICKUP": ConversationHSMEvents.CHOOSE_PICKUP,
                "COMPLETE_INTERACTION": ConversationHSMEvents.COMPLETE_INTERACTION,
                "REQUEST_ESCALATION": ConversationHSMEvents.REQUEST_ESCALATION
            }
        }
        
        # Get mapping for current state
        mapping = state_mappings.get(state_key, {})
        event_name = mapping.get(intent)
        
        if event_name:
            logger.info(f"Mapped intent {intent} to event {event_name}")
            return HSMEvent(event_name, {})
        else:
            logger.info(f"No event mapping for intent {intent} in state {state_key}")
            
        return None
    
    def _map_global_command_to_event(self, command: GlobalCommand) -> Optional[HSMEvent]:
        """Map global command to HSM event."""
        # Global commands that map to existing events
        command_to_event = {
            GlobalCommand.CANCEL: ConversationHSMEvents.USER_REQUESTS_CANCELLATION,
            GlobalCommand.HELP: ConversationHSMEvents.REQUEST_ESCALATION,
            # REPEAT, START_OVER, and GO_BACK will be handled specially
            # in the orchestrator, so they don't map to events
        }
        event_name = command_to_event.get(command)
        if event_name:
            return HSMEvent(event_name, {})
        return None
    
    async def detect_global_command(
        self, 
        transcript: str
    ) -> Tuple[GlobalCommand, float]:
        """
        Detect global command from transcript.
        
        Args:
            transcript: User's spoken text
            
        Returns:
            Tuple of (command, confidence)
        """
        return global_command_detector.detect_command(transcript)

# Singleton instance
intent_detector = AsyncIntentDetector()

# For backward compatibility with tests
async_intent_detector = intent_detector