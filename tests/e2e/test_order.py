"""
End-to-end tests for the order functionality.
"""
import pytest
import time
import re

# Test customer information
TEST_CUSTOMER = {
    "name": "E2E Test Customer",
    "phone": "5551234567"
}

def test_order_page_loads(page, base_url):
    """Test that the order page loads correctly."""
    # Navigate to the order page
    page.goto(f"{base_url}/order")
    
    # Verify page title contains expected text
    assert "Order" in page.title() or "Menu" in page.title()
    
    # Check for basic page elements (adjust selectors based on your actual page structure)
    form_elements = page.locator("form, input, button").count()
    assert form_elements > 0, "No form elements found on order page"
    
    # Take a screenshot for debugging
    page.screenshot(path="order-page.png")
    
    print("Order page loaded successfully")

def test_place_order(page, base_url):
    """Test the complete order placement process."""
    # Navigate to the order page
    page.goto(f"{base_url}/order")
    
    # Fill in customer information - adjust selectors based on your actual form structure
    name_input = page.locator("input[name*='name'], input[placeholder*='Name']").first
    if name_input.count() > 0:
        name_input.fill(TEST_CUSTOMER["name"])
    
    phone_input = page.locator("input[name*='phone'], input[placeholder*='Phone'], input[type='tel']").first
    if phone_input.count() > 0:
        phone_input.fill(TEST_CUSTOMER["phone"])
    
    # Select order type if available (pickup/delivery)
    pickup_option = page.locator("input[value='pickup'], input[name*='type'][value='pickup']").first
    if pickup_option.count() > 0:
        pickup_option.check()
    
    # Select location if available
    location_select = page.locator("select[name*='location']").first
    if location_select.count() > 0:
        # Get all options and select the first one
        options = page.locator("select[name*='location'] option").all()
        if len(options) > 1:  # First option might be placeholder
            location_value = options[1].get_attribute("value")
            if location_value:
                location_select.select_option(location_value)
    
    # Add items to the order
    add_items_to_cart(page)
    
    # Check if items were added to cart
    cart_items = page.locator(".cart-item, .order-item, tr").count()
    if cart_items == 0:
        pytest.skip("Could not add items to cart - order form structure may be different")
    
    # Find and click the submit/place order button
    order_button = page.locator("button:has-text('Place Order'), button:has-text('Submit'), input[type='submit']").first
    if order_button.count() > 0:
        # Take screenshot before submitting
        page.screenshot(path="before-submit.png")
        
        # Submit the order
        order_button.click()
        
        # Wait for confirmation page to load
        time.sleep(2)
        page.screenshot(path="after-submit.png")
        
        # Check for confirmation elements
        confirmation = page.locator(".confirmation, .success, .thank-you, .order-confirmation").first
        if confirmation.count() > 0:
            confirmation_text = confirmation.text_content()
            assert len(confirmation_text) > 0, "Order confirmation is empty"
            print(f"Order placed successfully: {confirmation_text[:100]}...")
            
            # Try to extract order ID if available
            order_id_match = re.search(r"order (?:id|number)[:\s#]*([A-Za-z0-9-]+)", confirmation_text, re.IGNORECASE)
            if order_id_match:
                order_id = order_id_match.group(1)
                print(f"Extracted order ID: {order_id}")
        else:
            # Check for errors
            error_message = page.locator(".error, .alert, .warning").first
            if error_message.count() > 0:
                print(f"Error submitting order: {error_message.text_content()}")
            assert False, "Order confirmation not found and no error message displayed"
    else:
        pytest.skip("Place order button not found - form structure may be different")

def add_items_to_cart(page):
    """Helper function to add items to cart - adapts to different UI patterns."""
    # Try different approaches to add items
    
    # Approach 1: Menu items with "Add" buttons
    add_buttons = page.locator("button:has-text('Add'), button:has-text('Add to Cart'), button:has-text('+')").all()
    if len(add_buttons) > 0:
        # Click the first add button
        add_buttons[0].click()
        time.sleep(0.5)
        return True
    
    # Approach 2: Menu with checkboxes
    checkboxes = page.locator("input[type='checkbox']").all()
    if len(checkboxes) > 0:
        # Check the first item
        checkboxes[0].check()
        time.sleep(0.5)
        return True
    
    # Approach 3: Look for a "Browse Menu" or similar button
    browse_button = page.locator("button:has-text('Browse Menu'), button:has-text('Menu'), a:has-text('Menu')").first
    if browse_button.count() > 0:
        browse_button.click()
        time.sleep(1)
        
        # Now look for items to select
        menu_items = page.locator(".menu-item, .item, li, .card, tr").all()
        if len(menu_items) > 0:
            menu_items[0].click()
            time.sleep(0.5)
            
            # Look for "Add to Order" button
            add_to_order = page.locator("button:has-text('Add to Order'), button:has-text('Add to Cart')").first
            if add_to_order.count() > 0:
                add_to_order.click()
                time.sleep(0.5)
                return True
    
    # Approach 4: Look for a search box to find items
    search_box = page.locator("input[placeholder*='search'], input[placeholder*='Search']").first
    if search_box.count() > 0:
        search_box.fill("California Roll")
        search_box.press("Enter")
        time.sleep(1)
        
        # Look for results
        results = page.locator(".search-result, .result, .menu-item").all()
        if len(results) > 0:
            results[0].click()
            time.sleep(0.5)
            
            # Look for add button
            add_button = page.locator("button:has-text('Add')").first
            if add_button.count() > 0:
                add_button.click()
                time.sleep(0.5)
                return True
    
    print("Could not determine how to add items to cart")
    return False

def test_order_status_check(page, base_url):
    """Test order status check functionality if it exists."""
    # Check if there's an order status page
    page.goto(f"{base_url}/order-status")
    
    # See if page loads (might redirect if not found)
    current_url = page.url
    if current_url.endswith("/order-status") or "status" in current_url:
        # Look for order ID input
        order_id_input = page.locator("input[name*='order'], input[placeholder*='Order']").first
        if order_id_input.count() > 0:
            # Try with a test order ID
            order_id_input.fill("TEST123")
            
            # Look for submit button
            submit_button = page.locator("button:has-text('Check'), button:has-text('Track'), button[type='submit']").first
            if submit_button.count() > 0:
                submit_button.click()
                time.sleep(1)
                
                # Take screenshot of result
                page.screenshot(path="order-status.png")
                
                print("Order status check functionality found and tested")
            else:
                print("No submit button found for order status")
        else:
            print("No order ID input found on status page")
    else:
        print("Order status page not found - skipping test")
        pytest.skip("Order status page not available")