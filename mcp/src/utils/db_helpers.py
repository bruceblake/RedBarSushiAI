"""
Database helper functions for the MCP server.

This module provides utility functions for database operations
used by the RedBarSushi MCP server tools.
"""

import json
from typing import Any, Dict, List, Optional
from sqlalchemy import text

def execute_read_query(db_session, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Execute a read-only SQL query.
    
    Args:
        db_session: SQLAlchemy session
        query: SQL query to execute
        params: Optional parameters for the query
    
    Returns:
        List of rows as dictionaries
    """
    if db_session is None:
        return [{"error": "Database session not available"}]
    
    # Ensure the query is read-only (starts with SELECT)
    if not query.strip().upper().startswith("SELECT"):
        return [{"error": "Only SELECT queries are allowed"}]
    
    # Execute the query
    try:
        result = db_session.execute(text(query), params or {})
        return [dict(row._mapping) for row in result]
    except Exception as e:
        return [{"error": str(e)}]

def get_menu_item_by_plu(db_session, plu: str) -> Dict[str, Any]:
    """
    Get detailed information about a menu item by PLU.
    
    Args:
        db_session: SQLAlchemy session
        plu: PLU of the menu item
    
    Returns:
        Dictionary with menu item details
    """
    if db_session is None:
        return {"error": "Database session not available"}
    
    try:
        # Get the basic menu item info
        item_query = text("""
            SELECT * FROM menu_items WHERE plu = :plu
        """)
        item_result = db_session.execute(item_query, {"plu": plu})
        item = item_result.fetchone()
        
        if not item:
            return {"error": f"No menu item found with PLU: {plu}"}
        
        # Convert to dictionary
        item_dict = dict(item._mapping)
        
        # Get the category
        if item_dict.get("category_id"):
            category_query = text("""
                SELECT * FROM menu_categories WHERE id = :id
            """)
            category_result = db_session.execute(category_query, {"id": item_dict["category_id"]})
            category = category_result.fetchone()
            if category:
                item_dict["category"] = dict(category._mapping)
        
        # Get the modifier groups
        modifier_groups_query = text("""
            SELECT mg.* FROM menu_modifier_groups mg
            JOIN item_modifier_groups img ON mg.id = img.modifier_group_id
            WHERE img.menu_item_id = :item_id
        """)
        modifier_groups_result = db_session.execute(modifier_groups_query, {"item_id": item_dict["id"]})
        modifier_groups = [dict(row._mapping) for row in modifier_groups_result]
        
        # Get the modifiers for each group
        for group in modifier_groups:
            modifiers_query = text("""
                SELECT * FROM menu_modifiers
                WHERE modifier_group_id = :group_id
            """)
            modifiers_result = db_session.execute(modifiers_query, {"group_id": group["id"]})
            group["modifiers"] = [dict(row._mapping) for row in modifiers_result]
        
        item_dict["modifier_groups"] = modifier_groups
        
        # Get any name variants
        variants_query = text("""
            SELECT * FROM menu_name_variants
            WHERE target_plu = :plu
        """)
        variants_result = db_session.execute(variants_query, {"plu": plu})
        item_dict["name_variants"] = [dict(row._mapping) for row in variants_result]
        
        return item_dict
    except Exception as e:
        return {"error": str(e)}

def get_order_summary(db_session, order_id: int) -> Dict[str, Any]:
    """
    Get a summary of an order with all its items and modifiers.
    
    Args:
        db_session: SQLAlchemy session
        order_id: ID of the order
        
    Returns:
        Dictionary with order details
    """
    if db_session is None:
        return {"error": "Database session not available"}
    
    try:
        # Get the order
        order_query = text("""
            SELECT * FROM orders WHERE id = :id
        """)
        order_result = db_session.execute(order_query, {"id": order_id})
        order = order_result.fetchone()
        
        if not order:
            return {"error": f"No order found with ID: {order_id}"}
        
        # Convert to dictionary
        order_dict = dict(order._mapping)
        
        # Get the order items
        items_query = text("""
            SELECT * FROM order_items WHERE order_id = :order_id
        """)
        items_result = db_session.execute(items_query, {"order_id": order_id})
        items = [dict(row._mapping) for row in items_result]
        
        # Get the modifiers for each item
        for item in items:
            modifiers_query = text("""
                SELECT * FROM order_item_modifiers
                WHERE order_item_id = :item_id
            """)
            modifiers_result = db_session.execute(modifiers_query, {"item_id": item["id"]})
            item["modifiers"] = [dict(row._mapping) for row in modifiers_result]
        
        order_dict["items"] = items
        
        # Calculate the subtotal from items
        subtotal = sum(item["price"] * item["quantity"] for item in items)
        
        # Calculate the modifiers total
        modifiers_total = sum(
            modifier["price_change"] * modifier["quantity"]
            for item in items
            for modifier in item["modifiers"]
        )
        
        # Add some helper calculations
        order_dict["price_breakdown"] = {
            "subtotal": subtotal,
            "modifiers_total": modifiers_total,
            "total": subtotal + modifiers_total
        }
        
        return order_dict
    except Exception as e:
        return {"error": str(e)}

def get_slow_queries(db_session, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get the slowest queries from pg_stat_statements.
    
    Args:
        db_session: SQLAlchemy session
        limit: Maximum number of queries to return
        
    Returns:
        List of slow queries with statistics
    """
    if db_session is None:
        return [{"error": "Database session not available"}]
    
    try:
        # Check if pg_stat_statements extension is available
        check_query = text("""
            SELECT COUNT(*) FROM pg_extension WHERE extname = 'pg_stat_statements'
        """)
        check_result = db_session.execute(check_query)
        if check_result.scalar() == 0:
            return [{"error": "pg_stat_statements extension is not available"}]
        
        # Get the slow queries
        query = text(f"""
            SELECT query, calls, total_time, mean_time, rows
            FROM pg_stat_statements
            ORDER BY mean_time DESC
            LIMIT {min(limit, 50)}
        """)
        
        result = db_session.execute(query)
        return [dict(row._mapping) for row in result]
    except Exception as e:
        return [{"error": str(e)}]