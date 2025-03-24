import json
import logging
import Levenshtein
from flask import session
# Ensure this function is defined in your helpers module
from app.utils.helpers import log_info
from app.utils.menu_utils import validate_modifier_constraints, process_meal_deal

# --- Analyze User Input using OpenAI ---


def analyze_user_input(user_input):
    """
    Uses the OpenAI API to analyze the user's input and extract an intent and any relevant entities.
    The AI is instructed to output valid JSON with an "intent" and, if ordering, a list of menu items.
    """
    import openai
    from app.config import OPENAI_API_KEY
    
    try:
        openai.api_key = OPENAI_API_KEY
        log_info(f"API Key: {'Valid' if OPENAI_API_KEY else 'Missing'}")
        
        log_info(f"Analyzing user input for intent/entities: {user_input}")

        system_prompt = (
            "You are an AI assistant for a restaurant. "
            "Analyze the customer's message and do two things:\n"
            "1) Provide an intent from [order_food, ask_menu, provide_name, list_menu_items, "
            "get_menu_item_price, describe_menu_item, modify_order, other].\n"
            "2) If intent is 'order_food', parse the items in a JSON format with the following structure:\n"
            "{\n"
            '  "intent": "order_food",\n'
            '  "menu_items": [\n'
            '    {"name": "Chicken Sate", "quantity": 1, "modifier": [\n'
            '       {"name": "White Rice", "quantity": 1}\n'
            '     ]}\n'
            '  ],\n'
            '  "caller_name": "John Doe"\n'
            "}\n"
            "IMPORTANT: DO NOT include prices in the response. Our system will automatically look up the "
            "correct prices from our menu database. If you include prices, they will be ignored and may cause problems.\n"
            "Make sure to include items and any modifiers with their quantities, but no prices. "
            "Modifiers should be attached to the base food item. Only output valid JSON and nothing else. "
            "If intent is unknown but there are common food items then the intent is most likely order_food"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]
        
        try:
            log_info("Making OpenAI API call...")
            response = openai.chat.completions.create(
                model="gpt-4o-2024-11-20",
                messages=messages,
                max_tokens=500,
                temperature=0.0
            )
            log_info("OpenAI API call successful")
            
            reply = response.choices[0].message.content.strip()
            log_info(f"OpenAI raw response: {reply}")
            
            data = json.loads(reply)
            log_info(f"OpenAI analysis: {data}")
            return data
            
        except json.JSONDecodeError as je:
            log_info(f"JSON decode error: {je}, Response: {reply}")
            return {"intent": "other"}
            
        except Exception as e:
            log_info(f"OpenAI call error: {str(e)}")
            return {"intent": "other"}
    except Exception as e:
        log_info(f"Overall OpenAI error: {str(e)}")
        return {"intent": "other"}


# --- Functions to Interpret User Speech/DTMF Input ---

def user_said_yes(u):
    """
    Checks if the user's input contains an affirmative phrase.
    """
    affirmatives = ["yes", "yeah", "yep", "correct",
                    "that's right", "sure", "ok", "okay", "sounds good"]
    return any(a in u.lower() for a in affirmatives)


def user_said_no(u):
    """
    Checks if the user's input contains a negative phrase.
    """
    negatives = ["no", "nope", "nah", "not correct", "that's not right", "that's incorrect", "make changes", "need changes"]
    return any(n in u.lower() for n in negatives)


def dtmf_yes_no(digit):
    """
    Interprets DTMF (touch-tone) input: '1' for yes, '2' for no.
    """
    if digit == '1':
        return "yes"
    elif digit == '2':
        return "no"
    return None


# --- Order-Related Utility Functions ---

def build_order_description(order_items):
    """
    Builds a textual description of the order based on the list of items.
    """
    description = "You ordered:\n"
    for item in order_items:
        quantity = item.get("quantity", 1)
        modifiers = item.get("modifier", [])
        if not modifiers:
            description += f"- {quantity} {item['name']}\n"
        else:
            mods = ", ".join(
                [f"{mod.get('quantity', 1)} {mod.get('name','')}" for mod in modifiers])
            description += f"- {quantity} {item['name']} with {mods}\n"
    return description


