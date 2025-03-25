"""
Order utility functions for handling orders.
This module provides minimal utility functions for order processing.
"""
import re
from typing import List, Dict, Any
from flask import session

# Simple helper functions for voice interactions

def user_said_yes(text: str) -> bool:
    """Check if user's input is affirmative."""
    if not text:
        return False
        
    text = text.lower().strip()
    
    # Simple pattern matching for yes responses
    affirmatives = ["yes", "yeah", "yep", "correct", "right", "confirm", 
                    "confirmed", "okay", "ok", "good", "sure", "exactly"]
    return any(word in text for word in affirmatives)

def user_said_no(text: str) -> bool:
    """Check if user's input is negative."""
    if not text:
        return False
        
    text = text.lower().strip()
    
    # Simple pattern matching for no responses
    negatives = ["no", "nope", "nah", "not correct", "that's wrong", "incorrect"]
    return any(word in text for word in negatives)

def dtmf_yes_no(dtmf: str) -> str:
    """Convert DTMF input to yes/no."""
    if dtmf == "1":
        return "yes"
    elif dtmf == "2":
        return "no"
    return None

def build_order_description(order_items: List[Dict[str, Any]]) -> str:
    """Build a text description of the order."""
    description = []
    for item in order_items:
        quantity = item.get("quantity", 1)
        name = item.get("name", "unknown item")
        modifiers = item.get("modifier", [])
        
        if not modifiers:
            description.append(f"- {quantity} {name}")
        else:
            mods = ", ".join([f"{mod.get('quantity', 1)} {mod.get('name','')}" for mod in modifiers])
            description.append(f"- {quantity} {name} with {mods}")
            
    return "\n".join(description)

def calculate_bill_amount(order_items: List[Dict[str, Any]], tax_rate: float = 0.0) -> float:
    """Calculate the total bill amount for the order."""
    subtotal = 0.0
    
    for item in order_items:
        price = item.get("price", 0.0)
        quantity = item.get("quantity", 1)
        item_total = price * quantity
        
        # Add modifier costs
        for mod in item.get("modifier", []):
            mod_price = mod.get("price", 0.0)
            mod_quantity = mod.get("quantity", 1)
            item_total += mod_price * mod_quantity
        
        subtotal += item_total
    
    # Calculate tax
    tax_amount = subtotal * tax_rate if tax_rate > 0 else 0.0
    
    # Calculate total
    total = subtotal + tax_amount
    
    # Store in session
    try:
        session['subtotal'] = round(subtotal, 2)
        session['tax_amount'] = round(tax_amount, 2)
        session['total_price'] = round(total, 2)
    except RuntimeError:
        # Not in request context
        pass
    
    return round(total, 2)