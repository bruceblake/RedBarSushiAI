// @ts-check
const { test, expect } = require('@playwright/test');

// Basic smoke test for the application
test('homepage loads successfully', async ({ page }) => {
  await page.goto('http://localhost:5000');
  
  // Basic assertion that the page loaded
  await expect(page).toHaveTitle(/Red Bar Sushi/);
});

// Menu page test
test('menu page displays items', async ({ page }) => {
  await page.goto('http://localhost:5000/menu');
  
  // Wait for menu items to load
  await page.waitForSelector('.menu-item', { timeout: 5000 });
  
  // Check that menu items exist
  const menuItems = await page.locator('.menu-item').count();
  expect(menuItems).toBeGreaterThan(0);
});

// Order form test
test('order form submission', async ({ page }) => {
  await page.goto('http://localhost:5000/order');
  
  // Fill out order form
  await page.fill('input[name="name"]', 'Test Customer');
  await page.fill('input[name="phone"]', '5551234567');
  
  // Select a menu item (adjust selectors based on your actual page structure)
  await page.click('.menu-select');
  await page.click('text=California Roll');
  
  // Add to cart
  await page.click('button:has-text("Add to Cart")');
  
  // Submit order
  await page.click('button:has-text("Place Order")');
  
  // Verify order confirmation appears
  await expect(page.locator('.order-confirmation')).toBeVisible();
  await expect(page.locator('.order-number')).toBeVisible();
});