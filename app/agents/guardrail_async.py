"""
Async Guardrail Agent for validating orders in RedBarSushiAI.

This agent enforces business rules and validates orders against constraints
such as item availability, modifier selection limits, and other business policies.
"""

import logging
from typing import Dict, Any, Optional, List
from app.agents.base_async import BaseAsyncAgent

logger = logging.getLogger(__name__)

class AsyncGuardrailAgent(BaseAsyncAgent):
    """
    Async agent for validating orders against business rules and constraints.
    
    This agent ensures that orders meet all validation criteria before
    they can proceed to fulfillment. It checks:
    - Item availability
    - Modifier constraints (min/max selections)
    - Item snooze status
    - Business rule compliance
    """
    
    def __init__(self, agent_name: str = "GuardrailAgent", **kwargs):
        """Initialize the guardrail agent."""
        super().__init__(agent_name=agent_name, **kwargs)
        logger.info(f"AsyncGuardrailAgent initialized with name: {self.agent_name}")
        self._db_session = None

    async def initialize(self):
        """Initialize any resources needed by the agent."""
        logger.info(f"AsyncGuardrailAgent: Initializing resources")

    async def validate_order(
        self, 
        call_sid: str, 
        order_details: Dict[str, Any],
        fsm_context_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate an order against business rules and constraints.
        
        Args:
            call_sid: The call session ID
            order_details: The order details to validate
            fsm_context_data: The full FSM context
            
        Returns:
            Dict with validation results and next actions
        """
        logger.info(f"[{call_sid}] AsyncGuardrailAgent: Validating order: {order_details}")
        
        # --- Placeholder for actual validation logic ---
        # This would involve:
        # 1. Checking item availability (perhaps against DB - needs async DB access)
        # 2. Validating modifier selections (min/max choices)
        # 3. Checking against business rules (max order value, delivery zones, etc.)
        # 4. Verifying item snooze status
        
        is_valid = True  # Default to valid
        validation_issues = []  # Collect any issues
        
        # Check if order has items
        if not order_details.get("items"):
            is_valid = False
            validation_issues.append("Your order is empty. Please add some items.")
        
        # Simple validation logic for now - will be replaced with actual DB checks
        items = order_details.get("items", [])
        for item in items:
            # Check if quantity is valid
            quantity = item.get("quantity", 0)
            if quantity <= 0:
                is_valid = False
                validation_issues.append(f"Invalid quantity for {item.get('name', 'unknown item')}.")
                
            # Check modifiers (placeholder)
            modifiers = item.get("modifiers", [])
            for modifier_group in modifiers:
                # Basic modifier validation logic would go here
                pass
        
        # Determine response based on validation
        if is_valid:
            tts_response = "Your order has been validated and looks good!"
            # Signal to FSM that order is valid
            fsm_context_data.get("call_specific_data", {})["next_fsm_event_name"] = "ORDER_VALID"
        else:
            tts_response = f"There are some issues with your order: {'. '.join(validation_issues)}. Please revise your order."
            fsm_context_data.get("call_specific_data", {})["next_fsm_event_name"] = "ORDER_INVALID"
        
        return {
            "text": tts_response,
            "is_valid": is_valid,
            "issues": validation_issues,
            "handled": True,
            "agent": self.agent_name
        }

    async def validate_modifiers(self, item: Dict[str, Any]) -> List[str]:
        """
        Validate that modifier selections meet min/max requirements.
        
        Args:
            item: The item with modifiers to validate
            
        Returns:
            List of validation error messages, empty if valid
        """
        validation_errors = []
        # This would typically check against DB for modifier group rules
        # For now, just return empty list (all valid)
        return validation_errors

    async def process_input(self, input_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process input in the validation state.
        
        This might be called if a user directly interacts while in the VALIDATION state,
        but more likely the ValidationHandler will call validate_order() directly.
        
        Args:
            input_text: User input text
            context: Current FSM context
            
        Returns:
            Response with validation results
        """
        call_sid = context.get("call_sid", "unknown_call")
        logger.info(f"[{call_sid}] AsyncGuardrailAgent process_input called. Input: '{input_text}'")
        
        # Extract order details from context
        order_data_from_context = context.get("call_specific_data", {}).get("current_cart", {})
        
        # Validate the order
        return await self.validate_order(call_sid, order_data_from_context, context)