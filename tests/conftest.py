import os
import pytest
from flask import Flask
from app import create_app

@pytest.fixture(scope='session')
def app():
    # Create Flask app in testing mode
    app = create_app({'TESTING': True})
    yield app

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