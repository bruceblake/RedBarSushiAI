import os
import json
import pytest
from playwright.sync_api import expect
from dotenv import load_dotenv

# Load test environment variables
load_dotenv(".env.test")

"""
These tests specifically target actual API integrations.
They will be skipped if the proper API keys are not configured.
"""

# Skip all tests if API keys are not set or external tests are disabled
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_EXTERNAL_API_TESTS") != "true",
    reason="External API tests disabled (set RUN_EXTERNAL_API_TESTS=true)"
)


# Check for required API keys before running tests
def setup_module(module):
    """Report API key status at the beginning."""
    if not os.getenv("OPENAI_API_KEY") or "your-actual" in os.getenv("OPENAI_API_KEY", ""):
        print("⚠️ OpenAI API key not configured - skipping OpenAI tests")
    
    if not os.getenv("TWILIO_ACCOUNT_SID") or "your-twilio" in os.getenv("TWILIO_ACCOUNT_SID", ""):
        print("⚠️ Twilio credentials not configured - skipping Twilio tests")
    
    if not os.getenv("DELIVERECT_CLIENT_ID") or "your-deliverect" in os.getenv("DELIVERECT_CLIENT_ID", ""):
        print("⚠️ Deliverect credentials not configured - skipping Deliverect tests")


class TestOpenAIIntegration:
    """Test OpenAI API integration."""
    
    # Skip these tests if OpenAI API key is not set
    pytestmark = pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY") or "your-actual" in os.getenv("OPENAI_API_KEY", ""),
        reason="OpenAI API key not configured"
    )
    
    def test_ai_order_parsing(self, page, api_client):
        """Test AI order parsing with real OpenAI API."""
        # Test with various order texts
        order_texts = [
            "I'd like to order a California roll",
            "Can I get two spicy tuna rolls and an order of edamame",
            "Three salmon nigiri please"
        ]
        
        for order_text in order_texts:
            response = api_client.post("/api/parse-order", 
                data=json.dumps({"text": order_text}),
                headers={"Content-Type": "application/json"}
            )
            
            # Verify response
            assert response.status == 200
            result = response.json()
            
            # Should have recognized items
            assert "items" in result
            assert isinstance(result["items"], list)
            assert len(result["items"]) > 0
            
            # Each item should have required properties
            for item in result["items"]:
                assert "name" in item
                assert "quantity" in item
                assert isinstance(item["quantity"], (int, float))
    
    def test_ai_order_modification(self, page, api_client):
        """Test AI order modification with real OpenAI API."""
        # Create an initial order
        initial_order_items = [
            {"name": "California Roll", "quantity": 2, "price": 7.95},
            {"name": "Edamame", "quantity": 1, "price": 5.95}
        ]
        
        # Test a modification request
        modification_text = "Actually, make that three California rolls and add a spicy tuna roll"
        
        response = api_client.post("/api/modify-order", 
            data=json.dumps({
                "text": modification_text,
                "current_items": initial_order_items
            }),
            headers={"Content-Type": "application/json"}
        )
        
        # Verify response
        assert response.status == 200
        result = response.json()
        
        # Should have additions and removals
        assert "additions" in result
        assert "removals" in result
        
        # Should have detected the changes correctly
        assert any(
            item["name"].lower().find("california") >= 0 and item["quantity"] in [1, 3]
            for item in result["additions"]
        )
        
        assert any(
            item["name"].lower().find("spicy tuna") >= 0 and item["quantity"] == 1
            for item in result["additions"]
        )


class TestTwilioIntegration:
    """Test Twilio API integration."""
    
    # Skip these tests if Twilio credentials are not set
    pytestmark = pytest.mark.skipif(
        not os.getenv("TWILIO_ACCOUNT_SID") or "your-twilio" in os.getenv("TWILIO_ACCOUNT_SID", ""),
        reason="Twilio credentials not configured"
    )
    
    def test_sms_endpoint(self, page, api_client):
        """Test the SMS webhook endpoint with real Twilio API."""
        # Test the SMS webhook endpoint
        sms_payload = {
            "From": os.getenv("TWILIO_NUMBER", "+15551234567"),
            "Body": "menu",
            "MessageSid": "SM" + str(int(os.urandom(4).hex(), 16))
        }
        
        response = api_client.post("/sms", 
            data=sms_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        # Verify response
        assert response.status == 200
        
        # Should return TwiML
        text = response.text()
        assert "<Response>" in text
        assert "<Message>" in text
    
    def test_voice_endpoint(self, page, api_client):
        """Test the voice webhook endpoint with real Twilio API."""
        # Test the voice webhook endpoint
        voice_payload = {
            "From": os.getenv("TWILIO_NUMBER", "+15551234567"),
            "CallSid": "CA" + str(int(os.urandom(4).hex(), 16))
        }
        
        response = api_client.post("/voice", 
            data=voice_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        # Verify response
        assert response.status == 200
        
        # Should return TwiML
        text = response.text()
        assert "<Response>" in text
        assert "<Gather>" in text or "<Say>" in text


class TestDeliverectIntegration:
    """Test Deliverect API integration."""
    
    # Skip these tests if Deliverect credentials are not set
    pytestmark = pytest.mark.skipif(
        not os.getenv("DELIVERECT_CLIENT_ID") or "your-deliverect" in os.getenv("DELIVERECT_CLIENT_ID", ""),
        reason="Deliverect credentials not configured"
    )
    
    def test_menu_sync(self, page, api_client):
        """Test menu synchronization with real Deliverect API."""
        # Test with a complete Deliverect menu payload
        menu_payload = {
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
                                    "available": True,
                                    "plu": "rainbow-roll",
                                    "posId": "rainbow-roll"
                                },
                                {
                                    "id": "dragon-roll",
                                    "name": "Dragon Roll",
                                    "description": "Eel and cucumber topped with avocado",
                                    "price": 13.95,
                                    "available": True,
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
                                    "available": True,
                                    "plu": "gyoza",
                                    "posId": "gyoza"
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
        
        # Find the new items in the menu
        rainbow_roll = next((item for item in menu_data["items"] if item["name"] == "Rainbow Roll"), None)
        dragon_roll = next((item for item in menu_data["items"] if item["name"] == "Dragon Roll"), None)
        gyoza = next((item for item in menu_data["items"] if item["name"] == "Gyoza"), None)
        
        assert rainbow_roll is not None
        assert rainbow_roll["price"] == 12.95
        
        assert dragon_roll is not None
        assert dragon_roll["price"] == 13.95
        
        assert gyoza is not None
        assert gyoza["price"] == 6.95
        
        # Categories should be correct
        assert rainbow_roll["category"] == "Signature Rolls"
        assert gyoza["category"] == "Appetizers"