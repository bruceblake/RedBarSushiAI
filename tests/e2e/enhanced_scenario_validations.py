"""
Enhanced validation examples for existing E2E scenarios.

These examples show how to make existing scenarios more thorough.
"""

# Example 1: Enhanced Simple Pickup Order
ConversationTurn(
    speaker="user",
    message="I'd like to place an order for pickup",
    expected_state="ORDERING",
    # Add AI response validation
    validation_function=lambda resp: all([
        "order" in resp.lower(),
        any(phrase in resp.lower() for phrase in ["what would you like", "what can i get", "ready to take"])
    ])
)

# Example 2: Enhanced Cart Validation
ConversationTurn(
    speaker="user",
    message="I'll have two California rolls please",
    expected_agent="cart",
    expected_context=lambda ctx: all([
        len(ctx.get("cart", [])) == 1,
        ctx["cart"][0].get("name", "").lower() == "california roll",
        ctx["cart"][0].get("quantity") == 2,
        ctx["cart"][0].get("plu") is not None  # Ensure PLU mapping
    ]),
    validation_function=lambda resp: all([
        "california roll" in resp.lower(),
        "2" in resp or "two" in resp.lower(),
        any(word in resp.lower() for word in ["added", "got it", "anything else"])
    ])
)

# Example 3: Enhanced Order Summary Validation
ConversationTurn(
    speaker="user",
    message="That's all for now",
    expected_state="VALIDATION",
    validation_function=lambda resp: all([
        "order" in resp.lower(),
        any(phrase in resp.lower() for phrase in ["i have", "your order includes", "to confirm"]),
        "california roll" in resp.lower(),
        "2" in resp  # Should mention quantity
    ])
)

# Example 4: Enhanced Final Order Validation
expected_outcome={
    "order_placed": True,
    "order_type": "pickup",
    "items_count": 1,
    "customer_phone": "555-1234",
    # Add more specific validations
    "final_cart_validation": lambda cart: all([
        len(cart) == 1,
        cart[0]["quantity"] == 2,
        cart[0]["unit_price"] > 0,
        cart[0]["total_price"] == cart[0]["unit_price"] * 2
    ]),
    "order_total": lambda total: total > 0 and total < 1000,  # Sanity check
    "pos_payload_structure": lambda payload: all([
        "items" in payload,
        "customer" in payload,
        "order_type" in payload,
        payload.get("order_type") == "pickup"
    ])
}