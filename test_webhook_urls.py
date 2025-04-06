#!/usr/bin/env python
"""
A test script to check the webhook URL generation with different configurations.
"""
import sys
import os
import json
from app.config import BASE_URL
from app.utils.deliverect import get_location_webhook_urls

def print_colored(text, color):
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'end': '\033[0m'
    }
    print(f"{colors.get(color, '')}{text}{colors['end']}")

def main():
    print_colored("===== Webhook URL Test =====", 'blue')
    print(f"Current BASE_URL = {BASE_URL}")
    
    # Check webhook URLs for a non-existent location
    print_colored("\nTesting webhook URLs for non-existent location:", 'yellow')
    urls = get_location_webhook_urls("test_location")
    
    # Print the webhook URLs
    print(json.dumps(urls, indent=2))
    
    # Check if all URLs have the correct base
    all_correct = all(url.startswith(BASE_URL) for url in urls.values())
    
    if all_correct:
        print_colored("\nSUCCESS: All webhook URLs use the correct BASE_URL", 'green')
    else:
        print_colored("\nERROR: Some webhook URLs do not use the correct BASE_URL", 'red')
        
        # Print the problematic URLs
        for key, url in urls.items():
            if not url.startswith(BASE_URL):
                print_colored(f"  - {key}: {url} (should start with {BASE_URL})", 'red')
    
    # Test with a custom BASE_URL
    print_colored("\nTesting with a custom BASE_URL:", 'yellow')
    custom_base = "https://custom.example.com"
    os.environ['BASE_URL'] = custom_base
    print(f"Set environment BASE_URL = {custom_base}")
    print("Note: This won't take effect until app restart")
    
    return 0 if all_correct else 1

if __name__ == "__main__":
    sys.exit(main())