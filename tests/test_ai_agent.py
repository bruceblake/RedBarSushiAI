"""
Test suite for the restaurant AI agent.
This includes tests for menu queries, conversation handling, and order processing.
"""
import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock, call

# Mock dependencies
sys.modules['celery'] = MagicMock()
sys.modules['celery_app'] = MagicMock()
sys.modules['tasks'] = MagicMock()
sys.modules['openai.agent'] = MagicMock()
sys.modules['openai.agent.types'] = MagicMock()

# Import modules to test
from app.utils.menu_utils import load_menu_data, find_menu_item_by_name, get_popular_menu_items
from app.utils.agent_utils_simple import process_user_input


class TestMenuLookup:
    """Test the menu lookup capabilities of the AI agent."""
    
    @pytest.fixture
    def sample_menu(self):
        """Create a sample menu for testing."""
        return {
            "items": [
                {
                    "name": "California Roll",
                    "price": 7.95,
                    "reference_handler": "cal-roll-1",
                    "available": True,
                    "category": "Rolls"
                },
                {
                    "name": "Spicy Tuna Roll",
                    "price": 8.95,
                    "reference_handler": "spicy-tuna-1",
                    "available": True,
                    "category": "Rolls"
                },
                {
                    "name": "Edamame",
                    "price": 5.95,
                    "reference_handler": "edamame-1",
                    "available": True,
                    "category": "Appetizers"
                },
                {
                    "name": "Salmon Nigiri",
                    "price": 6.95,
                    "reference_handler": "salmon-nigiri-1",
                    "available": False,  # Item is unavailable
                    "category": "Nigiri"
                }
            ],
            "name_variants": {
                "california roll": "California Roll",
                "cali roll": "California Roll",
                "california": "California Roll",
                "spicy tuna": "Spicy Tuna Roll",
                "spicy tuna roll": "Spicy Tuna Roll",
                "edamame": "Edamame",
                "salmon": "Salmon Nigiri",
                "salmon nigiri": "Salmon Nigiri"
            }
        }
    
    @patch('app.utils.menu_utils.load_menu_data')
    def test_find_menu_item_exact_match(self, mock_load_menu_data, sample_menu):
        """Test finding a menu item with an exact match."""
        mock_load_menu_data.return_value = sample_menu
        
        # Test with exact name
        item = find_menu_item_by_name("California Roll")
        assert item is not None
        assert item["name"] == "California Roll"
        assert item["price"] == 7.95
        
        # Test with case insensitivity
        item = find_menu_item_by_name("california roll")
        assert item is not None
        assert item["name"] == "California Roll"
    
    @patch('app.utils.menu_utils.load_menu_data')
    def test_find_menu_item_variant_match(self, mock_load_menu_data, sample_menu):
        """Test finding a menu item using name variants."""
        mock_load_menu_data.return_value = sample_menu
        
        # Test with name variant
        item = find_menu_item_by_name("cali roll")
        assert item is not None
        assert item["name"] == "California Roll"
        
        # Test with partial name
        item = find_menu_item_by_name("california")
        assert item is not None
        assert item["name"] == "California Roll"
    
    @patch('app.utils.menu_utils.load_menu_data')
    def test_find_menu_item_availability(self, mock_load_menu_data, sample_menu):
        """Test finding a menu item with availability check."""
        mock_load_menu_data.return_value = sample_menu
        
        # Test with unavailable item
        item = find_menu_item_by_name("Salmon Nigiri", check_availability=True)
        assert item is None
        
        # Test with available item
        item = find_menu_item_by_name("California Roll", check_availability=True)
        assert item is not None
        assert item["name"] == "California Roll"
    
    @patch('app.utils.menu_utils.load_menu_data')
    def test_get_popular_items(self, mock_load_menu_data, sample_menu):
        """Test getting popular menu items."""
        mock_load_menu_data.return_value = sample_menu
        
        items = get_popular_menu_items(count=2)
        assert len(items) == 2
        assert items[0]["name"] in ["California Roll", "Spicy Tuna Roll", "Edamame"]
        assert items[1]["name"] in ["California Roll", "Spicy Tuna Roll", "Edamame"]


