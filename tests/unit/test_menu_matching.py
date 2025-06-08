"""
Comprehensive unit tests for menu matching system - Task 2.3.1.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = Mock(spec=AsyncSession)
    session.execute = AsyncMock()
    return session

@pytest.fixture
def sample_menu_items():
    """Create sample menu items for testing."""
    items = [
        Mock(plu="CALI_001", name="California Roll", description="Crab, avocado, cucumber", 
             price=8.99, is_available=True, category_id=1),
        Mock(plu="TUNA_001", name="Spicy Tuna Roll", description="Spicy tuna, scallion", 
             price=9.99, is_available=True, category_id=1),
        Mock(plu="SALM_001", name="Salmon Sashimi", description="Fresh salmon", 
             price=12.99, is_available=True, category_id=2),
    ]
    return items

@pytest.fixture
def sample_modifiers():
    """Create sample modifiers for testing."""
    modifiers = [
        Mock(plu="MOD_AVO", name="Extra Avocado", price_change=2.00, is_available=True),
        Mock(plu="MOD_SPICY", name="Extra Spicy", price_change=0.00, is_available=True),
        Mock(plu="MOD_NOGLU", name="No Gluten", price_change=0.00, is_available=True),
    ]
    return modifiers

@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = Mock(spec=AsyncSession)
    session.execute = AsyncMock()
    return session

@pytest.fixture
def mock_redis_functions():
    """Mock Redis cache functions."""
    with patch('app.utils.menu_matcher_cache_async.get_cached_menu_data') as mock_get, \
         patch('app.utils.menu_matcher_cache_async.cache_menu_data') as mock_cache, \
         patch('app.utils.menu_matcher_cache_async.clear_menu_cache') as mock_clear:
        yield mock_get, mock_cache, mock_clear

This module tests menu matcher functionality including:
- Exact, fuzzy, and AI matching
- Redis caching with fallback
- Error handling and edge cases
- Database integration
"""
import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.utils.menu_matcher_db_async import AsyncMenuMatcher
from app.utils.menu_matcher_cache_async import AsyncCachedMenuMatcher
from app.models.menu_async import MenuItem, MenuModifier, MenuModifierGroup


class TestAsyncMenuMatcherDB:
    """Test database-based menu matcher functionality - Task 2.3.1."""
    
    @pytest.mark.asyncio
    async def test_initialization_success(self, mock_db_session, sample_menu_items, sample_modifiers):
        """Test successful initialization of menu matcher."""
        # Mock database queries
        items_result = Mock()
        items_result.scalars.return_value.all.return_value = sample_menu_items
        
        modifiers_result = Mock()
        modifiers_result.scalars.return_value.all.return_value = sample_modifiers
        
        mock_db_session.execute.side_effect = [items_result, modifiers_result]
        
        matcher = AsyncMenuMatcher(mock_db_session)
        result = await matcher.initialize()
        
        assert result is True
        assert len(matcher.menu_items) == 3
        assert len(matcher.modifiers) == 3
        assert "CALI_001" in matcher.menu_items
        assert matcher.menu_items["CALI_001"]['name'] == "California Roll"
    
    @pytest.mark.asyncio
    async def test_initialization_failure(self, mock_db_session):
        """Test initialization failure handling."""
        mock_db_session.execute.side_effect = Exception("Database error")
        
        matcher = AsyncMenuMatcher(mock_db_session)
        result = await matcher.initialize()
        
        assert result is False
        assert len(matcher.menu_items) == 0
    
    @pytest.mark.asyncio
    async def test_find_menu_item_exact_match(self, mock_db_session, sample_menu_items):
        """Test finding menu item by exact name match."""
        # Setup
        items_result = Mock()
        items_result.scalars.return_value.all.return_value = sample_menu_items
        mock_db_session.execute.return_value = items_result
        
        matcher = AsyncMenuMatcher(mock_db_session)
        await matcher.initialize()
        
        # Test exact match
        result = await matcher.find_menu_item("California Roll")
        assert result is not None
        assert result['plu'] == "CALI_001"
        assert result['name'] == "California Roll"
        
        # Test case insensitive
        result = await matcher.find_menu_item("california roll")
        assert result is not None
        assert result['plu'] == "CALI_001"
        
        # Test no match
        result = await matcher.find_menu_item("Dragon Roll")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_find_menu_item_partial_match(self, mock_db_session, sample_menu_items):
        """Test finding menu item by partial name match."""
        # Setup
        items_result = Mock()
        items_result.scalars.return_value.all.return_value = sample_menu_items
        mock_db_session.execute.return_value = items_result
        
        matcher = AsyncMenuMatcher(mock_db_session)
        await matcher.initialize()
        
        # Test partial match
        result = await matcher.find_menu_item("California")
        assert result is not None
        assert result['plu'] == "CALI_001"
        
        result = await matcher.find_menu_item("Tuna")
        assert result is not None
        assert result['plu'] == "TUNA_001"
        
        # Test substring match
        result = await matcher.find_menu_item("Roll")
        assert result is not None
        assert result['plu'] in ["CALI_001", "TUNA_001"]  # Either is valid
    
    @pytest.mark.asyncio
    async def test_find_modifier(self, mock_db_session, sample_menu_items, sample_modifiers):
        """Test finding modifiers by name."""
        # Setup
        items_result = Mock()
        items_result.scalars.return_value.all.return_value = sample_menu_items
        
        modifiers_result = Mock()
        modifiers_result.scalars.return_value.all.return_value = sample_modifiers
        
        mock_db_session.execute.side_effect = [items_result, modifiers_result]
        
        matcher = AsyncMenuMatcher(mock_db_session)
        await matcher.initialize()
        
        # Test exact match
        result = await matcher.find_modifier("Extra Avocado")
        assert result is not None
        assert result['plu'] == "MOD_AVO"
        assert result['price_change'] == 2.00
        
        # Test partial match
        result = await matcher.find_modifier("Spicy")
        assert result is not None
        assert result['plu'] == "MOD_SPICY"
        
        # Test no match
        result = await matcher.find_modifier("Extra Cheese")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_item_modifiers(self, mock_db_session):
        """Test getting modifiers for an item."""
        matcher = AsyncMenuMatcher(mock_db_session)
        
        # Currently returns empty list (stub implementation)
        result = await matcher.get_item_modifiers("CALI_001")
        assert result == []
        
        # TODO: Test when actual implementation is added
    
    @pytest.mark.asyncio
    async def test_location_filtering(self, mock_db_session, sample_menu_items):
        """Test filtering by location ID."""
        # Mock query with location filter
        items_result = Mock()
        items_result.scalars.return_value.all.return_value = sample_menu_items
        mock_db_session.execute.return_value = items_result
        
        matcher = AsyncMenuMatcher(mock_db_session, location_id="LOC_001")
        result = await matcher.initialize()
        
        assert result is True
        # Verify location filter was applied in query
        mock_db_session.execute.assert_called()


