"""
Functions for order analysis and modifications.
"""

import json
import logging
import openai
from typing import Dict, List, Any, Tuple

from app.utils.agent.config import OPENAI_API_KEY
from app.utils.agent.logging import log_openai_request, log_openai_response

logger = logging.getLogger(__name__)

def analyze_user_input(input_text: str) -> Dict[str, Any]:
    """
    Analyze user input for order confirmation and other intents.
    
    Args:
        input_text: User input text
        
    Returns:
        dict: Analysis results with detected intents
    """
    if not OPENAI_API_KEY:
        logger.warning("[ANALYZE] No OpenAI API key available for input analysis")
        # Simple fallback without AI
        input_lower = input_text.lower()
        return {
            "confirmed": "yes" in input_lower or "okay" in input_lower or "correct" in input_lower,
            "denied": "no" in input_lower or "wrong" in input_lower or "incorrect" in input_lower,
            "confidence": "low"
        }
    
    try:
        system_msg = (
            "You are an AI that analyzes customer responses in a restaurant ordering context. "
            "Your task is to determine if the user is confirming or denying something, or if "
            "they are requesting additional changes to their order. Return your analysis as JSON."
        )
        
        prompt = f"Analyze this customer response: '{input_text}'"
        
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt}
        ]
        
        # Log the request
        log_openai_request("gpt-4.1-mini", messages, "analyze_user_input")
        
        response = openai.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            temperature=0.2,
            max_tokens=150,
            response_format={"type": "json_object"}
        )
        
        # Log the response
        log_openai_response(response, "analyze_user_input")
        
        # Parse the JSON response
        result = json.loads(response.choices[0].message.content)
        
        # Ensure required fields are present
        if "confirmed" not in result:
            result["confirmed"] = False
        if "denied" not in result:
            result["denied"] = False
        
        logger.info(f"[ANALYZE] Input '{input_text}' analyzed: confirmed={result['confirmed']}, denied={result['denied']}")
        return result
        
    except Exception as e:
        logger.error(f"[ANALYZE-ERROR] Error analyzing input: {str(e)}")
        # Fallback with simple pattern matching
        input_lower = input_text.lower()
        return {
            "confirmed": "yes" in input_lower or "okay" in input_lower or "correct" in input_lower,
            "denied": "no" in input_lower or "wrong" in input_lower or "incorrect" in input_lower,
            "error": str(e),
            "confidence": "fallback"
        }

def get_order_modifications(order: Dict[str, Any], modification_text: str) -> Tuple[Dict[str, Any], str]:
    """
    Process natural language modifications to an existing order.
    
    Args:
        order: The current order
        modification_text: User's requested modifications
        
    Returns:
        tuple: (modified_order, explanation) with the updated order and explanation of changes
    """
    if not OPENAI_API_KEY:
        logger.warning("[MODIFY] No OpenAI API key available for order modification")
        # Return original order with explanation
        return order, "Sorry, I couldn't process the modifications at this time."
    
    try:
        # Prepare the current order as a string for the prompt
        order_summary = "Current order:\n"
        for idx, item in enumerate(order.get("items", [])):
            item_name = item.get("name", "Unknown item")
            quantity = item.get("quantity", 1)
            
            order_summary += f"{idx+1}. {quantity}x {item_name}"
            
            # Add modifiers if any
            modifiers = item.get("modifier", [])
            if modifiers:
                mod_strings = []
                for mod in modifiers:
                    mod_name = mod.get("name", "Unknown modifier")
                    mod_qty = mod.get("quantity", 1)
                    if mod_qty > 1:
                        mod_strings.append(f"{mod_qty}x {mod_name}")
                    else:
                        mod_strings.append(mod_name)
                
                if mod_strings:
                    order_summary += f" with {', '.join(mod_strings)}"
            
            order_summary += "\n"
        
        system_msg = (
            "You are an AI assistant helping with restaurant orders. "
            "Your task is to apply customers' modification requests to their existing order. "
            "Modifications may include: adding items, removing items, changing quantities, "
            "adding modifiers, removing modifiers, or changing modifiers. "
            "Return the modified order in JSON format, and a brief explanation of the changes made."
        )
        
        prompt = f"{order_summary}\n\nCustomer wants to modify this order: '{modification_text}'\n\n"
        prompt += "Please describe what changes should be made to the order."
        
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt}
        ]
        
        # Log the request
        log_openai_request("gpt-4.1-mini", messages, "get_order_modifications")
        
        response = openai.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages,
            temperature=0.3,
            max_tokens=500
        )
        
        # Log the response
        log_openai_response(response, "get_order_modifications")
        
        # Get the explanation of changes from the response
        explanation = response.choices[0].message.content.strip()
        logger.info(f"[MODIFY] Modification result: {explanation[:100]}...")
        
        # Now get the actual modified order structure
        system_msg_json = (
            "You are an AI assistant helping with restaurant orders. "
            "Take the original order JSON and the requested modifications, and return "
            "the modified order as valid JSON matching the original structure."
        )
        
        prompt_json = f"Original order: {json.dumps(order)}\n\n"
        prompt_json += f"Requested modifications: '{modification_text}'\n\n"
        prompt_json += "Apply these modifications and return the modified order as JSON."
        
        messages_json = [
            {"role": "system", "content": system_msg_json},
            {"role": "user", "content": prompt_json}
        ]
        
        # Log the request for JSON modification
        log_openai_request("gpt-4.1-mini", messages_json, "get_order_modifications_json")
        
        response_json = openai.chat.completions.create(
            model="gpt-4.1-mini",
            messages=messages_json,
            temperature=0.2,
            max_tokens=1000,
            response_format={"type": "json_object"}
        )
        
        # Log the response for JSON modification
        log_openai_response(response_json, "get_order_modifications_json")
        
        # Parse the modified order
        modified_order = json.loads(response_json.choices[0].message.content)
        
        # Verify the structure is maintained
        if "items" not in modified_order:
            logger.warning("[MODIFY] Modified order missing 'items' key, using original order")
            return order, "I couldn't properly modify your order. Please try again with clearer instructions."
        
        logger.info(f"[MODIFY] Successfully modified order with {len(modified_order['items'])} items")
        return modified_order, explanation
        
    except Exception as e:
        logger.error(f"[MODIFY-ERROR] Error modifying order: {str(e)}")
        # Return original order with explanation
        return order, f"Sorry, I encountered an error while modifying your order: {str(e)}"