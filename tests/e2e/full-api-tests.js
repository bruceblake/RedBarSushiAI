// @ts-check
const { test, expect } = require('@playwright/test');
require('dotenv').config({ path: '.env.test' });

/**
 * These tests specifically target actual API integrations
 * They will be skipped if the proper API keys are not configured
 */
test.describe('Full API Integration Tests', () => {
  // Check for required API keys before running tests
  test.beforeAll(({ }) => {
    // Report API key status
    if (!process.env.OPENAI_API_KEY || process.env.OPENAI_API_KEY.includes('your-actual')) {
      test.skip(true, 'OpenAI API key not configured');
    }
    
    if (!process.env.TWILIO_ACCOUNT_SID || process.env.TWILIO_ACCOUNT_SID.includes('your-twilio')) {
      test.skip(true, 'Twilio credentials not configured');
    }
    
    if (!process.env.DELIVERECT_CLIENT_ID || process.env.DELIVERECT_CLIENT_ID.includes('your-deliverect')) {
      test.skip(true, 'Deliverect credentials not configured');
    }
    
    if (process.env.RUN_EXTERNAL_API_TESTS !== 'true') {
      test.skip(true, 'External API tests disabled (set RUN_EXTERNAL_API_TESTS=true)');
    }
  });
  
  test.describe('OpenAI Integration', () => {
    test('voice transcription works', async ({ request }) => {
      // This test requires a test audio file
      const testAudioPath = 'tests/e2e/test-data/test-audio.mp3';
      
      // Create a FormData object
      const formData = new FormData();
      formData.append('file', await request.fetch(testAudioPath));
      formData.append('model', 'whisper-1');
      
      // Test the transcription endpoint
      const response = await request.post('/api/transcribe', {
        data: formData,
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      
      // Verify response
      expect(response.status()).toBe(200);
      const result = await response.json();
      
      // Should have transcription text
      expect(result).toHaveProperty('text');
      expect(typeof result.text).toBe('string');
      expect(result.text.length).toBeGreaterThan(0);
    });
    
    test('AI order parsing works', async ({ request }) => {
      // Test with various order texts
      const orderTexts = [
        "I'd like to order a California roll",
        "Can I get two spicy tuna rolls and an order of edamame",
        "Three salmon nigiri please"
      ];
      
      for (const orderText of orderTexts) {
        const response = await request.post('/api/parse-order', {
          data: { text: orderText },
          headers: { 'Content-Type': 'application/json' }
        });
        
        // Verify response
        expect(response.status()).toBe(200);
        const result = await response.json();
        
        // Should have recognized items
        expect(result).toHaveProperty('items');
        expect(Array.isArray(result.items)).toBeTruthy();
        expect(result.items.length).toBeGreaterThan(0);
        
        // Each item should have required properties
        for (const item of result.items) {
          expect(item).toHaveProperty('name');
          expect(item).toHaveProperty('quantity');
          expect(typeof item.quantity).toBe('number');
        }
      }
    });
    
    test('AI order modification works', async ({ request }) => {
      // Create an initial order
      const initialOrderItems = [
        { name: 'California Roll', quantity: 2, price: 7.95 },
        { name: 'Edamame', quantity: 1, price: 5.95 }
      ];
      
      // Test a modification request
      const modificationText = "Actually, make that three California rolls and add a spicy tuna roll";
      
      const response = await request.post('/api/modify-order', {
        data: { 
          text: modificationText,
          current_items: initialOrderItems
        },
        headers: { 'Content-Type': 'application/json' }
      });
      
      // Verify response
      expect(response.status()).toBe(200);
      const result = await response.json();
      
      // Should have additions and removals
      expect(result).toHaveProperty('additions');
      expect(result).toHaveProperty('removals');
      
      // Should have detected the changes correctly
      expect(result.additions.some(item => 
        item.name.includes('California') && item.quantity === 1
      )).toBeTruthy();
      
      expect(result.additions.some(item => 
        item.name.includes('Spicy Tuna') && item.quantity === 1
      )).toBeTruthy();
    });
  });
  
  test.describe('Twilio Integration', () => {
    test('SMS endpoint accepts messages', async ({ request }) => {
      // Test the SMS webhook endpoint
      const smsPayload = {
        From: process.env.TWILIO_NUMBER,
        Body: 'menu',
        MessageSid: 'SM' + Date.now()
      };
      
      const response = await request.post('/sms', {
        form: smsPayload,
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      });
      
      // Verify response
      expect(response.status()).toBe(200);
      
      // Should return TwiML
      const text = await response.text();
      expect(text).toContain('<Response>');
      expect(text).toContain('<Message>');
    });
    
    test('voice endpoint returns TwiML', async ({ request }) => {
      // Test the voice webhook endpoint
      const voicePayload = {
        From: process.env.TWILIO_NUMBER,
        CallSid: 'CA' + Date.now()
      };
      
      const response = await request.post('/voice', {
        form: voicePayload,
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      });
      
      // Verify response
      expect(response.status()).toBe(200);
      
      // Should return TwiML
      const text = await response.text();
      expect(text).toContain('<Response>');
      expect(text).toContain('<Gather>');
    });
  });
  
  test.describe('Deliverect Integration', () => {
    test('menu sync processes menu data correctly', async ({ request }) => {
      // Test with a complete Deliverect menu payload
      const menuPayload = {
        "type": "menu.updated",
        "data": {
          "menu": {
            "categories": [
              {
                "name": "Signature Rolls",
                "products": [
                  {
                    "id": "rainbow-roll",
                    "name": "Rainbow Roll",
                    "description": "California roll topped with assorted sashimi",
                    "price": 12.95,
                    "available": true,
                    "plu": "rainbow-roll",
                    "posId": "rainbow-roll"
                  },
                  {
                    "id": "dragon-roll",
                    "name": "Dragon Roll",
                    "description": "Eel and cucumber topped with avocado",
                    "price": 13.95,
                    "available": true,
                    "plu": "dragon-roll",
                    "posId": "dragon-roll"
                  }
                ]
              },
              {
                "name": "Appetizers",
                "products": [
                  {
                    "id": "gyoza",
                    "name": "Gyoza",
                    "description": "Pan-fried pork dumplings",
                    "price": 6.95,
                    "available": true,
                    "plu": "gyoza",
                    "posId": "gyoza"
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
      
      // Find the new items in the menu
      const rainbowRoll = menuData.items.find(item => item.name === 'Rainbow Roll');
      const dragonRoll = menuData.items.find(item => item.name === 'Dragon Roll');
      const gyoza = menuData.items.find(item => item.name === 'Gyoza');
      
      expect(rainbowRoll).toBeDefined();
      expect(rainbowRoll.price).toBe(12.95);
      
      expect(dragonRoll).toBeDefined();
      expect(dragonRoll.price).toBe(13.95);
      
      expect(gyoza).toBeDefined();
      expect(gyoza.price).toBe(6.95);
      
      // Categories should be correct
      expect(rainbowRoll.category).toBe('Signature Rolls');
      expect(gyoza.category).toBe('Appetizers');
    });
  });
});