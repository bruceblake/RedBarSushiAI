import os
import pytest
import json
import sys
from pathlib import Path
from flask import Flask
from app import create_app, db
from app.models import Location, Order

# Auto-mark all tests in the integration directory with the integration marker
def pytest_configure(config):
    """Configure pytest - mark all tests in the integration directory"""
    # Get the integration tests directory path
    integration_path = Path(__file__).parent / 'integration'
    
    # If tests are being collected from the integration directory, mark them
    if integration_path.exists():
        for item in os.listdir(integration_path):
            if item.startswith('test_') and item.endswith('.py'):
                # Add the module to the mark
                module = f"tests.integration.{item[:-3]}"
                config.addinivalue_line("markers", f"{module}: integration test")
                
    # Also mark the load tests
    load_path = Path(__file__).parent / 'load'
    if load_path.exists():
        for item in os.listdir(load_path):
            if item.startswith('test_') and item.endswith('.py'):
                # Add the module to the mark
                module = f"tests.load.{item[:-3]}"
                config.addinivalue_line("markers", f"{module}: load test")

@pytest.fixture(scope='session')
def app():
    # Load test environment variables
    from dotenv import load_dotenv
    load_dotenv('.env.test', override=True)
    
    # Create Flask app in testing mode with SQLite in-memory database
    test_config = {
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        # Configure optimized SQLite connection for testing
        'SQLALCHEMY_ENGINE_OPTIONS': {
            'poolclass': None,  # Disable connection pooling for in-memory db
            'connect_args': {'check_same_thread': False}  # Allow multi-threaded access
        }
    }
    
    app = create_app(test_config)
    
    # Create all database tables
    with app.app_context():
        db.create_all()
    
    yield app
    
    # Clean up after tests
    with app.app_context():
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def base_url():
    # Base URL for webhook tests
    return 'https://redbarsushiai.onrender.com'

@pytest.fixture(params=['status', 'help', 'menu'])
def command(request):
    # Commands to test SMS endpoint
    return request.param

