"""
Example usage of the OpenAI Agents-based order system.
"""
import requests
import json
import os

# Define the base URL
# If running locally, use localhost
BASE_URL = "http://localhost:5000"

def analyze_order(text):
    """
    Analyze a text order using the API.
    
    Args:
        text (str): The order text to analyze
        
    Returns:
        dict: The analysis result
    """
    url = f"{BASE_URL}/api/analyze"
    payload = {"text": text}
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()  # Raise an error for bad status codes
        return response.json()
    except requests.RequestException as e:
        print(f"Error sending request: {e}")
        return {"error": str(e)}

def modify_order(text, current_order):
    """
    Modify an existing order using the API.
    
    Args:
        text (str): The modification request
        current_order (dict): The current order
        
    Returns:
        dict: The modification result
    """
    url = f"{BASE_URL}/api/modify"
    payload = {
        "text": text,
        "current_order": current_order
    }
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error sending request: {e}")
        return {"error": str(e)}

def main():
    """Run the example."""
    # Test the analyze endpoint
    print("Testing analyze endpoint...")
    order_text = "I would like to order a California Roll and two Spicy Tuna Rolls with extra wasabi"
    result = analyze_order(order_text)
    print(f"Analysis result: {json.dumps(result, indent=2)}")
    
    # Test the modify endpoint
    print("\nTesting modify endpoint...")
    current_order = {
        "items": [
            {
                "name": "California Roll",
                "quantity": 1,
                "price": 7.95,
                "reference_handler": "cal-roll-1",
                "modifier": []
            }
        ]
    }
    modification_text = "Add a Spicy Tuna Roll and remove the California Roll"
    result = modify_order(modification_text, current_order)
    print(f"Modification result: {json.dumps(result, indent=2)}")

if __name__ == "__main__":
    main()