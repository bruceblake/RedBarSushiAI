# tests/conftest.py
import os
import pytest
from playwright.sync_api import APIRequestContext, Playwright

BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")

@pytest.fixture(scope="session")
def api_ctx(playwright: Playwright) -> APIRequestContext:
    """
    One HTTP context for the whole test session, using Playwright’s
    built-in 'playwright' fixture to manage the driver lifecycle.
    """
    ctx = playwright.request.new_context(
        base_url=BASE_URL,
        extra_http_headers={"accept": "application/json"},
        timeout=10_000,          # 10 s per request
    )
    yield ctx
    ctx.dispose()