@pytest.fixture
def mock_openai(monkeypatch):
    """Mock the OpenAI API client for testing."""
    class MockResponse:
        def __init__(self, json_data, status_code=200):
            self.json_data = json_data
            self.status_code = status_code
            
        def json(self):
            return self.json_data
    
    class MockMessage:
        def __init__(self, content):
            self.content = content
    
    class MockChoice:
        def __init__(self, message):
            self.message = message
            
    class MockCompletions:
        def create(self, *args, **kwargs):
            # Determine which response to provide based on the messages in kwargs
            messages = kwargs.get('messages', [])
            response_format = kwargs.get('response_format', None)
            
            # Create a mock response with the appropriate structure
            if any("modification request" in msg.get('content', '') for msg in messages if isinstance(msg, dict)):
                # For order modification requests
                message_content = json.dumps({
                    "additions": [{"name": "Spicy Tuna Roll", "quantity": 1, "price": 8.95, "reference_handler": "spicy-tuna-1", "modifier": []}],
                    "removals": []
                })
            else:
                # For regular order parsing
                message_content = json.dumps({
                    "intent": "order_food",
                    "items": [{"name": "California Roll", "quantity": 2, "price": 7.95, "reference_handler": "cal-roll-1"}]
                })
            
            # Create a properly structured mock result object
            mock_result = type('MockCreateResult', (object,), {})
            mock_result.choices = [MockChoice(MockMessage(message_content))]
            
            # Add other expected properties
            mock_result.model = kwargs.get('model', 'gpt-4.1-mini')
            mock_result.id = "chatcmpl-123456789"
            mock_result.created = 1716038000
            
            return mock_result
    
    class MockChat:
        def __init__(self):
            self.completions = MockCompletions()
    
    class MockOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = MockChat()
    
    # Mock the OpenAI client
    monkeypatch.setattr("openai.OpenAI", MockOpenAI)
    
    # We also need to mock the Agent API if it's being imported
    # Create a mock Agent class that mimics the one in test_agent.py
    class MockAgent:
        def __init__(self, *args, **kwargs):
            self.tools = type('obj', (object,), {
                'search_menu': lambda query: {"found": True, "items": []},
                'get_details': lambda item_name: {"found": True, "item": {}},
                'get_menu_categories': lambda: ["Rolls", "Appetizers", "Nigiri"],
                'get_items_by_category': lambda category: []
            })
            self.instructions = kwargs.get('instructions', '')
            
        def create_thread(self):
            mock_thread = type('obj', (object,), {})
            
            # Add the messages method
            mock_message = type('obj', (object,), {
                'id': 'msg_123',
                'content': [type('obj', (object,), {'text': type('obj', (object,), {})})],
            })
            
            # Set appropriate response based on agent type
            if "modify existing food orders" in self.instructions:
                mock_message.content[0].text.value = json.dumps({
                    "additions": [{"name": "Spicy Tuna Roll", "quantity": 1, "price": 8.95, "reference_handler": "spicy-tuna-1", "modifier": []}],
                    "removals": []
                })
            else:
                mock_message.content[0].text.value = json.dumps({
                    "items": [{"name": "California Roll", "quantity": 1, "price": 7.95, "reference_handler": "cal-roll-1", "modifier": []}]
                })
            
            # Create mock messages class with create and list methods
            mock_messages = type('obj', (object,), {
                'create': lambda role, content: mock_message,
                'list': lambda after: [mock_message]
            })
            
            # Create mock runs class with create and wait methods
            mock_run = type('obj', (object,), {'status': 'completed'})
            mock_runs = type('obj', (object,), {
                'create': lambda: mock_run,
                'wait': lambda run_id: mock_run
            })
            
            # Add messages and runs to thread
            mock_thread.messages = mock_messages
            mock_thread.runs = mock_runs
            
            return mock_thread
            
    # Just patch the OrderParsingAgent and OrderModificationAgent instead of 
    # trying to patch the Agent class directly
    monkeypatch.setattr("app.utils.agent_utils_simple.OrderParsingAgent", MockAgent)
    
    # Also patch the analyze_user_input and get_order_modifications functions
    def mock_analyze_user_input(text):
        return {
            "intent": "order_food",
            "menu_items": [{"name": "California Roll", "quantity": 2, "price": 7.95, "reference_handler": "cal-roll-1"}]
        }
    
    def mock_get_order_modifications(text, current_items=None):
        return {
            "additions": [{"name": "Spicy Tuna Roll", "quantity": 1, "price": 8.95, "reference_handler": "spicy-tuna-1", "modifier": []}],
            "removals": []
        }
    
    monkeypatch.setattr("app.utils.agent_utils_simple.analyze_user_input", mock_analyze_user_input)
    monkeypatch.setattr("app.utils.agent_utils_simple.get_order_modifications", mock_get_order_modifications)
    
    return MockOpenAI()

@pytest.fixture
def mock_twilio(monkeypatch):
    """Mock the Twilio client for testing."""
    class MockMessage:
        def __init__(self):
            self.sid = "SM123456"
            self.status = "queued"
            
    class MockMessages:
        def create(self, *args, **kwargs):
            return MockMessage()
            
    class MockClient:
        def __init__(self, *args, **kwargs):
            self.messages = MockMessages()
            
    monkeypatch.setattr("twilio.rest.Client", MockClient)
    return MockClient()

@pytest.fixture
def mock_deliverect(monkeypatch):
    """Mock Deliverect API client for testing."""
    class MockDeliverect:
        def get_token(self, *args, **kwargs):
            # Return a proper token structure
            return {
                "access_token": "mock_token",
                "token_type": "bearer",
                "expires_in": 3600
            }
            
        def get_channels(self, *args, **kwargs):
            return ["channel1", "channel2"]
    
    # Add monkeypatch for app.utils.deliverect.get_deliverect_token
    def mock_get_deliverect_token(*args, **kwargs):
        return {
            "access_token": "mock_token",
            "token_type": "bearer",
            "expires_in": 3600
        }
        
    monkeypatch.setattr("app.utils.deliverect.get_deliverect_token", mock_get_deliverect_token)
    return MockDeliverect()

