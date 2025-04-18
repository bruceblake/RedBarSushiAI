import os
import json
import pytest
from playwright.sync_api import expect
from dotenv import load_dotenv

# Load test environment variables
load_dotenv(".env.test")

# Global test data
test_phone = "+15551234567"
test_location = "downtown"
test_customer = {
    "name": "E2E Test Customer",
    "phone": test_phone
}

# Store order ID between tests
order_id = None

# Create test data directory if it doesn't exist
test_data_dir = os.path.join(os.path.dirname(__file__), "test-data")
if not os.path.exists(test_data_dir):
    os.makedirs(test_data_dir)

# Check if we have API keys for full testing
if not os.getenv("OPENAI_API_KEY") or "your-actual" in os.getenv("OPENAI_API_KEY", ""):
    print("⚠️ OPENAI_API_KEY not set. Some tests may be skipped or mocked.")

if not os.getenv("TWILIO_ACCOUNT_SID") or "your-twilio" in os.getenv("TWILIO_ACCOUNT_SID", ""):
    print("⚠️ TWILIO credentials not set. SMS and voice tests may be skipped or mocked.")

if not os.getenv("DELIVERECT_CLIENT_ID") or "your-deliverect" in os.getenv("DELIVERECT_CLIENT_ID", ""):
    print("⚠️ DELIVERECT credentials not set. Menu synchronization tests may be skipped or mocked.")


def test_application_homepage(page, base_url):
    """Test that the application homepage loads successfully."""
    page.goto(f"{base_url}/")
    expect(page).to_have_title(lambda title: "Red Bar Sushi" in title or "RedBarSushiAI" in title)
    expect(page.locator("h1")).to_contain_text(lambda text: "Red Bar Sushi" in text or "RedBarSushiAI" in text)


# Menu Management Tests
class TestMenuManagement:
    def test_menu_page_renders(self, page, base_url):
        """Test that the menu page renders menu items correctly."""
        page.goto(f"{base_url}/menu")
        
        # Basic elements should be present
        expect(page.locator(".menu-container")).to_be_visible()
        
        # Should have at least one menu item
        expect(page.locator(".menu-item")).to_have_count(lambda count: count >= 1)
        
        # Check for California Roll (should be in test data)
        menu_items = page.locator(".menu-item").all_text_contents()
        assert any("California Roll" in item for item in menu_items), "California Roll not found in menu items"
    
    def test_menu_api_returns_valid_data(self, api_client):
        """Test that the menu API returns valid data."""
        response = api_client.get("/api/menu")
        assert response.status == 200
        
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) > 0
        
        # Verify schema of a menu item
        first_item = data["items"][0]
        assert "name" in first_item
        assert "price" in first_item
        assert isinstance(first_item["price"], (int, float))
    
    def test_admin_menu_item_availability(self, page, base_url):
        """Test that admin can update menu item availability."""
        # Skip if BYPASS_AUTH_FOR_TESTING is not enabled
        if not os.getenv("BYPASS_AUTH_FOR_TESTING"):
            pytest.skip("Authentication bypass not enabled")
        
        page.goto(f"{base_url}/admin/menu")
        
        # Find a menu item toggle
        item_toggle = page.locator(".availability-toggle").first
        
        # Get current state
        initial_state = item_toggle.is_checked()
        
        # Toggle the state
        item_toggle.click()
        
        # Verify change was saved
        page.wait_for_selector(".success-message")
        
        # Refresh and verify state persisted
        page.reload()
        expect(item_toggle).to_be_checked(not initial_state)
        
        # Reset to original state
        item_toggle.click()
        page.wait_for_selector(".success-message")


