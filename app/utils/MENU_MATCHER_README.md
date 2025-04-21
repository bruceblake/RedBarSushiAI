# AI Menu Matcher

This module provides advanced AI-powered menu item matching and interactive order resolution. It replaces the previous name variants approach with a more flexible and accurate AI-based approach.

## Features

1. **AI-Powered Menu Matching**: Uses OpenAI's models to find the best match for customer requests, even with vague or non-exact descriptions.

2. **Interactive Order Resolution**: Engages in dialog with customers to clarify their orders when requests are ambiguous.

3. **Context-Aware Matching**: Takes into account previous conversation to better understand customer preferences and requirements.

## How to Use

### AI Menu Matching

```python
from app.utils.menu_matcher import find_menu_item_ai

# Simple matching
item = find_menu_item_ai("cheeseburger")

# With conversation context
context = {
    "conversation": "Customer: Do you have vegetarian options?"
}
item = find_menu_item_ai("veggie burger", context=context)
```

### Interactive Order Resolution

The interactive order resolution API allows for a conversation-based approach to order taking.

#### API Endpoints

1. **Start Order**
   - `POST /order_ai`
   - Request body: `{"customer_request": "I want a burger and fries"}`
   - Returns a session ID and initial clarification dialog

2. **Process Response**
   - `POST /order_ai/{session_id}`
   - Request body: `{"customer_response": "I'd like a cheeseburger and large fries"}`
   - Returns updated order state with clarification dialog

3. **Get Order State**
   - `GET /order_ai/{session_id}`
   - Returns current order state

4. **Confirm Order**
   - `POST /order_ai/{session_id}/confirm`
   - Finalizes the order after resolution is complete

5. **Cancel Order**
   - `POST /order_ai/{session_id}/cancel`
   - Cancels the ongoing order resolution

## Example Client Implementation

```javascript
// Start order
async function startOrder(customerRequest) {
    const response = await fetch('/order_ai', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({customer_request: customerRequest})
    });
    
    const data = await response.json();
    return {
        sessionId: data.session_id,
        clarification: data.clarification,
        resolved: data.resolved,
        items: data.items
    };
}

// Process customer response
async function processResponse(sessionId, customerResponse) {
    const response = await fetch(`/order_ai/${sessionId}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({customer_response: customerResponse})
    });
    
    return await response.json();
}

// Confirm the order
async function confirmOrder(sessionId) {
    const response = await fetch(`/order_ai/${sessionId}/confirm`, {
        method: 'POST'
    });
    
    return await response.json();
}
```

## Testing

You can test the menu matcher using the provided test script:

```
python -m app.routes.test_menu_matcher
```

This will run through various test cases including exact matches, AI matches, and interactive order resolution.

## Implementation Details

- The AI menu matcher uses OpenAI's models to find the best match for customer requests.
- It first tries an exact match to avoid unnecessary API calls.
- If no exact match is found, it uses AI to find the best match.
- A fallback mechanism using Levenshtein distance is provided in case of API issues.
- The interactive order resolution maintains conversation state and uses AI to process customer responses.