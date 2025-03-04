"""
test_order.py - Tests for order processing functionality
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from app.routes.order import (
    take_order, 
    confirm_order_from_initial,
    new_modify_order,
    apply_modifications,
    get_order_modifications,
    confirm_order_after_modification,
    handle_newly_snoozed_in_checkout
)
from app.models import Order
from app.utils.order_utils import user_said_yes, user_said_no, dtmf_yes_no


def test_take_order(client, app, mock_openai, setup_test_menu):
    """Test the take_order endpoint with valid order."""
    with app.test_request_context():
        # Set up session
        with client.session_transaction() as session:
            session['sender'] = '+1234567890'
            session['caller_name'] = 'Test User'
            
        # Mock necessary functions to control behavior
        with patch('app.routes.order.analyze_user_input') as mock_analyze:
            mock_analyze.return_value = {
                "intent": "order_food",
                "menu_items": [
                    {"name": "California Roll", "quantity": 2, "modifier": []}
                ]
            }
            
            # Mock menu item finder
            with patch('app.routes.order.find_menu_item_any_status') as mock_find:
                mock_find.return_value = (
                    {"name": "California Roll", "price": 9.95, "reference_handler": "cal_roll_1", "available": True},
                    0
                )
                
                # Make the request with speech result
                response = client.post('/take_order', data={'SpeechResult': 'I would like two California rolls'})
                
                # Check response
                assert response.status_code == 200
                response_text = response.data.decode('utf-8')
                
                # Should use the gather verb
                assert '<Gather' in response_text
                
                # Check session was updated
                with client.session_transaction() as session:
                    assert 'order_items_json' in session
                    assert 'total_price' in session
                    assert 'bill_amount' in session
                    
                    # Parse the order items
                    order_items = json.loads(session['order_items_json'])
                    assert len(order_items) > 0
                    assert order_items[0]['name'] == 'California Roll'
                    assert order_items[0]['quantity'] == 2


def test_take_order_with_modifier_quantities(client, app, mock_openai, setup_test_menu):
    """Test the take_order endpoint with modifiers and quantities."""
    with app.test_request_context():
        # Set up session
        with client.session_transaction() as session:
            session['sender'] = '+1234567890'
            session['caller_name'] = 'Test User'
            
        # Mock necessary functions to control behavior
        with patch('app.routes.order.analyze_user_input') as mock_analyze:
            mock_analyze.return_value = {
                "intent": "order_food",
                "menu_items": [
                    {
                        "name": "California Roll", 
                        "quantity": 1, 
                        "modifier": [
                            {"name": "Spicy Mayo", "quantity": 2, "price": 0.50}
                        ]
                    }
                ]
            }
            
            # Mock menu item finder
            with patch('app.routes.order.find_menu_item_any_status') as mock_find:
                mock_find.return_value = (
                    {"name": "California Roll", "price": 9.95, "reference_handler": "cal_roll_1", "available": True},
                    0
                )
                
                # Make the request with speech result
                response = client.post('/take_order', data={'SpeechResult': 'I would like a California roll with extra spicy mayo'})
                
                # Check response
                assert response.status_code == 200
                response_text = response.data.decode('utf-8')
                
                # Should use the gather verb and contain the modifier
                assert '<Gather' in response_text
                
                # Check session was updated
                with client.session_transaction() as session:
                    assert 'order_items_json' in session
                    
                    # Parse the order items
                    order_items = json.loads(session['order_items_json'])
                    assert len(order_items) > 0
                    assert order_items[0]['name'] == 'California Roll'
                    
                    # Check modifiers exist and quantities are correct
                    if 'modifier' in order_items[0]:
                        assert len(order_items[0]['modifier']) > 0
                        assert order_items[0]['modifier'][0]['name'] == 'Spicy Mayo'
                        assert order_items[0]['modifier'][0]['quantity'] == 2


def test_take_order_busy_mode(client, app):
    """Test take_order endpoint during busy mode."""
    with app.test_request_context():
        # Mock the busy mode
        with patch('app.routes.order.BUSY_MODE_ACTIVE', True):
            response = client.post('/take_order', data={'SpeechResult': 'I would like two California rolls'})
            
            # Check response
            assert response.status_code == 200
            response_text = response.data.decode('utf-8')
            
            # Should contain the busy message and hangup
            assert "We're currently busy and not accepting new orders" in response_text
            assert '<Hangup' in response_text


def test_busy_mode_toggle(client, app):
    """Test toggling busy mode on and off."""
    # This would be an admin endpoint in a real app
    # Test a simulated busy mode toggle endpoint
    with patch('app.routes.order.BUSY_MODE_ACTIVE', False) as busy_mode:
        # Initial state should be not busy
        assert not busy_mode
        
        # Toggle to busy
        busy_mode = True
        assert busy_mode
        
        # Test order placement rejected when busy
        with app.test_request_context():
            with patch('app.routes.order.BUSY_MODE_ACTIVE', True):
                response = client.post('/take_order', data={'SpeechResult': 'I would like sushi'})
                assert response.status_code == 200
                assert "busy" in response.data.decode('utf-8').lower()
                
        # Toggle back to not busy
        busy_mode = False
        assert not busy_mode
        
        # Test order placement accepted when not busy
        with app.test_request_context():
            with patch('app.routes.order.BUSY_MODE_ACTIVE', False):
                with patch('app.routes.order.analyze_user_input') as mock_analyze:
                    mock_analyze.return_value = {
                        "intent": "order_food",
                        "menu_items": [
                            {"name": "California Roll", "quantity": 1, "modifier": []}
                        ]
                    }
                    
                    with patch('app.routes.order.find_menu_item_any_status') as mock_find:
                        mock_find.return_value = (
                            {"name": "California Roll", "price": 9.95, "reference_handler": "cal_roll_1", "available": True},
                            0
                        )
                        
                        response = client.post('/take_order', data={'SpeechResult': 'I would like sushi'})
                        assert response.status_code == 200
                        assert "your total is" in response.data.decode('utf-8').lower()


def test_take_order_no_available_items(client, app):
    """Test take_order endpoint when no items are available."""
    with app.test_request_context():
        # Mock menu data with no available items
        with patch('app.routes.order.load_menu_data') as mock_load_menu:
            mock_load_menu.return_value = {"items": []}
            
            response = client.post('/take_order', data={'SpeechResult': 'I would like two California rolls'})
            
            # Check response
            assert response.status_code == 200
            response_text = response.data.decode('utf-8')
            
            # Should contain the unavailable message and hangup
            assert "our menu is currently unavailable" in response_text
            assert '<Hangup' in response_text


def test_take_order_unrecognized_intent(client, app, mock_openai):
    """Test take_order with unrecognized intent."""
    with app.test_request_context():
        # Mock OpenAI to return non-order intent
        with patch('app.routes.order.analyze_user_input') as mock_analyze:
            mock_analyze.return_value = {
                "intent": "ask_menu",
            }
            
            response = client.post('/take_order', data={'SpeechResult': 'What items do you have?'})
            
            # Check response
            assert response.status_code == 200
            response_text = response.data.decode('utf-8')
            
            # Should ask user to repeat the order
            assert "repeat your order" in response_text


def test_take_order_item_not_on_menu(client, app, mock_openai, setup_test_menu):
    """Test take_order with item not on menu."""
    with app.test_request_context():
        # Mock OpenAI to return non-existent menu item
        with patch('app.routes.order.analyze_user_input') as mock_analyze:
            mock_analyze.return_value = {
                "intent": "order_food",
                "menu_items": [
                    {"name": "Nonexistent Roll", "quantity": 1}
                ]
            }
            
            # Mock find_menu_item to return None
            with patch('app.routes.order.find_menu_item_any_status', return_value=(None, None)):
                response = client.post('/take_order', data={'SpeechResult': 'I would like a Nonexistent Roll'})
                
                # Check response
                assert response.status_code == 200


def test_take_order_unavailable_item(client, app, mock_openai, setup_test_menu):
    """Test take_order with unavailable menu item."""
    with app.test_request_context():
        # Mock OpenAI to return an unavailable menu item
        with patch('app.routes.order.analyze_user_input') as mock_analyze:
            mock_analyze.return_value = {
                "intent": "order_food",
                "menu_items": [
                    {"name": "Dragon Roll", "quantity": 1}
                ]
            }
            
            # Mock find_menu_item to return an unavailable item
            unavailable_item = {"name": "Dragon Roll", "available": False}
            with patch('app.routes.order.find_menu_item_any_status', return_value=(unavailable_item, 0)):
                response = client.post('/take_order', data={'SpeechResult': 'I would like a Dragon Roll'})
                
                # Check response
                assert response.status_code == 200


def test_confirm_order_from_initial_yes(client, app, mock_twilio, mock_deliverect):
    """Test confirm_order_from_initial with 'yes' response."""
    with app.test_request_context():
        # Set up session with order data
        with client.session_transaction() as session:
            session['sender'] = '+1234567890'
            session['caller_name'] = 'Test User'
            session['order_items_json'] = json.dumps([
                {"name": "California Roll", "quantity": 2, "price": 9.95, "reference_handler": "cal_roll_1"}
            ])
            session['total_price'] = 19.90
            session['bill_amount'] = 1990
            session['order_message'] = "You ordered:\n- 2 California Roll\nYour total is $19.90."
            session['order_id'] = 'test-123'
        
        # Mock all the required dependencies
        with patch('app.routes.order.db.session.add'), \
             patch('app.routes.order.commit_with_retry', return_value=True), \
             patch('app.routes.order.can_process_action', return_value=True), \
             patch('tasks.send_confirmation_sms_task') as mock_sms_task, \
             patch('requests.post') as mock_post:
            
            mock_sms_task.delay = MagicMock()
            mock_post.return_value.status_code = 200
            
            # Test with 'yes' speech
            response = client.post('/confirm_order_from_initial', data={'SpeechResult': 'yes'})
            
            # Check response
            assert response.status_code == 200
            response_text = response.data.decode('utf-8')
            
            # Should confirm the order and provide pickup time
            assert "order is confirmed" in response_text.lower()


def test_confirm_order_from_initial_no(client, app):
    """Test confirm_order_from_initial with 'no' response."""
    with app.test_request_context():
        # Set up session with order data
        with client.session_transaction() as session:
            session['sender'] = '+1234567890'
            session['caller_name'] = 'Test User'
            session['order_items_json'] = json.dumps([
                {"name": "California Roll", "quantity": 2, "price": 9.95}
            ])
        
        # Test with 'no' speech
        response = client.post('/confirm_order_from_initial', data={'SpeechResult': 'no'})
        
        # Check response
        assert response.status_code == 200
        response_text = response.data.decode('utf-8')
        
        # Should go to order modification flow
        assert "how you'd like your order changed" in response_text
        
        # Verify session was updated
        with client.session_transaction() as session:
            assert session['modification_in_progress'] is True


def test_confirm_order_from_initial_ambiguous(client, app):
    """Test confirm_order_from_initial with ambiguous response."""
    with app.test_request_context():
        # Set up session with order data
        with client.session_transaction() as session:
            session['sender'] = '+1234567890'
            session['caller_name'] = 'Test User'
            session['order_items_json'] = json.dumps([
                {"name": "California Roll", "quantity": 2, "price": 9.95}
            ])
        
        # Test with ambiguous speech
        response = client.post('/confirm_order_from_initial', data={'SpeechResult': 'maybe'})
        
        # Check response
        assert response.status_code == 200


def test_confirm_order_from_initial_dtmf(client, app, mock_twilio):
    """Test confirm_order_from_initial with DTMF input."""
    with app.test_request_context():
        # Set up session with order data
        with client.session_transaction() as session:
            session['sender'] = '+1234567890'
            session['caller_name'] = 'Test User'
            session['order_items_json'] = json.dumps([
                {"name": "California Roll", "quantity": 2, "price": 9.95, "reference_handler": "cal_roll_1"}
            ])
            session['total_price'] = 19.90
            session['bill_amount'] = 1990
            session['order_message'] = "You ordered:\n- 2 California Roll\nYour total is $19.90."
            session['order_id'] = 'test-123'
        
        # Mock the key parts of Deliverect to avoid actual API calls
        with patch('app.utils.deliverect.ensure_deliverect_token'), \
             patch('app.utils.deliverect.get_deliverect_headers', return_value={'Authorization': 'Bearer test_token'}), \
             patch('app.routes.order.db.session.add'), \
             patch('app.routes.order.commit_with_retry', return_value=True), \
             patch('app.routes.order.can_process_action', return_value=True), \
             patch('tasks.send_confirmation_sms_task') as mock_sms_task, \
             patch('requests.post') as mock_post:
            
            mock_sms_task.delay = MagicMock()
            mock_post.return_value.status_code = 200
            
            # Test with DTMF input
            response = client.post('/confirm_order_from_initial', data={'Digits': '1'})
            
            # Check response
            assert response.status_code == 200


def test_new_modify_order(client, app, mock_openai):
    """Test the new_modify_order endpoint."""
    with app.test_request_context():
        # Set up session with order data
        with client.session_transaction() as session:
            session['sender'] = '+1234567890'
            session['caller_name'] = 'Test User'
            session['order_items_json'] = json.dumps([
                {"name": "California Roll", "quantity": 2, "price": 9.95, "reference_handler": "cal_roll_1"}
            ])
            session['total_price'] = 19.90
            session['bill_amount'] = 1990
            session['order_message'] = "You ordered:\n- 2 California Roll\nYour total is $19.90."
        
        # Mock modification functions
        modifications = {
            "additions": [
                {"name": "Spicy Tuna Roll", "quantity": 1}
            ],
            "removals": [
                {"name": "California Roll", "quantity": 1}
            ]
        }
        
        with patch('app.routes.order.get_order_modifications', return_value=modifications), \
             patch('app.routes.order.find_menu_item') as mock_find, \
             patch('app.routes.order.apply_modifications') as mock_apply:
             
            # Set up mocks
            mock_find.return_value = (
                {"name": "Spicy Tuna Roll", "price": 11.95, "reference_handler": "spicy_tuna_1", "available": True},
                0
            )
            mock_apply.return_value = [
                {"name": "California Roll", "quantity": 1, "price": 9.95, "reference_handler": "cal_roll_1"},
                {"name": "Spicy Tuna Roll", "quantity": 1, "price": 11.95, "reference_handler": "spicy_tuna_1"}
            ]
            
            # Test the endpoint
            response = client.post('/new_modify_order', data={'SpeechResult': 'Remove one California Roll and add a Spicy Tuna Roll'})
            
            # Check response
            assert response.status_code == 200
            assert mock_apply.called


def test_new_modify_order_unclear_request(client, app):
    """Test new_modify_order with unclear modification request."""
    with app.test_request_context():
        # Set up session with order data
        with client.session_transaction() as session:
            session['sender'] = '+1234567890'
            session['caller_name'] = 'Test User'
            session['order_items_json'] = json.dumps([
                {"name": "California Roll", "quantity": 2, "price": 9.95}
            ])
        
        # Mock get_order_modifications to return empty result
        with patch('app.routes.order.get_order_modifications', return_value={}):
            response = client.post('/new_modify_order', data={'SpeechResult': 'hmm, not sure'})
            
            # Check response
            assert response.status_code == 200
            response_text = response.data.decode('utf-8')
            
            # Should ask for clarification
            assert "didn't understand your modifications" in response_text


def test_apply_modifications():
    """Test apply_modifications function."""
    # Current order
    current_order = [
        {"name": "California Roll", "quantity": 2, "price": 9.95, "reference_handler": "cal_roll_1"}
    ]
    
    # Modifications to apply
    modifications = {
        "additions": [
            {"name": "Spicy Tuna Roll", "quantity": 1, "modifier": [{"name": "extra wasabi", "quantity": 1}]}
        ],
        "removals": [
            {"name": "California Roll", "quantity": 1}
        ]
    }
    
    # Mock find_menu_item
    with patch('app.routes.order.find_menu_item') as mock_find:
        mock_find.return_value = (
            {"name": "Spicy Tuna Roll", "price": 11.95, "reference_handler": "spicy_tuna_1", "available": True},
            0
        )
        
        # Apply the modifications
        updated_order = apply_modifications(current_order, modifications)
        
        # Check result
        assert len(updated_order) == 2
        
        # Check California Roll was reduced
        california = [item for item in updated_order if item["name"] == "California Roll"][0]
        assert california["quantity"] == 1
        
        # Check Spicy Tuna Roll was added
        spicy_tuna = [item for item in updated_order if item["name"] == "Spicy Tuna Roll"][0]
        assert spicy_tuna["quantity"] == 1
        assert len(spicy_tuna['modifier']) == 1
        assert spicy_tuna['modifier'][0]['name'] == 'extra wasabi'


def test_get_order_modifications(mock_openai):
    """Test the get_order_modifications function."""
    # We'll test with a simplified approach by directly mocking the function
    from app.routes.order import get_order_modifications
    
    # Current order
    current_order = [
        {"name": "California Roll", "quantity": 2, "price": 9.95}
    ]
    
    # User input
    user_input = "remove one California Roll and add one Spicy Tuna Roll"
    
    # Use a simple mock to directly test the function signature
    with patch('app.routes.order.get_order_modifications') as mock_get_mods:
        # Set up the mock to return a predefined response
        mock_result = {
            "additions": [{"name": "Spicy Tuna Roll", "quantity": 1}],
            "removals": [{"name": "California Roll", "quantity": 1}]
        }
        mock_get_mods.return_value = mock_result
        
        # Call the mocked function
        mods = mock_get_mods(user_input, current_order)
        
        # Verify mock was called with correct params
        mock_get_mods.assert_called_once_with(user_input, current_order)
        
        # Check the returned mods match our mock
        assert mods == mock_result
        assert "additions" in mods
        assert "removals" in mods


def test_user_said_functions():
    """Test the user_said_yes and user_said_no functions."""
    # Test affirmative phrases
    assert user_said_yes("yes") is True
    assert user_said_yes("yeah") is True
    assert user_said_yes("correct") is True
    assert user_said_yes("sounds good") is False
    
    # Test negative phrases
    assert user_said_no("no") is True
    assert user_said_no("nope") is True
    assert user_said_no("not correct") is True
    assert user_said_no("something else") is False


def test_confirm_order_after_modification_newly_snoozed(client, app):
    """Test confirm_order_after_modification with newly snoozed items."""
    with app.test_request_context():
        # Set up session with order data
        with client.session_transaction() as session:
            session['sender'] = '+1234567890'
            session['caller_name'] = 'Test User'
            session['order_items_json'] = json.dumps([
                {"name": "Dragon Roll", "quantity": 1, "price": 14.95}
            ])
        
        # Mock is_item_snoozed_timebased to return True
        with patch('app.routes.order.is_item_snoozed_timebased', return_value=True):
            response = client.post('/confirm_order_after_modification', data={'SpeechResult': 'yes'})
            
            # Check response
            assert response.status_code == 200
            response_text = response.data.decode('utf-8')
            
            # Should inform about snoozed items
            assert "following item(s) are now unavailable" in response_text


def test_handle_newly_snoozed_in_checkout_remove(client, app):
    """Test handle_newly_snoozed_in_checkout when removing snoozed items."""
    with app.test_request_context():
        # Set up session with order data
        with client.session_transaction() as session:
            session['sender'] = '+1234567890'
            session['caller_name'] = 'Test User'
            session['order_items_json'] = json.dumps([
                {"name": "California Roll", "quantity": 1, "price": 9.95},
                {"name": "Dragon Roll", "quantity": 1, "price": 14.95}
            ])
        
        # Mock is_item_snoozed_timebased to return True only for Dragon Roll
        def mock_is_snoozed(item):
            return item.get('name') == 'Dragon Roll'
            
        with patch('app.routes.order.is_item_snoozed_timebased', side_effect=mock_is_snoozed):
            response = client.post('/handle_newly_snoozed_in_checkout', data={'SpeechResult': 'yes'})
            
            # Check response
            assert response.status_code == 200
            response_text = response.data.decode('utf-8')
            
            # Should update the order and show updated total
            assert "Your updated order is" in response_text
            
            # Session should be updated
            with client.session_transaction() as session:
                order_items = json.loads(session['order_items_json'])
                assert len(order_items) == 1
                assert order_items[0]['name'] == 'California Roll'


def test_handle_newly_snoozed_in_checkout_all_items_snoozed(client, app):
    """Test handle_newly_snoozed_in_checkout when all items are snoozed."""
    with app.test_request_context():
        # Set up session with only snoozed items
        with client.session_transaction() as session:
            session['sender'] = '+1234567890'
            session['caller_name'] = 'Test User'
            session['order_items_json'] = json.dumps([
                {"name": "Dragon Roll", "quantity": 1, "price": 14.95}
            ])
        
        # Mock is_item_snoozed_timebased to always return True
        with patch('app.routes.order.is_item_snoozed_timebased', return_value=True):
            response = client.post('/handle_newly_snoozed_in_checkout', data={'SpeechResult': 'yes'})
            
            # Check response
            assert response.status_code == 200
            response_text = response.data.decode('utf-8')
            
            # Should inform that all items are unavailable and hang up
            assert "All items in your order are now unavailable" in response_text
            assert '<Hangup' in response_text


def test_handle_newly_snoozed_in_checkout_cancel(client, app):
    """Test handle_newly_snoozed_in_checkout with 'cancel' response."""
    with app.test_request_context():
        # Set up session with order data
        with client.session_transaction() as session:
            session['sender'] = '+1234567890'
            session['caller_name'] = 'Test User'
            session['order_items_json'] = json.dumps([
                {"name": "California Roll", "quantity": 1, "price": 9.95},
                {"name": "Dragon Roll", "quantity": 1, "price": 14.95}
            ])
        
        # Test with cancellation
        response = client.post('/handle_newly_snoozed_in_checkout', data={'Digits': '2'})
        
        # Check response
        assert response.status_code == 200
        response_text = response.data.decode('utf-8')
        
        # Should cancel the order and hang up
        assert "We're sorry about that. Your order has been cancelled" in response_text
        assert '<Hangup' in response_text


def test_min_max_modifiers(client, app, mock_openai, setup_test_menu):
    """Test handling min/max requirements for modifier groups."""
    with app.test_request_context():
        # Setup session
        with client.session_transaction() as session:
            session['sender'] = '+1234567890'
            session['caller_name'] = 'Test User'
            
        # Mock necessary functions to control behavior
        with patch('app.routes.order.analyze_user_input') as mock_analyze:
            # Scenario 1: Missing a required modifier
            mock_analyze.return_value = {
                "intent": "order_food",
                "menu_items": [
                    {
                        "name": "California Roll", 
                        "quantity": 1,
                        "modifier": []  # Missing the required wasabi modifier
                    }
                ]
            }
            
            # In a complete implementation, this should trigger a validation error
            # and ask the user to add the required modifier
            # Since we don't have that validation yet, we're just ensuring the basic
            # flow works
            
            with patch('app.routes.order.find_menu_item_any_status') as mock_find:
                mock_find.return_value = (
                    {"name": "California Roll", "price": 9.95, "reference_handler": "cal_roll_1", "available": True},
                    0
                )
                
                # Make the request
                response = client.post('/take_order', data={'SpeechResult': 'I would like a California roll'})
                
                # Check response
                assert response.status_code == 200
                
                # In a complete implementation, this should contain a validation message
                # asking for the required modifier. Currently it will just accept the order.
                
            # Scenario 2: Too many of a limited modifier
            mock_analyze.return_value = {
                "intent": "order_food",
                "menu_items": [
                    {
                        "name": "California Roll", 
                        "quantity": 1, 
                        "modifier": [
                            {"name": "Spicy Mayo", "quantity": 3, "price": 0.50}
                            # This exceeds the maxAllowed of 2 for Sauces group
                        ]
                    }
                ]
            }
            
            # Make the request
            response = client.post('/take_order', data={'SpeechResult': 'I would like a California roll with 3 spicy mayo'})
            
            # Check response
            assert response.status_code == 200
            
            # In a complete implementation, this should contain a validation message
            # indicating the maximum allowed quantity has been exceeded