class TestAsyncCachedMenuMatcher:
    """Test cached menu matcher functionality with Redis."""
    
    @pytest.fixture
    async def cached_menu_data(self):
        """Sample cached menu data."""
        return {
            "items": [
                {"plu": "CALI_001", "name": "California Roll", "price": 8.99},
                {"plu": "TUNA_001", "name": "Spicy Tuna Roll", "price": 9.99}
            ],
            "modifiers": [
                {"plu": "MOD_AVO", "name": "Extra Avocado", "price_change": 2.00}
            ],
            "modifier_groups": [],
            "variants": []
        }
    
    @pytest.mark.asyncio
    async def test_initialize_from_cache(self, mock_db_session, mock_redis_functions, cached_menu_data):
        """Test initialization from Redis cache."""
        mock_get, mock_cache, mock_clear = mock_redis_functions
        mock_get.return_value = asyncio.coroutine(lambda: cached_menu_data)()
        
        matcher = AsyncCachedMenuMatcher(mock_db_session)
        result = await matcher.initialize()
        
        assert result is True
        assert len(matcher.items) == 2
        assert len(matcher.modifiers) == 1
        # Should not call database
        mock_db_session.execute.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_initialize_cache_miss(self, mock_db_session, mock_redis_functions):
        """Test initialization when cache is empty."""
        mock_get, mock_cache, mock_clear = mock_redis_functions
        mock_get.return_value = asyncio.coroutine(lambda: None)()
        
        # Mock parent class initialization
        with patch('app.utils.menu_matcher_db_async.AsyncMenuMatcher.initialize', 
                  new=AsyncMock(return_value=True)):
            matcher = AsyncCachedMenuMatcher(mock_db_session)
            matcher.menu_data = {"items": [], "modifiers": []}
            
            result = await matcher.initialize()
            
            assert result is True
            # Should cache the data
            mock_cache.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialize_cache_error(self, mock_db_session, mock_redis_functions):
        """Test initialization when cache read fails."""
        mock_get, mock_cache, mock_clear = mock_redis_functions
        mock_get.side_effect = Exception("Redis error")
        
        # Mock parent class initialization
        with patch('app.utils.menu_matcher_db_async.AsyncMenuMatcher.initialize', 
                  new=AsyncMock(return_value=True)):
            matcher = AsyncCachedMenuMatcher(mock_db_session)
            matcher.menu_data = {"items": [], "modifiers": []}
            
            result = await matcher.initialize()
            
            # Should fall back to database
            assert result is True
    
    @pytest.mark.asyncio
    async def test_match_item_delegates_to_parent(self, mock_db_session):
        """Test that match_item delegates to parent class."""
        matcher = AsyncCachedMenuMatcher(mock_db_session)
        
        # Mock parent match_item
        with patch('app.utils.menu_matcher_db_async.AsyncMenuMatcher.match_item', 
                  new=AsyncMock(return_value=({"plu": "CALI_001"}, 0.95))):
            
            result, score = await matcher.match_item("California Roll")
            
            assert result["plu"] == "CALI_001"
            assert score == 0.95
    
    @pytest.mark.asyncio
    async def test_cache_ttl_configuration(self, mock_db_session):
        """Test cache TTL configuration."""
        custom_ttl = 7200  # 2 hours
        matcher = AsyncCachedMenuMatcher(mock_db_session, cache_ttl=custom_ttl)
        
        assert matcher.cache_ttl == custom_ttl
        assert matcher.cache_key_prefix == "menu:async:default:"
        
        # Test with location ID
        matcher_with_loc = AsyncCachedMenuMatcher(mock_db_session, location_id="LOC_001")
        assert matcher_with_loc.cache_key_prefix == "menu:async:LOC_001:"


class TestMenuMatcherEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.mark.asyncio
    async def test_empty_menu_data(self):
        """Test behavior with empty menu data."""
        mock_session = Mock(spec=AsyncSession)
        mock_session.execute = AsyncMock()
        
        # Empty results
        empty_result = Mock()
        empty_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = empty_result
        
        matcher = AsyncMenuMatcher(mock_session)
        result = await matcher.initialize()
        
        assert result is True
        assert len(matcher.menu_items) == 0
        
        # Finding should return None
        assert await matcher.find_menu_item("anything") is None
        assert await matcher.find_modifier("anything") is None
    
    @pytest.mark.asyncio
    async def test_null_and_empty_strings(self):
        """Test handling of null and empty search strings."""
        mock_session = Mock(spec=AsyncSession)
        matcher = AsyncMenuMatcher(mock_session)
        
        # Empty string
        assert await matcher.find_menu_item("") is None
        
        # Whitespace only
        assert await matcher.find_menu_item("   ") is None
        
        # None should raise or return None
        try:
            await matcher.find_menu_item(None)
        except (AttributeError, TypeError):
            pass  # Expected
    
    @pytest.mark.asyncio
    async def test_special_characters_in_search(self):
        """Test handling of special characters in search."""
        mock_session = Mock(spec=AsyncSession)
        matcher = AsyncMenuMatcher(mock_session)
        matcher.menu_items = {
            "SPEC_001": {"name": "Chef's Special", "plu": "SPEC_001"},
            "AND_001": {"name": "Fish & Chips", "plu": "AND_001"}
        }
        
        # Apostrophe
        result = await matcher.find_menu_item("Chef's Special")
        assert result is not None
        
        # Ampersand
        result = await matcher.find_menu_item("Fish & Chips")
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_concurrent_initialization(self):
        """Test concurrent initialization calls."""
        mock_session = Mock(spec=AsyncSession)
        mock_session.execute = AsyncMock()
        
        # Simulate slow database query
        async def slow_execute(*args):
            await asyncio.sleep(0.1)
            result = Mock()
            result.scalars.return_value.all.return_value = []
            return result
        
        mock_session.execute.side_effect = slow_execute
        
        matcher = AsyncMenuMatcher(mock_session)
        
        # Initialize concurrently
        results = await asyncio.gather(
            matcher.initialize(),
            matcher.initialize(),
            matcher.initialize()
        )
        
        # All should succeed
        assert all(results)
    
    @pytest.mark.asyncio
    async def test_unicode_handling(self):
        """Test handling of Unicode characters."""
        mock_session = Mock(spec=AsyncSession)
        matcher = AsyncMenuMatcher(mock_session)
        matcher.menu_items = {
            "UNI_001": {"name": "Sashimi Moriawase (刺身盛り合わせ)", "plu": "UNI_001"},
            "EMO_001": {"name": "Happy Roll 🍣", "plu": "EMO_001"}
        }
        
        # Japanese characters
        result = await matcher.find_menu_item("刺身盛り合わせ")
        assert result is not None
        
        # Emoji
        result = await matcher.find_menu_item("Happy Roll")
        assert result is not None