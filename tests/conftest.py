import os
import pytest
import json
from flask import Flask
from app import create_app, db
from app.models import Location, Order

@pytest.fixture(scope='session')
def app():
    # Create Flask app in testing mode
    app = create_app({'TESTING': True})
    
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
    
    class MockOpenAI:
        def __init__(self, *args, **kwargs):
            pass
            
        def chat_completions_create(self, *args, **kwargs):
            return {"choices": [{"message": {"content": json.dumps({
                "intent": "order",
                "items": [{"name": "California Roll", "quantity": 2}],
                "modifications": []
            })}}]}
            
    monkeypatch.setattr("openai.OpenAI", MockOpenAI)
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
            return "mock_token_12345"
            
        def get_channels(self, *args, **kwargs):
            return ["channel1", "channel2"]
            
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
        # Clean up any existing records
        Location.query.delete()
        db.session.commit()
        
        # Add new location records
        locations = [
            Location(id="downtown", name="Downtown Location", status="active",
                     webhook_base="https://example.com/downtown"),
            Location(id="uptown", name="Uptown Location", status="registered",
                     webhook_base="https://example.com/uptown")
        ]
        for loc in locations:
            db.session.add(loc)
        db.session.commit()
    
    return app