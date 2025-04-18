#!/usr/bin/env python
"""
Test script for menu_update endpoint.

This script allows you to send test data to the menu_update endpoint
to test the menu processing functionality without using Deliverect.

Usage:
    python test_menu_endpoint.py [file_path] [server_url]

If no file_path is provided, it defaults to test_data/deliverect_sample.json
If no server_url is provided, it defaults to http://localhost:5001/menu_update
"""

import json
import sys
import os
import requests


def main():
    # Get command line arguments
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = "test_data/deliverect_sample.json"

    if len(sys.argv) > 2:
        server_url = sys.argv[2]
    else:
        server_url = "http://localhost:5001/menu_update"

    print(f"Using file: {file_path}")
    print(f"Sending to: {server_url}")

    # Check if file exists
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found")
        return 1

    # Read the file
    try:
        with open(file_path, "r") as f:
            menu_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {file_path}: {e}")
        return 1

    # Send to server
    print("\nSending request...")
    try:
        response = requests.post(
            server_url, json=menu_data, headers={"Content-Type": "application/json"}
        )

        # Print response details
        print(f"Status code: {response.status_code}")
        print(f"Response headers: {response.headers}")

        # Try to parse response as JSON
        try:
            response_json = response.json()
            print("\nResponse (JSON):")
            print(json.dumps(response_json, indent=2))
        except:
            print("\nResponse (raw):")
            print(response.text)

        # Return success/failure
        return 0 if response.status_code == 200 else 1

    except requests.RequestException as e:
        print(f"Error sending request: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
