# app/utils/helpers_async.py
import logging

# import time # Removed as unused
import asyncio

# log_info_async function removed as unused


async def commit_with_retry_async(session, max_retries=3):
    """
    Commit a database session with retries on failure (async version).

    Args:
        session: SQLAlchemy AsyncSession
        max_retries: Maximum number of retry attempts

    Returns:
        bool: True if commit succeeded, False otherwise
    """
    for attempt in range(max_retries):
        try:
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            logging.error(f"Commit attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(1)  # Wait before retrying
    return False


# get_common_prices_async function removed as unused
