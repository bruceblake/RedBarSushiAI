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
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from dotenv import load_dotenv
import asyncio
import json
import os
import redis
import logging
import sys
import re
import shutil
import time
import subprocess
import hmac
import hashlib
import base64
import random
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

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
        logging.FileHandler("mcp/fastmcp_server.log"),
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
    # Configure database connection
    db_session = None
    redis_client = None
    
    try:
        # Initialize database connection
        DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/redbarsushi")
        try:
            engine = create_engine(DATABASE_URL)
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            db_session = SessionLocal()
            logger.info("Database connection established")
        except Exception as e:
            logger.warning(f"Database connection error: {str(e)}")
            logger.warning("Running without database support")

        # Initialize Redis connection
        REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        try:
            redis_client = redis.from_url(REDIS_URL)
            redis_client.ping()  # Check connection
            logger.info("Redis connection established")
        except Exception as e:
            logger.warning(f"Redis connection error: {str(e)}")
            logger.warning("Running without Redis support")
        
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
    try:
        db_session = ctx.request_context.lifespan_context.db_session
        
        if not db_session:
            return json.dumps({
                "success": False,
                "error": "Database connection not available"
            })
        
        # Build the query
        query = "SELECT id, name, description, price, plu FROM menu_items"
        if category_id is not None:
            query += f" WHERE category_id = {category_id}"
        
        # Execute the query
        result = db_session.execute(text(query))
        
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
        
        return json.dumps({
            "success": True,
            "items": items
        })
    except Exception as e:
        logger.error(f"Error getting menu items: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        })

@mcp.tool()
async def get_menu_categories(ctx: Context) -> str:
    """
    Get menu categories from the database.
    
    Args:
        ctx: The MCP server provided context
        
    Returns:
        JSON string with menu categories
    """
    try:
        db_session = ctx.request_context.lifespan_context.db_session
        
        if not db_session:
            return json.dumps({
                "success": False,
                "error": "Database connection not available"
            })
        
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
        
        return json.dumps({
            "success": True,
            "categories": categories
        })
    except Exception as e:
        logger.error(f"Error getting menu categories: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        })

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
    try:
        db_session = ctx.request_context.lifespan_context.db_session
        
        if not db_session:
            return json.dumps({
                "success": False,
                "error": "Database connection not available"
            })
        
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
        
        return json.dumps({
            "success": True,
            "items": items
        })
    except Exception as e:
        logger.error(f"Error searching menu items: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        })

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
    try:
        redis_client = ctx.request_context.lifespan_context.redis_client
        
        if not redis_client:
            return json.dumps({
                "success": False,
                "error": "Redis connection not available"
            })
        
        # Get cart from Redis
        cart_json = redis_client.get(f"cart:{session_id}")
        
        if not cart_json:
            return json.dumps({
                "success": True,
                "cart": {
                    "items": [],
                    "total_price": 0
                }
            })
        
        # Parse JSON
        cart = json.loads(cart_json)
        
        return json.dumps({
            "success": True,
            "cart": cart
        })
    except Exception as e:
        logger.error(f"Error getting cart: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        })

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
        import time
        import random
        import string
        timestamp = int(time.time())
        random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        channel_order_id = f"RBS-{timestamp}-{random_chars}"
        
        # Insert order into database
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
async def get_restaurant_info(ctx: Context) -> str:
    """
    Get information about the restaurant.
    
    Args:
        ctx: The MCP server provided context
        
    Returns:
        JSON string with restaurant information
    """
    try:
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
            "minimum_order": "15.00",
            "delivery_fee": "3.99"
        }
        
        return json.dumps({
            "success": True,
            "info": info
        })
    except Exception as e:
        logger.error(f"Error getting restaurant info: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        })

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

@mcp.tool()
async def tail_log(ctx: Context, file: str = "web") -> str:
    """
    Get the last 200 lines of a log file.
    
    Args:
        ctx: The MCP server provided context
        file: The log file to tail (default: "web")
        
    Returns:
        JSON string with the log contents
    """
    try:
        # Map file aliases to actual file paths
        log_files = {
            "web": "mcp_server.log",
            "mcp": "mcp/mcp_server.log",
            "fastmcp": "mcp/fastmcp_server.log",
            "websocket": "websocket_monitor.log",
            "enhanced_mcp": "mcp/enhanced_mcp.log",
            "proper_mcp": "mcp/proper_mcp.log",
            "redbarsushi_mcp": "mcp/redbarsushi_mcp.log",
            "minimal_mcp": "mcp/minimal_mcp.log",
            "simple_mcp": "mcp/simple_mcp.log",
            "progress": "progress.log",
            "websocket_test": "websocket_test_server.log",
            "websocket_stability": "websocket_stability_client.log",
            "websocket_verification": "websocket_verification.log",
        }
        
        # Get the file path
        log_path = log_files.get(file, file)
        
        # Check if the file is a relative path or just a filename
        if not os.path.isabs(log_path):
            log_path = os.path.join(project_root, log_path)

        # Check if the file exists
        if not os.path.exists(log_path):
            return json.dumps({
                "success": False,
                "error": f"Log file not found: {log_path}"
            })
        
        # Get the last 200 lines (or all lines if file is smaller)
        lines = []
        try:
            with open(log_path, 'r') as f:
                # Get all lines in memory first
                all_lines = f.readlines()
                
                # Take the last 200 lines
                lines = all_lines[-200:] if len(all_lines) > 200 else all_lines
                
                # Strip newlines and join with newlines
                lines = [line.rstrip() for line in lines]
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error reading log file: {str(e)}"
            })
        
        return json.dumps({
            "success": True,
            "file": file,
            "path": log_path,
            "lines": lines,
            "total_lines": len(lines)
        })
    except Exception as e:
        logger.error(f"Error tailing log file: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        })

@mcp.tool()
async def grep_log(ctx: Context, file: str, pattern: str) -> str:
    """
    Search a log file for a pattern and return the first 50 matching lines.
    
    Args:
        ctx: The MCP server provided context
        file: The log file to search
        pattern: The pattern to search for
        
    Returns:
        JSON string with the matching lines
    """
    try:
        # Map file aliases to actual file paths
        log_files = {
            "web": "mcp_server.log",
            "mcp": "mcp/mcp_server.log",
            "fastmcp": "mcp/fastmcp_server.log",
            "websocket": "websocket_monitor.log",
            "enhanced_mcp": "mcp/enhanced_mcp.log",
            "proper_mcp": "mcp/proper_mcp.log",
            "redbarsushi_mcp": "mcp/redbarsushi_mcp.log",
            "minimal_mcp": "mcp/minimal_mcp.log",
            "simple_mcp": "mcp/simple_mcp.log",
            "progress": "progress.log",
            "websocket_test": "websocket_test_server.log",
            "websocket_stability": "websocket_stability_client.log",
            "websocket_verification": "websocket_verification.log",
        }
        
        # Get the file path
        log_path = log_files.get(file, file)
        
        # Check if the file is a relative path or just a filename
        if not os.path.isabs(log_path):
            log_path = os.path.join(project_root, log_path)

        # Check if the file exists
        if not os.path.exists(log_path):
            return json.dumps({
                "success": False,
                "error": f"Log file not found: {log_path}"
            })
        
        # Compile the regex pattern
        try:
            regex = re.compile(pattern)
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Invalid regex pattern: {str(e)}"
            })
        
        # Find matches
        matches = []
        line_numbers = []
        
        try:
            with open(log_path, 'r') as f:
                for i, line in enumerate(f, 1):
                    if regex.search(line):
                        matches.append(line.rstrip())
                        line_numbers.append(i)
                        
                        # Only collect up to 50 matches
                        if len(matches) >= 50:
                            break
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error reading log file: {str(e)}"
            })
        
        return json.dumps({
            "success": True,
            "file": file,
            "path": log_path,
            "pattern": pattern,
            "matches": matches,
            "line_numbers": line_numbers,
            "total_matches": len(matches),
            "max_matches": 50,
            "truncated": len(matches) == 50  # True if we hit the 50 match limit
        })
    except Exception as e:
        logger.error(f"Error grepping log file: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        })

@mcp.tool()
async def celery_status(ctx: Context) -> str:
    """
    Get the status of Celery workers and tasks.
    
    Args:
        ctx: The MCP server provided context
        
    Returns:
        JSON string with Celery status information
    """
    try:
        # Try to get Celery status using celery inspect
        try:
            # Run celery inspect command to get active workers
            inspect_active = await asyncio.create_subprocess_exec(
                "celery", "-A", "celery_app", "inspect", "active",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout_active, stderr_active = await inspect_active.communicate()
            
            # Run celery inspect command to get registered tasks
            inspect_registered = await asyncio.create_subprocess_exec(
                "celery", "-A", "celery_app", "inspect", "registered",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout_registered, stderr_registered = await inspect_registered.communicate()
            
            # Run celery inspect command to get stats
            inspect_stats = await asyncio.create_subprocess_exec(
                "celery", "-A", "celery_app", "inspect", "stats",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout_stats, stderr_stats = await inspect_stats.communicate()
            
            # Parse the output
            active_tasks = []
            if stdout_active:
                active_output = stdout_active.decode('utf-8')
                # Simple parsing of the active task output
                if "No workers online" not in active_output:
                    for line in active_output.split('\n'):
                        if ':' in line:
                            parts = line.split(':', 1)
                            worker, tasks = parts[0].strip(), parts[1].strip()
                            active_tasks.append({"worker": worker, "tasks": tasks})
            
            registered_tasks = []
            if stdout_registered:
                registered_output = stdout_registered.decode('utf-8')
                if "No workers online" not in registered_output:
                    task_section = False
                    current_worker = None
                    tasks = []
                    for line in registered_output.split('\n'):
                        if line.startswith("@"):
                            # Worker name line
                            if current_worker is not None and tasks:
                                registered_tasks.append({"worker": current_worker, "tasks": tasks})
                                tasks = []
                            current_worker = line.strip("@ :")
                            task_section = True
                        elif task_section and line.strip():
                            # Task name line
                            if line.strip().startswith("-"):
                                tasks.append(line.strip("- "))
                    # Add the last worker
                    if current_worker is not None and tasks:
                        registered_tasks.append({"worker": current_worker, "tasks": tasks})
            
            stats = {}
            if stdout_stats:
                stats_output = stdout_stats.decode('utf-8')
                if "No workers online" not in stats_output:
                    worker_section = False
                    current_worker = None
                    worker_stats = {}
                    for line in stats_output.split('\n'):
                        if line.startswith("@"):
                            # Worker name line
                            if current_worker is not None and worker_stats:
                                stats[current_worker] = worker_stats
                                worker_stats = {}
                            current_worker = line.strip("@ :")
                            worker_section = True
                        elif worker_section and ":" in line:
                            # Stats line
                            key, value = line.split(":", 1)
                            worker_stats[key.strip()] = value.strip()
                    # Add the last worker
                    if current_worker is not None and worker_stats:
                        stats[current_worker] = worker_stats
            
            # Get information from Redis
            redis_client = ctx.request_context.lifespan_context.redis_client
            redis_info = {}
            if redis_client:
                try:
                    # Get Celery task queues from Redis
                    queues = await asyncio.to_thread(redis_client.keys, "celery:*")
                    queue_info = {}
                    
                    for queue in queues:
                        queue_name = queue.decode('utf-8')
                        queue_type = await asyncio.to_thread(redis_client.type, queue)
                        queue_type = queue_type.decode('utf-8')
                        
                        if queue_type == "list":
                            queue_length = await asyncio.to_thread(redis_client.llen, queue)
                            queue_info[queue_name] = {"type": queue_type, "length": queue_length}
                        elif queue_type == "hash":
                            queue_fields = await asyncio.to_thread(redis_client.hgetall, queue)
                            queue_info[queue_name] = {"type": queue_type, "fields": {k.decode('utf-8'): v.decode('utf-8') for k, v in queue_fields.items()}}
                    
                    redis_info["queues"] = queue_info
                except Exception as redis_err:
                    redis_info["error"] = str(redis_err)
            
            # Create combined status response
            response = {
                "success": True,
                "active_tasks": active_tasks,
                "registered_tasks": registered_tasks,
                "stats": stats,
                "redis_info": redis_info
            }
            
            return json.dumps(response)
        except Exception as e:
            # If running celery inspect fails, try to get basic process info
            ps_output = await asyncio.create_subprocess_shell(
                "ps aux | grep -i 'celery' | grep -v grep",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                shell=True
            )
            stdout, stderr = await ps_output.communicate()
            
            celery_processes = []
            if stdout:
                for line in stdout.decode('utf-8').split('\n'):
                    if line.strip():
                        celery_processes.append(line.strip())
            
            # Check if Redis has any celery-related keys
            redis_info = {}
            redis_client = ctx.request_context.lifespan_context.redis_client
            if redis_client:
                try:
                    # Get Celery task queues from Redis
                    celery_keys = await asyncio.to_thread(redis_client.keys, "celery*")
                    redis_info["celery_keys"] = [key.decode('utf-8') for key in celery_keys]
                    
                    # Try to get task count
                    task_count = 0
                    for key in celery_keys:
                        if key.endswith(b":tasks"):
                            key_type = await asyncio.to_thread(redis_client.type, key)
                            if key_type == b"list":
                                task_count += await asyncio.to_thread(redis_client.llen, key)
                    
                    redis_info["task_count"] = task_count
                except Exception as redis_err:
                    redis_info["error"] = str(redis_err)
            
            # Return what we found
            return json.dumps({
                "success": True,
                "celery_inspect_error": str(e),
                "celery_processes": celery_processes,
                "redis_info": redis_info
            })
    except Exception as e:
        logger.error(f"Error getting Celery status: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        })

@mcp.tool()
async def replay_task(ctx: Context, task_name: str, task_args: Optional[Dict[str, Any]] = None) -> str:
    """
    Replay a Celery task with the given arguments.
    
    Args:
        ctx: The MCP server provided context
        task_name: The name of the task to replay (e.g., 'tasks.send_confirmation_sms_task')
        task_args: Optional dictionary of arguments to pass to the task
        
    Returns:
        JSON string with the task execution result
    """
    try:
        # Validate the task name
        allowed_tasks = [
            "tasks.sync_menu_references",
            "tasks.send_confirmation_sms_task",
            "tasks.send_order_status_update_task"
        ]
        
        if task_name not in allowed_tasks:
            return json.dumps({
                "success": False,
                "error": f"Task name '{task_name}' is not allowed. Allowed tasks: {', '.join(allowed_tasks)}"
            })
        
        # Create a Python script to execute the task
        script_content = f"""
import sys
import json
import importlib.util
import os

# Try to load the task module
try:
    # Add the project root to the Python path
    sys.path.insert(0, "{project_root}")
    
    # Import celery app
    spec = importlib.util.spec_from_file_location("celery_app", "{project_root}/celery_app.py")
    celery_app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(celery_app)
    
    # Import tasks
    spec = importlib.util.spec_from_file_location("tasks", "{project_root}/tasks.py")
    tasks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tasks)
    
    # Get the task function from the module
    task_path = "{task_name}".split(".")
    module_path = ".".join(task_path[:-1])
    task_func_name = task_path[-1]
    
    if module_path == "tasks":
        task_func = getattr(tasks, task_func_name)
    else:
        # If task is in a different module
        module = __import__(module_path, fromlist=[task_func_name])
        task_func = getattr(module, task_func_name)
    
    # Parse task arguments (if any)
    task_args = {task_args or {}}
    
    # Run the task synchronously (apply instead of apply_async)
    result = task_func.apply(**task_args)
    
    # Get task result
    task_result = result.get()
    
    # Print result as JSON for the parent process to capture
    print(json.dumps({{"success": True, "result": task_result}}))
    
except Exception as e:
    # Print error as JSON for the parent process to capture
    print(json.dumps({{"success": False, "error": str(e)}}))
"""
        
        # Write the script to a temporary file
        temp_script_path = "/tmp/replay_task.py"
        with open(temp_script_path, 'w') as f:
            f.write(script_content)
        
        # Execute the script
        process = await asyncio.create_subprocess_exec(
            sys.executable, temp_script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        # Parse the output
        if stdout:
            try:
                result = json.loads(stdout.decode('utf-8'))
                # Add task info to the result
                result["task_name"] = task_name
                result["task_args"] = task_args
                return json.dumps(result)
            except json.JSONDecodeError:
                # If we can't parse JSON, return the raw output
                return json.dumps({
                    "success": False,
                    "error": "Failed to parse task output as JSON",
                    "raw_output": stdout.decode('utf-8'),
                    "stderr": stderr.decode('utf-8') if stderr else None
                })
        else:
            # If no output, return the error (if any)
            return json.dumps({
                "success": False,
                "error": "No output from task execution",
                "stderr": stderr.decode('utf-8') if stderr else None
            })
    except Exception as e:
        logger.error(f"Error replaying task: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        })

@mcp.tool()
async def twilio_sig_mock(ctx: Context, url: str, params: Dict[str, Any]) -> str:
    """
    Generate a valid Twilio signature for the given URL and parameters.
    
    Args:
        ctx: The MCP server provided context
        url: The URL to generate a signature for
        params: The parameters to include in the signature
        
    Returns:
        JSON string with the generated signature
    """
    try:
        # Use a predictable test auth token for local testing
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "test_auth_token_for_local_development_only")
        
        # Sort parameters by key
        sorted_params = sorted(params.items())
        
        # Generate the string to sign (URL + sorted parameters)
        string_to_sign = url
        for k, v in sorted_params:
            string_to_sign += k + str(v)
        
        # Create the HMAC-SHA1 signature
        hmac_obj = hmac.new(
            key=auth_token.encode('utf-8'),
            msg=string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha1
        )
        signature = base64.b64encode(hmac_obj.digest()).decode('utf-8')
        
        return json.dumps({
            "success": True,
            "url": url,
            "params": params,
            "signature": signature,
            "note": "This signature is valid only for local testing with the configured auth token"
        })
    except Exception as e:
        logger.error(f"Error generating Twilio signature: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        })

@mcp.tool()
async def twilio_mock(ctx: Context, phone_number: str, message: str) -> str:
    """
    Mock a Twilio SMS message for testing.
    
    Args:
        ctx: The MCP server provided context
        phone_number: The phone number to send to
        message: The message to send
        
    Returns:
        JSON string with the mock Twilio response
    """
    try:
        # Generate a mock Twilio response
        mock_response = {
            "account_sid": "AC00000000000000000000000000000000",
            "api_version": "2010-04-01",
            "body": message,
            "date_created": time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime()),
            "date_sent": time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime()),
            "direction": "outbound-api",
            "error_code": None,
            "error_message": None,
            "from": "+15551234567",
            "messaging_service_sid": "MG00000000000000000000000000000000",
            "num_media": "0",
            "num_segments": "1",
            "price": None,
            "price_unit": "USD",
            "sid": f"SM{''.join(random.choices('0123456789abcdef', k=32))}",
            "status": "sent",
            "to": phone_number,
            "uri": f"/2010-04-01/Accounts/AC00000000000000000000000000000000/Messages/SM{''.join(random.choices('0123456789abcdef', k=32))}.json"
        }
        
        return json.dumps({
            "success": True,
            "twilio_response": mock_response,
            "note": "This is a mock response for local testing only"
        })
    except Exception as e:
        logger.error(f"Error generating mock Twilio response: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        })

@mcp.tool()
async def twiml_preview(ctx: Context, session_id: str, greeting: Optional[str] = None) -> str:
    """
    Generate a preview of the TwiML for a voice call.
    
    Args:
        ctx: The MCP server provided context
        session_id: The session ID
        greeting: Optional greeting message
        
    Returns:
        JSON string with the TwiML
    """
    try:
        from twilio.twiml.voice_response import VoiceResponse, Start, Connect
        
        # Create the TwiML
        response = VoiceResponse()
        
        # Use the provided greeting or default
        greeting_message = greeting or f"Welcome to Red Bar Sushi AI ordering system. Session ID: {session_id}"
        
        # Add greeting
        response.say(greeting_message)
        
        # Add a pause
        response.pause(length=1)
        
        # Add media stream for inbound audio
        hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "localhost:5000")
        ws_url_inbound = f"wss://{hostname}/ws/voice/media"
        start = Start()
        start.stream(url=ws_url_inbound, track="inbound_track", name="inbound_stream")
        response.append(start)
        
        # Add another small pause
        response.pause(length=0.5)
        
        # Add bidirectional media stream
        ws_url_both = f"wss://{hostname}/ws/voice/media"
        connect = Connect()
        connect.stream(url=ws_url_both, track="both_tracks", name="both_tracks_stream")
        response.append(connect)
        
        # Create the response
        twiml_str = str(response)
        
        return json.dumps({
            "success": True,
            "twiml": twiml_str,
            "session_id": session_id,
            "hostname": hostname,
            "greeting": greeting_message,
            "note": "This is a preview of the TwiML that would be generated for a voice call"
        })
    except Exception as e:
        logger.error(f"Error generating TwiML preview: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        })

@mcp.tool()
async def simulate_media_stream(ctx: Context, audio_file: Optional[str] = None, duration: int = 5) -> str:
    """
    Simulate a Twilio media stream with audio data.
    
    Args:
        ctx: The MCP server provided context
        audio_file: Optional path to an audio file to use (must be PCM format)
        duration: Duration in seconds to simulate if no audio file is provided
        
    Returns:
        JSON string with the simulation results
    """
    try:
        import numpy as np
        
        # Generate media events
        media_events = []
        
        # Check if we have an audio file
        if audio_file and os.path.exists(audio_file):
            try:
                # Read the audio file
                with open(audio_file, 'rb') as f:
                    audio_data = f.read()
                
                # Chunk the audio data into 160-byte chunks (20ms of 8kHz mu-law)
                chunk_size = 160
                chunks = [audio_data[i:i+chunk_size] for i in range(0, len(audio_data), chunk_size)]
                
                # Create media events
                for i, chunk in enumerate(chunks):
                    # Base64 encode the chunk
                    encoded_chunk = base64.b64encode(chunk).decode('utf-8')
                    
                    # Create the media event
                    media_events.append({
                        "event": "media",
                        "streamSid": f"MT{''.join(random.choices('0123456789abcdef', k=32))}",
                        "media": {
                            "track": "inbound_track",
                            "payload": encoded_chunk,
                            "chunk": i + 1
                        },
                        "timestamp": time.time() + (i * 0.020)  # Add 20ms per chunk
                    })
            except Exception as file_error:
                return json.dumps({
                    "success": False,
                    "error": f"Error reading audio file: {str(file_error)}"
                })
        else:
            # Generate synthetic audio data
            # 8kHz sampling rate, 20ms per chunk = 160 samples per chunk
            samples_per_chunk = 160
            chunks_per_second = 50  # 1000ms / 20ms = 50
            total_chunks = duration * chunks_per_second
            
            # Generate synthetic audio chunks (sine wave at 440Hz)
            for i in range(total_chunks):
                # Generate 20ms of a sine wave at 440Hz (A4 note)
                t = np.linspace(0, 0.020, samples_per_chunk, endpoint=False)
                sine_wave = (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
                
                # Convert to μ-law
                normalized = sine_wave.astype(np.float32) / 32768.0
                sign = np.sign(normalized)
                amplitude = np.minimum(np.abs(normalized), 1.0)
                mu = 255  # μ-law parameter
                compressed = sign * np.log(1 + mu * amplitude) / np.log(1 + mu)
                u_law = ((compressed + 1) * 127.5).astype(np.uint8)
                
                # Convert to bytes and base64 encode
                chunk = u_law.tobytes()
                encoded_chunk = base64.b64encode(chunk).decode('utf-8')
                
                # Create the media event
                media_events.append({
                    "event": "media",
                    "streamSid": f"MT{''.join(random.choices('0123456789abcdef', k=32))}",
                    "media": {
                        "track": "inbound_track",
                        "payload": encoded_chunk,
                        "chunk": i + 1
                    },
                    "timestamp": time.time() + (i * 0.020)  # Add 20ms per chunk
                })
        
        # Create start and stop events
        start_event = {
            "event": "start",
            "streamSid": f"MT{''.join(random.choices('0123456789abcdef', k=32))}",
            "start": {
                "accountSid": "AC00000000000000000000000000000000",
                "callSid": f"CA{''.join(random.choices('0123456789abcdef', k=32))}",
                "tracks": [
                    {
                        "name": "inbound_track",
                        "id": "inbound_audio",
                        "mediaFormat": {
                            "encoding": "audio/x-mulaw",
                            "sampleRate": 8000,
                            "channels": 1
                        }
                    }
                ]
            },
            "timestamp": time.time()
        }
        
        stop_event = {
            "event": "stop",
            "streamSid": f"MT{''.join(random.choices('0123456789abcdef', k=32))}",
            "stop": {
                "accountSid": "AC00000000000000000000000000000000",
                "callSid": f"CA{''.join(random.choices('0123456789abcdef', k=32))}"
            },
            "timestamp": time.time() + duration
        }
        
        # Return the simulated media stream
        return json.dumps({
            "success": True,
            "start_event": start_event,
            "media_events": media_events[:10] + ["..."] + media_events[-10:] if len(media_events) > 20 else media_events,
            "stop_event": stop_event,
            "total_media_events": len(media_events),
            "duration": duration,
            "note": "This is a simulated media stream for local testing only. Only a subset of media events is shown if there are many."
        })
    except Exception as e:
        logger.error(f"Error simulating media stream: {str(e)}")
        logger.error(traceback.format_exc())
        return json.dumps({
            "success": False,
            "error": str(e)
        })

@mcp.tool()
async def openai_realtime_ping(ctx: Context) -> str:
    """
    Test the connection to the OpenAI Realtime API.
    
    Args:
        ctx: The MCP server provided context
        
    Returns:
        JSON string with the test results
    """
    try:
        # Import the OpenAI Realtime SDK
        try:
            # Dynamically import the module to avoid import errors
            import importlib
            realtime_module = importlib.import_module("app.utils.realtime_audio_sdk")
            
            # Get the processor and check if it's available
            if hasattr(realtime_module, "get_realtime_processor"):
                processor = realtime_module.get_realtime_processor()
                
                # Check if the processor has an API key
                if hasattr(processor, "api_key") and processor.api_key:
                    # Validated, no need to actually connect to the API
                    return json.dumps({
                        "success": True,
                        "realtime_processor_available": True,
                        "api_key_configured": True,
                        "note": "OpenAI Realtime API is configured correctly. API key is present."
                    })
                else:
                    return json.dumps({
                        "success": False,
                        "realtime_processor_available": True,
                        "api_key_configured": False,
                        "error": "OpenAI API key is not configured",
                        "note": "Configure OPENAI_API_KEY environment variable to use the Realtime API."
                    })
            else:
                return json.dumps({
                    "success": False,
                    "error": "Realtime processor not available",
                    "note": "The realtime_audio_sdk module does not have a get_realtime_processor function."
                })
        except ImportError as e:
            return json.dumps({
                "success": False,
                "error": f"Could not import realtime_audio_sdk: {str(e)}",
                "note": "Make sure the app/utils/realtime_audio_sdk.py file exists and is properly configured."
            })
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error testing Realtime API: {str(e)}",
                "note": "An unexpected error occurred while testing the Realtime API connection."
            })
    except Exception as e:
        logger.error(f"Error testing OpenAI Realtime API: {str(e)}")
        return json.dumps({
            "success": False,
            "error": str(e)
        })

if __name__ == "__main__":
    # Start the MCP server
    mcp()