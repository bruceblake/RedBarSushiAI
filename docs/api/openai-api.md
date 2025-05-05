# OpenAI Assistants API Documentation

## Overview

RedBarSushiAI uses OpenAI's Assistants API for natural language processing, enabling sophisticated conversation management for order taking and menu inquiries.

## Key Components

### Assistant

The configured AI personality with specific capabilities.

```python
assistant = client.beta.assistants.create(
    name="RedBarSushi Assistant",
    instructions="You are a helpful assistant for Red Bar Sushi restaurant.",
    tools=[{"type": "function", "function": tool_definition}],
    model="gpt-4-turbo"
)
```

### Thread

Represents a single conversation between the user and the assistant.

```python
thread = client.beta.threads.create()
```

### Message

User input or assistant response within a thread.

```python
message = client.beta.threads.messages.create(
    thread_id=thread.id,
    role="user",
    content="I want to order a California roll with extra avocado"
)
```

### Run

Execution of the assistant on a thread, potentially with tool calls.

```python
run = client.beta.threads.runs.create(
    thread_id=thread.id,
    assistant_id=assistant_id
)
```

## Tool Integration

The Assistants API can call functions defined by the application:

### Tool Definition

```python
tool_definition = {
    "name": "lookup_menu_item",
    "description": "Find a menu item by name",
    "parameters": {
        "type": "object",
        "properties": {
            "item_name": {
                "type": "string",
                "description": "The name of the menu item to look up"
            }
        },
        "required": ["item_name"]
    }
}
```

### Handling Tool Calls

```python
if run.status == "requires_action":
    for tool_call in run.required_action.submit_tool_outputs.tool_calls:
        if tool_call.function.name == "lookup_menu_item":
            args = json.loads(tool_call.function.arguments)
            result = lookup_menu_item(args["item_name"])
            
            # Submit the tool output back to the Assistant
            client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread.id,
                run_id=run.id,
                tool_outputs=[
                    {
                        "tool_call_id": tool_call.id,
                        "output": json.dumps(result)
                    }
                ]
            )
```

## Essential Tools

RedBarSushiAI implements these key tools for the Assistant:

### lookup_menu_item

Translates user requests to specific menu items by PLU.

```python
def lookup_menu_item(item_name):
    # Find the menu item in the database
    menu_item = find_menu_item(item_name)
    
    return {
        "name": menu_item.name,
        "description": menu_item.description,
        "price": menu_item.price,
        "plu": menu_item.plu
    }
```

### add_item_to_cart

Updates the current order with items and modifiers.

```python
def add_item_to_cart(plu, quantity, modifiers=None):
    # Add the item to the cart in Redis
    cart.add_item(plu, quantity, modifiers)
    
    return {
        "success": True,
        "cart": cart.get_contents()
    }
```

### place_order

Submits the order to Deliverect.

```python
def place_order(customer_details, delivery_details=None, order_type=1):
    # Format the order for Deliverect
    order_payload = format_order_payload(
        cart.get_contents(),
        customer_details,
        delivery_details,
        order_type
    )
    
    # Submit to Deliverect
    response = submit_to_deliverect(order_payload)
    
    return {
        "success": response.status_code == 201,
        "order_id": response.json().get("orderId")
    }
```

## Error Handling

The system implements retry logic for OpenAI API calls:

```python
@retry(
    retry=retry_if_exception_type(openai.error.APIError),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(5),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
def run_with_retry(thread_id, assistant_id):
    return client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id
    )
```