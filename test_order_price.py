#!/usr/bin/env python
"""
Test script to simulate order price calculation
"""

import json
import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_veggie_burger_price():
    """Test how the Veggie Burger price is calculated"""
    try:
        # Direct file access
        file_path = os.path.join(os.getcwd(), 'menu_data.json')
        with open(file_path, 'r') as f:
            menu_data = json.load(f)
            
        # Find veggie burger
        veggie_burger = None
        for item in menu_data.get("items", []):
            if "veggie" in item.get("name", "").lower() and "burger" in item.get("name", "").lower():
                veggie_burger = item
                break
                
        if not veggie_burger:
            print("Veggie burger not found in menu data")
            return
            
        print(f"\nFound veggie burger in menu data:")
        print(f"Name: {veggie_burger.get('name')}")
        print(f"Price: ${veggie_burger.get('price')}")
        print(f"Price type: {type(veggie_burger.get('price'))}")
        
        # Simulate the "or 0.0" problem we identified
        price_value = veggie_burger.get("price")
        calculated_price = price_value or 0.0
        
        print(f"\nSimulating the issue with 'or 0.0':")
        print(f"Original price: {price_value}")
        print(f"After 'or 0.0': {calculated_price}")
        
        # Test the fix
        if price_value is None:
            fixed_price = 0.0
        else:
            try:
                fixed_price = float(price_value)
            except (ValueError, TypeError):
                fixed_price = 0.0
                
        print(f"\nUsing our fix:")
        print(f"Fixed price: {fixed_price}")
        
    except Exception as e:
        print(f"Error in test: {str(e)}")

if __name__ == "__main__":
    test_veggie_burger_price()