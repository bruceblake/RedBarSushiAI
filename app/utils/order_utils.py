import json
import logging
import Levenshtein
from flask import session
# Ensure this function is defined in your helpers module
from app.utils.helpers import log_info

# --- Analyze User Input using OpenAI ---


def analyze_user_input(user_input):
    """
    Uses the OpenAI API to analyze the user's input and extract an intent and any relevant entities.
    The AI is instructed to output valid JSON with an "intent" and, if ordering, a list of menu items.
    """
    import openai
    from app.config import OPENAI_API_KEY
    openai.api_key = OPENAI_API_KEY

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
        '       {"name": "White Rice", "quantity": 1, "price": 1.50}\n'
        '     ], "price": 8.00}\n'
        '  ],\n'
        '  "caller_name": "John Doe"\n'
        "}\n"
        "Make sure to include any modifiers and their quantities. "
        "Modifiers should be attached to the base food item. Only output valid JSON and nothing else."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ]
    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=messages,
            max_tokens=500,
            temperature=0.0
        )
        reply = response.choices[0].message.content.strip()
        data = json.loads(reply)
        log_info(f"OpenAI analysis: {data}")
        return data
    except Exception as e:
        log_info(f"OpenAI error: {e}")
        return {"intent": "other"}


# --- Functions to Interpret User Speech/DTMF Input ---

def user_said_yes(u):
    """
    Checks if the user’s input contains an affirmative phrase.
    """
    affirmatives = ["yes", "yeah", "yep", "correct",
                    "that's right", "sure", "ok", "okay"]
    return any(a in u.lower() for a in affirmatives)


def user_said_no(u):
    """
    Checks if the user’s input contains a negative phrase.
    """
    negatives = ["no", "nope", "nah", "not correct", "that's not right"]
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


def calculate_bill_amount(order_items):
    """
    Calculates the total bill amount based on order items.
    Stores the total in the session.
    """
    total = 0.0
    for item in order_items:
        base_price = item.get("price", 0.0) or 0.0
        quantity = item.get("quantity", 1)
        total += base_price * quantity
        for mod in item.get("modifier", []):
            mod_price = mod.get("price", 0.0) or 0.0
            mod_quantity = mod.get("quantity", 1)
            total += mod_price * mod_quantity
    session['total_price'] = total


def find_menu_item(user_input, threshold=35):
    """
    Searches for a menu item whose name best matches the user input.
    Uses Levenshtein distance to compute a match if an exact match is not found.
    """
    from app.utils.menu_utils import load_menu_data
    data = load_menu_data()
    all_items = data.get("items", [])
    user_lower = user_input.lower().strip()
    # Check for an exact match first.
    for item in all_items:
        if item["name"].lower() == user_lower:
            return item, 0
    # Fuzzy search: find the best match.
    best_item = None
    best_distance = 9999
    for item in all_items:
        distance = Levenshtein.distance(user_lower, item["name"].lower())
        if distance < best_distance:
            best_distance = distance
            best_item = item
    if best_item and best_distance <= threshold:
        return best_item, best_distance
    return None, None


def find_menu_item_any_status(user_input, threshold=35):
    """
    Wrapper for find_menu_item that ignores availability status.
    """
    return find_menu_item(user_input, threshold)
