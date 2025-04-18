// @ts-check
const { test, expect } = require('@playwright/test');

// Menu feature tests
test.describe('Menu feature tests', () => {
  test('can fetch menu via API', async ({ request }) => {
    // Make a request to the menu API endpoint
    const response = await request.get('/api/menu');
    
    // Verify response status
    expect(response.status()).toBe(200);
    
    // Parse response body
    const menuData = await response.json();
    
    // Validate menu structure
    expect(menuData).toHaveProperty('items');
    expect(Array.isArray(menuData.items)).toBeTruthy();
    
    // Check if menu has items
    expect(menuData.items.length).toBeGreaterThan(0);
    
    // Check structure of a menu item
    const firstItem = menuData.items[0];
    expect(firstItem).toHaveProperty('name');
    expect(firstItem).toHaveProperty('price');
    expect(firstItem).toHaveProperty('reference_handler');
  });
  
  test('menu item availability toggle works', async ({ page }) => {
    // Go to admin page (assuming authentication is bypassed in test mode)
    await page.goto('/admin/menu');
    
    // Find a menu item toggle
    const itemToggle = page.locator('.availability-toggle').first();
    
    // Get current state
    const initialState = await itemToggle.isChecked();
    
    // Toggle the state
    await itemToggle.click();
    
    // Verify toggle changed state
    await expect(itemToggle).toBeChecked(!initialState);
    
    // Refresh page to verify persistence
    await page.reload();
    
    // Check that the new state persisted
    await expect(itemToggle).toBeChecked(!initialState);
  });
  
  test('snooze functionality works', async ({ page }) => {
    // Go to admin page
    await page.goto('/admin/menu');
    
    // Find snooze button for an item
    const snoozeButton = page.locator('.snooze-button').first();
    
    // Click snooze
    await snoozeButton.click();
    
    // Set snooze duration in dialog
    await page.locator('.snooze-duration').fill('30');
    await page.locator('button:has-text("Snooze Item")').click();
    
    // Verify item shows as snoozed
    await expect(page.locator('.snoozed-badge')).toBeVisible();
    
    // Verify item is not available in customer menu
    await page.goto('/menu');
    const itemName = await page.locator('.unavailable-item').textContent();
    expect(itemName).toBeDefined();
  });
});