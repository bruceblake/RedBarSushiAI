"""
conftest.py - Global pytest fixtures for RedBarSushiAI testing
"""
import json
import os
import tempfile
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
import sys

# Create Agent mock class
class MockAgent:
    def __init__(self, *args, **kwargs):
        self.tools = MagicMock()
        self.tools.search_menu = MagicMock(return_value={"found": True, "items": []})
        self.tools.get_details = MagicMock(return_value={"found": True, "item": {}})
        
    def create_thread(self):
        mock_thread = MagicMock()
        mock_run = MagicMock()
        mock_message = MagicMock()
        
        # Add required properties
        mock_message.id = "msg_123"
        mock_message.content = [MagicMock()]
        mock_message.content[0].text = MagicMock()
        mock_message.content[0].text.value = json.dumps({"items": [{"name": "California Roll", "quantity": 1}]})
        
        # Configure the mock objects
        mock_thread.messages.create.return_value = mock_message
        mock_thread.messages.list.return_value = [mock_message]
        mock_thread.runs.create.return_value = mock_run
        mock_thread.runs.wait.return_value = mock_run
        
        return mock_thread

# Mock all the required modules
openai_mock = MagicMock()
openai_mock.api_key = "test_key"
agent_mock = MagicMock()
agent_mock.Agent = MockAgent

# Apply the necessary mocks
sys.modules['openai'] = openai_mock
sys.modules['openai.agent'] = agent_mock
sys.modules['openai.agent.types'] = MagicMock()
sys.modules['celery'] = MagicMock()
sys.modules['celery_app'] = MagicMock()
sys.modules['tasks'] = MagicMock()
tasks_mock = sys.modules['tasks']
tasks_mock.send_confirmation_sms_task = MagicMock()
tasks_mock.send_confirmation_sms_task.delay = MagicMock()
tasks_mock.send_order_status_update_task = MagicMock()
tasks_mock.send_order_status_update_task.delay = MagicMock()

# Now import from app
from app import create_app, db


@pytest.fixture
def app():
    """Create and configure a Flask app for testing."""
    # Create a temporary file to serve as the database
    db_fd, db_path = tempfile.mkstemp()
    
    # Configure app for testing with SQLite
    test_config = {
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'SQLALCHEMY_ENGINE_OPTIONS': {
            'connect_args': {'check_same_thread': False}
        },
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'SERVER_NAME': 'localhost',
        'WTF_CSRF_ENABLED': False,
        'MENU_FILE_PATH': os.path.join(os.path.dirname(__file__), 'test_menu_data.json'),
        'BASE_URL': 'https://test.example.com'
    }
    app = create_app(test_config=test_config)
    
    # Share channel_status between modules
    from app.routes.order import channel_status
    app.config['channel_status'] = channel_status
    
    # Create the database and the tables
    with app.app_context():
        db.create_all()
    
    yield app
    
    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """A test CLI runner for the app."""
    return app.test_cli_runner()


@pytest.fixture
def app_context(app):
    """App context for tests."""
    with app.app_context() as ctx:
        yield ctx


@pytest.fixture
def mock_menu_data():
    """Sample menu data for testing."""
    return {
        "items": [
            {
                "name": "California Roll",
                "price": 9.95,
                "reference_handler": "cal_roll_1",
                "snoozed": False,
                "scheduleAvailable": True,
                "available": True,
                "availabilities": [
                    {"dayOfWeek": 1, "startTime": "11:00", "endTime": "22:00"},
                    {"dayOfWeek": 2, "startTime": "11:00", "endTime": "22:00"},
                    {"dayOfWeek": 3, "startTime": "11:00", "endTime": "22:00"},
                    {"dayOfWeek": 4, "startTime": "11:00", "endTime": "22:00"},
                    {"dayOfWeek": 5, "startTime": "11:00", "endTime": "23:00"},
                    {"dayOfWeek": 6, "startTime": "11:00", "endTime": "23:00"},
                    {"dayOfWeek": 7, "startTime": "12:00", "endTime": "21:00"}
                ]
            },
            {
                "name": "Spicy Tuna Roll",
                "price": 11.95,
                "reference_handler": "spicy_tuna_1",
                "snoozed": False,
                "scheduleAvailable": True,
                "available": True,
                "availabilities": []
            },
            {
                "name": "Dragon Roll",
                "price": 14.95,
                "reference_handler": "dragon_roll_1",
                "snoozed": True,
                "snoozeStart": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
                "snoozeEnd": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                "scheduleAvailable": True,
                "available": False,
                "availabilities": []
            },
            {
                "name": "Miso Soup",
                "price": 3.50,
                "reference_handler": "miso_soup_1",
                "snoozed": False,
                "scheduleAvailable": False,  # Not available based on schedule
                "available": False,
                "availabilities": [
                    {"dayOfWeek": 1, "startTime": "17:00", "endTime": "22:00"}
                ]
            }
        ],
        "modifiers": [
            {
                "name": "Spicy Mayo",
                "price": 0.50,
                "reference_handler": "mod_spicy_mayo",
                "available": True
            },
            {
                "name": "Extra Wasabi",
                "price": 0.50,
                "reference_handler": "mod_wasabi",
                "available": True
            }
        ],
        "modifierGroups": [
            {
                "name": "Sauces",
                "modifiers": ["mod_spicy_mayo"],
                "minAllowed": 0,
                "maxAllowed": 2
            },
            {
                "name": "Required Sides",
                "modifiers": ["mod_wasabi"],
                "minAllowed": 1,
                "maxAllowed": 1
            }
        ],
        "name_variants": {
            "california roll": "California Roll",
            "california": "California Roll",
            "roll": "California Roll",
            "californiaroll": "California Roll",
            "spicy tuna roll": "Spicy Tuna Roll",
            "spicy": "Spicy Tuna Roll",
            "tuna": "Spicy Tuna Roll",
            "dragon roll": "Dragon Roll",
            "dragon": "Dragon Roll",
            "miso soup": "Miso Soup",
            "miso": "Miso Soup",
            "soup": "Miso Soup"
        }
    }


@pytest.fixture
def setup_test_menu(app, mock_menu_data):
    """Set up a test menu file."""
    menu_path = app.config['MENU_FILE_PATH']
    os.makedirs(os.path.dirname(menu_path), exist_ok=True)
    
    with open(menu_path, 'w') as f:
        json.dump(mock_menu_data, f)
    
    # Force a cache refresh in menu_utils
    from app.utils.menu_utils import load_menu_data
    load_menu_data(force_refresh=True)
    
    yield
    
    # Clean up
    if os.path.exists(menu_path):
        os.remove(menu_path)


@pytest.fixture
def mock_deliverect():
    """Mock Deliverect API for testing."""
    with patch('requests.post') as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True, 'orderId': 'test123'}
        mock_post.return_value = mock_response
        
        # Also mock the token fetching
        mock_token_response = MagicMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            'access_token': 'mock_token',
            'expires_in': 3600
        }
        
        # Make the first call return the token response
        mock_post.side_effect = [mock_token_response, mock_response]
        
        yield mock_post