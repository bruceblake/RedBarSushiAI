"""
CRUD operations for Location model.
"""

import logging
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.models.location_async import Location

logger = logging.getLogger(__name__)


async def get_location(db: AsyncSession, location_id: str) -> Optional[Location]:
    """Get a location by ID."""
    try:
        stmt = select(Location).where(Location.id == location_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Error getting location {location_id}: {e}")
        return None


async def get_location_by_channel_link_id(db: AsyncSession, channel_link_id: str) -> Optional[Location]:
    """Get a location by Deliverect channel link ID."""
    try:
        stmt = select(Location).where(Location.deliverect_channel_link_id == channel_link_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Error getting location by channel link {channel_link_id}: {e}")
        return None


async def create_or_update_location(
    db: AsyncSession,
    location_id: str,
    channel_link_id: str,
    channel_link_name: str,
    status: str = "registered"
) -> Optional[Location]:
    """Create or update a location record."""
    try:
        # Check if location exists
        existing = await get_location(db, location_id)
        
        if existing:
            # Update existing location
            stmt = (
                update(Location)
                .where(Location.id == location_id)
                .values(
                    deliverect_channel_link_id=channel_link_id,
                    deliverect_channel_name=channel_link_name,
                    status=status
                )
            )
            await db.execute(stmt)
            await db.commit()
            return await get_location(db, location_id)
        else:
            # Create new location
            location = Location(
                id=location_id,
                name=channel_link_name,
                status=status,
                deliverect_channel_link_id=channel_link_id,
                deliverect_channel_name=channel_link_name
            )
            db.add(location)
            await db.commit()
            await db.refresh(location)
            return location
            
    except Exception as e:
        logger.error(f"Error creating/updating location: {e}")
        await db.rollback()
        return None


async def update_location_status(
    db: AsyncSession,
    channel_link_id: str,
    status: str
) -> bool:
    """Update location status."""
    try:
        stmt = (
            update(Location)
            .where(Location.deliverect_channel_link_id == channel_link_id)
            .values(status=status)
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0
    except Exception as e:
        logger.error(f"Error updating location status: {e}")
        await db.rollback()
        return False


async def update_location_busy_status(
    db: AsyncSession,
    channel_link_id: str,
    is_busy: bool
) -> bool:
    """Update location busy status."""
    try:
        stmt = (
            update(Location)
            .where(Location.deliverect_channel_link_id == channel_link_id)
            .values(is_busy=is_busy)
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0
    except Exception as e:
        logger.error(f"Error updating location busy status: {e}")
        await db.rollback()
        return False


async def update_location_prep_time(
    db: AsyncSession,
    channel_link_id: str,
    prep_time: int
) -> bool:
    """Update location preparation time."""
    try:
        stmt = (
            update(Location)
            .where(Location.deliverect_channel_link_id == channel_link_id)
            .values(prep_time_minutes=prep_time)
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0
    except Exception as e:
        logger.error(f"Error updating location prep time: {e}")
        await db.rollback()
        return False


async def get_all_locations(db: AsyncSession) -> List[Location]:
    """Get all locations."""
    try:
        stmt = select(Location)
        result = await db.execute(stmt)
        return list(result.scalars().all())
    except Exception as e:
        logger.error(f"Error getting all locations: {e}")
        return []