# tests/conftest.py
import os, pytest
from playwright.sync_api import sync_playwright


@pytest.fixture(scope="session")
def api_request():
    base = os.getenv("BASE_URL", "http://localhost:8080")
    with sync_playwright() as p:
        ctx = p.request.new_context(base_url=base, timeout=10_000)
        yield ctx
        ctx.dispose()
