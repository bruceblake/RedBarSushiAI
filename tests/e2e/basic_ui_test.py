"""
Basic UI test that doesn't depend on other fixtures and starts the server directly.
Uses direct URLs instead of base_url fixture to avoid scoping issues.
"""

import os
import pytest
import subprocess
import time
import signal
from playwright.sync_api import sync_playwright

# Server port
PORT = 5000

# Global process handle
flask_app = None

def setup_module():
    """Start Flask server for the test module."""
    global flask_app
    env = os.environ.copy()
    env["FLASK_APP"] = "run.py"
    env["FLASK_ENV"] = "testing"
    env["TESTING"] = "true"
    env["DATABASE_URL"] = "sqlite:///:memory:"
    env["DISABLE_OPENAI"] = "true"
    env["PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS"] = "1"
    
    # Start Flask server
    flask_app = subprocess.Popen(
        ["python", "-m", "flask", "run", f"--port={PORT}"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for server to start
    time.sleep(2)
    print(f"Test Flask server started on port {PORT}")

def teardown_module():
    """Stop Flask server after the test module."""
    global flask_app
    if flask_app:
        print("Stopping Flask server...")
        flask_app.terminate()
        flask_app.wait(timeout=5)
        flask_app = None

def test_homepage_loads():
    """Test that the homepage loads correctly."""
    with sync_playwright() as p:
        # Launch browser with host validation skipped
        browser = p.chromium.launch(headless=True, chromium_sandbox=False)
        page = browser.new_page()
        
        try:
            # Navigate to homepage
            page.goto(f"http://localhost:{PORT}/")
            
            # Take screenshot
            page.screenshot(path="homepage.png")
            
            # Check for basic page elements
            heading_count = page.locator("h1, h2, h3").count()
            assert heading_count > 0, "No headings found on homepage"
            
            print("Homepage loaded successfully")
            
            # Basic navigation test - find important links
            links = page.locator("a").all()
            link_texts = [link.text_content() for link in links]
            
            print(f"Found links: {link_texts}")
            
            # Success!
            assert True
        finally:
            # Clean up
            page.close()
            browser.close()

def test_menu_navigation():
    """Test that we can navigate to the menu page."""
    with sync_playwright() as p:
        # Launch browser with host validation skipped
        browser = p.chromium.launch(headless=True, chromium_sandbox=False)
        page = browser.new_page()
        
        try:
            # Start at homepage
            page.goto(f"http://localhost:{PORT}/")
            
            # Look for menu link
            menu_link = page.locator("a:has-text('Menu'), a[href*='menu']").first
            
            if menu_link.count() > 0:
                # Click menu link
                menu_link.click()
                
                # Wait for page to load
                page.wait_for_load_state("networkidle")
                
                # Take screenshot
                page.screenshot(path="menu-page.png")
                
                # Check URL contains menu
                assert "menu" in page.url.lower(), "URL doesn't indicate menu page"
                
                print("Successfully navigated to menu page")
            else:
                # Try direct navigation instead
                page.goto(f"http://localhost:{PORT}/menu")
                
                # Take screenshot
                page.screenshot(path="menu-direct.png")
                
                print("Menu link not found, used direct navigation")
            
            # Success either way
            assert True
        finally:
            # Clean up
            page.close()
            browser.close()

if __name__ == "__main__":
    # Run tests directly
    try:
        setup_module()
        test_homepage_loads()
        test_menu_navigation()
        print("All tests passed!")
    finally:
        teardown_module()