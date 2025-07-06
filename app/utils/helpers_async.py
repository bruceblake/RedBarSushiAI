"""
Async helper utilities for RedBarSushiAI.

This module provides async utility functions used across the application.
"""

import asyncio
import logging
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

async def commit_with_retry_async(
    db: AsyncSession,
    max_retries: int = 3,
    backoff_factor: float = 0.5
) -> bool:
    """
    Commit database session with retry logic.
    
    Args:
        db: The async database session
        max_retries: Maximum number of retry attempts
        backoff_factor: Backoff multiplier for retry delays
        
    Returns:
        bool: True if commit succeeded, False otherwise
    """
    for attempt in range(max_retries + 1):
        try:
            await db.commit()
            return True
        except SQLAlchemyError as e:
            logger.warning(f"Database commit failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
            
            if attempt < max_retries:
                # Rollback and wait before retry
                await db.rollback()
                await asyncio.sleep(backoff_factor * (2 ** attempt))
            else:
                # Final attempt failed - rollback and return False
                await db.rollback()
                logger.error(f"Database commit failed after {max_retries + 1} attempts")
                return False
    
    return False


async def log_info_async(message: str, **kwargs) -> None:
    """
    Async logging helper function.
    
    Args:
        message: Log message
        **kwargs: Additional logging context
    """
    logger.info(message, extra=kwargs)