@pytest.fixture
def setup_test_menu(app):
    """Set up test menu data for testing."""
    # Create test menu data in a standard location
    menu_data = {
        "items": [
            {
                "name": "California Roll",
                "price": 7.95,
                "reference_handler": "cal-roll-1",
                "available": True,
                "category": "Rolls",
                "description": "Crab, avocado, and cucumber"
            },
            {
                "name": "Spicy Tuna Roll",
                "price": 8.95,
                "reference_handler": "spicy-tuna-1",
                "available": True,
                "category": "Rolls",
                "description": "Fresh tuna with spicy mayo"
            },
            {
                "name": "Edamame",
                "price": 5.95,
                "reference_handler": "edamame-1",
                "available": True,
                "category": "Appetizers",
                "description": "Steamed soybeans with sea salt"
            },
            {
                "name": "Salmon Nigiri",
                "price": 6.95,
                "reference_handler": "salmon-nigiri-1",
                "available": False,
                "category": "Nigiri",
                "description": "Fresh salmon over rice"
            }
        ],
        "modifiers": [
            {
                "name": "Extra Wasabi",
                "price": 0.50,
                "reference_handler": "mod-wasabi-1"
            },
            {
                "name": "Extra Ginger",
                "price": 0.50,
                "reference_handler": "mod-ginger-1"
            }
        ],
        "modifierGroups": [
            {
                "name": "Additions",
                "modifiers": ["mod-wasabi-1", "mod-ginger-1"]
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
    
    # Create the test menu file
    test_menu_path = os.path.join(os.path.dirname(__file__), '..', 'test_menu_data.json')
    with open(test_menu_path, 'w') as f:
        json.dump(menu_data, f, indent=2)
        
    # Configure app to use this menu
    app.config['MENU_FILE_PATH'] = test_menu_path
    
    # Also set up the test data directory
    os.makedirs(os.path.join(os.path.dirname(__file__), '..', 'testing_data'), exist_ok=True)
    
    return menu_data

@pytest.fixture
def mock_menu_data():
    """Return a standard set of menu data for testing."""
    return {
        "items": [
            {
                "name": "California Roll",
                "price": 7.95,
                "reference_handler": "cal-roll-1",
                "available": True,
                "category": "Rolls",
                "description": "Crab, avocado, and cucumber"
            },
            {
                "name": "Spicy Tuna Roll",
                "price": 8.95,
                "reference_handler": "spicy-tuna-1",
                "available": True,
                "category": "Rolls",
                "description": "Fresh tuna with spicy mayo"
            }
        ],
        "modifiers": [
            {
                "name": "Extra Wasabi",
                "price": 0.50,
                "reference_handler": "mod-wasabi-1"
            }
        ],
        "modifierGroups": [
            {
                "name": "Additions",
                "modifiers": ["mod-wasabi-1"]
            }
        ],
        "name_variants": {
            "california roll": "California Roll",
            "spicy tuna roll": "Spicy Tuna Roll"
        }
    }

@pytest.fixture
def app_with_locations(app):
    """Set up app with sample locations in the database."""
    with app.app_context():
        # First, make sure the table exists and is empty
        db.create_all()
        
        # Clean up the entire location table to avoid any integrity errors
        db.session.query(Location).delete()
        db.session.commit()
        
        # Create test locations with the ORM
        try:
            # Add downtown location
            downtown = Location(
                id="downtown", 
                name="Downtown Location", 
                status="active",
                webhook_base="https://example.com/downtown"
            )
            db.session.add(downtown)
            db.session.commit()
            
            # Add uptown location
            uptown = Location(
                id="uptown", 
                name="Uptown Location", 
                status="registered",
                webhook_base="https://example.com/uptown"
            )
            db.session.add(uptown)
            db.session.commit()
            
            print("Successfully added test locations")
        except Exception as e:
            db.session.rollback()
            print(f"Error adding locations: {str(e)}")
            raise  # Re-raise to fail the test explicitly
    
    return app