#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Simple MCP Server for RedBarSushiAI following the crawl4ai-rag model
"""

import os
import sys
import time
import json
import logging
from typing import Dict, Any, Optional, List, Union
from flask import Flask, jsonify, request, Response
import redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("redbarsushi_mcp.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("redbarsushi_mcp")

# Create Flask app
app = Flask(__name__)

# Configure database connection
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/redbarsushi")
try:
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info("Database connection established")
    has_db = True
except Exception as e:
    logger.warning(f"Database connection error: {str(e)}")
    logger.warning("Running without database support")
    engine = None
    SessionLocal = None
    has_db = False

# Configure Redis connection
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
try:
    redis_client = redis.from_url(REDIS_URL)
    redis_client.ping()
    logger.info("Redis connection established")
    has_redis = True
except Exception as e:
    logger.warning(f"Redis connection error: {str(e)}")
    logger.warning("Running without Redis support")
    redis_client = None
    has_redis = False

# Define our tools
available_tools = {
    "echo": {
        "description": "Echo a message back (for testing)",
        "parameters": {
            "message": {
                "type": "string",
                "description": "The message to echo"
            }
        }
    },
    "get_restaurant_info": {
        "description": "Get information about the restaurant",
        "parameters": {}
    },
    "get_menu_items": {
        "description": "Get menu items, optionally filtered by category",
        "parameters": {
            "category_id": {
                "type": "integer",
                "description": "Category ID to filter items (optional)"
            }
        }
    },
    "search_menu_items": {
        "description": "Search menu items by name or description",
        "parameters": {
            "query": {
                "type": "string",
                "description": "Search query string"
            }
        }
    },
    "get_cart": {
        "description": "Get the current cart for a session",
        "parameters": {
            "session_id": {
                "type": "string",
                "description": "The session ID"
            }
        }
    },
    "add_to_cart": {
        "description": "Add an item to the cart",
        "parameters": {
            "session_id": {
                "type": "string",
                "description": "The session ID"
            },
            "item_plu": {
                "type": "string",
                "description": "The PLU of the item to add"
            },
            "quantity": {
                "type": "integer",
                "description": "The quantity to add (default: 1)"
            }
        }
    }
}

# Tool implementations
def echo_tool(arguments):
    """Echo a message back."""
    message = arguments.get("message", "No message provided")
    return f"Echo: {message}"

def get_restaurant_info_tool():
    """Get information about the restaurant."""
    info = {
        "name": "Red Bar Sushi",
        "address": "123 Main St, Anytown, USA",
        "phone": "+1-555-123-4567",
        "hours": {
            "Monday": "11:00 AM - 10:00 PM",
            "Tuesday": "11:00 AM - 10:00 PM",
            "Wednesday": "11:00 AM - 10:00 PM",
            "Thursday": "11:00 AM - 10:00 PM",
            "Friday": "11:00 AM - 11:00 PM",
            "Saturday": "12:00 PM - 11:00 PM",
            "Sunday": "12:00 PM - 9:00 PM"
        },
        "delivery_radius": "5 miles",
        "minimum_order": "$15.00",
        "delivery_fee": "$3.99"
    }
    return json.dumps(info, indent=2)

def get_menu_items_tool(arguments):
    """Get menu items from the database."""
    if not has_db:
        return json.dumps({"error": "Database not available"})
    
    try:
        category_id = arguments.get("category_id")
        
        db = SessionLocal()
        
        # Build query
        query = "SELECT id, name, description, price, plu FROM menu_items"
        params = {}
        
        if category_id is not None:
            query += " WHERE category_id = :category_id"
            params["category_id"] = category_id
        
        # Execute query
        result = db.execute(text(query), params)
        
        # Convert to list of dictionaries
        items = []
        for row in result:
            items.append({
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "price": row[3],
                "plu": row[4]
            })
        
        db.close()
        
        return json.dumps({"items": items}, indent=2)
    except Exception as e:
        logger.error(f"Error getting menu items: {str(e)}")
        return json.dumps({"error": str(e)})

def search_menu_items_tool(arguments):
    """Search menu items by name or description."""
    if not has_db:
        return json.dumps({"error": "Database not available"})
    
    try:
        query = arguments.get("query", "")
        
        db = SessionLocal()
        
        # Execute query with ILIKE for case-insensitive search
        sql = text("SELECT id, name, description, price, plu FROM menu_items WHERE name ILIKE :query OR description ILIKE :query")
        result = db.execute(sql, {"query": f"%{query}%"})
        
        # Convert to list of dictionaries
        items = []
        for row in result:
            items.append({
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "price": row[3],
                "plu": row[4]
            })
        
        db.close()
        
        return json.dumps({"items": items}, indent=2)
    except Exception as e:
        logger.error(f"Error searching menu items: {str(e)}")
        return json.dumps({"error": str(e)})

def get_cart_tool(arguments):
    """Get the current cart for a session."""
    if not has_redis:
        return json.dumps({"error": "Redis not available"})
    
    try:
        session_id = arguments.get("session_id", "")
        
        # Get cart from Redis
        cart_json = redis_client.get(f"cart:{session_id}")
        
        if not cart_json:
            return json.dumps({"items": [], "total_price": 0})
        
        # Parse JSON
        cart = json.loads(cart_json)
        
        return json.dumps(cart, indent=2)
    except Exception as e:
        logger.error(f"Error getting cart: {str(e)}")
        return json.dumps({"error": str(e)})

def add_to_cart_tool(arguments):
    """Add an item to the cart."""
    if not has_db or not has_redis:
        return json.dumps({"error": "Database or Redis not available"})
    
    try:
        session_id = arguments.get("session_id", "")
        item_plu = arguments.get("item_plu", "")
        quantity = arguments.get("quantity", 1)
        
        db = SessionLocal()
        
        # Get item details from database
        sql = text("SELECT id, name, price FROM menu_items WHERE plu = :plu")
        result = db.execute(sql, {"plu": item_plu})
        row = result.fetchone()
        
        if not row:
            db.close()
            return json.dumps({"error": f"Item with PLU {item_plu} not found"})
        
        item_id, item_name, item_price = row
        db.close()
        
        # Get current cart from Redis
        cart_json = redis_client.get(f"cart:{session_id}")
        cart = json.loads(cart_json) if cart_json else {"items": [], "total_price": 0}
        
        # Add item to cart
        new_item = {
            "plu": item_plu,
            "name": item_name,
            "price": item_price,
            "quantity": quantity,
            "modifiers": []
        }
        
        # Calculate item total price
        item_total = item_price * quantity
        
        cart["items"].append(new_item)
        cart["total_price"] += item_total
        
        # Save updated cart to Redis
        redis_client.set(f"cart:{session_id}", json.dumps(cart))
        
        return json.dumps({"success": True, "cart": cart}, indent=2)
    except Exception as e:
        logger.error(f"Error adding to cart: {str(e)}")
        return json.dumps({"error": str(e)})

# Map tool names to their implementations
tool_implementations = {
    "echo": echo_tool,
    "get_restaurant_info": get_restaurant_info_tool,
    "get_menu_items": get_menu_items_tool,
    "search_menu_items": search_menu_items_tool,
    "get_cart": get_cart_tool,
    "add_to_cart": add_to_cart_tool
}

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy", 
        "server": "RedBarSushiAI MCP Server",
        "database": "connected" if has_db else "disconnected",
        "redis": "connected" if has_redis else "disconnected"
    })

# SSE endpoint for MCP server
@app.route('/', methods=['GET'])
def mcp_sse():
    logger.debug("SSE connection established")
    
    def stream():
        """Generate SSE events."""
        logger.debug("Starting SSE stream")
        yield f"data: {{\"jsonrpc\":\"2.0\",\"method\":\"server/hello\",\"params\":{{\"name\":\"RedBarSushiAI MCP Server\",\"version\":\"1.0.0\"}}}}\n\n"
        
        counter = 0
        while True:
            time.sleep(5)
            yield f"data: {{\"jsonrpc\":\"2.0\",\"method\":\"server/ping\",\"params\":{{\"counter\":{counter}}}}}\n\n"
            counter += 1
    
    return Response(stream(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Access-Control-Allow-Origin": "*"
    })

# JSON-RPC endpoint
@app.route('/', methods=['POST'])
def mcp_jsonrpc():
    """HTTP endpoint for MCP JSON-RPC requests."""
    try:
        request_data = request.json
        method = request_data.get("method")
        params = request_data.get("params", {})
        request_id = request_data.get("id")
        
        logger.debug(f"Received {method} request: {request_data}")
        
        # Handle different methods
        if method == "execute_tool":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            if tool_name in tool_implementations:
                try:
                    if tool_name == "get_restaurant_info":
                        result = tool_implementations[tool_name]()
                    else:
                        result = tool_implementations[tool_name](tool_args)
                    
                    return jsonify({
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": result
                    })
                except Exception as e:
                    logger.error(f"Error executing tool {tool_name}: {str(e)}")
                    return jsonify({
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32000,
                            "message": f"Error executing tool: {str(e)}"
                        }
                    })
            else:
                return jsonify({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Tool not found: {tool_name}"
                    }
                })
        elif method == "list_tools":
            return jsonify({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": [
                    {
                        "name": name,
                        "description": info["description"],
                        "parameters": info["parameters"]
                    } for name, info in available_tools.items()
                ]
            })
        else:
            return jsonify({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not supported: {method}"
                }
            })
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({
            "jsonrpc": "2.0",
            "id": request_id if 'request_id' in locals() else None,
            "error": {
                "code": -32700,
                "message": f"Parse error: {str(e)}"
            }
        })

if __name__ == '__main__':
    # Use simple Flask instead of uvicorn to avoid compatibility issues
    port = int(os.environ.get("PORT", 8050))
    logger.info(f"Starting MCP server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)