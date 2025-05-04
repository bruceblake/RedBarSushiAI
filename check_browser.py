#!/usr/bin/env python3
"""
Simple script to check if Playwright browsers are properly installed.
Exit code 0 means browsers are working, non-zero means they're not.
"""
import sys

try:
    from playwright.sync_api import sync_playwright
    
    print("Checking if Playwright browsers are installed...")
    
    with sync_playwright() as p:
        try:
            # Try to launch browser
            browser = p.chromium.launch()
            page = browser.new_page()
            browser.close()
            print("✅ Playwright browsers are working correctly")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Failed to launch browser: {e}")
            sys.exit(1)
            
except ImportError:
    print("❌ Playwright is not installed")
    sys.exit(2)
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    sys.exit(3)