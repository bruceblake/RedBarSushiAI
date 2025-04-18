"""
Playwright configuration for end-to-end tests.
Keeps test fixtures separate from main app conftest.py to avoid conflicts.
"""
import os
import pytest
import subprocess
import time
import signal
import atexit
import json
import urllib.parse
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

# Load test environment variables
load_dotenv(".env.test")

# Set environment variables for testing
os.environ["TESTING"] = "true"
os.environ["PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS"] = "1"

# Server process
app_process = None
flask_port = 5000

def start_flask_server():
    """Start Flask server as a separate process."""
    global app_process
    env = os.environ.copy()
    env["FLASK_APP"] = "run.py"
    env["FLASK_ENV"] = "testing"
    env["TESTING"] = "true"
    env["DATABASE_URL"] = "sqlite:///:memory:"
    
    # Check if we should mock OpenAI
    if os.environ.get("USE_REAL_API_KEYS", "").lower() != "true":
        env["DISABLE_OPENAI"] = "true"
        print("Using mocked OpenAI API")
    else:
        env["DISABLE_OPENAI"] = "false"
        print("Using real OpenAI API")
    
    # Check if another Flask server is running on the port
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', flask_port))
    sock.close()
    
    if result == 0:
        print(f"Port {flask_port} is already in use. Stopping any existing Flask servers...")
        os.system(f"pkill -f 'flask run --port={flask_port}'")
        time.sleep(1)
    
    # Start the Flask application
    print(f"Starting Flask server on port {flask_port}...")
    app_process = subprocess.Popen(
        ["python", "-m", "flask", "run", f"--port={flask_port}", "--host=0.0.0.0"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Register cleanup function
    atexit.register(stop_flask_server)
    
    # Wait for server to start and verify it's running
    for _ in range(10):
        time.sleep(1)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', flask_port))
        sock.close()
        
        if result == 0:
            print(f"✅ Flask server started and responding on port {flask_port}")
            return True
    
    # If we get here, server failed to start
    stderr = app_process.stderr.read()
    print(f"❌ Flask server failed to start on port {flask_port}")
    print(f"Server error output: {stderr}")
    return False

def stop_flask_server():
    """Stop the Flask server."""
    global app_process
    if app_process:
        print("Stopping Flask server...")
        app_process.terminate()
        app_process.wait(timeout=5)
        app_process = None

@pytest.fixture(scope="session")
def browser_type():
    """Get the browser type based on environment variable."""
    with sync_playwright() as playwright:
        browser_name = os.getenv("BROWSER", "chromium")
        if browser_name == "chromium":
            yield playwright.chromium
        elif browser_name == "firefox":
            yield playwright.firefox
        elif browser_name == "webkit":
            yield playwright.webkit
        else:
            raise ValueError(f"Unsupported browser: {browser_name}")

@pytest.fixture(scope="session")
def browser(browser_type):
    """Launch the browser with headless mode configurable by environment variable."""
    # Start the Flask server before browser tests
    start_flask_server()
    
    # Configure browser
    headed_mode = os.getenv("HEADED", "false").lower() == "true"
    browser = browser_type.launch(
        headless=not headed_mode,
        chromium_sandbox=False  # Often needed for Linux
    )
    yield browser
    browser.close()
    
    # Stop the Flask server after tests
    stop_flask_server()

@pytest.fixture
def page(browser):
    """Create a new page for each test."""
    page = browser.new_page()
    page.set_default_timeout(10000)  # 10 seconds timeout
    yield page
    page.close()

@pytest.fixture(scope="session")
def base_url():
    """Return the base URL for the application."""
    return f"http://localhost:{flask_port}"

@pytest.fixture(scope="session")
def api_url():
    """Return the base URL for the application API."""
    return f"http://localhost:{flask_port}/api"

# API client fixture to fix "TopRequest" object issues
class APIClient:
    """HTTP client wrapper for API testing."""
    
    def __init__(self, page, base_url):
        self.page = page
        self.base_url = base_url
    
    def _resolve_url(self, url):
        """Resolve relative URLs against the base URL."""
        if url.startswith("http"):
            return url
        # Handle URLs with or without leading slash
        if url.startswith("/"):
            return f"{self.base_url}{url}"
        else:
            return f"{self.base_url}/{url}"
    
    def get(self, url, **kwargs):
        """Make a GET request."""
        full_url = self._resolve_url(url)
        return self.page.request.get(full_url, **kwargs)
    
    def post(self, url, data=None, json=None, headers=None, **kwargs):
        """Make a POST request."""
        full_url = self._resolve_url(url)
        
        if json is not None:
            if headers is None:
                headers = {}
            headers["Content-Type"] = "application/json"
            data = json_data = json
        elif isinstance(data, dict) and headers and headers.get("Content-Type") == "application/x-www-form-urlencoded":
            # Handle form data
            data = urllib.parse.urlencode(data)
        
        return self.page.request.post(
            full_url, 
            data=data,
            headers=headers,
            **kwargs
        )

@pytest.fixture
def api_client(page, base_url):
    """Provide an API client for making HTTP requests."""
    return APIClient(page, base_url)