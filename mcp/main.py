#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RedBarSushiAI MCP Server using FastMCP.

Implements Model Context Protocol (MCP) for RedBarSushiAI using the FastMCP framework.
This server provides tools for menu management, order processing, and restaurant management.
"""

from mcp.server.fastmcp import FastMCP, Context
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from pathlib import Path
from dotenv import load_dotenv
import asyncio
import json
import os
import redis
import logging
import sys
from sqlalchemy.orm import Session
import time
import random
import string

# Import our utility functions
from redbarsushi_mcp.utils import (
    get_database_connection, 
    get_redis_connection,
    get_menu_items_from_db,
    get_menu_categories_from_db,
    search_menu_items_in_db,
    get_cart_from_redis,
    get_restaurant_info
)

# Load environment variables from the project root .env file
project_root = Path(__file__).resolve().parent.parent
dotenv_path = project_root / '.env'

# Force override of existing environment variables
load_dotenv(dotenv_path, override=True)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("redbarsushi_mcp.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("redbarsushi_mcp")
logger.setLevel(logging.DEBUG)

# Create a dataclass for our application context
@dataclass
class RedBarSushiContext:
    """Context for the RedBarSushi MCP server."""
    db_session: Optional[Session] = None
    redis_client: Optional[redis.Redis] = None

@asynccontextmanager
async def redbarsushi_lifespan(server: FastMCP) -> AsyncIterator[RedBarSushiContext]:
    """
    Manages the RedBarSushi context lifecycle.
    
    Args:
        server: The FastMCP server instance
        
    Yields:
        RedBarSushiContext: The context containing database and Redis connections
    """
    # Initialize connections
    db_session, db_error = get_database_connection()
    redis_client, redis_error = get_redis_connection()
    
    if db_error:
        logger.warning(db_error)
    
    if redis_error:
        logger.warning(redis_error)
    
    try:
        # Yield the context
        yield RedBarSushiContext(
            db_session=db_session,
            redis_client=redis_client
        )
    finally:
        # Clean up resources
        if db_session:
            db_session.close()
            logger.info("Database connection closed")
        
        if redis_client:
            redis_client.close()
            logger.info("Redis connection closed")

# Initialize FastMCP server
mcp = FastMCP(
    "redbarsushi-mcp",
    description="MCP server for RedBarSushi AI voice ordering system",
    lifespan=redbarsushi_lifespan,
    host=os.getenv("HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", "8050"))
)

@mcp.tool()
async def get_menu_items(ctx: Context, category_id: Optional[int] = None) -> str:
    """
    Get menu items from the database.
    
    Args:
        ctx: The MCP server provided context
        category_id: Optional category ID to filter items
        
    Returns:
        JSON string with menu items
    """
    db_session = ctx.request_context.lifespan_context.db_session
    
    if not db_session:
        return json.dumps({
            "success": False,
            "error": "Database connection not available"
        })
    
    result = get_menu_items_from_db(db_session, category_id)
    return json.dumps(result)

@mcp.tool()
async def get_menu_categories(ctx: Context) -> str:
    """
    Get menu categories from the database.
    
    Args:
        ctx: The MCP server provided context
        
    Returns:
        JSON string with menu categories
    """
    db_session = ctx.request_context.lifespan_context.db_session
    
    if not db_session:
        return json.dumps({
            "success": False,
            "error": "Database connection not available"
        })
    
    result = get_menu_categories_from_db(db_session)
    return json.dumps(result)

@mcp.tool()
async def search_menu_items(ctx: Context, query: str) -> str:
    """
    Search menu items by name or description.
    
    Args:
        ctx: The MCP server provided context
        query: Search query string
        
    Returns:
        JSON string with matching menu items
    """
    db_session = ctx.request_context.lifespan_context.db_session
    
    if not db_session:
        return json.dumps({
            "success": False,
            "error": "Database connection not available"
        })
    
    result = search_menu_items_in_db(db_session, query)
    return json.dumps(result)

@mcp.tool()
async def get_cart(ctx: Context, session_id: str) -> str:
    """
    Get the current cart for a session from Redis.
    
    Args:
        ctx: The MCP server provided context
        session_id: The session ID
        
    Returns:
        JSON string with cart contents
    """
    redis_client = ctx.request_context.lifespan_context.redis_client
    
    if not redis_client:
        return json.dumps({
            "success": False,
            "error": "Redis connection not available"
        })
    
    result = get_cart_from_redis(redis_client, session_id)
    return json.dumps(result)

@mcp.tool()
async def add_to_cart(ctx: Context, session_id: str, item_plu: str, quantity: int = 1, modifiers: Optional[List[Dict[str, Any]]] = None) -> str:
    """
    Add an item to the cart in Redis.
    
    Args:
        ctx: The MCP server provided context
        session_id: The session ID
        item_plu: The PLU of the item to add
        quantity: The quantity to add (default: 1)
        modifiers: Optional list of modifiers to add
        
    Returns:
        JSON string with updated cart
    """
    try:
        db_session = ctx.request_context.lifespan_context.db_session
        redis_client = ctx.request_context.lifespan_context.redis_client
        
        if not db_session or not redis_client:
            return json.dumps({
                "success": False,
                "error": "Database or Redis connection not available"
            })
        
        # Get item details from database
        from sqlalchemy import text
        sql = text("SELECT id, name, price FROM menu_items WHERE plu = :plu")
        result = db_session.execute(sql, {"plu": item_plu})
        row = result.fetchone()
        
        if not row:
            return json.dumps({
                "success": False,
                "error": f"Item with PLU {item_plu} not found"
            })
        
        item_id, item_name, item_price = row
        
        # Get current cart from Redis
        cart_json = redis_client.get(f"cart:{session_id}")
        cart = json.loads(cart_json) if cart_json else {"items": [], "total_price": 0}
        
        # Add item to cart
        new_item = {
            "plu": item_plu,
            "name": item_name,
            "price": item_price,
            "quantity": quantity,
            "modifiers": modifiers or []
        }
        
        # Calculate item total price including modifiers
        item_total = item_price * quantity
        for modifier in (modifiers or []):
            if "price_change" in modifier:
                item_total += modifier["price_change"] * quantity
        
        cart["items"].append(new_item)
        cart["total_price"] += item_total
        
        # Save updated cart to Redis
        redis_client.set(f"cart:{session_id}", json.dumps(cart))
        
        return json.dumps({
            "success": True,
            "cart": cart
        })
    except Exception as e:
        logger.error(f"Error adding to cart: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        })

@mcp.tool()
async def remove_from_cart(ctx: Context, session_id: str, item_index: int) -> str:
    """
    Remove an item from the cart in Redis.
    
    Args:
        ctx: The MCP server provided context
        session_id: The session ID
        item_index: The index of the item to remove
        
    Returns:
        JSON string with updated cart
    """
    try:
        redis_client = ctx.request_context.lifespan_context.redis_client
        
        if not redis_client:
            return json.dumps({
                "success": False,
                "error": "Redis connection not available"
            })
        
        # Get current cart from Redis
        cart_json = redis_client.get(f"cart:{session_id}")
        
        if not cart_json:
            return json.dumps({
                "success": False,
                "error": "Cart not found"
            })
        
        cart = json.loads(cart_json)
        
        if item_index < 0 or item_index >= len(cart["items"]):
            return json.dumps({
                "success": False,
                "error": f"Item index {item_index} out of range"
            })
        
        # Remove item and update total price
        item = cart["items"].pop(item_index)
        item_total = item["price"] * item["quantity"]
        for modifier in item.get("modifiers", []):
            if "price_change" in modifier:
                item_total += modifier["price_change"] * item["quantity"]
        
        cart["total_price"] -= item_total
        
        # Save updated cart to Redis
        redis_client.set(f"cart:{session_id}", json.dumps(cart))
        
        return json.dumps({
            "success": True,
            "cart": cart
        })
    except Exception as e:
        logger.error(f"Error removing from cart: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        })

@mcp.tool()
async def clear_cart(ctx: Context, session_id: str) -> str:
    """
    Clear the cart in Redis.
    
    Args:
        ctx: The MCP server provided context
        session_id: The session ID
        
    Returns:
        JSON string with empty cart
    """
    try:
        redis_client = ctx.request_context.lifespan_context.redis_client
        
        if not redis_client:
            return json.dumps({
                "success": False,
                "error": "Redis connection not available"
            })
        
        # Create empty cart
        empty_cart = {
            "items": [],
            "total_price": 0
        }
        
        # Save empty cart to Redis
        redis_client.set(f"cart:{session_id}", json.dumps(empty_cart))
        
        return json.dumps({
            "success": True,
            "cart": empty_cart
        })
    except Exception as e:
        logger.error(f"Error clearing cart: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        })

@mcp.tool()
async def place_order(ctx: Context, session_id: str, customer_name: str, customer_phone: str, 
                     order_type: int, delivery_address: Optional[str] = None) -> str:
    """
    Place an order from the cart.
    
    Args:
        ctx: The MCP server provided context
        session_id: The session ID
        customer_name: The customer's name
        customer_phone: The customer's phone number
        order_type: The order type (1=pickup, 2=delivery, 3=eat-in, 4=curbside)
        delivery_address: The delivery address (required for delivery orders)
        
    Returns:
        JSON string with order details
    """
    try:
        db_session = ctx.request_context.lifespan_context.db_session
        redis_client = ctx.request_context.lifespan_context.redis_client
        
        if not db_session or not redis_client:
            return json.dumps({
                "success": False,
                "error": "Database or Redis connection not available"
            })
        
        # Validate order type
        if order_type not in [1, 2, 3, 4]:
            return json.dumps({
                "success": False,
                "error": "Invalid order type"
            })
        
        # Validate delivery address for delivery orders
        if order_type == 2 and not delivery_address:
            return json.dumps({
                "success": False,
                "error": "Delivery address is required for delivery orders"
            })
        
        # Get cart from Redis
        cart_json = redis_client.get(f"cart:{session_id}")
        
        if not cart_json:
            return json.dumps({
                "success": False,
                "error": "Cart not found"
            })
        
        cart = json.loads(cart_json)
        
        if not cart["items"]:
            return json.dumps({
                "success": False,
                "error": "Cart is empty"
            })
        
        # Generate a unique order ID
        timestamp = int(time.time())
        random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        channel_order_id = f"RBS-{timestamp}-{random_chars}"
        
        # Insert order into database
        from sqlalchemy import text
        sql = text("""
            INSERT INTO orders 
            (deliverect_channel_order_id, customer_phone, customer_name, order_type, 
             status, total_price, delivery_address) 
            VALUES (:channel_order_id, :customer_phone, :customer_name, :order_type, 
                   :status, :total_price, :delivery_address)
            RETURNING id
        """)
        
        result = db_session.execute(sql, {
            "channel_order_id": channel_order_id,
            "customer_phone": customer_phone,
            "customer_name": customer_name,
            "order_type": order_type,
            "status": 10,  # Initial status
            "total_price": cart["total_price"],
            "delivery_address": delivery_address
        })
        
        order_id = result.fetchone()[0]
        
        # Insert order items
        for item in cart["items"]:
            # Insert order item
            sql = text("""
                INSERT INTO order_items 
                (order_id, menu_item_plu, name, price, quantity) 
                VALUES (:order_id, :menu_item_plu, :name, :price, :quantity)
                RETURNING id
            """)
            
            result = db_session.execute(sql, {
                "order_id": order_id,
                "menu_item_plu": item["plu"],
                "name": item["name"],
                "price": item["price"],
                "quantity": item["quantity"]
            })
            
            order_item_id = result.fetchone()[0]
            
            # Insert modifiers
            for modifier in item.get("modifiers", []):
                sql = text("""
                    INSERT INTO order_item_modifiers 
                    (order_item_id, modifier_plu, name, price_change, quantity) 
                    VALUES (:order_item_id, :modifier_plu, :name, :price_change, :quantity)
                """)
                
                db_session.execute(sql, {
                    "order_item_id": order_item_id,
                    "modifier_plu": modifier["plu"],
                    "name": modifier["name"],
                    "price_change": modifier["price_change"],
                    "quantity": 1
                })
        
        # Commit the transaction
        db_session.commit()
        
        # Clear the cart
        redis_client.delete(f"cart:{session_id}")
        
        # Return order details
        return json.dumps({
            "success": True,
            "order": {
                "id": order_id,
                "channel_order_id": channel_order_id,
                "total_price": cart["total_price"],
                "items": [
                    {
                        "name": item["name"],
                        "quantity": item["quantity"],
                        "price": item["price"],
                        "modifiers": item.get("modifiers", [])
                    }
                    for item in cart["items"]
                ]
            }
        })
    except Exception as e:
        logger.error(f"Error placing order: {str(e)}")
        # Rollback transaction if there was an error
        if db_session:
            db_session.rollback()
        return json.dumps({
            "success": False,
            "error": str(e)
        })

@mcp.tool()
async def get_restaurant_info_tool(ctx: Context) -> str:
    """
    Get information about the restaurant.
    
    Args:
        ctx: The MCP server provided context
        
    Returns:
        JSON string with restaurant information
    """
    result = get_restaurant_info()
    return json.dumps(result)

@mcp.tool()
async def echo(ctx: Context, message: str) -> str:
    """
    Echo a message back (for testing).
    
    Args:
        ctx: The MCP server provided context
        message: The message to echo
        
    Returns:
        The message echoed back
    """
    return f"Echo: {message}"

if __name__ == "__main__":
    # Start the MCP server
    import uvicorn
    uvicorn.run(
        "main:mcp",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8050")),
        reload=False
    )