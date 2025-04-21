"""
Interactive order resolution API routes using AI.
These routes allow customers to interact with the AI to clarify their orders.
"""

from flask import Blueprint, request, jsonify, session
import logging
import json
import uuid

from app.utils.menu_matcher import menu_matcher

order_ai_bp = Blueprint("order_ai", __name__)
logger = logging.getLogger(__name__)

# Store ongoing order interactions
active_orders = {}

@order_ai_bp.route("/order_ai", methods=["POST"])
def start_order():
    """
    Initialize an interactive order resolution process.
    
    Request:
        JSON with 'customer_request' field containing the customer's order request
        
    Returns:
        JSON with order session ID and initial clarification dialog
    """
    try:
        data = request.get_json()
        if not data or "customer_request" not in data:
            return jsonify({"error": "Missing customer_request field"}), 400
            
        customer_request = data["customer_request"]
        
        # Create a new order session
        session_id = str(uuid.uuid4())
        
        # Initialize the order state with context if provided
        context = data.get("context", {})
        
        # Start the interactive order resolution
        order_state = menu_matcher.interactive_order_resolution(customer_request, context)
        
        # Add a conversation field to track the full dialog
        order_state["conversation"] = [
            {"role": "user", "content": customer_request}
        ]
        
        # Store the order state
        active_orders[session_id] = order_state
        
        # Return the initial clarification dialog
        return jsonify({
            "session_id": session_id,
            "clarification": order_state["clarification_dialog"],
            "resolved": order_state["resolved"],
            "items": order_state.get("items", [])
        }), 200
        
    except Exception as e:
        logger.error(f"[ORDER-AI] Error in start_order: {str(e)}")
        return jsonify({"error": f"Failed to process order: {str(e)}"}), 500

@order_ai_bp.route("/order_ai/<session_id>", methods=["POST"])
def process_response(session_id):
    """
    Process a customer's response in an ongoing order resolution.
    
    Request:
        JSON with 'customer_response' field containing the customer's response
        
    Returns:
        JSON with updated order state
    """
    try:
        # Check if the session exists
        if session_id not in active_orders:
            return jsonify({"error": "Order session not found"}), 404
            
        data = request.get_json()
        if not data or "customer_response" not in data:
            return jsonify({"error": "Missing customer_response field"}), 400
            
        customer_response = data["customer_response"]
        
        # Get the current order state
        order_state = active_orders[session_id]
        
        # Process the customer's response
        updated_state = menu_matcher.process_customer_response(order_state, customer_response)
        
        # Update the stored order state
        active_orders[session_id] = updated_state
        
        # Return the updated clarification dialog
        return jsonify({
            "session_id": session_id,
            "clarification": updated_state["clarification_dialog"],
            "resolved": updated_state["resolved"],
            "items": updated_state.get("items", [])
        }), 200
        
    except Exception as e:
        logger.error(f"[ORDER-AI] Error in process_response: {str(e)}")
        return jsonify({"error": f"Failed to process response: {str(e)}"}), 500

@order_ai_bp.route("/order_ai/<session_id>", methods=["GET"])
def get_order_state(session_id):
    """
    Get the current state of an order resolution.
    
    Returns:
        JSON with the current order state
    """
    try:
        # Check if the session exists
        if session_id not in active_orders:
            return jsonify({"error": "Order session not found"}), 404
            
        # Get the current order state
        order_state = active_orders[session_id]
        
        # Return the current state
        return jsonify({
            "session_id": session_id,
            "original_request": order_state.get("original_request", ""),
            "clarification": order_state["clarification_dialog"],
            "resolved": order_state["resolved"],
            "items": order_state.get("items", [])
        }), 200
        
    except Exception as e:
        logger.error(f"[ORDER-AI] Error in get_order_state: {str(e)}")
        return jsonify({"error": f"Failed to get order state: {str(e)}"}), 500

@order_ai_bp.route("/order_ai/<session_id>/confirm", methods=["POST"])
def confirm_order(session_id):
    """
    Confirm an order after resolution is complete.
    
    Returns:
        JSON with the finalized order
    """
    try:
        # Check if the session exists
        if session_id not in active_orders:
            return jsonify({"error": "Order session not found"}), 404
            
        # Get the current order state
        order_state = active_orders[session_id]
        
        # Check if the order is ready to be confirmed
        if not order_state["resolved"]:
            return jsonify({
                "error": "Order is not fully resolved yet",
                "clarification": order_state["clarification_dialog"]
            }), 400
            
        # Get the confirmed items
        confirmed_items = order_state.get("items", [])
        
        # Clear the session after confirmation
        del active_orders[session_id]
        
        # Return the confirmed order
        return jsonify({
            "success": True,
            "message": "Order confirmed",
            "items": confirmed_items
        }), 200
        
    except Exception as e:
        logger.error(f"[ORDER-AI] Error in confirm_order: {str(e)}")
        return jsonify({"error": f"Failed to confirm order: {str(e)}"}), 500

@order_ai_bp.route("/order_ai/<session_id>/cancel", methods=["POST"])
def cancel_order(session_id):
    """
    Cancel an ongoing order resolution.
    
    Returns:
        JSON with confirmation of cancellation
    """
    try:
        # Check if the session exists
        if session_id not in active_orders:
            return jsonify({"error": "Order session not found"}), 404
            
        # Clear the session
        del active_orders[session_id]
        
        # Return confirmation
        return jsonify({
            "success": True,
            "message": "Order cancelled"
        }), 200
        
    except Exception as e:
        logger.error(f"[ORDER-AI] Error in cancel_order: {str(e)}")
        return jsonify({"error": f"Failed to cancel order: {str(e)}"}), 500