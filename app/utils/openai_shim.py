"""
OpenAI shim to handle cases where the OpenAI package is not available.
This provides fallback functionality for when OpenAI is not installed.
"""

import logging

# Flag for openai availability
OPENAI_AVAILABLE = False
OPENAI_AGENTS_AVAILABLE = False

# Try to import OpenAI
try:
    import openai

    OPENAI_AVAILABLE = True

    # Test Agent API availability
    try:
        from openai.agent.types import AgentAction, AgentFinish, AgentStep

        OPENAI_AGENTS_AVAILABLE = True
    except ImportError:
        OPENAI_AGENTS_AVAILABLE = False
except ImportError:
    # Create dummy classes and objects
    class DummyCompletion:
        def create(self, *args, **kwargs):
            return {"choices": [{"message": {"content": "OpenAI not available"}}]}

    class DummyChat:
        def __init__(self):
            self.completions = DummyCompletion()

    class DummyOpenAI:
        def __init__(self):
            self.chat = DummyChat()

        def __getattr__(self, name):
            logging.warning(
                f"Attempted to access '{name}' but OpenAI package is not available"
            )
            return self

    # Create the dummy openai module
    openai = DummyOpenAI()
    logging.warning("OpenAI package not available, using fallback implementation")


# Simple fallback functions
def fallback_analyze_user_input(text: str) -> dict:
    """Fallback function when OpenAI is not available"""
    logging.warning("Using fallback analysis - OpenAI not available")

    # Include basic quantity extraction logic
    import re

    quantity_match = re.search(r"(\d+)\s*(?:of|x|,)?\s*(.+)", text.lower())
    quantity = 1  # Default quantity

    if quantity_match:
        try:
            quantity = int(quantity_match.group(1))
            # Update text to only include the item part
            text = quantity_match.group(2).strip()
            logging.info(f"Extracted quantity: {quantity}, item text: {text}")
        except (ValueError, IndexError):
            pass

    # Special case for veggie burger
    from app.utils.menu_utils import find_menu_item_by_name

    if "veggie" in text.lower() and "burger" in text.lower():
        menu_item = find_menu_item_by_name("veggie burger")
        if menu_item:
            return {
                "intent": "order_food",
                "items": [
                    {
                        "name": menu_item.get("name"),
                        "price": menu_item.get("price", 0.0),
                        "reference_handler": menu_item.get("reference_handler", ""),
                        "quantity": quantity,
                    }
                ],
                "confidence": 0.9,
            }

    # Special case for chicken satay/sate
    if ("chicken" in text.lower() and "satay" in text.lower()) or (
        "chicken" in text.lower() and "sate" in text.lower()
    ):
        menu_item = find_menu_item_by_name("chicken sate")
        if menu_item:
            logging.info(
                "[OPENAI-SHIM] Found 'Chicken Sate' via special case handling"
            )
            return {
                "intent": "order_food",
                "items": [
                    {
                        "name": menu_item.get("name"),
                        "price": menu_item.get("price", 0.0),
                        "reference_handler": menu_item.get("reference_handler", ""),
                        "quantity": quantity,
                    }
                ],
                "confidence": 0.9,
            }

    # Default response with empty items
    return {
        "intent": "order_food",
        "items": [],  # Using items instead of menu_items for consistency
        "confidence": 0,
    }


def fallback_get_order_modifications(text: str, current_items: list) -> dict:
    """Fallback function when OpenAI is not available"""
    logging.warning("Using fallback modification - OpenAI not available")

    # Extract quantity from the modification request
    import re

    quantity_match = re.search(r"(\d+)\s*(?:of|x|,)?\s*(.+)", text.lower())
    quantity = 1  # Default quantity

    if quantity_match:
        try:
            quantity = int(quantity_match.group(1))
            # Update text to only include the item part
            text = quantity_match.group(2).strip()
            logging.info(
                f"Extracted quantity in modification: {quantity}, item text: {text}"
            )
        except (ValueError, IndexError):
            pass

    # Special case for chicken satay/sate in modifications
    if ("chicken" in text.lower() and "satay" in text.lower()) or (
        "chicken" in text.lower() and "sate" in text.lower()
    ):
        from app.utils.menu_utils import find_menu_item_by_name

        # Check if it's a replacement request
        if (
            "not" in text.lower()
            or "instead" in text.lower()
            or "replace" in text.lower()
        ):
            # Find something to remove - likely chicken tenders
            item_to_remove = None
            for item in current_items:
                if (
                    "chicken" in item.get("name", "").lower()
                    and "tender" in item.get("name", "").lower()
                ):
                    item_to_remove = item.get("name")
                    break

            # Find Chicken Sate to add
            menu_item = find_menu_item_by_name("chicken sate")
            if menu_item:
                return {
                    "additions": [f"{quantity}x {menu_item.get('name')}"],
                    "removals": (
                        [f"{quantity}x {item_to_remove}"] if item_to_remove else []
                    ),
                }
        else:
            # Just adding chicken sate
            menu_item = find_menu_item_by_name("chicken sate")
            if menu_item:
                return {
                    "additions": [f"{quantity}x {menu_item.get('name')}"],
                    "removals": [],
                }

    # List to store modifications
    additions = []
    removals = []

    # Special case for veggie burger
    if "veggie" in text.lower() and "burger" in text.lower():
        from app.utils.menu_utils import find_menu_item_by_name

        menu_item = find_menu_item_by_name("veggie burger")
        if menu_item:
            additions.append({"name": menu_item.get("name"), "quantity": quantity})
            # Return immediately with specific veggie burger addition
            return {
                "additions": [f"{quantity}x {menu_item.get('name')}"],
                "removals": [],
            }

    # Check for addition keywords
    if any(word in text.lower() for word in ["add", "want", "with", "one", "get"]):
        # Try to find a specific menu item if possible
        from app.utils.menu_utils import find_menu_item_by_name

        # Extract item name after keywords
        words = ["add", "want", "with", "one", "get", "of"]
        for word in words:
            if word in text.lower():
                parts = text.lower().split(word, 1)
                if len(parts) > 1 and parts[1].strip():
                    potential_item = parts[1].strip()
                    menu_item = find_menu_item_by_name(potential_item)
                    if menu_item:
                        return {
                            "additions": [f"{quantity}x {menu_item.get('name')}"],
                            "removals": [],
                        }
                    break

        # If no specific item found, add a placeholder
        additions.append({"name": "Unknown Item", "quantity": quantity})

    # Check for removal keywords
    if any(word in text.lower() for word in ["remove", "without", "no"]):
        # If we have current items, try to match which one to remove
        if current_items:
            for item in current_items:
                item_name = item.get("name", "").lower()
                if any(word in text.lower() for word in item_name.split()):
                    return {
                        "additions": [],
                        "removals": [f"{quantity}x {item.get('name')}"],
                    }

        # If no specific match, use a placeholder
        removals.append({"name": "Unknown Item", "quantity": quantity})

    # Format for return
    addition_strings = [f"{item['quantity']}x {item['name']}" for item in additions]
    removal_strings = [f"{item['quantity']}x {item['name']}" for item in removals]

    # Return the modifications
    return {"additions": addition_strings, "removals": removal_strings}
