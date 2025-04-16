#!/usr/bin/env python
"""
Helper script to manage locations in the RedBarSushiAI system.

This script helps you:
1. List all registered locations
2. Get details about a specific location
3. Register a new location
4. Update an existing location
5. Test webhook URLs for a location

Usage:
  python manage_locations.py list --url https://rebarsushiai-staging.onrender.com
  python manage_locations.py info <location_id> --url https://rebarsushiai-staging.onrender.com
  python manage_locations.py register <location_id> <name> --url https://rebarsushiai-staging.onrender.com
  python manage_locations.py test-webhooks <location_id> --url https://rebarsushiai-staging.onrender.com
"""
import argparse
import json
import requests
import sys

def list_locations(base_url):
    """List all registered locations."""
    url = f"{base_url}/location/list"
    print(f"Fetching locations from: {url}")
    
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        locations = data.get("locations", [])
        
        if not locations:
            print("No locations registered.")
            return
        
        print("\nRegistered Locations:")
        print("=" * 70)
        print(f"{'ID':<20} {'Name':<30} {'Status':<15}")
        print("-" * 70)
        
        for location in locations:
            print(f"{location.get('id', 'N/A'):<20} {location.get('name', 'N/A'):<30} {location.get('status', 'N/A'):<15}")
        
        print("\nUse the following command to get details about a specific location:")
        print(f"python {sys.argv[0]} info <location_id> --url {base_url}")
    else:
        print(f"Error: {response.status_code}")
        try:
            print(response.json())
        except:
            print(response.text)

def get_location_info(base_url, location_id):
    """Get information about a specific location."""
    url = f"{base_url}/location/info/{location_id}"
    print(f"Fetching information for location {location_id} from: {url}")
    
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        
        print("\nLocation Details:")
        print("=" * 70)
        for key, value in data.items():
            if key == "webhooks":
                print("\nWebhook URLs:")
                for webhook_name, webhook_url in value.items():
                    print(f"  {webhook_name:<20}: {webhook_url}")
            else:
                print(f"{key:<15}: {value}")
    else:
        print(f"Error: {response.status_code}")
        try:
            print(response.json())
        except:
            print(response.text)

def register_location(base_url, location_id, name, client_id=None, client_secret=None):
    """Register a new location."""
    url = f"{base_url}/location/{location_id}/register"
    
    # Prepare request data
    data = {
        "status": "register",
        "name": name,
        "webhook_base": base_url
    }
    
    # Add credentials if provided
    if client_id and client_secret:
        data["credentials"] = {
            "client_id": client_id,
            "client_secret": client_secret
        }
    
    print(f"Registering location '{name}' with ID '{location_id}' at: {url}")
    
    response = requests.post(url, json=data)
    
    if response.status_code == 200:
        print("\nLocation registered successfully!")
        try:
            print(json.dumps(response.json(), indent=2))
        except:
            print(response.text)
    else:
        print(f"Error: {response.status_code}")
        try:
            print(json.dumps(response.json(), indent=2))
        except:
            print(response.text)

def test_webhooks(base_url, location_id):
    """Test webhook URLs for a location."""
    # First, get the location info
    info_url = f"{base_url}/location/info/{location_id}"
    print(f"Fetching information for location {location_id} from: {info_url}")
    
    response = requests.get(info_url)
    
    if response.status_code != 200:
        print(f"Error fetching location info: {response.status_code}")
        try:
            print(response.json())
        except:
            print(response.text)
        return
    
    # Get the webhook URLs
    data = response.json()
    webhooks = data.get("webhooks", {})
    
    if not webhooks:
        print("No webhook URLs found for this location.")
        return
    
    print("\nTesting Webhook URLs:")
    print("=" * 70)
    
    # Test each webhook URL
    for webhook_name, webhook_url in webhooks.items():
        print(f"\nTesting {webhook_name}: {webhook_url}")
        
        # Skip status update webhook as it might change order status
        if webhook_name == "statusUpdateURL":
            print("  Skipping status update webhook to avoid changing order statuses")
            continue
        
        # Skip payment update webhook as it might affect payments
        if webhook_name == "paymentUpdateURL":
            print("  Skipping payment update webhook to avoid affecting payments")
            continue
        
        # Prepare test data based on webhook type
        test_data = {
            "test": True,
            "location_id": location_id,
            "source": "webhook_test_script"
        }
        
        # Add webhook-specific test data
        if webhook_name == "menuUpdateURL":
            test_data["categories"] = []
        elif webhook_name == "snoozeUnsnoozeURL":
            test_data["operations"] = []
        elif webhook_name == "busyModeURL":
            test_data["status"] = "PAUSED"
        
        try:
            response = requests.post(webhook_url, json=test_data)
            print(f"  Status code: {response.status_code}")
            try:
                print(f"  Response: {json.dumps(response.json(), indent=2)}")
            except:
                print(f"  Response: {response.text[:100]}")
        except Exception as e:
            print(f"  Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage locations in the RedBarSushiAI system")
    
    # Base URL parameter
    parser.add_argument(
        "--url", 
        default="http://localhost:5000",
        help="Base URL of the API (e.g., https://rebarsushiai-staging.onrender.com)"
    )
    
    # Subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all registered locations")
    
    # Info command
    info_parser = subparsers.add_parser("info", help="Get information about a specific location")
    info_parser.add_argument("location_id", help="ID of the location")
    
    # Register command
    register_parser = subparsers.add_parser("register", help="Register a new location")
    register_parser.add_argument("location_id", help="ID for the new location")
    register_parser.add_argument("name", help="Name of the location")
    register_parser.add_argument("--client-id", help="Deliverect client ID")
    register_parser.add_argument("--client-secret", help="Deliverect client secret")
    
    # Test webhooks command
    test_webhooks_parser = subparsers.add_parser("test-webhooks", help="Test webhook URLs for a location")
    test_webhooks_parser.add_argument("location_id", help="ID of the location")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Clean up base URL
    base_url = args.url.rstrip("/")
    if not base_url.startswith("http"):
        base_url = "https://" + base_url
    
    # Execute command
    if args.command == "list":
        list_locations(base_url)
    elif args.command == "info":
        get_location_info(base_url, args.location_id)
    elif args.command == "register":
        register_location(base_url, args.location_id, args.name, args.client_id, args.client_secret)
    elif args.command == "test-webhooks":
        test_webhooks(base_url, args.location_id)
    else:
        parser.print_help()