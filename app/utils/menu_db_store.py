"""
Wrapper for menu_db_store that works with FastAPI.
This module provides compatibility between Flask and FastAPI versions.
"""

# Import the FastAPI version
from app.utils.menu_db_store_fastapi import menu_db_store

# Export the instance
__all__ = ["menu_db_store"]