def calculate_bill_amount(order_items, tax_rate=0.0):
    """
    Calculates the total bill amount based on order items.
    Stores the total in the session.
    
    Args:
        order_items: List of order items with quantities and prices
        tax_rate: Optional sales tax rate as a decimal (e.g., 0.08 for 8%)
    """
    subtotal = 0.0
    for item in order_items:
        # Get a verified price from the menu for this item
        item_name = item.get("name", "")
        price_value = item.get("price")
        
        # ALWAYS verify with the menu data regardless of what price was provided
        from app.utils.menu_utils import verify_and_update_menu_item
        
        # Debug print original values before verification
        log_info(f"DEBUG - BEFORE VERIFICATION - Item: {item_name}, Original price: {price_value}")
        
        # Use our improved verification system always, regardless of the original price
        verified_data = verify_and_update_menu_item(item_name, item)
        
        # Update the item with verified data
        item["price"] = verified_data.get("price")
        item["reference_handler"] = verified_data.get("reference_handler")
        base_price = item["price"]
        
        # Debug what happened during verification
        log_info(f"DEBUG - AFTER VERIFICATION - Item {item_name} price updated to {base_price}, ref: {item['reference_handler']}")
                
        # Log the price for debugging
        log_info(f"Item: {item.get('name')}, Original price: {price_value}, Used price: {base_price}")
        
        quantity = item.get("quantity", 1)
        item_total = base_price * quantity
        
        # Add modifier costs
        for mod in item.get("modifier", []):
            # Handle modifier prices - simpler approach since modifiers often have 0 price
            mod_price_value = mod.get("price")
            if mod_price_value is None:
                mod_price = 0.0
            else:
                try:
                    mod_price = float(mod_price_value)
                except (ValueError, TypeError):
                    mod_price = 0.0
                    
            mod_quantity = mod.get("quantity", 1)
            item_total += mod_price * mod_quantity
            
        subtotal += item_total
    
    # Store the subtotal
    session['subtotal'] = round(subtotal, 2)
    
    # Calculate and store tax amount if applicable
    tax_amount = 0.0
    if tax_rate > 0:
        tax_amount = subtotal * tax_rate
        session['tax_amount'] = round(tax_amount, 2)
    
    # Calculate final total with tax
    total = subtotal + tax_amount
    
    # Round to avoid floating point issues
    session['total_price'] = round(total, 2)


def find_menu_item(user_input, threshold=35):
    """
    Searches for a menu item whose name best matches the user input.
    Uses Levenshtein distance to compute a match if an exact match is not found.
    """
    from app.utils.menu_utils import load_menu_data
    data = load_menu_data()
    all_items = data.get("items", [])
    user_lower = user_input.lower().strip()
    
    # Debug the search
    log_info(f"Searching for menu item: '{user_input}', lowercase: '{user_lower}'")
    
    # Check for an exact match first.
    for item in all_items:
        item_name = item.get("name", "")
        if not item_name:  # Skip items with no name
            continue
            
        if item_name.lower() == user_lower:
            log_info(f"Found exact match for '{user_input}': '{item_name}'")
            return item, 0
            
    # Fuzzy search: find the best match.
    best_item = None
    best_distance = 9999
    for item in all_items:
        item_name = item.get("name", "")
        if not item_name:  # Skip items with no name
            continue
            
        distance = Levenshtein.distance(user_lower, item_name.lower())
        log_info(f"Distance between '{user_lower}' and '{item_name.lower()}': {distance}")
        if distance < best_distance:
            best_distance = distance
            best_item = item
            
    if best_item and best_distance <= threshold:
        log_info(f"Found fuzzy match for '{user_input}': '{best_item.get('name')}' with distance {best_distance}")
        return best_item, best_distance
        
    log_info(f"No match found for '{user_input}'")
    return None, None


def find_menu_item_any_status(user_input, threshold=35):
    """
    Wrapper for find_menu_item that ignores availability status.
    """
    return find_menu_item(user_input, threshold)


def get_verified_menu_price(item_name, default_price=7.5):
    """
    Get the correct price for a menu item directly from the menu data.
    This ensures we always use menu-defined prices rather than prices from API responses.
    
    Args:
        item_name: The name of the menu item
        default_price: Default price to use if item not found or has no price
    
    Returns:
        float: The verified price from the menu data
    """
    from app.utils.menu_utils import verify_and_update_menu_item
    
    # Use our centralized verification function
    try:
        verified_data = verify_and_update_menu_item(item_name, {"name": item_name})
        price = verified_data.get("price", default_price)
        log_info(f"Verified menu price for {item_name}: ${price}")
        return float(price)
    except Exception as e:
        log_info(f"Error getting verified menu price: {e}")
    
    # If all else fails, return the default price
    log_info(f"Using default price for {item_name}: ${default_price}")
    return default_price
