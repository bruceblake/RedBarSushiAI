"""
Async Validation Agent for RedBarSushiAI.

This agent acts as a final checkpoint before order confirmation, ensuring
all business rules are met and required selections are complete.
"""

import logging
from typing import Dict, Any, List, Optional

from app.agents.base_async import BaseAsyncAgent
from app.agents.ai_mixin import AIIntelligenceMixin
from app.services.deliverect_service import deliverect_service
from app.utils.enhanced_logging import get_logger
from app.config import settings

logger = get_logger(__name__)


class AsyncValidationAgent(BaseAsyncAgent, AIIntelligenceMixin):
    """
    Validation specialist that analyzes orders for completeness and business rule compliance.
    
    This agent:
    - Validates required modifier selections
    - Checks business rules and constraints
    - Identifies missing or invalid order components
    - Provides specific remediation instructions
    """
    
    def __init__(self, agent_id: Optional[str] = None, **kwargs):
        """Initialize the validation agent."""
        BaseAsyncAgent.__init__(self, agent_id=agent_id, name="ValidationAgent", **kwargs)
        AIIntelligenceMixin.__init__(self)
        
        # Set agent-specific max tokens
        self._default_max_tokens = getattr(settings, 'VALIDATION_AGENT_MAX_TOKENS', 128)
        
        self.instructions = f"""
        You are a validation specialist for {settings.RESTAURANT_NAME}. Your job is to analyze 
        a customer's cart and identify any issues based on business rules and item requirements 
        using the tools provided.
        
        CRITICAL RESPONSIBILITIES:
        1. Ensure all required modifier selections are complete
        2. Validate business rules and constraints
        3. Identify missing required choices
        4. Provide clear remediation instructions
        5. Maintain order accuracy and completeness
        
        Be thorough but efficient. Focus on critical validation issues that would 
        prevent successful order processing.
        """
        
        # Define validation tools
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "validate_order_for_checkout",
                    "description": "Validate a complete order against menu requirements and business rules",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "cart": {
                                "type": "object",
                                "description": "The cart object containing all order items and details"
                            }
                        },
                        "required": ["cart"]
                    }
                }
            },
            {
                "type": "function", 
                "function": {
                    "name": "validate_single_item",
                    "description": "Validate a single item for completeness and requirements",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item": {
                                "type": "object",
                                "description": "The item object to validate"
                            }
                        },
                        "required": ["item"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_allergen_conflicts",
                    "description": "Check for potential allergen conflicts in the order",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "cart": {
                                "type": "object",
                                "description": "The cart to check for allergen conflicts"
                            },
                            "allergens": {
                                "type": "array",
                                "description": "List of allergens to check against",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["cart"]
                    }
                }
            }
        ]
    
    async def process_input(self, input_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process validation requests using AI and validation tools."""
        context = context or {}
        
        logger.info(f"[{self.name}] Processing validation request: {input_text}")
        
        # Use AI to understand and process the validation request
        response = await self.process_with_ai(input_text, context)
        
        return response
    
    async def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute validation tools."""
        logger.info(f"[{self.name}] Executing tool: {tool_name} with args: {args}")
        
        try:
            if tool_name == "validate_order_for_checkout":
                return await self._validate_order_for_checkout(args.get("cart", {}))
                
            elif tool_name == "validate_single_item":
                return await self._validate_single_item(args.get("item", {}))
                
            elif tool_name == "check_allergen_conflicts":
                return await self._check_allergen_conflicts(
                    args.get("cart", {}),
                    args.get("allergens", [])
                )
                
            else:
                return {"error": f"Tool '{tool_name}' not found in ValidationAgent."}
                
        except Exception as e:
            logger.error(f"Validation tool execution error: {e}")
            return {"error": str(e)}
    
    async def _validate_order_for_checkout(self, cart: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates a complete cart against menu requirements and business rules.
        
        Args:
            cart: The cart object containing all order items
            
        Returns:
            Dict with validation results including any issues found
        """
        logger.info("Validating complete order for checkout")
        
        issues = []
        cart_items = cart.get("items", [])
        
        if not cart_items:
            return {
                "is_valid": False,
                "issues": [{
                    "issue_type": "EMPTY_CART",
                    "message": "Cart is empty. Please add items before checkout.",
                    "remediation_prompt": "What would you like to order?"
                }]
            }
        
        # Validate each item in the cart
        for item_index, item in enumerate(cart_items):
            item_plu = item.get('plu') or item.get('menu_item_plu')
            
            if not item_plu:
                logger.warning(f"Item missing PLU: {item}")
                continue
            
            # Get product details from cache
            try:
                product = await deliverect_service.get_cached_product(item_plu)
                
                if not product:
                    logger.warning(f"Product not found in cache: {item_plu}")
                    continue
                
                # Check if item is available
                if product.snoozed:
                    issues.append({
                        "issue_type": "ITEM_UNAVAILABLE",
                        "item_name": item.get('name', product.name),
                        "item_index": item_index,
                        "message": f"The item '{product.name}' is currently unavailable.",
                        "remediation_prompt": f"I'm sorry, '{product.name}' is not available right now. Would you like to choose something else?",
                        "context": {"item_plu": item_plu}
                    })
                    continue
                
                # Validate required modifiers
                for group_plu in product.sub_products:
                    group = await deliverect_service.get_cached_modifier_group(group_plu)
                    
                    if group and group.min_selection > 0:
                        # Count selected modifiers from this group
                        item_modifiers = item.get('modifiers', [])
                        selected_count = 0
                        
                        for modifier in item_modifiers:
                            modifier_plu = modifier.get('plu') if isinstance(modifier, dict) else modifier
                            if modifier_plu in group.sub_products:
                                selected_count += 1
                        
                        if selected_count < group.min_selection:
                            # Get available modifier names for the prompt
                            available_modifiers = []
                            for mod_plu in group.sub_products[:3]:  # Limit to first 3 for readability
                                modifier = await deliverect_service.get_cached_modifier(mod_plu)
                                if modifier and not modifier.snoozed:
                                    available_modifiers.append(modifier.name)
                            
                            issues.append({
                                "issue_type": "MISSING_REQUIRED_MODIFIER",
                                "item_name": item.get('name', product.name),
                                "item_index": item_index,
                                "group_name": group.name,
                                "required_count": group.min_selection,
                                "selected_count": selected_count,
                                "message": f"The item '{product.name}' is missing a required selection from '{group.name}'.",
                                "remediation_prompt": f"For the '{product.name}', what would you like for the '{group.name}'? You can choose from: {', '.join(available_modifiers)}.",
                                "available_options": available_modifiers,
                                "context": {
                                    "item_plu": item_plu,
                                    "group_plu": group_plu,
                                    "item_index": item_index
                                }
                            })
                
                # Check maximum modifier limits
                for group_plu in product.sub_products:
                    group = await deliverect_service.get_cached_modifier_group(group_plu)
                    
                    if group and group.max_selection > 0:
                        # Count selected modifiers from this group
                        item_modifiers = item.get('modifiers', [])
                        selected_count = 0
                        
                        for modifier in item_modifiers:
                            modifier_plu = modifier.get('plu') if isinstance(modifier, dict) else modifier
                            if modifier_plu in group.sub_products:
                                selected_count += 1
                        
                        if selected_count > group.max_selection:
                            issues.append({
                                "issue_type": "TOO_MANY_MODIFIERS",
                                "item_name": item.get('name', product.name),
                                "item_index": item_index,
                                "group_name": group.name,
                                "max_allowed": group.max_selection,
                                "selected_count": selected_count,
                                "message": f"The item '{product.name}' has too many selections from '{group.name}' (max: {group.max_selection}).",
                                "remediation_prompt": f"For the '{product.name}', please choose only {group.max_selection} option(s) from '{group.name}'.",
                                "context": {
                                    "item_plu": item_plu,
                                    "group_plu": group_plu,
                                    "item_index": item_index
                                }
                            })
                
            except Exception as e:
                logger.error(f"Error validating item {item_plu}: {e}")
                continue
        
        # Return validation results
        is_valid = len(issues) == 0
        
        logger.info(f"Order validation complete: {is_valid}, {len(issues)} issues found")
        
        return {
            "is_valid": is_valid,
            "issues": issues,
            "total_items": len(cart_items),
            "issues_count": len(issues)
        }
    
    async def _validate_single_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a single item for completeness and requirements.
        
        Args:
            item: The item object to validate
            
        Returns:
            Dict with validation results for the single item
        """
        logger.info(f"Validating single item: {item.get('name')}")
        
        # Use the same logic as the full cart validation but for a single item
        mock_cart = {"items": [item]}
        result = await self._validate_order_for_checkout(mock_cart)
        
        return result
    
    async def _check_allergen_conflicts(self, cart: Dict[str, Any], allergens: List[str] = None) -> Dict[str, Any]:
        """
        Check for potential allergen conflicts in the order.
        
        Args:
            cart: The cart to check
            allergens: List of allergens to check against
            
        Returns:
            Dict with allergen conflict results
        """
        logger.info(f"Checking allergen conflicts for: {allergens}")
        
        # Placeholder implementation - in production this would check product tags
        # against known allergen mappings
        conflicts = []
        
        try:
            for item in cart.get("items", []):
                item_plu = item.get('plu') or item.get('menu_item_plu')
                
                if item_plu:
                    product = await deliverect_service.get_cached_product(item_plu)
                    
                    if product and allergens:
                        # Check product tags for allergen indicators
                        # This would need a mapping of product_tags to allergens
                        # For now, we'll do a simple name-based check
                        item_name_lower = product.name.lower()
                        
                        for allergen in allergens:
                            allergen_lower = allergen.lower()
                            
                            # Simple keyword matching (would be more sophisticated in production)
                            if (allergen_lower in ['nuts', 'peanuts'] and any(word in item_name_lower for word in ['peanut', 'almond', 'walnut'])) or \
                               (allergen_lower in ['dairy', 'milk'] and any(word in item_name_lower for word in ['cheese', 'cream', 'milk'])) or \
                               (allergen_lower == 'gluten' and any(word in item_name_lower for word in ['bread', 'noodle', 'tempura'])):
                                
                                conflicts.append({
                                    "item_name": product.name,
                                    "allergen": allergen,
                                    "warning": f"'{product.name}' may contain {allergen}. Please verify with staff."
                                })
        
        except Exception as e:
            logger.error(f"Error checking allergen conflicts: {e}")
        
        return {
            "has_conflicts": len(conflicts) > 0,
            "conflicts": conflicts,
            "allergens_checked": allergens or []
        }