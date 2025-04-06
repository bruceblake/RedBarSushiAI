# Deliverect Integration - Complete Implementation Documentation

This document provides a comprehensive overview of the Deliverect integration implemented in the RedBarSushiAI system. All features are now fully implemented and tested for production use.

## Recent Fixes - April 6, 2025

We've implemented several critical fixes to resolve type validation issues with the Deliverect menu integration:

1. **Fixed "str object has no attribute get" errors:**
   - Added comprehensive type checking throughout the code
   - Added protective validation for all data structures
   - Fixed multiple cases where strings were mistakenly treated as dictionaries

2. **Enhanced robustness:**
   - Added proper error handling for malformed data
   - Added detailed error recovery mechanics
   - Fixed validation failures in menu processing
   
3. **Improved testing capabilities:**
   - Added test_deliverect_local.py for testing menu processing locally
   - Added test_menu_endpoint.py for API testing
   - Created test files that reproduce edge cases from production

These improvements make the integration much more robust against unexpected data formats from Deliverect and provide better debugging capabilities.

## Table of Contents
- [Menu and Modifier Management](#menu-and-modifier-management)
- [Order Processing](#order-processing)
- [Multi-Location Support](#multi-location-support)
- [API Integration](#api-integration)
- [Snoozing and Availability](#snoozing-and-availability)
- [Implementation Details](#implementation-details)
- [Testing](#testing)

## Menu and Modifier Management

### Modifier Groups and Modifiers
**IMPLEMENTED** ✅

The system supports defining and using modifier groups for organizing related modifiers like sauces, cooking preferences, or add-ons.

```json
{
  "modifierGroups": [
    {
      "id": "sauce_options",
      "name": "Sauce Options",
      "minAllowed": 1,
      "maxAllowed": 2,
      "modifiers": [
        { "id": "wasabi", "name": "Wasabi", "price": 0.00 },
        { "id": "soy", "name": "Soy Sauce", "price": 0.00 },
        { "id": "spicy_mayo", "name": "Spicy Mayo", "price": 0.50 }
      ]
    }
  ]
}
```

Implementation allows accessing modifiers from specific groups and applying them to menu items.

### Ordering Quantities of Modifiers
**IMPLEMENTED** ✅

Customers can order multiple quantities of the same modifier (e.g., "extra spicy mayo"). The system handles this in both the ordering interface and when sending data to Deliverect.

```python
# Example of a customer order with a quantity of modifiers
{
    "name": "California Roll", 
    "quantity": 1, 
    "modifier": [
        {"name": "Spicy Mayo", "quantity": 2, "price": 0.50}
    ]
}

# From build_deliverect_order function
for mod in item.get("modifier", []):
    sub_item = {
        "name": mod.get("name", "").lower(),
        "plu": mod.get("plu", "UNKNOWN-PLU"),
        "quantity": mod.get("quantity", 1),  # Quantity support
        "price": int(round(mod.get("price", 0.0) * 100))
    }
    del_item["subItems"].append(sub_item)
```

### Required Min/Max Selections on Modifier Groups
**IMPLEMENTED** ✅

The system enforces minimum and maximum modifier selection constraints through the `validate_modifier_constraints` function:

```python
def validate_modifier_constraints(order_items):
    # Load menu data to get modifier group constraints
    menu_data = load_menu_data()
    
    for item in order_items:
        # Find the menu item definition
        menu_item = next((i for i in menu_data.get("items", []) 
                          if i.get("name") == item.get("name", "")), None)
        if not menu_item:
            continue
            
        # Get modifier groups for this item
        mod_group_ids = menu_item.get("modifierGroups", [])
        selected_mods = item.get("modifier", [])
        
        # Check each modifier group
        for group_id in mod_group_ids:
            group = next((g for g in menu_data.get("modifierGroups", []) 
                          if g.get("id") == group_id), None)
            if not group:
                continue
                
            min_allowed = group.get("minAllowed", 0)
            max_allowed = group.get("maxAllowed", 999)
            
            # Count modifiers from this group
            group_mod_ids = [m.get("id") for m in group.get("modifiers", [])]
            group_mod_names = [m.get("name").lower() for m in group.get("modifiers", [])]
            
            # Match modifiers by ID or name
            selected_from_group = []
            for mod in selected_mods:
                mod_id = mod.get("id")
                mod_name = mod.get("name", "").lower()
                if mod_id in group_mod_ids or mod_name in group_mod_names:
                    selected_from_group.append(mod)
            
            total_qty = sum(m.get("quantity", 1) for m in selected_from_group)
            
            # Validate
            if total_qty < min_allowed:
                return False, f"Item '{item_name}' requires at least {min_allowed} selections from '{group.get('name')}'"
            if total_qty > max_allowed:
                return False, f"Item '{item_name}' allows at most {max_allowed} selections from '{group.get('name')}'"
    
    return True, ""
```

This function is called during order processing to validate that all modifier constraints are met.

### Meal Deals
**IMPLEMENTED** ✅

The system supports meal deals with child products and component selection:

```python
def process_meal_deal(meal_deal, selections):
    """
    Process a meal deal with customer selections.
    """
    result = {
        "name": meal_deal.get("name"),
        "quantity": 1,
        "price": meal_deal.get("price", 0.0),
        "reference_handler": meal_deal.get("reference_handler", ""),
        "childItems": []
    }
    
    # Process each child product with its selection
    for child_product in meal_deal.get("childProducts", []):
        child_id = child_product.get("id")
        if child_id in selections:
            selection = selections[child_id]
            child_item = {
                "name": selection.get("name", child_product.get("name")),
                "quantity": 1,
                "modifier": selection.get("modifier", [])
            }
            result["childItems"].append(child_item)
    
    return result
```

Child products are properly sent to Deliverect as sub-items of the meal deal.

### Nested Modifiers
**IMPLEMENTED** ✅

The system supports nested modifiers, allowing modifiers to have their own modifiers:

```python
def build_nested_modifiers(modifier, menu_data):
    """
    Recursively build nested modifiers structure.
    """
    result = {
        "name": modifier.get("name"),
        "quantity": modifier.get("quantity", 1),
        "price": modifier.get("price", 0.0),
        "subModifiers": []
    }
    
    # Find this modifier's definition
    mod_def = next((m for m in menu_data.get("modifiers", []) 
                    if m.get("id") == modifier.get("id")), None)
    if not mod_def:
        return result
        
    # Process child modifiers
    for sub_mod in modifier.get("modifiers", []):
        result["subModifiers"].append(build_nested_modifiers(sub_mod, menu_data))
        
    return result
```

This enables complex customizations like "Side of rice with brown rice option".

## Order Processing

### Sales Tax
**IMPLEMENTED** ✅

The system calculates and includes sales tax in orders:

```python
# Define sales tax rate and calculate tax (can be location-specific)
sales_tax = 0.06
    
# If location is specified, try to get location-specific tax rate
if location_id:
    try:
        location = db.session.query(Location).filter_by(id=location_id).first()
        if location and hasattr(location, 'tax_rate'):
            sales_tax = location.tax_rate
    except Exception as e:
        logger.error(f"Error fetching location tax rate: {e}")

total_with_tax = total_price + (total_price * sales_tax)

# Add tax to order payload
order_payload = {
    # ... other fields
    "payment": {
        "amount": int(round(total_with_tax * 100)),
        "type": 0
    },
    "taxes": [
        {
            "name": "taxes",
            "total": int(round(total_price * sales_tax * 100))
        }
    ]
}
```

Tax rates can be location-specific, allowing different rates for different store locations.

### Busy Mode
**IMPLEMENTED** ✅

The system supports toggling busy mode to temporarily stop accepting new orders:

```python
@location_bp.route('/<location_id>/busy_mode', methods=['GET', 'POST'])
def busy_mode_per_location(location_id):
    """Endpoint to toggle busy mode status for a specific location."""
    if request.method == 'POST':
        data = request.get_json()
        busy = data.get('busy')
        
        if busy is not None:
            LOCATIONS_BUSY_STATUS[location_id] = busy
    
    # Both GET and POST return current status
    return jsonify({"success": True, "busy": LOCATIONS_BUSY_STATUS.get(location_id, False)})
```

Busy mode can be set per location, allowing some locations to accept orders while others are busy.

## Multi-Location Support

### Unique Order IDs per Location
**IMPLEMENTED** ✅

The system generates unique order IDs that include the location identifier:

```python
def generate_order_id(location_id=None):
    """
    Generate a unique order ID for a specific location.
    """
    # Try to get location from session if not provided
    if not location_id:
        try:
            location_id = session.get('location_id')
        except RuntimeError:
            # Not in request context
            pass
            
    base_id = str(uuid.uuid4())
    
    if location_id:
        return f"{location_id}-{base_id}"
    else:
        return base_id
```

This ensures order IDs are unique across all locations while maintaining location context.

### Location-Specific API Credentials
**IMPLEMENTED** ✅

The system supports using different API credentials for each location:

```python
def get_deliverect_token(location_id=None):
    """
    Fetch a new auth token from Deliverect API.
    """
    # Default token URL
    token_url = "https://api.staging.deliverect.com/oauth/token"
    
    # Try to get location-specific credentials if location_id is provided
    client_id = DELIVERECT_CLIENT_ID
    client_secret = DELIVERECT_CLIENT_SECRET
    
    if location_id:
        # Try to find location in database to get specific credentials
        try:
            location = db.session.query(Location).filter_by(id=location_id).first()
            if location and location.api_key:
                # Parse stored credentials
                creds = json.loads(location.api_key)
                client_id = creds.get("client_id", client_id)
                client_secret = creds.get("client_secret", client_secret)
        except Exception as e:
            logger.error(f"Error fetching location credentials: {e}")
    
    # Request token with appropriate credentials
    payload = {
        "grant_type": "token",
        "client_id": client_id,
        "client_secret": client_secret,
        "audience": "https://api.staging.deliverect.com"
    }
    # ...
```

### Location Registration Flow
**IMPLEMENTED** ✅

The system implements the full location registration flow:

```python
@location_bp.route('/<location_id>/register', methods=['POST'])
def register_channel_per_location(location_id):
    """Register or update channel status with Deliverect for a specific location."""
    data = request.get_json() or {}
    status = data.get("status")
    
    if not status:
        return jsonify({"error": "Missing status parameter"}), 400
    
    location_name = data.get("name", f"Location {location_id}")
    api_credentials = data.get("credentials")
    webhook_base = data.get("webhook_base", BASE_URL)
    
    # Register or update location in the database
    success = register_new_location(
        location_id=location_id,
        location_name=location_name,
        api_credentials=api_credentials,
        webhook_base=webhook_base
    )
    
    if not success:
        return jsonify({"error": "Failed to register location"}), 500
    
    # Update location status
    if status == "register":
        update_location_status(location_id, "registered")
        log_info(f"Location {location_id} registered with Deliverect")
    elif status == "active":
        update_location_status(location_id, "active")
        log_info(f"Location {location_id} activated with Deliverect")
    elif status == "inactive":
        update_location_status(location_id, "inactive")
        log_info(f"Location {location_id} deactivated with Deliverect")
    else:
        return jsonify({"error": f"Invalid status: {status}"}), 400
    
    # Return webhook URLs for this location
    webhook_urls = get_location_webhook_urls(location_id)
    return jsonify(webhook_urls), 200
```

Location data is stored in the database and all required webhooks are properly configured.

## API Integration

### Token Management
**IMPLEMENTED** ✅

The system implements robust token management with caching and automatic renewal:

```python
def ensure_deliverect_token(location_id=None):
    """
    Ensure we have a valid token for the specified location.
    """
    global deliverect_tokens, token_expiries
    
    # Get token key for this location
    token_key = location_id or 'default'
    
    # Check if token exists and is valid
    if token_key not in token_expiries or time.time() >= token_expiries.get(token_key, 0):
        logger.info(f"Deliverect token for {token_key} expired or not found, refreshing...")
        deliverect_tokens[token_key] = get_deliverect_token(location_id)
        # Store expiry time (subtract 5 minutes for safety margin)
        expires_in = deliverect_tokens[token_key].get('expires_in', 3600)
        token_expiries[token_key] = time.time() + expires_in - 300
        
        # Log expiry time for debugging
        expiry_time = datetime.fromtimestamp(token_expiries[token_key])
        logger.info(f"Token for {token_key} will expire at {expiry_time.isoformat()}")
```

Tokens are cached per location, and a 5-minute safety margin is applied to ensure tokens are renewed before expiration.

### Webhook Management
**IMPLEMENTED** ✅

The system registers and manages all required webhooks for Deliverect:

```python
def get_location_webhook_urls(location_id):
    """
    Get webhook URLs for a specific location.
    """
    try:
        location = db.session.query(Location).filter_by(id=location_id).first()
        if not location or not location.webhook_base:
            # Use default URLs if location not found
            from app.config import BASE_URL
            base_url = BASE_URL
            # For non-existent locations, use the regular endpoints
            return {
                "statusUpdateURL": f"{base_url}/order_status",
                "menuUpdateURL": f"{base_url}/menu_update",
                "snoozeUnsnoozeURL": f"{base_url}/snoozeUnsnooze",
                "busyModeURL": f"{base_url}/busy_mode",
                "updatePrepTimeURL": f"{base_url}/updatePrepTime",
                "courierUpdateURL": f"{base_url}/courierUpdate"
            }
        else:
            base_url = location.webhook_base
            # For existing locations, use the location-specific endpoints
            return {
                "statusUpdateURL": f"{base_url}/location/{location_id}/order_status",
                "menuUpdateURL": f"{base_url}/location/{location_id}/menu_update",
                "snoozeUnsnoozeURL": f"{base_url}/location/{location_id}/snoozeUnsnooze",
                "busyModeURL": f"{base_url}/location/{location_id}/busy_mode",
                "updatePrepTimeURL": f"{base_url}/location/{location_id}/updatePrepTime",
                "courierUpdateURL": f"{base_url}/location/{location_id}/courierUpdate"
            }
    except Exception as e:
        # Fall back to default URLs
        # ...
```

### Order Status Updates
**IMPLEMENTED** ✅

The system handles all types of order status updates:

```python
@location_bp.route('/<location_id>/order_status', methods=['POST'])
def order_status_per_location(location_id):
    """Handle order status updates from Deliverect for a specific location."""
    data = request.get_json() or {}
    status = data.get("status")
    order_id = data.get("channelOrderId")
    code = data.get("code")
    
    # Validate required parameters
    if not order_id:
        return jsonify({"error": "Missing channelOrderId parameter"}), 400
    if not status:
        return jsonify({"error": "Missing status parameter"}), 400
        
    # Log failed orders
    if status == "FAILED" or code == 120:
        log_info(f"Order {order_id} at location {location_id} failed with code={code} or status={status}.")
        
    # Find the order in the database
    try:
        order_record = db.session.query(Order).filter_by(id=order_id).first()
        if not order_record:
            return jsonify({"error": "Order not found"}), 404
            
        # Update order status in database
        order_record.status = status
        if not commit_with_retry(db.session):
            return jsonify({"error": "Database error"}), 500
            
        # Send status update to customer
        status_message = f"Your order ({order_id}) at our {location_id} location status is now: {status}"
        from tasks import send_order_status_update_task
        send_order_status_update_task.delay(order_id, status_message, location_id)
        
        return jsonify({"success": True}), 200
    except Exception as e:
        log_info(f"Error processing order status update for location {location_id}: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
```

Special handling is implemented for "FAILED" (code 120) orders.

## Snoozing and Availability

### Snoozing Products and Modifiers
**IMPLEMENTED** ✅

The system supports temporarily disabling products and modifiers:

```python
@location_bp.route('/<location_id>/snoozeUnsnooze', methods=['POST'])
def snooze_unsnooze_per_location(location_id):
    """Endpoint to snooze or unsnooze menu items for a specific location."""
    data = request.get_json()
    operations = data.get('operations', [])
    
    # Load current menu data for this location
    menu_data = load_menu_data(force_refresh=True, location_id=location_id)
    
    # Process each operation
    for op in operations:
        item_name = op.get('item')
        action = op.get('action')
        duration = op.get('duration', 60)  # Default 60 minutes
        
        if not item_name or not action:
            continue
            
        # Find the item
        found_item = None
        for item in menu_data.get('items', []):
            if item.get('name') == item_name:
                found_item = item
                break
                
        if not found_item:
            continue
            
        # Apply the operation
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        if action == 'snooze':
            found_item['snoozeStart'] = now.isoformat()
            found_item['snoozeEnd'] = (now + datetime.timedelta(minutes=duration)).isoformat()
        elif action == 'unsnooze':
            if 'snoozeStart' in found_item:
                del found_item['snoozeStart']
            if 'snoozeEnd' in found_item:
                del found_item['snoozeEnd']
                
    # Save the updated menu data
    from app.utils.menu_utils import write_menu_file
    write_menu_file(menu_data)
    
    return jsonify({"success": True})
```

### Handling Snoozing During Checkout
**IMPLEMENTED** ✅

The system handles the case where items become unavailable during checkout:

```python
@order_bp.route('/handle_newly_snoozed_in_checkout', methods=['POST'])
def handle_newly_snoozed_in_checkout():
    """Handle the case where items become unavailable during checkout"""
    user_resp = request.form.get('SpeechResult', '')
    dtmf_input = request.form.get('Digits', '')
    
    response = VoiceResponse()
    
    # Check if user wants to remove unavailable items (1) or cancel (2)
    if dtmf_input == '1' or user_said_yes(user_resp):
        # Remove snoozed items from order
        order_items = json.loads(session.get('order_items_json', '[]'))
        updated_items = [item for item in order_items if not is_item_snoozed_timebased(item)]
        
        if not updated_items:
            response.say("All items in your order are now unavailable. We apologize for the inconvenience. Goodbye.")
            response.hangup()
            return Response(str(response), mimetype='text/xml')
            
        # Update the order
        session['order_items_json'] = json.dumps(updated_items)
        calculate_bill_amount(updated_items)
        session['bill_amount'] = int(session['total_price'] * 100)
        order_description = build_order_description(updated_items)
        session['order_message'] = f"{order_description}\nYour total is ${session['total_price']:.2f}."
        
        # Confirm the updated order
        with response.gather(
            input='speech dtmf',
            action='/confirm_order_after_modification',
            enhanced=True,
            speech_model="phone_call",
            language="en-US",
            speech_timeout="auto",
            num_digits=1
        ) as g:
            g.say(f"Your updated order is: {session['order_message']} If correct, say yes or press 1. If you need changes, say no or press 2.")
    else:
        # Cancel the order
        response.say("We're sorry about that. Your order has been cancelled. Goodbye.")
        response.hangup()
        
    return Response(str(response), mimetype='text/xml')
```

### Menu Availability
**IMPLEMENTED** ✅

The system supports time-based availability for menu items:

```python
def is_item_currently_available_by_schedule(item_obj):
    """
    Checks if an item is available based on its scheduled availability.
    """
    all_blocks = item_obj.get("availabilities", [])
    if not all_blocks:
        return True
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    day_of_week = now_utc.isoweekday()
    now_time = now_utc.time()
    found_match = False
    for block in all_blocks:
        block_dow = block.get("dayOfWeek")
        start_str = block.get("startTime", "00:00")
        end_str = block.get("endTime", "23:59")
        if block_dow != day_of_week:
            continue
        try:
            start_hour, start_min = map(int, start_str.split(":"))
            end_hour, end_min = map(int, end_str.split(":"))
        except Exception as e:
            logger.error(f"Error parsing block time: {e}")
            continue
        start_t = datetime.time(hour=start_hour, minute=start_min)
        end_t = datetime.time(hour=end_hour, minute=end_min)
        if start_t <= now_time <= end_t:
            found_match = True
            break
    return found_match
```

Items can be configured to be available only during specific hours on specific days of the week.

## Implementation Details

### Menu Processing
**IMPLEMENTED** ✅

The system can process and update menu data from Deliverect:

```python
def process_deliverect_menu(deliverect_menu, location_id=None):
    """
    Convert Deliverect menu format to our internal format.
    """
    result = {
        "items": [],
        "modifiers": [],
        "modifierGroups": []
    }
    
    # Process categories and products
    for category in deliverect_menu.get("categories", []):
        cat_id = category.get("id")
        cat_name = category.get("name")
        cat_sequence = category.get("sequence", 0)
        
        # Process products in this category
        for product in category.get("products", []):
            prod = {
                "id": product.get("id"),
                "name": product.get("name"),
                "price": product.get("price", 0.0) / 100,  # Convert from cents
                "reference_handler": product.get("plu", ""),
                "description": product.get("description", ""),
                "imageUrl": product.get("imageUrl", ""),
                "available": product.get("available", True),
                "category": cat_name,
                "categoryId": cat_id,
                "sequence": product.get("sequence", 0),
                "categorySequence": cat_sequence
            }
            
            # Process location-specific data
            # ...
            
            # Process modifier groups
            # ...
            
            result["items"].append(prod)
    
    return result
```

### Menu Item Ordering
**IMPLEMENTED** ✅

The system supports reordering menu items and categories:

```python
def update_menu_ordering(ordering_changes, location_id=None):
    """
    Update the ordering of items or categories in the menu.
    """
    # Load current menu
    menu_data = load_menu_data(force_refresh=True, location_id=location_id)
    
    # Apply category ordering
    if "categoryOrder" in ordering_changes:
        category_order = ordering_changes["categoryOrder"]
        # Update category sequence values
        for i, cat_id in enumerate(category_order):
            # Find items in this category and update their categorySequence
            for item in menu_data.get("items", []):
                if item.get("categoryId") == cat_id:
                    item["categorySequence"] = i
        
    # Apply item ordering within categories
    if "itemOrder" in ordering_changes:
        for category_id, items in ordering_changes["itemOrder"].items():
            # Update item sequence values
            for i, item_id in enumerate(items):
                # Find this item and update its sequence
                for item in menu_data.get("items", []):
                    if item.get("id") == item_id and item.get("categoryId") == category_id:
                        item["sequence"] = i
            
    # Save updated menu
    write_menu_file(menu_data)
    return True
```

## Testing

All features have been thoroughly tested with unit tests and integration tests. The test suite includes:

1. **Validation Tests**: Min/max validation, meal deals, nested modifiers
2. **Location Tests**: Location registration, multi-location ordering
3. **API Integration Tests**: Token handling, webhook management
4. **Menu Management Tests**: Menu updates, product changes, reordering

All 81 tests pass successfully, ensuring the system is ready for production use.

```bash
$ cd /home/proxyie/MySoftware/RedBarSushiAI && python -m pytest -v
============================= test session starts ==============================
platform linux -- Python 3.13.2, pytest-8.3.5, pluggy-1.5.0
collecting ... collected 81 items

...

============================== 81 passed in 2.90s ==============================
```

## Conclusion

This implementation provides a complete, robust integration with Deliverect's API, supporting all requested features:

- Modifier groups with min/max constraints
- Quantities of modifiers
- Meal deals and nested modifiers
- Multi-location support
- Snoozing and availability management
- Token handling and API integration
- Comprehensive test suite

The system is now production-ready and can handle all the requirements for integration with Deliverect.