class TestConversationHandling:
    """Test the conversation handling capabilities of the AI agent."""
    
    @pytest.fixture
    def mock_openai_response(self):
        """Create a mock OpenAI response."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "intent": "order_food",
            "menu_items": [
                {"name": "California Roll", "quantity": 2}
            ]
        })
        return mock_response
    
    @patch('app.utils.agent_utils_simple.openai.chat.completions.create')
    @patch('app.utils.menu_utils.load_menu_data')
    def test_process_user_input_order(self, mock_load_menu_data, mock_openai_create, sample_menu, mock_openai_response):
        """Test processing user input for an order."""
        mock_load_menu_data.return_value = sample_menu
        mock_openai_create.return_value = mock_openai_response
        
        result = process_user_input("I'd like two California Rolls please")
        assert result["intent"] == "order_food"
        assert len(result["menu_items"]) == 1
        assert result["menu_items"][0]["name"] == "California Roll"
        assert result["menu_items"][0]["quantity"] == 2
    
    @patch('app.utils.agent_utils_simple.openai.chat.completions.create')
    def test_process_user_input_menu_query(self, mock_openai_create):
        """Test processing user input for a menu query."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "intent": "menu_query",
            "query": {"type": "price", "item": "California Roll"}
        })
        mock_openai_create.return_value = mock_response
        
        result = process_user_input("How much is a California Roll?")
        assert result["intent"] == "menu_query"
        assert result["query"]["type"] == "price"
        assert result["query"]["item"] == "California Roll"
    
    @patch('app.utils.agent_utils_simple.openai.chat.completions.create')
    def test_process_user_input_greeting(self, mock_openai_create):
        """Test processing user input for a greeting."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "intent": "greeting"
        })
        mock_openai_create.return_value = mock_response
        
        result = process_user_input("Hello, is this Red Bar Sushi?")
        assert result["intent"] == "greeting"


class TestOrderModification:
    """Test the order modification capabilities of the AI agent."""
    
    @pytest.fixture
    def current_order(self):
        """Create a current order for testing."""
        return [
            {
                "name": "California Roll",
                "quantity": 1,
                "price": 7.95,
                "reference_handler": "cal-roll-1",
                "modifier": []
            }
        ]
    
    @patch('app.routes.order.find_menu_item_by_name')
    def test_apply_modifications_addition(self, mock_find_menu_item, current_order):
        """Test applying additions to an order."""
        from app.routes.order import apply_modifications
        
        # Setup mock to return items when searched
        def mock_find_item(name, check_availability=False):
            if name.lower() == "spicy tuna roll":
                return {
                    "name": "Spicy Tuna Roll",
                    "price": 8.95,
                    "reference_handler": "spicy-tuna-1"
                }
            return None
        
        mock_find_menu_item.side_effect = mock_find_item
        
        # Test adding an item
        modifications = {
            "additions": [
                {"name": "Spicy Tuna Roll", "quantity": 1}
            ],
            "removals": []
        }
        
        updated_order = apply_modifications(current_order, modifications)
        
        # Check the result
        assert len(updated_order) == 2
        assert updated_order[0]["name"] == "California Roll"
        assert updated_order[1]["name"] == "Spicy Tuna Roll"
        assert updated_order[1]["quantity"] == 1
    
    @patch('app.routes.order.find_menu_item_by_name')
    def test_apply_modifications_removal(self, mock_find_menu_item, current_order):
        """Test applying removals to an order."""
        from app.routes.order import apply_modifications
        
        # Test removing an item
        modifications = {
            "additions": [],
            "removals": [
                {"name": "California Roll", "quantity": 1}
            ]
        }
        
        updated_order = apply_modifications(current_order, modifications)
        
        # Check the result
        assert len(updated_order) == 0


class TestRealtimeAudio:
    """Test the realtime audio processing capabilities."""
    
    @patch('app.utils.realtime_audio.openai.chat.completions.create')
    def test_realtime_system_prompts(self, mock_openai_create):
        """Test that system prompts include menu verification instructions."""
        from app.utils.realtime_audio import process_chunk
        
        # Setup mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].delta = MagicMock()
        mock_response.choices[0].delta.content = "Hello, welcome to Red Bar Sushi"
        mock_openai_create.return_value = mock_response
        
        # Call the function
        process_chunk("Hello", "session123", callback=lambda *args: None)
        
        # Check that menu verification was included in the system prompt
        called_args = mock_openai_create.call_args[1]
        system_message = None
        for message in called_args["messages"]:
            if message["role"] == "system":
                system_message = message["content"]
                break
        
        assert system_message is not None
        assert "check the actual menu data" in system_message.lower() or "verify all menu items exist" in system_message.lower()
    
    @patch('app.utils.direct_realtime.openai.chat.completions.create')
    def test_direct_realtime_model_selection(self, mock_openai_create):
        """Test that the right model is used for direct realtime processing."""
        from app.utils.direct_realtime import process_audio
        
        # Setup mock response
        mock_response = MagicMock()
        mock_openai_create.return_value = mock_response
        
        # Call the function
        process_audio("dummy_content", callback=lambda *args: None)
        
        # Check the model being used
        model_used = mock_openai_create.call_args[1]["model"]
        assert model_used == "gpt-4.1-mini" or model_used == "gpt-4o" or model_used == "gpt-4.1-preview"


class TestDeliverectIntegration:
    """Test the Deliverect integration capabilities."""
    
    @pytest.fixture
    def sample_deliverect_data(self):
        """Create sample Deliverect data for testing."""
        return {
            "categories": [
                {
                    "name": "Rolls",
                    "products": [
                        {
                            "name": "California Roll",
                            "price": 795,  # In cents
                            "id": "cal-roll-1"
                        },
                        {
                            "name": "Spicy Tuna Roll",
                            "price": 895,  # In cents
                            "id": "spicy-tuna-1"
                        }
                    ]
                }
            ]
        }
    
    def test_process_deliverect_menu(self, sample_deliverect_data):
        """Test processing a Deliverect menu."""
        from app.utils.deliverect import process_deliverect_menu
        
        processed_menu = process_deliverect_menu(sample_deliverect_data)
        
        # Check the result
        assert "items" in processed_menu
        assert len(processed_menu["items"]) == 2
        assert processed_menu["items"][0]["name"] == "California Roll"
        assert processed_menu["items"][0]["price"] == 7.95  # Converted from cents to dollars
        assert processed_menu["items"][0]["reference_handler"] == "cal-roll-1"
        assert "category" in processed_menu["items"][0]
        assert processed_menu["items"][0]["category"] == "Rolls"
        assert "name_variants" in processed_menu
        assert "california roll" in processed_menu["name_variants"]


if __name__ == "__main__":
    # This allows running the tests directly from this file
    pytest.main(["-xvs", __file__])