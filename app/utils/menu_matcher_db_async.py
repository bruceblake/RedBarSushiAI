"""
Menu item matching using AI to find the best match from database - async version.
This is an updated version of menu_matcher_db.py that uses async SQLAlchemy.
"""

import os
import json
import logging
import traceback
import time
from typing import Dict, List, Any, Optional, Tuple, Union
import openai

from app.utils.menu_utils_db_async import load_menu_data
from app.utils.agent_utils import log_openai_request, log_openai_response
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AsyncMenuMatcher:
    """Menu item matching using AI to find the best match for natural language descriptions."""

    def __init__(self, db: AsyncSession, location_id: Optional[str] = None):
        """
        Initialize the menu matcher with the database session.
        
        Args:
            db: AsyncSession for database access
            location_id: Optional location ID to filter menu items
        """
        self.db = db
        self.location_id = location_id
        self.menu_data = None
        self.items = []
        self.modifiers = []
        self.modifier_groups = []
        self.variants = []
        
    async def initialize(self):
        """Load menu data from the database."""
        try:
            menu_data = await load_menu_data(self.db, self.location_id)
            self.menu_data = menu_data
            self.items = menu_data.get("items", [])
            self.modifiers = menu_data.get("modifiers", [])
            self.modifier_groups = menu_data.get("modifier_groups", [])
            self.variants = menu_data.get("variants", [])
            logger.info(f"AsyncMenuMatcher initialized with {len(self.items)} items, "
                       f"{len(self.modifiers)} modifiers, "
                       f"{len(self.modifier_groups)} modifier groups, "
                       f"{len(self.variants)} variants")
            return True
        except Exception as e:
            logger.error(f"Error initializing AsyncMenuMatcher: {e}")
            return False
            
    async def match_item(self, description: str) -> Tuple[Optional[Dict[str, Any]], float]:
        """
        Match a natural language description to a menu item.
        
        Args:
            description: Natural language description of the item
            
        Returns:
            Tuple of (best matching item or None, confidence score)
        """
        if not self.items:
            logger.warning("No menu items loaded, initializing now")
            success = await self.initialize()
            if not success or not self.items:
                logger.error("Failed to load menu items")
                return None, 0.0
                
        # Implement matching logic here
        # For now, return a placeholder implementation
        for item in self.items:
            if description.lower() in item.get("name", "").lower():
                return item, 0.9
                
        # No exact match found
        return None, 0.0
        
    async def match_modifier(self, description: str, item_plu: Optional[str] = None) -> Tuple[Optional[Dict[str, Any]], float]:
        """
        Match a natural language description to a modifier.
        
        Args:
            description: Natural language description of the modifier
            item_plu: Optional PLU of the associated item
            
        Returns:
            Tuple of (best matching modifier or None, confidence score)
        """
        if not self.modifiers:
            logger.warning("No modifiers loaded, initializing now")
            success = await self.initialize()
            if not success or not self.modifiers:
                logger.error("Failed to load modifiers")
                return None, 0.0
                
        # Implement matching logic here
        # For now, return a placeholder implementation
        for modifier in self.modifiers:
            if description.lower() in modifier.get("name", "").lower():
                return modifier, 0.9
                
        # No exact match found
        return None, 0.0