import os
import pytest
from playwright.sync_api import sync_playwright, APIRequestContext

# Base URL comes from the Render job or local env var
BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")

@pytest.fixture(scope="session")
def api_ctx() -> APIRequestContext:
    """One Playwright HTTP context for the whole session."""
    with sync_playwright() as p:
        ctx = p.request.new_context(
            base_url=BASE_URL,
            extra_http_headers={"accept": "application/json"},
            timeout=10_000,
        )
        yield ctx
        ctx.dispose()
