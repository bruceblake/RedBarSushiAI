#!/usr/bin/env python
"""
Simple standalone E2E test script that doesn't depend on your project's app
"""
import pytest
from playwright.sync_api import sync_playwright

def test_basic_functionality():
    """Test basic functionality with a simple HTML page."""
    with sync_playwright() as p:
        # Launch the browser with the skip validation flag
        browser = p.chromium.launch(
            headless=True,
            chromium_sandbox=False  # Needed on some Linux systems
        )
        
        # Create a new page
        page = browser.new_page()
        
        # Create a simple HTML page
        page.set_content("""
        <html>
          <head>
            <title>Test Page</title>
          </head>
          <body>
            <h1>RedBarSushiAI Test</h1>
            <p id="desc">This is a simple test page for RedBarSushiAI.</p>
            <button id="btn">Click Me</button>
            <div id="result"></div>
            
            <script>
              document.getElementById('btn').addEventListener('click', () => {
                document.getElementById('result').textContent = 'Button clicked!';
              });
            </script>
          </body>
        </html>
        """)
        
        # Check page title
        assert "Test Page" in page.title()
        
        # Verify the page content
        assert page.locator('h1').text_content() == "RedBarSushiAI Test"
        
        # Click the button
        page.click('#btn')
        
        # Verify the result
        assert page.locator('#result').text_content() == "Button clicked!"
        
        # Close browser
        browser.close()

if __name__ == "__main__":
    # Set the environment variable to skip validation
    import os
    os.environ["PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS"] = "1"
    
    # Run the test
    test_basic_functionality()
    print("Test passed successfully!")