"""
Utility functions for the RedBarSushiAI MCP server.
"""
import os
import json
import logging
import redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from typing import Optional, Dict, Any, Tuple

# Set up logging
logger = logging.getLogger("redbarsushi_mcp.utils")

def get_database_connection() -> Tuple[Optional[Session], str]:
    """
    Get a database connection.
    
    Returns:
        Tuple of (database session, error message if any)
    """
    DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/redbarsushi")
    try:
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db_session = SessionLocal()
        logger.info("Database connection established")
        return db_session, ""
    except Exception as e:
        error_msg = f"Database connection error: {str(e)}"
        logger.warning(error_msg)
        return None, error_msg

def get_redis_connection() -> Tuple[Optional[redis.Redis], str]:
    """
    Get a Redis connection.
    
    Returns:
        Tuple of (Redis client, error message if any)
    """
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    try:
        redis_client = redis.from_url(REDIS_URL)
        redis_client.ping()  # Check connection
        logger.info("Redis connection established")
        return redis_client, ""
    except Exception as e:
        error_msg = f"Redis connection error: {str(e)}"
        logger.warning(error_msg)
        return None, error_msg

def get_menu_items_from_db(db_session: Session, category_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Get menu items from the database.
    
    Args:
        db_session: Database session
        category_id: Optional category ID to filter items
        
    Returns:
        Dictionary with menu items
    """
    try:
        # Build the query
        query = "SELECT id, name, description, price, plu FROM menu_items"
        params = {}
        
        if category_id is not None:
            query += " WHERE category_id = :category_id"
            params["category_id"] = category_id
        
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
        
        return {
            "success": True,
            "items": items
        }
    except Exception as e:
        logger.error(f"Error getting menu items: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def get_menu_categories_from_db(db_session: Session) -> Dict[str, Any]:
    """
    Get menu categories from the database.
    
    Args:
        db_session: Database session
        
    Returns:
        Dictionary with menu categories
    """
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
        
        return {
            "success": True,
            "categories": categories
        }
    except Exception as e:
        logger.error(f"Error getting menu categories: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def search_menu_items_in_db(db_session: Session, query: str) -> Dict[str, Any]:
    """
    Search menu items by name or description.
    
    Args:
        db_session: Database session
        query: Search query string
        
    Returns:
        Dictionary with matching menu items
    """
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
        
        return {
            "success": True,
            "items": items
        }
    except Exception as e:
        logger.error(f"Error searching menu items: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def get_cart_from_redis(redis_client: redis.Redis, session_id: str) -> Dict[str, Any]:
    """
    Get the current cart for a session from Redis.
    
    Args:
        redis_client: Redis client
        session_id: The session ID
        
    Returns:
        Dictionary with cart contents
    """
    try:
        # Get cart from Redis
        cart_json = redis_client.get(f"cart:{session_id}")
        
        if not cart_json:
            return {
                "success": True,
                "cart": {
                    "items": [],
                    "total_price": 0
                }
            }
        
        # Parse JSON
        cart = json.loads(cart_json)
        
        return {
            "success": True,
            "cart": cart
        }
    except Exception as e:
        logger.error(f"Error getting cart: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

def get_restaurant_info() -> Dict[str, Any]:
    """
    Get information about the restaurant.
    
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
        "minimum_order": "15.00",
        "delivery_fee": "3.99"
    }
    
    return {
        "success": True,
        "info": info
    }