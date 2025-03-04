"""
test_voice.py - Tests for voice call handling
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from twilio.twiml.voice_response import VoiceResponse

from app.routes.voice import voice_bp


def test_receive_call(client, app):
    """Test the initial call endpoint."""
    with app.test_request_context():
        response = client.post('/')
        
        # Check status code
        assert response.status_code == 200
        
        # Check content type
        assert response.content_type == 'text/xml; charset=utf-8'
        
        # Parse the XML response
        response_text = response.data.decode('utf-8')
        
        # Check for expected TwiML elements
        assert '<Gather' in response_text
        assert 'action="/take_name"' in response_text
        assert 'Hello! Thank you for calling Red Bar Sushi' in response_text
        assert 'input="speech"' in response_text


def test_take_name_with_name(client, app):
    """Test the take name endpoint with a name provided."""
    with app.test_request_context():
        # Test with name in the request
        with client.session_transaction() as session:
            session['sender'] = '+1234567890'
        
        data = {'SpeechResult': 'John Doe'}
        response = client.post('/take_name', data=data)
        
        # Check status code
        assert response.status_code == 200
        
        # Parse the XML response
        response_text = response.data.decode('utf-8')
        
        # Check for expected TwiML elements
        assert '<Gather' in response_text
        assert 'action="/main_menu"' in response_text
        assert 'Thanks, John Doe!' in response_text
        
        # Verify session update
        with client.session_transaction() as session:
            assert session['caller_name'] == 'John Doe'


def test_take_name_without_name(client, app):
    """Test the take name endpoint with no name provided."""
    with app.test_request_context():
        # Test without name in the request
        response = client.post('/take_name', data={})
        
        # Check status code
        assert response.status_code == 200
        
        # Parse the XML response
        response_text = response.data.decode('utf-8')
        
        # Check for expected TwiML elements
        assert '<Gather' in response_text
        assert 'action="/main_menu"' in response_text
        assert 'I didn\'t catch your name' in response_text


def test_main_menu_with_dtmf(client, app):
    """Test the main menu endpoint with DTMF input."""
    test_cases = [
        # DTMF '1': Order
        {'Digits': '1', 'expected_action': '/take_order', 'expected_text': 'Please tell me what you would like to order'},
        # DTMF '2': Menu questions
        {'Digits': '2', 'expected_action': '/handle_menu_questions', 'expected_text': 'You can ask for the menu'},
        # DTMF '3': Real person
        {'Digits': '3', 'expected_text': 'Please hold, transferring to a real person'},
    ]
    
    for case in test_cases:
        with app.test_request_context():
            response = client.post('/main_menu', data=case)
            
            # Check status code
            assert response.status_code == 200
            
            # Parse the XML response
            response_text = response.data.decode('utf-8')
            
            # Check for expected TwiML elements
            if 'expected_action' in case:
                assert f'action="{case["expected_action"]}"' in response_text
            assert case['expected_text'] in response_text


def test_main_menu_with_speech(client, app):
    """Test the main menu endpoint with speech input."""
    test_cases = [
        # Speech containing '1': Order
        {'SpeechResult': 'I want to order food', 'expected_action': '/take_order', 'expected_text': 'Please tell me what you would like to order'},
        # Speech containing '2': Menu questions
        {'SpeechResult': 'I have questions about the menu', 'expected_action': '/handle_menu_questions', 'expected_text': 'You can ask for the menu'},
        # Speech containing '3': Real person
        {'SpeechResult': 'I want to speak to a real person', 'expected_text': 'Please hold, transferring to a real person'},
        # Unknown speech: Prompt again
        {'SpeechResult': 'something else', 'expected_action': '/main_menu', 'expected_text': 'I didn\'t understand'},
    ]
    
    for case in test_cases:
        with app.test_request_context():
            with patch('app.routes.voice.channel_status', 1):  # Mock channel status as active
                response = client.post('/main_menu', data=case)
                
                # Check status code
                assert response.status_code == 200
                
                # Parse the XML response
                response_text = response.data.decode('utf-8')
                
                # Check for expected TwiML elements
                if 'expected_action' in case:
                    assert f'action="{case["expected_action"]}"' in response_text
                assert case['expected_text'] in response_text


def test_session_variables_initialized(client, app):
    """Test that session variables are properly initialized."""
    with app.test_request_context():
        # Test with a phone number in the request
        response = client.post('/', data={'From': '+1234567890'})
        
        # Verify session variables are set
        with client.session_transaction() as session:
            assert session['sender'] == '+1234567890'
            assert session['order_message'] == ""
            assert session['total_price'] == 0
            assert session['modification_in_progress'] is False
            assert session['caller_name'] == "Valued Customer"
            assert session['ordering_in_progress'] is False


def test_handle_menu_questions_order_intent(client, app, mock_openai):
    """Test handle_menu_questions when user expresses intent to order."""
    with app.test_request_context():
        # Mock the OpenAI response to indicate order_food intent
        mock_openai.chat.completions.create.return_value.choices[0].message.content = json.dumps({
            "intent": "order_food",
            "menu_items": [
                {
                    "name": "California Roll", 
                    "quantity": 1,
                    "modifier": []
                }
            ]
        })
        
        response = client.post('/handle_menu_questions', data={'SpeechResult': 'I want to order a California Roll'})
        
        # Check status code
        assert response.status_code == 200
        
        # Parse the XML response
        response_text = response.data.decode('utf-8')
        
        # Check for expected TwiML elements
        assert 'action="/take_order"' in response_text
        assert "I'll take your order now" in response_text
        
        # Verify session update
        with client.session_transaction() as session:
            assert session['ordering_in_progress'] is True


def test_handle_menu_questions_menu_intent(client, app, mock_openai):
    """Test handle_menu_questions when user asks about the menu."""
    with app.test_request_context():
        # Mock the OpenAI response to indicate ask_menu intent
        mock_openai.chat.completions.create.return_value.choices[0].message.content = json.dumps({
            "intent": "ask_menu"
        })
        
        response = client.post('/handle_menu_questions', data={'SpeechResult': 'Tell me about your menu'})
        
        # Check status code
        assert response.status_code == 200
        
        # Parse the XML response
        response_text = response.data.decode('utf-8')
        
        # Check for expected TwiML elements
        assert 'action="/handle_menu_questions"' in response_text
        assert "Our menu features" in response_text


def test_handle_menu_questions_price_intent(client, app, mock_openai, mock_menu_data):
    """Test handle_menu_questions when user asks about an item price."""
    with app.test_request_context():
        # Setup mock for the menu data
        with patch('app.utils.menu_utils.load_menu_data') as mock_load:
            mock_load.return_value = mock_menu_data
            
            # Mock the OpenAI response for price inquiry
            mock_openai.chat.completions.create.return_value.choices[0].message.content = json.dumps({
                "intent": "get_menu_item_price",
                "menu_items": [
                    {
                        "name": "California Roll"
                    }
                ]
            })
            
            response = client.post('/handle_menu_questions', data={'SpeechResult': 'How much is a California Roll?'})
            
            # Check status code
            assert response.status_code == 200
            
            # Parse the XML response
            response_text = response.data.decode('utf-8')
            
            # Check for expected TwiML elements
            assert 'action="/handle_menu_questions"' in response_text
            assert "The California Roll costs $9.95" in response_text


def test_handle_menu_questions_unknown_intent(client, app, mock_openai):
    """Test handle_menu_questions with an unknown intent."""
    with app.test_request_context():
        # Mock the OpenAI response for an unknown intent
        mock_openai.chat.completions.create.return_value.choices[0].message.content = json.dumps({
            "intent": "other"
        })
        
        response = client.post('/handle_menu_questions', data={'SpeechResult': 'Something unrelated'})
        
        # Check status code
        assert response.status_code == 200
        
        # Parse the XML response
        response_text = response.data.decode('utf-8')
        
        # Check for expected TwiML elements
        assert 'action="/main_menu"' in response_text
        assert "I'm not sure I understood your question" in response_text
