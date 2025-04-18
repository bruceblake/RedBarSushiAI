// @ts-check
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
require('dotenv').config({ path: '.env.test' });

// Global test data
const testPhone = '+15551234567';
const testLocation = 'downtown';
const testCustomer = {
  name: 'E2E Test Customer',
  phone: testPhone
};

// Comprehensive E2E Test Suite
test.describe('Comprehensive End-to-End Tests', () => {
  test.beforeAll(async () => {
    console.log('Setting up comprehensive E2E test suite...');
    
    // Check if we have API keys for full testing
    if (!process.env.OPENAI_API_KEY || process.env.OPENAI_API_KEY.includes('your-actual')) {
      console.warn('⚠️ OPENAI_API_KEY not set. Some tests may be skipped or mocked.');
    }
    
    if (!process.env.TWILIO_ACCOUNT_SID || process.env.TWILIO_ACCOUNT_SID.includes('your-twilio')) {
      console.warn('⚠️ TWILIO credentials not set. SMS and voice tests may be skipped or mocked.');
    }
    
    if (!process.env.DELIVERECT_CLIENT_ID || process.env.DELIVERECT_CLIENT_ID.includes('your-deliverect')) {
      console.warn('⚠️ DELIVERECT credentials not set. Menu synchronization tests may be skipped or mocked.');
    }
  });
  
  test('application homepage loads successfully', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Red Bar Sushi/);
    await expect(page.locator('h1')).toContainText(/Red Bar Sushi|RedBarSushiAI/);
  });
  
  test.describe('Menu Management', () => {
    test('menu page renders menu items correctly', async ({ page }) => {
      await page.goto('/menu');
      
      // Basic elements should be present
      await expect(page.locator('.menu-container')).toBeVisible();
      
      // Should have at least one menu item
      await expect(page.locator('.menu-item')).toHaveCount({ min: 1 });
      
      // Check for California Roll (should be in test data)
      const menuItems = await page.locator('.menu-item').allTextContents();
      const hasCaliforniaRoll = menuItems.some(item => item.includes('California Roll'));
      expect(hasCaliforniaRoll).toBeTruthy();
    });
    
    test('menu API returns valid data', async ({ request }) => {
      const response = await request.get('/api/menu');
      expect(response.status()).toBe(200);
      
      const data = await response.json();
      expect(data).toHaveProperty('items');
      expect(Array.isArray(data.items)).toBeTruthy();
      expect(data.items.length).toBeGreaterThan(0);
      
      // Verify schema of a menu item
      const firstItem = data.items[0];
      expect(firstItem).toHaveProperty('name');
      expect(firstItem).toHaveProperty('price');
      expect(typeof firstItem.price).toBe('number');
    });
    
    test('admin can update menu item availability', async ({ page }) => {
      // Skip if BYPASS_AUTH_FOR_TESTING is not enabled
      test.skip(!process.env.BYPASS_AUTH_FOR_TESTING, 'Authentication bypass not enabled');
      
      await page.goto('/admin/menu');
      
      // Find a menu item toggle
      const itemToggle = await page.locator('.availability-toggle').first();
      
      // Get current state
      const initialState = await itemToggle.isChecked();
      
      // Toggle the state
      await itemToggle.click();
      
      // Verify change was saved
      await page.waitForSelector('.success-message');
      
      // Refresh and verify state persisted
      await page.reload();
      await expect(itemToggle).toBeChecked(!initialState);
      
      // Reset to original state
      await itemToggle.click();
      await page.waitForSelector('.success-message');
    });
  });
  
  test.describe('Order Processing', () => {
    test('customer can place an order', async ({ page }) => {
      await page.goto('/order');
      
      // Fill customer information
      await page.fill('input[name="customer_name"]', testCustomer.name);
      await page.fill('input[name="customer_phone"]', testCustomer.phone);
      
      // Select order type
      await page.click('input[value="pickup"]');
      
      // Select location
      await page.selectOption('select[name="location"]', testLocation);
      
      // Add items to order
      await page.click('button:has-text("Browse Menu")');
      await page.click('text=California Roll');
      await page.fill('input[name="quantity"]', '2');
      await page.click('button:has-text("Add to Order")');
      
      // Verify item added to cart
      await expect(page.locator('.cart-item')).toContainText('California Roll');
      await expect(page.locator('.cart-quantity')).toContainText('2');
      
      // Submit order
      await page.click('button:has-text("Place Order")');
      
      // Verify order confirmation
      await expect(page.locator('.order-confirmation')).toBeVisible();
      await expect(page.locator('.order-id')).toBeVisible();
      
      // Capture order ID for later tests
      const orderId = await page.locator('.order-id').textContent();
      test.info().annotations.push({
        type: 'Order ID',
        description: orderId
      });
      
      // Save to test data file for other tests
      const testData = { orderId };
      fs.writeFileSync(path.join(__dirname, 'test-data.json'), JSON.stringify(testData));
    });
    
    test('order shows in admin dashboard', async ({ page }) => {
      // Skip if BYPASS_AUTH_FOR_TESTING is not enabled
      test.skip(!process.env.BYPASS_AUTH_FOR_TESTING, 'Authentication bypass not enabled');
      
      // Try to get the order ID from previous test
      let orderId;
      try {
        const testData = JSON.parse(fs.readFileSync(path.join(__dirname, 'test-data.json'), 'utf8'));
        orderId = testData.orderId;
      } catch (error) {
        test.fail(true, 'Could not get order ID from previous test');
      }
      
      // Go to admin orders page
      await page.goto('/admin/orders');
      
      // Search for the order
      await page.fill('input[placeholder="Search orders"]', orderId);
      await page.click('button:has-text("Search")');
      
      // Verify order appears in results
      await expect(page.locator(`text=${orderId}`)).toBeVisible();
      
      // Verify order details
      await expect(page.locator('.order-details')).toContainText('California Roll');
      await expect(page.locator('.order-details')).toContainText('2'); // Quantity
      await expect(page.locator('.customer-info')).toContainText(testCustomer.name);
    });
    
    test('admin can update order status', async ({ page }) => {
      // Skip if BYPASS_AUTH_FOR_TESTING is not enabled
      test.skip(!process.env.BYPASS_AUTH_FOR_TESTING, 'Authentication bypass not enabled');
      
      // Try to get the order ID from test data
      let orderId;
      try {
        const testData = JSON.parse(fs.readFileSync(path.join(__dirname, 'test-data.json'), 'utf8'));
        orderId = testData.orderId;
      } catch (error) {
        test.fail(true, 'Could not get order ID from previous test');
      }
      
      // Go to admin orders page
      await page.goto('/admin/orders');
      
      // Search for the order
      await page.fill('input[placeholder="Search orders"]', orderId);
      await page.click('button:has-text("Search")');
      
      // Update status to "preparing"
      await page.selectOption('select.status-dropdown', 'preparing');
      await page.click('button:has-text("Update")');
      
      // Verify status updated
      await page.waitForSelector('.success-message');
      await page.reload();
      
      // Search again
      await page.fill('input[placeholder="Search orders"]', orderId);
      await page.click('button:has-text("Search")');
      
      // Verify new status
      const statusValue = await page.locator('select.status-dropdown').inputValue();
      expect(statusValue).toBe('preparing');
    });
    
    test('customer can check order status', async ({ page }) => {
      // Try to get the order ID from previous test
      let orderId;
      try {
        const testData = JSON.parse(fs.readFileSync(path.join(__dirname, 'test-data.json'), 'utf8'));
        orderId = testData.orderId;
      } catch (error) {
        test.fail(true, 'Could not get order ID from previous test');
      }
      
      // Go to order status page
      await page.goto(`/order-status?order_id=${orderId}`);
      
      // Verify order info is displayed
      await expect(page.locator('.order-id')).toContainText(orderId);
      await expect(page.locator('.order-status')).toBeVisible();
      
      // Should show "preparing" status that we set in previous test
      await expect(page.locator('.order-status')).toContainText(/preparing/i);
    });
  });
  
  test.describe('API Integration Tests', () => {
    test('menu update API accepts valid menu data', async ({ request }) => {
      // Skip if RUN_EXTERNAL_API_TESTS is not enabled
      test.skip(process.env.RUN_EXTERNAL_API_TESTS !== 'true', 'External API tests disabled');
      
      // Create test menu payload
      const menuPayload = {
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
                    "available": true,
                    "plu": "spicy-tuna-roll",
                    "posId": "spicy-tuna-roll"
                  }
                ]
              }
            ]
          }
        }
      };
      
      // Send to menu update API
      const response = await request.post('/menu_update', {
        data: menuPayload,
        headers: {
          'Content-Type': 'application/json',
          'User-Agent': 'Deliverect/1.0'
        }
      });
      
      // Verify response
      expect(response.status()).toBe(200);
      const result = await response.json();
      expect(result).toHaveProperty('success', true);
      
      // Verify menu was updated by fetching it
      const menuResponse = await request.get('/api/menu');
      const menuData = await menuResponse.json();
      
      // Find the Spicy Tuna Roll in the menu
      const spicyTunaRoll = menuData.items.find(item => item.name === 'Spicy Tuna Roll');
      expect(spicyTunaRoll).toBeDefined();
      expect(spicyTunaRoll.price).toBe(8.95);
    });
    
    test('OpenAI integration for order processing', async ({ request }) => {
      // Skip if OpenAI API key not set or external tests disabled
      test.skip(!process.env.OPENAI_API_KEY || process.env.OPENAI_API_KEY.includes('your-actual') || 
                process.env.RUN_EXTERNAL_API_TESTS !== 'true', 
                'OpenAI API key not configured or external tests disabled');
      
      // Test the AI order parsing endpoint
      const orderText = "I'd like to order two California rolls and one spicy tuna roll";
      
      const response = await request.post('/api/parse-order', {
        data: { text: orderText },
        headers: { 'Content-Type': 'application/json' }
      });
      
      // Verify response
      expect(response.status()).toBe(200);
      const result = await response.json();
      
      // Should have parsed the order items
      expect(result).toHaveProperty('items');
      expect(Array.isArray(result.items)).toBeTruthy();
      
      // Should have the correct items and quantities
      const calRoll = result.items.find(item => item.name.toLowerCase().includes('california'));
      const spicyTuna = result.items.find(item => item.name.toLowerCase().includes('spicy tuna'));
      
      expect(calRoll).toBeDefined();
      expect(calRoll.quantity).toBe(2);
      
      expect(spicyTuna).toBeDefined();
      expect(spicyTuna.quantity).toBe(1);
    });
  });
});