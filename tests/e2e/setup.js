// Global setup - runs before all tests
const { chromium } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

async function globalSetup() {
  console.log('Setting up test environment...');
  
  // Initialize the application with test data
  try {
    // Ensure test menu data exists
    const testMenuData = {
      items: [
        {
          name: "California Roll",
          price: 7.95,
          reference_handler: "cal-roll-1",
          available: true,
          category: "Rolls",
          description: "Crab, avocado, and cucumber"
        },
        {
          name: "Spicy Tuna Roll",
          price: 8.95,
          reference_handler: "spicy-tuna-1",
          available: true,
          category: "Rolls",
          description: "Fresh tuna with spicy mayo"
        }
      ],
      modifiers: [
        {
          name: "Extra Wasabi",
          price: 0.50,
          reference_handler: "mod-wasabi-1"
        }
      ],
      modifierGroups: [
        {
          name: "Additions",
          modifiers: ["mod-wasabi-1"]
        }
      ],
      name_variants: {
        "california roll": "California Roll",
        "spicy tuna roll": "Spicy Tuna Roll"
      }
    };
    
    // Create a test menu file if it doesn't exist
    const testMenuPath = path.join(__dirname, '../../test_menu_data.json');
    fs.writeFileSync(testMenuPath, JSON.stringify(testMenuData, null, 2));
    console.log('Test menu data created successfully');
  } catch (error) {
    console.error('Error setting up test data:', error);
  }
}

module.exports = globalSetup;