#!/usr/bin/env python3
"""
Simple script to test the health of the staging environment.
"""
import sys
import requests

BASE_URL = "https://redbarsushiai-staging.onrender.com"

def check_health():
    """Check the health endpoints of the staging environment."""
    try:
        # Check the health endpoint
        health_url = f"{BASE_URL}/healthcheck"
        print(f"Checking health endpoint: {health_url}")
        health_response = requests.get(health_url, timeout=10)
        
        print(f"Status code: {health_response.status_code}")
        if health_response.status_code == 200:
            print("Health check: SUCCESS")
            try:
                print(f"Response: {health_response.json()}")
            except:
                print(f"Response: {health_response.text}")
        else:
            print("Health check: FAILED")
            print(f"Response: {health_response.text}")
        
        # Check the environment endpoint
        env_url = f"{BASE_URL}/environment"
        print(f"\nChecking environment endpoint: {env_url}")
        env_response = requests.get(env_url, timeout=10)
        
        print(f"Status code: {env_response.status_code}")
        if env_response.status_code == 200:
            print("Environment check: SUCCESS")
            try:
                print(f"Response: {env_response.json()}")
            except:
                print(f"Response: {env_response.text}")
        else:
            print("Environment check: FAILED")
            print(f"Response: {env_response.text}")
        
        # Check the menu endpoint
        menu_url = f"{BASE_URL}/menu"
        print(f"\nChecking menu endpoint: {menu_url}")
        menu_response = requests.get(menu_url, timeout=10)
        
        print(f"Status code: {menu_response.status_code}")
        if menu_response.status_code == 200:
            print("Menu check: SUCCESS")
            try:
                menu_data = menu_response.json()
                if "items" in menu_data and len(menu_data["items"]) > 0:
                    print(f"Menu contains {len(menu_data['items'])} items")
                else:
                    print("Menu doesn't contain any items")
            except:
                print(f"Response: {menu_response.text}")
        else:
            print("Menu check: FAILED")
            print(f"Response: {menu_response.text}")
            
        # Final result
        if (health_response.status_code == 200 and 
            env_response.status_code == 200 and 
            menu_response.status_code == 200):
            print("\nAll tests PASSED!")
            return True
        else:
            print("\nSome tests FAILED!")
            return False
            
    except Exception as e:
        print(f"Error during health check: {str(e)}")
        return False

if __name__ == "__main__":
    success = check_health()
    sys.exit(0 if success else 1)