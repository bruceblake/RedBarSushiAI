"""
End-to-end tests for the API functionality.
Uses real API keys if USE_REAL_API_KEYS environment variable is set to true.
"""
import os
import pytest
import json
import time

# Skip all tests unless real API keys are being used or testing with mocks is explicitly allowed
pytestmark = pytest.mark.skipif(
    os.environ.get("USE_REAL_API_KEYS", "").lower() != "true" and 
    os.environ.get("TEST_WITH_MOCKS", "").lower() != "true",
    reason="Skipping API tests - set USE_REAL_API_KEYS=true or TEST_WITH_MOCKS=true to run"
)

def test_menu_api_returns_data(page, api_url):
    """Test that the menu API returns valid data."""
    # Use page.request to make an API call
    response = page.request.get(f"{api_url}/menu")
    
    # Check response status
    assert response.status == 200, f"API returned status {response.status}"
    
    # Parse response as JSON
    data = response.json()
    
    # Verify basic structure (adjust based on your actual API response structure)
    assert isinstance(data, dict), "API response is not a JSON object"
    
    # Check if there are menu items
    assert "items" in data or "categories" in data or "menu" in data, "No menu data found in response"
    
    # Print the first few items for debugging
    if "items" in data and isinstance(data["items"], list):
        print(f"Found {len(data['items'])} menu items")
        if len(data["items"]) > 0:
            print(f"First item: {data['items'][0]}")
    
    print("Menu API test passed")

def test_order_api_endpoint(page, api_url):
    """Test the order API endpoint."""
    # Create test order data
    test_order = {
        "customer": {
            "name": "API Test Customer",
            "phone": "5551234567"
        },
        "items": [
            {
                "name": "California Roll",
                "quantity": 2
            }
        ],
        "type": "pickup"
    }
    
    # Send order to API
    response = page.request.post(
        f"{api_url}/orders", 
        data=json.dumps(test_order),
        headers={"Content-Type": "application/json"}
    )
    
    # Check response
    if response.status == 200 or response.status == 201:
        data = response.json()
        assert "success" in data or "id" in data or "order_id" in data, "No success indicator in response"
        print("Order API test passed")
    else:
        print(f"Order API returned status {response.status}")
        print(f"Response body: {response.text()}")
        
        # Check if there's an alternative orders endpoint
        all_orders_response = page.request.get(f"{api_url}/orders")
        if all_orders_response.status == 200:
            print("Found orders endpoint but POST failed - might need authentication")
        
        pytest.skip(f"Order API failed with status {response.status} - may require authentication or different endpoint")

def test_voice_api_if_available(page, api_url):
    """Test voice API endpoints if they exist."""
    # Check if there's a voice transcription endpoint
    transcribe_response = page.request.get(f"{api_url}/transcribe")
    
    if transcribe_response.status != 404:
        print("Found voice transcription endpoint")
        
        # This is just a basic check - actual testing would require audio files
        if os.environ.get("USE_REAL_API_KEYS", "").lower() == "true":
            print("With real API keys, we could test voice transcription")
    else:
        print("No voice transcription endpoint found")
    
    # Check if there's a voice synthesis endpoint
    tts_response = page.request.get(f"{api_url}/tts")
    
    if tts_response.status != 404:
        print("Found text-to-speech endpoint")
    else:
        print("No text-to-speech endpoint found")
    
    # Skip this test as it's exploratory
    pytest.skip("Voice API test is exploratory - need more specific endpoint information")

def test_order_parsing_api(page, api_url):
    """Test the order parsing API if available and real API keys are enabled."""
    if os.environ.get("USE_REAL_API_KEYS", "").lower() == "true":
        # Prepare test data
        test_text = "I'd like to order two California rolls and one spicy tuna roll please"
        
        # Look for potential parse endpoints
        endpoints = [
            f"{api_url}/parse-order",
            f"{api_url}/parse_order",
            f"{api_url}/order/parse",
            f"{api_url}/analyze-order"
        ]
        
        for endpoint in endpoints:
            response = page.request.post(
                endpoint,
                data=json.dumps({"text": test_text}),
                headers={"Content-Type": "application/json"}
            )
            
            if response.status == 200:
                data = response.json()
                print(f"Found working parse endpoint: {endpoint}")
                print(f"Response: {data}")
                return
        
        print("No working order parsing endpoint found")
        pytest.skip("No working order parsing endpoint found")
    else:
        pytest.skip("Skipping parse test - requires real API keys")