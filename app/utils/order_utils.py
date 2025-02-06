# app/utils/order_utils.py
import json
import logging
import Levenshtein
from flask import session
from app.utils.helpers import log_info


def analyze_user_input(user_input):
    """
    Uses the OpenAI API to analyze the customer's input and extract an intent and any relevant order details.
    Returns a JSON structure with keys like "intent" and "menu_items".
    """
    import openai
    from app.config import OPENAI_API_KEY
    openai.api_key = OPENAI_API_KEY

    log_info(f"Analyzing user input: {user_input}")
    system_prompt = (
        "You are an AI assistant for a restaurant. Analyze the customer's message and provide:"
        "\n1) an intent (one of: order_food, ask_menu, provide_name, list_menu_items, get_menu_item_price, "
        "describe_menu_item, modify_order, other), and"
        "\n2) if intent is 'order_food', a list of menu_items (each with name, quantity, and an optional list of modifiers)."
        "\nRespond in valid JSON format only."
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
        log_info(f"Error in OpenAI analysis: {e}")
        # Fallback: assume the user wants to order the spoken text
        return {"intent": "order_food", "menu_items": [{"name": user_input, "quantity": 1, "modifier": []}]}


def user_said_yes(u):
    affirmatives = ["yes", "yeah", "yep", "correct",
                    "that's right", "sure", "ok", "okay"]
    return any(a in u.lower() for a in affirmatives)


def user_said_no(u):
    negatives = ["no", "nope", "nah", "not correct", "that's not right"]
    return any(n in u.lower() for n in negatives)


def dtmf_yes_no(digit):
    if digit == '1':
        return "yes"
    elif digit == '2':
        return "no"
    return None


def build_order_description(order_items):
    description = "You ordered:\n"
    for item in order_items:
        q = item.get("quantity", 1)
        mods = item.get("modifier", [])
        if not mods:
            description += f"- {q} {item['name']}\n"
        else:
            mod_str = ", ".join(
                [f"{mod.get('quantity',1)} {mod.get('name','')}" for mod in mods])
            description += f"- {q} {item['name']} with {mod_str}\n"
    return description


def calculate_bill_amount(order_items):
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
    from app.utils.menu_utils import load_menu_data
    data = load_menu_data()
    all_items = data.get("items", [])
    user_lower = user_input.lower().strip()
    # Exact match first
    for item in all_items:
        if item["name"].lower() == user_lower:
            return item, 0
    # Fuzzy matching
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
    return find_menu_item(user_input, threshold)

