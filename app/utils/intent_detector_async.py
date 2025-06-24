"""
LLM-based intent detection for FSM state transitions.

This module uses OpenAI to detect user intents from transcripts,
replacing keyword-based detection with intelligent understanding.
"""

import logging
from typing import Optional, Dict, Any, Tuple
from openai import AsyncOpenAI
from app.config import settings
from app.fsm.core import ConversationState, ConversationEvent
from app.utils.enhanced_logging import get_logger
from app.utils.global_commands import (
    GlobalCommand, global_command_detector, global_command_context
)

logger = get_logger(__name__)

class AsyncIntentDetector:
    """Detects user intents using LLM for FSM state transitions."""
    
    def __init__(self):
        """Initialize the intent detector with OpenAI client."""
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o-mini"  # Fast model for intent detection
        
    async def detect_intent(
        self, 
        transcript: str, 
        current_state: ConversationState,
        context: Dict[str, Any]
    ) -> Optional[ConversationEvent]:
        """
        Detect user intent from transcript using LLM.
        
        Args:
            transcript: User's spoken text
            current_state: Current FSM state
            context: Conversation context
            
        Returns:
            ConversationEvent to trigger, or None
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
            logger.info(f"LLM Intent Detection - State: {current_state.name}, Transcript: '{transcript[:50]}...', Detected: {intent}")
            
            # Map intent to event
            event = self._map_intent_to_event(intent, current_state)
            if event:
                logger.info(f"Intent '{intent}' mapped to event: {event.name}")
            else:
                logger.info(f"Intent '{intent}' has no event mapping in state {current_state.name}")
            
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
        
        state_prompts = {
            ConversationState.GREETING: """
Allowed intents:
- PROVIDE_NAME: User is giving their name or responding to name request
- SKIP_NAME: User wants to skip giving name or proceed without it
- REQUEST_ESCALATION: User is confused or asking for help

IMPORTANT: If user mentions ordering or menu in GREETING state, still return PROVIDE_NAME if no name is detected, or SKIP_NAME if they're trying to proceed without giving name.

Examples:
"John" -> PROVIDE_NAME
"My name is Sarah" -> PROVIDE_NAME  
"I don't want to give my name" -> SKIP_NAME
"Can I order?" -> SKIP_NAME
"What do you have?" -> SKIP_NAME
"What?" -> REQUEST_ESCALATION
""",
            
            ConversationState.MAIN_MENU: """
Allowed intents:
- START_ORDER: User wants to place an order or add items
- REQUEST_MENU: User wants to know about menu/items/prices
- REQUEST_HOURS: User asking about hours or location
- REQUEST_HUMAN: User wants to speak to a person
- GENERAL_QUESTION: User has a question not covered above

Examples:
"I'd like to order something" -> START_ORDER
"Can I get two items" -> START_ORDER
"What do you have on the menu?" -> REQUEST_MENU
"Are you open now?" -> REQUEST_HOURS
"I need to speak to someone" -> REQUEST_HUMAN
"Do you deliver?" -> GENERAL_QUESTION
""",
            
            ConversationState.ORDERING: """
Allowed intents:
- ADD_ITEM: User is adding items to their order
- REMOVE_ITEM: User wants to remove something
- MODIFY_ITEM: User wants to change something (quantity, preparation)
- REQUEST_MENU: User asking about menu items while ordering
- COMPLETE_ORDER: User is done ordering
- CANCEL_ORDER: User wants to cancel everything
- REQUEST_CANCELLATION: User mentions cancelling but isn't sure

Examples:
"Add an item" -> ADD_ITEM
"Remove that item" -> REMOVE_ITEM
"Make that 3 instead" -> MODIFY_ITEM
"What comes with that?" -> REQUEST_MENU
"That's all for now" -> COMPLETE_ORDER
"Never mind, cancel everything" -> CANCEL_ORDER
"Actually, maybe I should cancel" -> REQUEST_CANCELLATION
"I want to cancel my order" -> REQUEST_CANCELLATION
""",
            
            ConversationState.VALIDATION: """
Allowed intents:
- CONFIRM: User confirms the order is correct
- REQUEST_CHANGE: User wants to modify something
- REQUEST_REPEAT: User wants to hear the order again
- CANCEL: User wants to cancel
- REQUEST_ADD_MORE: User wants to add more items

Examples:
"Yes that's correct" -> CONFIRM
"Actually can you change..." -> REQUEST_CHANGE
"Can you repeat that?" -> REQUEST_REPEAT
"No, cancel it" -> CANCEL
"Can I add one more thing?" -> REQUEST_ADD_MORE
"I forgot to order something" -> REQUEST_ADD_MORE
""",
            
            ConversationState.CONFIRMATION: """
Allowed intents:
- CONFIRM_ORDER: User confirms and wants to proceed
- MODIFY_ORDER: User wants to change something
- CANCEL_ORDER: User wants to cancel
- REQUEST_INFO: User has questions

Examples:
"Yes, place the order" -> CONFIRM_ORDER
"Actually can I add one more thing" -> MODIFY_ORDER
"Cancel the order" -> CANCEL_ORDER
"How long will it take?" -> REQUEST_INFO
""",
            
            ConversationState.FULFILLMENT: """
Allowed intents:
- PROVIDE_DELIVERY: User providing delivery information
- CHOOSE_PICKUP: User wants pickup instead
- PROVIDE_PAYMENT: User providing payment details
- REQUEST_ESCALATION: User needs assistance

