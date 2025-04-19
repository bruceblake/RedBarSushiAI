import pytest
from xml.etree import ElementTree as ET

import app.routes.voice as voice_mod

@pytest.fixture(autouse=True)
def disable_async(monkeypatch):
    # Ensure no real async loops or audio processing is invoked
    monkeypatch.setattr(voice_mod, 'get_audio_processor', lambda *args, **kwargs: None)
    yield

def make_client(app, client):
    # convenience alias
    return client

def test_handle_menu_questions_dynamic_success(client, monkeypatch):
    # Monkeypatch analysis to always go to ask_menu intent
    monkeypatch.setattr(voice_mod, 'analyze_user_input', lambda text: {'intent': 'ask_menu'})
    # Dummy menu tool with categories and items
    class DummyMenuTool:
        def get_menu_categories(self):
            return ['Rolls', 'Appetizers', 'Nigiri', 'Sashimi']
        def get_items_by_category(self, category):
            # return 3 items per category
            return [
                {'name': f'{category}Item1', 'price': 1.11},
                {'name': f'{category}Item2', 'price': 2.22},
                {'name': f'{category}Item3', 'price': 3.33},
            ]
    # Dummy agent uses DummyMenuTool
    class DummyAgent:
        def __init__(self):
            self.menu_tool = DummyMenuTool()
    monkeypatch.setattr(voice_mod, 'OrderParsingAgent', DummyAgent)

    # Call endpoint
    resp = client.post('/handle_menu_questions', data={'SpeechResult': 'menu'},)
    assert resp.status_code == 200
    # Parse TwiML
    tree = ET.fromstring(resp.data)
    # Find Say element
    say = tree.find('.//Say')
    assert say is not None, 'Expected <Say> in TwiML'
    text = say.text
    # Should list categories Rolls, Appetizers, Nigiri
    assert 'Rolls:' in text
    assert 'RollsItem1 at $1.11' in text
    assert 'Appetizers:' in text
    assert 'AppetizersItem2 at $2.22' in text
    # Should include three categories only (limit 3)
    assert 'Nigiri:' in text
    assert 'Sashimi:' not in text
    # Ends with prompt
    assert 'place an order now' in text

def test_handle_menu_questions_fallback(monkeypatch, client):
    # Monkeypatch analysis to ask menu
    monkeypatch.setattr(voice_mod, 'analyze_user_input', lambda text: {'intent': 'ask_menu'})
    # Dummy agent that raises on init or not
    class DummyAgentBad:
        def __init__(self):
            raise RuntimeError('agent failed')
    monkeypatch.setattr(voice_mod, 'OrderParsingAgent', DummyAgentBad)

    # Call endpoint
    resp = client.post('/handle_menu_questions', data={'SpeechResult': 'anything'})
    assert resp.status_code == 200
    tree = ET.fromstring(resp.data)
    say = tree.find('.//Say')
    assert say is not None
    text = say.text
    # Should fallback to generic prompt
    assert 'selection of sushi rolls' in text or 'Our menu includes' in text

def test_handle_menu_questions_with_example_menu(client, monkeypatch):
    # Load the example Deliverect payload
    import json, os
    from xml.etree import ElementTree as ET
    from app.routes import voice as voice_mod

    data_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'testing_data', 'test_deliverect_payload.json')
    )
    payload = json.load(open(data_path))
    # Navigate to the menu inside the payload
    menu_obj = payload.get('data', {}).get('menu', {})
    categories = [c.get('name') for c in menu_obj.get('categories', [])]
    class MenuTool:
        def get_menu_categories(self):
            return categories
        def get_items_by_category(self, category):
            for c in menu_obj.get('categories', []):
                if c.get('name') == category:
                    # Return product dicts directly
                    return c.get('products', [])
            return []
    class DummyAgent2:
        def __init__(self):
            self.menu_tool = MenuTool()
    # Patch agent and analysis intent
    monkeypatch.setattr(voice_mod, 'OrderParsingAgent', DummyAgent2)
    monkeypatch.setattr(voice_mod, 'analyze_user_input', lambda t: {'intent': 'ask_menu'})
    # Call endpoint
    resp = client.post('/handle_menu_questions', data={'SpeechResult': 'menu'})
    assert resp.status_code == 200
    # Parse TwiML and verify contents
    tree = ET.fromstring(resp.data)
    say = tree.find('.//Say')
    assert say is not None
    txt = say.text
    # Should mention first category and a product name
    assert categories, 'Expected categories in payload'
    assert categories[0] in txt
    # First product name
    # Check first category's first product name appears
    if menu_obj.get('categories'):
        first_cat = menu_obj['categories'][0]
        prod_list = first_cat.get('products', [])
        if prod_list:
            prod0 = prod_list[0].get('name')
            assert prod0 and prod0 in txt