# Order Processing Tests
class TestOrderProcessing:
    def test_place_order(self, page, base_url):
        """Test that a customer can place an order."""
        global order_id
        
        page.goto(f"{base_url}/order")
        
        # Fill customer information
        page.fill('input[name="customer_name"]', test_customer["name"])
        page.fill('input[name="customer_phone"]', test_customer["phone"])
        
        # Select order type
        page.click('input[value="pickup"]')
        
        # Select location
        page.select_option('select[name="location"]', test_location)
        
        # Add items to order
        page.click('button:has-text("Browse Menu")')
        page.click('text=California Roll')
        page.fill('input[name="quantity"]', "2")
        page.click('button:has-text("Add to Order")')
        
        # Verify item added to cart
        expect(page.locator(".cart-item")).to_contain_text("California Roll")
        expect(page.locator(".cart-quantity")).to_contain_text("2")
        
        # Submit order
        page.click('button:has-text("Place Order")')
        
        # Verify order confirmation
        expect(page.locator(".order-confirmation")).to_be_visible()
        expect(page.locator(".order-id")).to_be_visible()
        
        # Capture order ID for later tests
        order_id_element = page.locator(".order-id")
        order_id = order_id_element.text_content()
        
        # Save to test data file for other tests
        with open(os.path.join(test_data_dir, "order_id.json"), "w") as f:
            json.dump({"order_id": order_id}, f)
    
    def test_order_in_admin_dashboard(self, page, base_url):
        """Test that order shows in admin dashboard."""
        global order_id
        
        # Skip if BYPASS_AUTH_FOR_TESTING is not enabled
        if not os.getenv("BYPASS_AUTH_FOR_TESTING"):
            pytest.skip("Authentication bypass not enabled")
        
        # Try to get the order ID from previous test or test data file
        if not order_id:
            try:
                with open(os.path.join(test_data_dir, "order_id.json"), "r") as f:
                    data = json.load(f)
                    order_id = data.get("order_id")
            except:
                pytest.fail("Could not get order ID from previous test")
        
        # Go to admin orders page
        page.goto(f"{base_url}/admin/orders")
        
        # Search for the order
        page.fill('input[placeholder="Search orders"]', order_id)
        page.click('button:has-text("Search")')
        
        # Verify order appears in results
        expect(page.locator(f"text={order_id}")).to_be_visible()
        
        # Verify order details
        expect(page.locator(".order-details")).to_contain_text("California Roll")
        expect(page.locator(".order-details")).to_contain_text("2")  # Quantity
        expect(page.locator(".customer-info")).to_contain_text(test_customer["name"])
    
    def test_update_order_status(self, page, base_url):
        """Test that admin can update order status."""
        global order_id
        
        # Skip if BYPASS_AUTH_FOR_TESTING is not enabled
        if not os.getenv("BYPASS_AUTH_FOR_TESTING"):
            pytest.skip("Authentication bypass not enabled")
        
        # Try to get the order ID from test data
        if not order_id:
            try:
                with open(os.path.join(test_data_dir, "order_id.json"), "r") as f:
                    data = json.load(f)
                    order_id = data.get("order_id")
            except:
                pytest.fail("Could not get order ID from previous test")
        
        # Go to admin orders page
        page.goto(f"{base_url}/admin/orders")
        
        # Search for the order
        page.fill('input[placeholder="Search orders"]', order_id)
        page.click('button:has-text("Search")')
        
        # Update status to "preparing"
        page.select_option("select.status-dropdown", "preparing")
        page.click('button:has-text("Update")')
        
        # Verify status updated
        page.wait_for_selector(".success-message")
        page.reload()
        
        # Search again
        page.fill('input[placeholder="Search orders"]', order_id)
        page.click('button:has-text("Search")')
        
        # Verify new status
        status_value = page.locator("select.status-dropdown").input_value()
        assert status_value == "preparing"
    
    def test_customer_order_status(self, page, base_url):
        """Test that customer can check order status."""
        global order_id
        
        # Try to get the order ID from previous test
        if not order_id:
            try:
                with open(os.path.join(test_data_dir, "order_id.json"), "r") as f:
                    data = json.load(f)
                    order_id = data.get("order_id")
            except:
                pytest.fail("Could not get order ID from previous test")
        
        # Go to order status page
        page.goto(f"{base_url}/order-status?order_id={order_id}")
        
        # Verify order info is displayed
        expect(page.locator(".order-id")).to_contain_text(order_id)
        expect(page.locator(".order-status")).to_be_visible()
        
        # Should show "preparing" status that we set in previous test
        expect(page.locator(".order-status")).to_contain_text("preparing")


# API Integration Tests
class TestAPIIntegration:
    def test_menu_update_api(self, api_client):
        """Test that menu update API accepts valid menu data."""
        # Skip if RUN_EXTERNAL_API_TESTS is not enabled
        if os.getenv("RUN_EXTERNAL_API_TESTS") != "true":
            pytest.skip("External API tests disabled")
        
        # Create test menu payload
        menu_payload = {
            "type": "menu.updated",
            "data": {
                "menu": {
                    "categories": [
                        {
                            "name": "Sushi Rolls",
                            "products": [
                                {
                                    "id": "spicy-tuna-roll",
                                    "name": "Spicy Tuna Roll",
                                    "description": "Fresh tuna with spicy mayo",
                                    "price": 8.95,
                                    "available": True,
                                    "plu": "spicy-tuna-roll",
                                    "posId": "spicy-tuna-roll"
                                }
                            ]
                        }
                    ]
                }
            }
        }
        
        # Send to menu update API
        response = api_client.post("/menu_update", 
            data=json.dumps(menu_payload),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Deliverect/1.0"
            }
        )
        
        # Verify response
        assert response.status == 200
        result = response.json()
        assert result.get("success") == True
        
        # Verify menu was updated by fetching it
        menu_response = api_client.get("/api/menu")
        menu_data = menu_response.json()
        
        # Find the Spicy Tuna Roll in the menu
        spicy_tuna_roll = next((item for item in menu_data["items"] if item["name"] == "Spicy Tuna Roll"), None)
        assert spicy_tuna_roll is not None
        assert spicy_tuna_roll["price"] == 8.95
    
    def test_openai_order_processing(self, api_client):
        """Test OpenAI integration for order processing."""
        # Skip if OpenAI API key not set or external tests disabled
        if (not os.getenv("OPENAI_API_KEY") or "your-actual" in os.getenv("OPENAI_API_KEY", "") or 
            os.getenv("RUN_EXTERNAL_API_TESTS") != "true"):
            pytest.skip("OpenAI API key not configured or external tests disabled")
        
        # Test the AI order parsing endpoint
        order_text = "I'd like to order two California rolls and one spicy tuna roll"
        
        response = api_client.post("/api/parse-order", 
            json={"text": order_text},
            headers={"Content-Type": "application/json"}
        )
        
        # Verify response
        assert response.status == 200
        result = response.json()
        
        # Should have parsed the order items
        assert "items" in result
        assert isinstance(result["items"], list)
        
        # Should have the correct items and quantities
        cal_roll = next((item for item in result["items"] if "california" in item["name"].lower()), None)
        spicy_tuna = next((item for item in result["items"] if "spicy tuna" in item["name"].lower()), None)
        
        assert cal_roll is not None
        assert cal_roll["quantity"] == 2
        
        assert spicy_tuna is not None
        assert spicy_tuna["quantity"] == 1