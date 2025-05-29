#!/usr/bin/env python3
"""
Monitor ConversationRelay, FSM states, and menu updates in real-time.
This script helps debug issues with state transitions and menu recognition.
"""

import asyncio
import sys
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db_async import get_db
from sqlalchemy import select, func
from app.models.menu_async import MenuItem, MenuCategory
from app.redis_async import get_redis_client

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class ConversationRelayMonitor:
    def __init__(self):
        self.redis_client = None
        self.db = None
        
    async def initialize(self):
        """Initialize connections."""
        self.redis_client = await get_redis_client()
        
    async def check_menu_database(self):
        """Check menu items in the database."""
        logger.info("\n=== DATABASE MENU CHECK ===")
        
        async for db in get_db():
            # Count categories
            category_count = await db.scalar(
                select(func.count()).select_from(MenuCategory)
            )
            logger.info(f"Total categories: {category_count}")
            
            # Count items
            item_count = await db.scalar(
                select(func.count()).select_from(MenuItem)
            )
            logger.info(f"Total menu items: {item_count}")
            
            # Check available items
            available_count = await db.scalar(
                select(func.count()).select_from(MenuItem).where(MenuItem.is_available == True)
            )
            logger.info(f"Available items: {available_count}")
            
            # Sample some items
            result = await db.execute(
                select(MenuItem).limit(5)
            )
            items = result.scalars().all()
            
            logger.info("\nSample items:")
            for item in items:
                logger.info(f"  - {item.name} (PLU: {item.plu}, Available: {item.is_available})")
            
            break
    
    async def check_menu_cache(self):
        """Check menu cache in Redis."""
        logger.info("\n=== REDIS MENU CACHE CHECK ===")
        
        if not self.redis_client:
            logger.warning("Redis client not available")
            return
            
        try:
            # Check for menu cache keys
            menu_keys = await self.redis_client.keys("menu:*")
            logger.info(f"Found {len(menu_keys)} menu cache keys")
            
            for key in menu_keys[:5]:  # Show first 5
                ttl = await self.redis_client.ttl(key)
                logger.info(f"  - {key.decode()}: TTL={ttl}s")
                
        except Exception as e:
            logger.error(f"Error checking Redis cache: {e}")
    
    async def check_active_calls(self):
        """Check for active ConversationRelay sessions."""
        logger.info("\n=== ACTIVE CALLS CHECK ===")
        
        if not self.redis_client:
            logger.warning("Redis client not available")
            return
            
        try:
            # Check for conversation keys
            conv_keys = await self.redis_client.keys("conversation:*")
            logger.info(f"Found {len(conv_keys)} conversation keys")
            
            # Check for FSM keys
            fsm_keys = await self.redis_client.keys("fsm:*")
            logger.info(f"Found {len(fsm_keys)} FSM state keys")
            
            # Show FSM states
            for key in fsm_keys[:5]:  # Show first 5
                try:
                    state_data = await self.redis_client.get(key)
                    if state_data:
                        logger.info(f"  - {key.decode()}: {state_data.decode()[:50]}...")
                except Exception as e:
                    logger.error(f"Error reading {key}: {e}")
                    
        except Exception as e:
            logger.error(f"Error checking active calls: {e}")
    
    async def monitor_logs(self, duration: int = 30):
        """Monitor logs for specific patterns."""
        logger.info(f"\n=== MONITORING PATTERNS FOR {duration}s ===")
        logger.info("Patterns to watch:")
        logger.info("  - FSM State transitions")
        logger.info("  - Menu lookup attempts")
        logger.info("  - Cache operations")
        logger.info("  - ConversationRelay events")
        logger.info("\nUse docker-compose logs -f app | grep -E 'FSM State|menu|cache|ConversationRelay'")
    
    async def run_all_checks(self):
        """Run all monitoring checks."""
        await self.initialize()
        
        # Database checks
        await self.check_menu_database()
        
        # Cache checks
        await self.check_menu_cache()
        
        # Active call checks
        await self.check_active_calls()
        
        # Log monitoring reminder
        await self.monitor_logs()
        
        # Cleanup
        if self.redis_client:
            await self.redis_client.close()

async def main():
    """Run the monitor."""
    monitor = ConversationRelayMonitor()
    
    logger.info("ConversationRelay & Menu Monitor")
    logger.info("=" * 50)
    
    await monitor.run_all_checks()
    
    logger.info("\n" + "=" * 50)
    logger.info("TROUBLESHOOTING TIPS:")
    logger.info("=" * 50)
    logger.info("1. If menu items show in DB but not recognized:")
    logger.info("   - Check if Redis cache was cleared after update")
    logger.info("   - Force refresh: docker-compose exec app python -c 'from app.utils.menu_matcher_cache_async import clear_cached_menu_matcher; import asyncio; asyncio.run(clear_cached_menu_matcher())'")
    logger.info("\n2. If FSM stays in MAIN_MENU:")
    logger.info("   - Check if 'order' keywords are detected")
    logger.info("   - Verify cart agent is initialized")
    logger.info("\n3. If no response from agents:")
    logger.info("   - Check OPENAI_API_KEY is valid")
    logger.info("   - Verify agent initialization in logs")

if __name__ == "__main__":
    asyncio.run(main())