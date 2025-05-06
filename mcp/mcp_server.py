#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RedBarSushiAI MCP Server using the FastMCP approach.
"""

from mcp.server.fastmcp import FastMCP, Context
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Union
import os
import sys
import json
import logging
import redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

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

# Create a context class for our application
@dataclass
class RedBarSushiContext:
    """Context for the RedBarSushi MCP server."""
    db_session: Optional[Session] = None
    redis_client: Optional[redis.Redis] = None

# Create a context manager for our application
@asynccontextmanager
async def redbarsushi_lifespan() -> AsyncIterator[RedBarSushiContext]:
    """
    Manages the RedBarSushi context lifecycle.
    
    Yields:
        RedBarSushiContext: The context containing database and Redis connections
    """
    # Initialize connections
    db_session = None
    redis_client = None
    
    # Configure database connection
    DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/redbarsushi")
    try:
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db_session = SessionLocal()
        logger.info("Database connection established")
    except Exception as e:
        logger.warning(f"Database connection error: {str(e)}")
        logger.warning("Running without database support")
    
    # Configure Redis connection
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    try:
        redis_client = redis.from_url(REDIS_URL)
        redis_client.ping()  # Check connection
        logger.info("Redis connection established")
    except Exception as e:
        logger.warning(f"Redis connection error: {str(e)}")
        logger.warning("Running without Redis support")
    
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

# Initialize the MCP server
mcp = FastMCP(
    "redbarsushi-mcp",
    description="MCP server for RedBarSushi AI voice ordering system",
    lifespan=redbarsushi_lifespan
)

@mcp.tool()
async def echo(message: str, ctx: Context) -> str:
    """
    Echo a message back (for testing).
    
    Args:
        message: The message to echo
        ctx: The MCP context
        
    Returns:
        The message echoed back
    """
    await ctx.info(f"Echoing: {message}")
    return f"Echo: {message}"

@mcp.tool()
async def get_restaurant_info(ctx: Context) -> Dict[str, Any]:
    """
    Get information about the restaurant.
    
    Args:
        ctx: The MCP context
        
    Returns:
        Dictionary with restaurant information
    """
    # Static restaurant information
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
    
    await ctx.info("Retrieved restaurant information")
    return info

@mcp.tool()
async def get_menu_categories(ctx: Context) -> List[Dict[str, Any]]:
    """
    Get menu categories from the database.
    
    Args:
        ctx: The MCP context
        
    Returns:
        List of menu categories
    """
    # Get database session from context
    db_session = ctx.request_context.lifespan_context.db_session
    
    if not db_session:
        await ctx.error("Database connection not available")
        return []
    
    try:
        # Execute the query
        result = db_session.execute(text("SELECT id, name, description FROM menu_categories"))
        
        # Convert to list of dictionaries
        categories = []
        for row in result:
            categories.append({
                "id": row[0],
                "name": row[1],
                "description": row[2]
            })
        
        await ctx.info(f"Retrieved {len(categories)} menu categories")
        return categories
    except Exception as e:
        await ctx.error(f"Error getting menu categories: {str(e)}")
        return []

@mcp.tool()
async def get_menu_items(category_id: Optional[int] = None, ctx: Context = None) -> List[Dict[str, Any]]:
    """
    Get menu items from the database.
    
    Args:
        category_id: Optional category ID to filter items
        ctx: The MCP context
        
    Returns:
        List of menu items
    """
    # Get database session from context
    db_session = ctx.request_context.lifespan_context.db_session
    
    if not db_session:
        await ctx.error("Database connection not available")
        return []
    
    try:
        # Build the query
        query = "SELECT id, name, description, price, plu FROM menu_items"
        params = {}
        
        if category_id is not None:
            query += " WHERE category_id = :category_id"
            params["category_id"] = category_id
            await ctx.info(f"Getting menu items for category {category_id}")
        else:
            await ctx.info("Getting all menu items")
        
        # Execute the query
        result = db_session.execute(text(query), params)
        
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
        
        await ctx.info(f"Retrieved {len(items)} menu items")
        return items
    except Exception as e:
        await ctx.error(f"Error getting menu items: {str(e)}")
        return []

@mcp.tool()
async def search_menu_items(query: str, ctx: Context) -> List[Dict[str, Any]]:
    """
    Search menu items by name or description.
    
    Args:
        query: Search query string
        ctx: The MCP context
        
    Returns:
        List of matching menu items
    """
    # Get database session from context
    db_session = ctx.request_context.lifespan_context.db_session
    
    if not db_session:
        await ctx.error("Database connection not available")
        return []
    
    try:
        # Execute the query with ILIKE for case-insensitive search
        sql = text("SELECT id, name, description, price, plu FROM menu_items WHERE name ILIKE :query OR description ILIKE :query")
        result = db_session.execute(sql, {"query": f"%{query}%"})
        
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
        
        await ctx.info(f"Found {len(items)} menu items matching '{query}'")
        return items
    except Exception as e:
        await ctx.error(f"Error searching menu items: {str(e)}")
        return []

@mcp.tool()
async def get_cart(session_id: str, ctx: Context) -> Dict[str, Any]:
    """
    Get the current cart for a session from Redis.
    
    Args:
        session_id: The session ID
        ctx: The MCP context
        
    Returns:
        Dictionary with cart contents
    """
    # Get Redis client from context
    redis_client = ctx.request_context.lifespan_context.redis_client
    
    if not redis_client:
        await ctx.error("Redis connection not available")
        return {"items": [], "total_price": 0}
    
    try:
        # Get cart from Redis
        cart_json = redis_client.get(f"cart:{session_id}")
        
        if not cart_json:
            await ctx.info(f"Cart not found for session {session_id}")
            return {"items": [], "total_price": 0}
        
        # Parse JSON
        cart = json.loads(cart_json)
        
        await ctx.info(f"Retrieved cart with {len(cart.get('items', []))} items")
        return cart
    except Exception as e:
        await ctx.error(f"Error getting cart: {str(e)}")
        return {"items": [], "total_price": 0}

@mcp.tool()
async def add_to_cart(session_id: str, item_plu: str, quantity: int = 1, 
                    modifiers: Optional[List[Dict[str, Any]]] = None, ctx: Context = None) -> Dict[str, Any]:
    """
    Add an item to the cart in Redis.
    
    Args:
        session_id: The session ID
        item_plu: The PLU of the item to add
        quantity: The quantity to add (default: 1)
        modifiers: Optional list of modifiers to add
        ctx: The MCP context
        
    Returns:
        Dictionary with updated cart
    """
    try:
        # Get connections from context
        db_session = ctx.request_context.lifespan_context.db_session
        redis_client = ctx.request_context.lifespan_context.redis_client
        
        if not db_session or not redis_client:
            await ctx.error("Database or Redis connection not available")
            return {"success": False, "error": "Database or Redis connection not available"}
        
        # Get item details from database
        sql = text("SELECT id, name, price FROM menu_items WHERE plu = :plu")
        result = db_session.execute(sql, {"plu": item_plu})
        row = result.fetchone()
        
        if not row:
            await ctx.error(f"Item with PLU {item_plu} not found")
            return {"success": False, "error": f"Item with PLU {item_plu} not found"}
        
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
        
        await ctx.info(f"Added {quantity} x {item_name} to cart")
        return {"success": True, "cart": cart}
    except Exception as e:
        await ctx.error(f"Error adding to cart: {str(e)}")
        return {"success": False, "error": str(e)}

# Run the MCP server if executed directly
if __name__ == "__main__":
    # Get host and port from environment variables
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8050"))
    
    # Run the server
    import uvicorn
    logger.info(f"Starting MCP server on {host}:{port}")
    uvicorn.run(
        "mcp_server:mcp",
        host=host,
        port=port,
        reload=False
    )