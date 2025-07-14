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
from app.utils.metrics_logger import log_intent_confidence
from app.services.alerting import alert_low_confidence_pattern

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
            
        # First check for global commands using AI
        global_cmd, confidence = await global_command_detector.detect_command(transcript)
        threshold = settings.GLOBAL_COMMAND_CONFIDENCE_THRESHOLD
        
        # Log global command confidence for monitoring
        if global_cmd != GlobalCommand.NONE:
            log_intent_confidence(
                confidence=confidence,
                intent=f"global_command_{global_cmd.value}",
                call_sid=context.get("call_sid"),
                state=current_state
            )
            
            # Alert on low confidence patterns
            if confidence < settings.LOW_CONFIDENCE_ALERT_THRESHOLD:
                import asyncio
                asyncio.create_task(alert_low_confidence_pattern(
                    confidence=confidence,
                    threshold=settings.LOW_CONFIDENCE_ALERT_THRESHOLD,
                    metadata={
                        "intent": f"global_command_{global_cmd.value}",
                        "state": current_state,
                        "transcript": transcript[:100]  # Truncate for privacy
                    },
                    call_sid=context.get("call_sid")
                ))
        
        if global_cmd != GlobalCommand.NONE and confidence >= threshold:
            # Map global commands to events
            global_event = self._map_global_command_to_event(global_cmd)
            if global_event:
                logger.info(
                    f"Global command detected: {global_cmd.value} -> event: {global_event.name} (confidence: {confidence})"
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
    
    def _build_system_prompt(self, current_state: str) -> str:
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
- USER_PROVIDES_NAME: User is providing their name in response to greeting
- START_ORDER: User wants to skip name and proceed directly to ordering
- REQUEST_ESCALATION: User is confused or requesting help

Use AI intelligence to analyze if the user is giving their name or trying to proceed with ordering.
""",
            
            "MAIN_MENU": """
Allowed intents:
- START_ORDER: User wants to place an order or add items to cart
- REQUEST_MENU_INFO: User wants information about menu items, categories, or prices
- REQUEST_ESCALATION: User wants to speak to a human or needs assistance
- REQUEST_FOLLOW_UP: User has questions or is asking for clarification about something

Use AI intelligence to determine user intent from context and conversational flow.
""",
            
            "ORDERING": """
Allowed intents:
- ADD_ITEM: User is adding items to their order
- REMOVE_ITEM: User wants to remove something from order
- MODIFY_ITEM: User wants to change quantity, preparation, or modifiers
- REQUEST_MENU_INFO: User asking about menu items while ordering
- COMPLETE_ORDER: User indicates they are finished ordering
- USER_REQUESTS_CANCELLATION: User wants to cancel the entire order

Use AI intelligence to understand ordering intent from natural language.
""",
            
            "VALIDATION": """
Allowed intents:
- ORDER_VALID: User confirms the order is correct as stated
- ORDER_INVALID: User wants to modify, change, or correct something
- REQUEST_ESCALATION: User needs assistance or clarification

Use AI intelligence to determine if user is confirming or requesting changes.
""",
            
            "CONFIRMATION": """
Allowed intents:
- CONFIRM_ORDER: User confirms order and wants to proceed to fulfillment
- MODIFY_ORDER: User wants to make changes before finalizing
- REJECT_ORDER: User wants to cancel the order
- REQUEST_ESCALATION: User has questions or needs help

Use AI intelligence to understand final confirmation intent.
""",
            
            "FULFILLMENT": """
Allowed intents:
- PROVIDE_DELIVERY_INFO: User providing delivery address or information
- CHOOSE_PICKUP: User selecting pickup instead of delivery
- COMPLETE_INTERACTION: User is satisfied and ready to end conversation
- REQUEST_ESCALATION: User needs assistance with fulfillment

Use AI intelligence to understand fulfillment and completion intent.
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
    
    async def detect_go_back_intent(self, transcript: str) -> Optional[Dict[str, Any]]:
        """
        Detect enhanced go back intent with target state extraction.
        
        Args:
            transcript: User's spoken text
            
        Returns:
            Dict with go_back info or None if not detected
        """
        if not transcript.strip():
            return None
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are analyzing user input for enhanced navigation commands in a restaurant ordering system.

Detect if the user wants to go back to a specific state or step. Analyze these patterns:
1. "go back to ordering" → target specific state
2. "go back 2 steps" → target number of steps  
3. "return to main menu" → target specific state
4. "take me back to the beginning" → target specific state

Return ONLY a JSON object:
{
  "intent": "GO_BACK_TO_STATE" | "GO_BACK_STEPS" | "NONE",
  "target_state": "ORDERING" | "MAIN_MENU" | "GREETING" | null,
  "steps": number | null,
  "confidence": 0.0-1.0
}

State mappings:
- "ordering", "order", "items" → "ORDERING"
- "main menu", "menu", "beginning", "start" → "MAIN_MENU"
- "greeting", "introduction" → "GREETING"
- Numbers like "2", "two", "three" → steps count"""
                    },
                    {
                        "role": "user",
                        "content": transcript
                    }
                ],
                temperature=0.1,
                max_tokens=100
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Parse JSON response
            import json
            result = json.loads(result_text)
            
            if result.get("intent") == "NONE":
                return None
            
            return result
            
        except Exception as e:
            logger.error(f"Error detecting go back intent: {e}")
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
        return await global_command_detector.detect_command(transcript)

async def detect_confirmation_intent(transcript: str) -> Dict[str, Any]:
    """
    Detect confirmation intent using AI intelligence.
    
    Args:
        transcript: User's spoken text
        
    Returns:
        Dict with 'confirmed' boolean and 'confidence' float
    """
    if not transcript.strip():
        return {"confirmed": False, "confidence": 0.0}
    
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """You are a confirmation intent detector for restaurant orders. 
                    
Analyze the user's response and determine if they are confirming their order or not.

Return ONLY a JSON object with:
{"confirmed": true/false, "confidence": 0.0-1.0}

Examples:
- "Yes, that's right" → {"confirmed": true, "confidence": 0.95}
- "No, I want to change it" → {"confirmed": false, "confidence": 0.9}
- "Sounds good" → {"confirmed": true, "confidence": 0.85}
- "Wait, actually..." → {"confirmed": false, "confidence": 0.8}
- "Hmm, maybe" → {"confirmed": false, "confidence": 0.3}"""
                },
                {
                    "role": "user",
                    "content": transcript
                }
            ],
            temperature=0.1,
            max_tokens=50
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Parse JSON response
        import json
        result = json.loads(result_text)
        
        return {
            "confirmed": result.get("confirmed", False),
            "confidence": result.get("confidence", 0.0)
        }
        
    except Exception as e:
        logger.error(f"Error detecting confirmation intent: {e}")
        return {"confirmed": False, "confidence": 0.0}

# Singleton instance
intent_detector = AsyncIntentDetector()

# For backward compatibility with tests
async_intent_detector = intent_detector