Examples:
"123 Main Street" -> PROVIDE_DELIVERY
"I'll pick it up" -> CHOOSE_PICKUP
"I'll pay with card" -> PROVIDE_PAYMENT
"I don't understand" -> REQUEST_ESCALATION
""",
            
            ConversationState.CANCELLATION_PENDING: """
Allowed intents:
- CONFIRM_CANCELLATION: User confirms they want to cancel
- DECLINE_CANCELLATION: User decides not to cancel
- YES: Affirmative response (maps to confirm)
- NO: Negative response (maps to decline)

Examples:
"Yes, cancel it" -> CONFIRM_CANCELLATION
"Yes" -> YES
"No, keep my order" -> DECLINE_CANCELLATION
"No" -> NO
"Actually, don't cancel" -> DECLINE_CANCELLATION
""",
            
            ConversationState.MENU_QUERY_SUBSTATE: """
Allowed intents:
- QUERY_COMPLETE: User is done asking menu questions
- CONTINUE: User wants to continue with their previous task

Examples:
"OK thanks" -> QUERY_COMPLETE
"That's all I needed to know" -> QUERY_COMPLETE
"Let me continue ordering" -> CONTINUE
"""
        }
        
        state_prompt = state_prompts.get(
            current_state, 
            "Allowed intents: CONTINUE, REQUEST_ESCALATION, REQUEST_HUMAN"
        )
        
        return base_prompt.format(state=current_state.name) + state_prompt
    
    def _map_intent_to_event(self, intent: str, current_state: ConversationState) -> Optional[ConversationEvent]:
        """Map detected intent to FSM event based on current state."""
        
        # State-specific intent mappings
        state_mappings = {
            ConversationState.GREETING: {
                "PROVIDE_NAME": ConversationEvent.USER_PROVIDES_NAME,
                "SKIP_NAME": ConversationEvent.USER_PROVIDES_NAME,
                "REQUEST_ESCALATION": None
            },
            ConversationState.MAIN_MENU: {
                "START_ORDER": ConversationEvent.START_ORDER,
                "REQUEST_MENU": ConversationEvent.REQUEST_MENU_INFO,
                "REQUEST_HOURS": ConversationEvent.REQUEST_MENU_INFO,
                "REQUEST_HUMAN": ConversationEvent.REQUEST_ESCALATION,
                "GENERAL_QUESTION": None
            },
            ConversationState.ORDERING: {
                "ADD_ITEM": None,  # Handled by cart agent
                "REMOVE_ITEM": None,  # Handled by cart agent
                "MODIFY_ITEM": None,  # Handled by cart agent
                "REQUEST_MENU": ConversationEvent.REQUEST_MENU_QUERY,
                "COMPLETE_ORDER": ConversationEvent.COMPLETE_ORDER,
                "CANCEL_ORDER": ConversationEvent.CANCEL_ORDER,
                "REQUEST_CANCELLATION": ConversationEvent.USER_REQUESTS_CANCELLATION
            },
            ConversationState.VALIDATION: {
                "CONFIRM": ConversationEvent.VALIDATE_ORDER,
                "REQUEST_CHANGE": ConversationEvent.MODIFY_ORDER,
                "REQUEST_REPEAT": None,
                "CANCEL": ConversationEvent.CANCEL_ORDER,
                "REQUEST_ADD_MORE": ConversationEvent.REQUEST_ADD_MORE_ITEMS
            },
            ConversationState.CONFIRMATION: {
                "CONFIRM_ORDER": ConversationEvent.CONFIRM_ORDER,
                "MODIFY_ORDER": ConversationEvent.MODIFY_ORDER,
                "CANCEL_ORDER": ConversationEvent.REJECT_ORDER,
                "REQUEST_INFO": None
            },
            ConversationState.FULFILLMENT: {
                "PROVIDE_DELIVERY": ConversationEvent.PROVIDE_DELIVERY_INFO,
                "CHOOSE_PICKUP": ConversationEvent.CHOOSE_PICKUP,
                "PROVIDE_PAYMENT": ConversationEvent.PROVIDE_DELIVERY_INFO,  # Using delivery info for payment
                "REQUEST_ESCALATION": ConversationEvent.REQUEST_ESCALATION
            },
            ConversationState.CANCELLATION_PENDING: {
                "CONFIRM_CANCELLATION": ConversationEvent.CONFIRM_CANCELLATION,
                "DECLINE_CANCELLATION": ConversationEvent.DECLINE_CANCELLATION,
                "YES": ConversationEvent.CONFIRM_CANCELLATION,
                "NO": ConversationEvent.DECLINE_CANCELLATION
            },
            ConversationState.MENU_QUERY_SUBSTATE: {
                "QUERY_COMPLETE": ConversationEvent.MENU_QUERY_RESOLVED,
                "CONTINUE": ConversationEvent.MENU_QUERY_RESOLVED
            }
        }
        
        # Get mapping for current state
        mapping = state_mappings.get(current_state, {})
        event = mapping.get(intent)
        
        if event:
            logger.info(f"Mapped intent {intent} to event {event.name}")
        else:
            logger.info(f"No event mapping for intent {intent} in state {current_state.name}")
            
        return event
    
    def _map_global_command_to_event(self, command: GlobalCommand) -> Optional[ConversationEvent]:
        """Map global command to FSM event."""
        # Global commands that map to existing events
        command_to_event = {
            GlobalCommand.CANCEL: ConversationEvent.CANCEL_ORDER,
            GlobalCommand.HELP: ConversationEvent.REQUEST_ESCALATION,
            # REPEAT, START_OVER, and GO_BACK will be handled specially
            # in the orchestrator, so they don't map to events
        }
        return command_to_event.get(command)
    
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