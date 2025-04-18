#!/usr/bin/env python
"""
Simple script to verify Playwright installation.
"""
import sys
import os
from pathlib import Path

def verify_playwright_import():
    """Verify that Playwright can be imported."""
    try:
        from playwright.sync_api import sync_playwright
        print("✅ Playwright import successful")
        return True
    except ImportError as e:
        print(f"❌ Error importing Playwright: {e}")
        print("\nTry running: pip install playwright==1.41.2")
        return False

def verify_browser_launch():
    """Verify that Playwright can launch a browser."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            print("Launching browser...")
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Create a simple test page
            page.set_content("""
            <html>
              <head><title>Playwright Test</title></head>
              <body><h1>Playwright Verification</h1></body>
            </html>
            """)
            
            # Take a screenshot
            screenshots_dir = Path("screenshots")
            screenshots_dir.mkdir(exist_ok=True)
            
            screenshot_path = screenshots_dir / "verification.png"
            page.screenshot(path=str(screenshot_path))
            
            # Cleanup
            page.close()
            browser.close()
            
            if screenshot_path.exists():
                print(f"✅ Browser launched successfully and screenshot saved to {screenshot_path}")
                return True
            else:
                print(f"❌ Failed to save screenshot to {screenshot_path}")
                return False
                
    except Exception as e:
        print(f"❌ Error launching browser: {e}")
        print("\nTry running: python -m playwright install")
        print("              python -m playwright install-deps")
        return False

if __name__ == "__main__":
    print("==== Playwright Verification ====")
    
    # Set environment variable to skip host requirements validation
    os.environ["PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS"] = "1"
    
    # Verify Playwright import
    import_success = verify_playwright_import()
    
    if import_success:
        # Verify browser launch
        launch_success = verify_browser_launch()
    else:
        launch_success = False
    
    # Overall verification result
    if import_success and launch_success:
        print("\n✅ Playwright verification PASSED")
        sys.exit(0)
    else:
        print("\n❌ Playwright verification FAILED")
        sys.exit(1)