#!/usr/bin/env python3
"""
Simple test script to verify Playwright installation and functionality.
"""

import sys
from playwright.sync_api import sync_playwright

def main():
    """Run a simple test with Playwright."""
    print("Starting Playwright test...")
    
    try:
        with sync_playwright() as p:
            # Launch the browser
            print("Launching browser...")
            browser = p.chromium.launch(headless=True)
            
            # Create a new page
            print("Creating new page...")
            page = browser.new_page()
            
            # Navigate to a website
            print("Navigating to example.com...")
            page.goto('https://example.com')
            
            # Get the title
            title = page.title()
            print(f"Page title: {title}")
            
            # Take a screenshot
            print("Taking screenshot...")
            page.screenshot(path="screenshot.png")
            
            # Close the browser
            print("Closing browser...")
            browser.close()
            
        print("Playwright test completed successfully!")
        return 0
    
    except Exception as e:
        print(f"Error running Playwright test: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())