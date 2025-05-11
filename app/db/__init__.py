"""
Database package for RedBarSushiAI.

This package contains database models, sessions, and CRUD operations.
"""

# Re-export commonly used items for easier imports
from app.db_async import Base, get_db, async_engine, AsyncSessionFactory

# Re-export CRUD modules for convenience
from app.db.crud_menu_async import (
    # Categories
    get_categories, count_categories, get_category, 
    create_category, update_category, delete_category,
    
    # Items
    get_items, count_items, get_item, get_items_by_category,
    create_item, update_item, delete_item, snooze_item, unsnooze_item,
    
    # Modifiers
    get_modifiers, count_modifiers, get_modifier,
    create_modifier, update_modifier, delete_modifier, 
    snooze_modifier, unsnooze_modifier,
    
    # Modifier Groups
    get_modifier_groups, count_modifier_groups, get_modifier_group,
    create_modifier_group, update_modifier_group, delete_modifier_group,
    
    # Association Operations
    add_modifier_to_group, remove_modifier_from_group,
    add_modifier_group_to_item, remove_modifier_group_from_item,
    
    # Variants
    get_variants, count_variants, get_variant, get_variant_by_phrase,
    create_variant, update_variant, delete_variant
)

__all__ = [
    # Database session
    "Base", "get_db", "async_engine", "AsyncSessionFactory",
    
    # Categories
    "get_categories", "count_categories", "get_category", 
    "create_category", "update_category", "delete_category",
    
    # Items
    "get_items", "count_items", "get_item", "get_items_by_category",
    "create_item", "update_item", "delete_item", "snooze_item", "unsnooze_item",
    
    # Modifiers
    "get_modifiers", "count_modifiers", "get_modifier",
    "create_modifier", "update_modifier", "delete_modifier", 
    "snooze_modifier", "unsnooze_modifier",
    
    # Modifier Groups
    "get_modifier_groups", "count_modifier_groups", "get_modifier_group",
    "create_modifier_group", "update_modifier_group", "delete_modifier_group",
    
    # Association Operations
    "add_modifier_to_group", "remove_modifier_from_group",
    "add_modifier_group_to_item", "remove_modifier_group_from_item",
    
    # Variants
    "get_variants", "count_variants", "get_variant", "get_variant_by_phrase",
    "create_variant", "update_variant", "delete_variant"
]