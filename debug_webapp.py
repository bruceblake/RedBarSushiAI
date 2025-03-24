#!/usr/bin/env python
"""
Debug script for simulating the web app in a simplified environment
"""

import os
import sys
import json
from flask import Flask, session, request, jsonify

# Import the app modules
sys.path.append(os.getcwd())
from app.utils.menu_utils import load_menu_data
from app.utils.order_utils import calculate_bill_amount, find_menu_item_any_status, analyze_user_input

# Create a simple Flask app
app = Flask(__name__)
app.secret_key = "debug_key"
app.config['MENU_FILE_PATH'] = os.path.join(os.getcwd(), 'menu_data.json')

@app.route('/debug_order', methods=['GET'])
def debug_order():
    """Endpoint to simulate the order process"""
    item_name = request.args.get('item', 'Veggie Burger')
    
    # Simulate what happens in order.py
    with app.app_context():
        # Get menu data
        menu_data = load_menu_data()
        item_count = len(menu_data.get('items', []))
        
        # Find the menu item
        matched_item, distance = find_menu_item_any_status(item_name)
        
        if matched_item:
            # Build an order item as in the real app
            order_item = {
                "name": matched_item.get("name"),
                "reference_handler": matched_item.get("reference_handler", ""),
                "modifier": [],
                "quantity": 1,
                "price": matched_item.get("price", 0.0)
            }
            
            # Calculate the bill
            calculate_bill_amount([order_item])
            total_price = session.get('total_price', 0.0)
            
            return jsonify({
                "success": True,
                "menu_item_count": item_count,
                "matched_item_name": matched_item.get("name"),
                "matched_item_price": matched_item.get("price"),
                "order_item_price": order_item.get("price"),
                "calculated_total": total_price,
                "price_type": str(type(matched_item.get("price")))
            })
        else:
            return jsonify({
                "success": False,
                "error": f"Item '{item_name}' not found in menu",
                "menu_item_count": item_count
            })

if __name__ == "__main__":
    # Run the Flask app in debug mode
    app.run(debug=True, port=5000)