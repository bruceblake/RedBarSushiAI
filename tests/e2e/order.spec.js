// @ts-check
const { test, expect } = require('@playwright/test');

// Order processing tests
test.describe('Order processing', () => {
  test('can create a new order via API', async ({ request }) => {
    // Create test order data
    const orderData = {
      customer: {
        name: 'Test Customer',
        phone: '5551234567'
      },
      items: [
        { 
          name: 'California Roll',
          quantity: 2,
          price: 7.95,
          reference_handler: 'cal-roll-1'
        }
      ],
      location_id: 'downtown',
      order_type: 'pickup',
      pickup_time: '2025-04-20T18:00:00'
    };
    
    // Send order to API
    const response = await request.post('/api/orders', {
      data: orderData
    });
    
    // Verify successful response
    expect(response.status()).toBe(200);
    
    // Parse response body
    const result = await response.json();
    
    // Check order created successfully
    expect(result).toHaveProperty('success', true);
    expect(result).toHaveProperty('order_id');
    expect(result.order_id).toBeTruthy();
  });
  
  test('order form submits successfully', async ({ page }) => {
    // Navigate to order page
    await page.goto('/order');
    
    // Fill customer information
    await page.fill('input[name="customer.name"]', 'Test Customer');
    await page.fill('input[name="customer.phone"]', '5551234567');
    
    // Select order type
    await page.click('input[value="pickup"]');
    
    // Select pickup time
    await page.fill('input[name="pickup_time"]', '2025-04-20T18:00:00');
    
    // Select location
    await page.selectOption('select[name="location_id"]', 'downtown');
    
    // Add items to order
    await page.click('button:has-text("Add Items")');
    await page.click('text=California Roll');
    await page.fill('input[name="quantity"]', '2');
    await page.click('button:has-text("Add to Order")');
    
    // Verify item added to cart
    await expect(page.locator('.cart-item')).toContainText('California Roll');
    await expect(page.locator('.cart-quantity')).toContainText('2');
    
    // Submit order
    await page.click('button:has-text("Place Order")');
    
    // Verify success message
    await expect(page.locator('.order-confirmation')).toBeVisible();
    await expect(page.locator('.order-id')).toBeVisible();
  });
  
  test('order status updates', async ({ page }) => {
    // Create an order first
    await page.goto('/order');
    await page.fill('input[name="customer.name"]', 'Status Test');
    await page.fill('input[name="customer.phone"]', '5559876543');
    await page.click('input[value="pickup"]');
    await page.fill('input[name="pickup_time"]', '2025-04-20T19:00:00');
    await page.selectOption('select[name="location_id"]', 'downtown');
    await page.click('button:has-text("Add Items")');
    await page.click('text=California Roll');
    await page.fill('input[name="quantity"]', '1');
    await page.click('button:has-text("Add to Order")');
    await page.click('button:has-text("Place Order")');
    
    // Get order ID from confirmation page
    const orderIdElement = page.locator('.order-id');
    await expect(orderIdElement).toBeVisible();
    const orderId = await orderIdElement.textContent();
    
    // Go to order status page
    await page.goto(`/order-status?order_id=${orderId}`);
    
    // Verify initial status
    await expect(page.locator('.order-status')).toContainText('Received');
    
    // In a separate context, update the order status as admin
    const adminContext = await page.context().newPage();
    await adminContext.goto('/admin/orders');
    await adminContext.fill('input[placeholder="Search orders"]', orderId);
    await adminContext.click('button:has-text("Search")');
    await adminContext.selectOption('select.status-dropdown', 'preparing');
    await adminContext.click('button:has-text("Update")');
    await adminContext.close();
    
    // Check status updated on customer page
    await page.reload();
    await expect(page.locator('.order-status')).toContainText('Preparing');
  });
});