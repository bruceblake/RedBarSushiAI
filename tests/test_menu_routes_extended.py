import os
import json
import tempfile
import importlib

import pytest

from flask import current_app

# -----------------------------------------------------------------------------
# Extended tests for menu-related routes to improve coverage
# -----------------------------------------------------------------------------

def test_busy_mode_pause_and_unpause(client):
    # Pause
    resp1 = client.post('/busy_mode', json={'status': 'PAUSED'})
    assert resp1.status_code == 200
    from app.routes.order import BUSY_MODE_ACTIVE
    assert BUSY_MODE_ACTIVE is True
    # Unpause
    resp2 = client.post('/busy_mode', json={'status': 'UNPAUSED'})
    assert resp2.status_code == 200
    from app.routes.order import BUSY_MODE_ACTIVE as new_busy
    assert new_busy is False
    # Invalid status
    resp3 = client.post('/busy_mode', json={'status': 'INVALID'})
    assert resp3.status_code == 400

def test_update_reference_success_and_not_found(client, monkeypatch):
    # Prepare mock menu
    menu_data = {'items': [{'name': 'Test Item', 'reference_handler': 'old', 'available': True}],
                 'modifierGroups': [], 'name_variants': {}}
    monkeypatch.setattr('app.routes.menu.load_menu_data', lambda force_refresh=True: menu_data)
    writes = []
    def fake_write(data):
        writes.append(data)
        return True
    monkeypatch.setattr('app.routes.menu.write_menu_file', fake_write)
    # Successful update
    resp1 = client.post('/update_reference', json={'item_name': 'Test Item', 'reference_handler': 'new'})
    assert resp1.status_code == 200
    assert writes and writes[0]['items'][0]['reference_handler'] == 'new'
    # Not found
    resp2 = client.post('/update_reference', json={'item_name': 'No Such', 'reference_handler': 'x'})
    assert resp2.status_code == 404

def test_sync_references_success_and_error(client, monkeypatch):
    # Success path: accept keyword args
    monkeypatch.setattr(
        'app.routes.menu.sync_reference_handlers',
        lambda **kwargs: {'count': 3}
    )
    resp1 = client.post('/sync_references', json={'source_location': 'A', 'target_location': 'B'})
    assert resp1.status_code == 200
    assert resp1.json['stats']['count'] == 3
    # Error path: raise when called
    def fail(**kwargs):
        raise RuntimeError('fail')
    monkeypatch.setattr(
        'app.routes.menu.sync_reference_handlers', fail
    )
    resp2 = client.post(
        '/sync_references', json={'source_location': 'A', 'target_location': 'B'}
    )
    assert resp2.status_code == 500

def test_get_menu_and_clear_cache(client, monkeypatch):
    data = {'items': [{'name': 'ItemX'}]}
    monkeypatch.setattr('app.routes.menu.load_menu_data', lambda force_refresh=True, location_id=None: data)
    # GET /menu
    resp1 = client.get('/menu')
    assert resp1.status_code == 200
    j1 = resp1.json
    assert j1['items'][0]['name'] == 'ItemX'
    assert '_debug' in j1
    # With location param
    resp2 = client.get('/menu?location_id=loc1')
    assert resp2.status_code == 200
    # GET /clear_menu_cache
    resp3 = client.get('/clear_menu_cache')
    assert resp3.status_code == 200
    assert resp3.json.get('success') is True

def test_delete_menu(tmp_path, client, monkeypatch):
    # Create a fake menu file
    fake_file = tmp_path / 'menu_data.json'
    fake_file.write_text('{}')
    # Monkeypatch known paths list
    monkeypatch.setattr('app.routes.menu.MENU_FILE_PATH', str(fake_file))
    # Call endpoint
    resp = client.get('/delete_menu')
    assert resp.status_code == 200
    assert 'deleted_files' in resp.json

def test_toggle_menu(monkeypatch, client):
    # Save original
    orig = os.environ.get('USE_REDBAR_MENU')
    # Toggle without param
    resp1 = client.post('/toggle_menu')
    assert resp1.status_code == 200
    # Explicit true
    resp2 = client.post('/toggle_menu?use_redbar=true')
    assert resp2.status_code == 200
    assert resp2.json['use_redbar_menu'] is True
    # Explicit false
    resp3 = client.post('/toggle_menu?use_redbar=false')
    assert resp3.status_code == 200
    assert resp3.json['use_redbar_menu'] is False
    # Restore
    if orig is not None:
        os.environ['USE_REDBAR_MENU'] = orig

def test_write_test(client):
    resp = client.get('/write_test')
    assert resp.status_code == 200
    j = resp.json
    assert 'results' in j and 'cwd' in j and 'env' in j

def test_menu_settings(client, monkeypatch):
    data = {'items': [{'name': 'A'}], 'modifiers': [], 'modifierGroups': [], 'name_variants': {}}
    monkeypatch.setattr('app.routes.menu.load_menu_data', lambda force_refresh=True, location_id=None: data)
    resp = client.get('/menu_settings')
    assert resp.status_code == 200
    j = resp.json
    assert 'menu_file_path' in j and isinstance(j['item_count'], int)

def test_fix_item_error(client):
    resp = client.get('/fix_item_error')
    assert resp.status_code == 200
    j = resp.json
    assert j.get('success') is True
    assert isinstance(j.get('result'), list)