// @ts-check
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

// Deliverect integration tests
test.describe('Deliverect integration', () => {
  test.beforeEach(async ({ page }) => {
    // Load test payload from file
    const testDataPath = path.join(__dirname, '../../testing_data/test_deliverect_payload.json');
    let testData;
    
    if (fs.existsSync(testDataPath)) {
      testData = JSON.parse(fs.readFileSync(testDataPath, 'utf-8'));
    } else {
      console.log('Test data file not found, using default test data');
      // Create mock Deliverect payload if file doesn't exist
      testData = {
        "type": "menu.updated",
        "data": {
          "menu": {
            "categories": [
              {
                "name": "Sushi Rolls",
                "products": [
                  {
                    "id": "cal-roll",
                    "name": "California Roll",
                    "description": "Crab, avocado, and cucumber",
                    "price": 7.95,
                    "available": true,
                    "plu": "cal-roll",
                    "posId": "cal-roll"
                  },
                  {
                    "id": "spicy-tuna",
                    "name": "Spicy Tuna Roll",
                    "description": "Fresh tuna with spicy mayo",
                    "price": 8.95,
                    "available": true,
                    "plu": "spicy-tuna",
                    "posId": "spicy-tuna"
                  }
                ]
              }
            ]
          }
        }
      };
      
      // Save it for future use
      fs.mkdirSync(path.dirname(testDataPath), { recursive: true });
      fs.writeFileSync(testDataPath, JSON.stringify(testData, null, 2));
    }
    
    // Store test data for use in tests
    test.info().attach('deliverect-payload', {
      body: JSON.stringify(testData),
      contentType: 'application/json'
    });
  });
  
  test('menu update webhook works', async ({ request }) => {
    // Get test data
    const testDataPath = path.join(__dirname, '../../testing_data/test_deliverect_payload.json');
    const testData = JSON.parse(fs.readFileSync(testDataPath, 'utf-8'));
    
    // Send webhook request
    const response = await request.post('/menu_update', {
      data: testData,
      headers: {
        'User-Agent': 'Deliverect/1.0',
        'Content-Type': 'application/json'
      }
    });
    
    // Verify response
    expect(response.status()).toBe(200);
    const result = await response.json();
    expect(result).toHaveProperty('success', true);
    
    // Verify menu was updated by fetching updated menu
    const menuResponse = await request.get('/api/menu');
    const menuData = await menuResponse.json();
    
    // Check if items from payload are in menu
    const itemNames = menuData.items.map(item => item.name);
    expect(itemNames).toContain('California Roll');
    expect(itemNames).toContain('Spicy Tuna Roll');
  });
  
  test('order submission to Deliverect', async ({ page, request }) => {
    // Create a test order
    await page.goto('/order');
    await page.fill('input[name="customer.name"]', 'Deliverect Test');
    await page.fill('input[name="customer.phone"]', '5551234567');
    await page.click('input[value="pickup"]');
    await page.fill('input[name="pickup_time"]', '2025-04-20T19:00:00');
    await page.selectOption('select[name="location_id"]', 'downtown');
    await page.click('button:has-text("Add Items")');
    await page.click('text=California Roll');
    await page.fill('input[name="quantity"]', '1');
    await page.click('button:has-text("Add to Order")');
    await page.click('button:has-text("Place Order")');
    
    // Get order ID from confirmation
    const orderIdElement = page.locator('.order-id');
    await expect(orderIdElement).toBeVisible();
    const orderId = await orderIdElement.textContent();
    
    // Check order logs to verify Deliverect API call was made
    await page.goto('/admin/logs');
    await page.fill('input[placeholder="Search logs"]', orderId);
    await page.click('button:has-text("Search")');
    
    // Verify Deliverect API call was logged
    await expect(page.locator('.log-entry')).toContainText('Deliverect API');
    await expect(page.locator('.log-entry')).toContainText('Success');
  });
});