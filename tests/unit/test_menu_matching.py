"""
Unit tests for menu matching system.
"""
import pytest
from app.utils.menu_matcher_cache_async import AsyncMenuMatcher
from app.models.menu_async import MenuItem, MenuNameVariant


class TestMenuMatching:
    """Test menu matching functionality."""
    
    @pytest.mark.asyncio
    async def test_exact_match(self, db_session, sample_menu_data):
        """Test exact menu item matching."""
        matcher = AsyncMenuMatcher(db_session)
        
        # Test exact name match
        result = await matcher.match_item("California Roll")
        assert result is not None
        assert result["plu"] == "CALI_001"
        assert result["name"] == "California Roll"
        
        # Test PLU match
        result = await matcher.match_item("CALI_001")
        assert result is not None
        assert result["plu"] == "CALI_001"
    
    @pytest.mark.asyncio
    async def test_case_insensitive_match(self, db_session, sample_menu_data):
        """Test case insensitive matching."""
        matcher = AsyncMenuMatcher(db_session)
        
        result = await matcher.match_item("california roll")
        assert result is not None
        assert result["plu"] == "CALI_001"
        
        result = await matcher.match_item("CALIFORNIA ROLL")
        assert result is not None
        assert result["plu"] == "CALI_001"
    
    @pytest.mark.asyncio
    async def test_variant_matching(self, db_session, sample_menu_data):
        """Test matching with name variants."""
        # Add a variant
        variant = MenuNameVariant(
            variant_phrase="cali roll",
            canonical_name="California Roll",
            target_plu="CALI_001"
        )
        db_session.add(variant)
        await db_session.commit()
        
        matcher = AsyncMenuMatcher(db_session)
        
        result = await matcher.match_item("cali roll")
        assert result is not None
        assert result["plu"] == "CALI_001"
        assert result["name"] == "California Roll"
    
    @pytest.mark.asyncio
    async def test_fuzzy_matching(self, db_session, sample_menu_data):
        """Test fuzzy matching for typos."""
        matcher = AsyncMenuMatcher(db_session)
        
        # Small typo
        result = await matcher.match_item("Californa Roll")  # Missing 'i'
        assert result is not None
        assert result["plu"] == "CALI_001"
        
        # Another typo
        result = await matcher.match_item("Spicy Tuna Rol")  # Missing 'l'
        assert result is not None
        assert result["plu"] == "TUNA_001"
    
    @pytest.mark.asyncio
    async def test_no_match(self, db_session, sample_menu_data):
        """Test when no match is found."""
        matcher = AsyncMenuMatcher(db_session)
        
        result = await matcher.match_item("Dragon Roll")  # Doesn't exist
        assert result is None
    
    @pytest.mark.asyncio
    async def test_modifier_matching(self, db_session, sample_menu_data):
        """Test modifier matching."""
        matcher = AsyncMenuMatcher(db_session)
        
        result = await matcher.match_modifier("Extra Avocado")
        assert result is not None
        assert result["plu"] == "MOD_AVO"
        assert result["price_change"] == 200
    
    @pytest.mark.asyncio
    async def test_category_filtering(self, db_session, sample_menu_data):
        """Test matching within category."""
        matcher = AsyncMenuMatcher(db_session)
        
        # Get items in specific category
        sushi_items = await matcher.get_items_by_category("Sushi Rolls")
        assert len(sushi_items) == 2
        assert all(item["category_name"] == "Sushi Rolls" for item in sushi_items)
        
        appetizer_items = await matcher.get_items_by_category("Appetizers")
        assert len(appetizer_items) == 1
        assert appetizer_items[0]["name"] == "Edamame"
    
    @pytest.mark.asyncio
    async def test_availability_check(self, db_session, sample_menu_data):
        """Test availability checking."""
        matcher = AsyncMenuMatcher(db_session)
        
        # Make item unavailable
        california_roll = await db_session.get(MenuItem, 1)
        california_roll.is_available = False
        await db_session.commit()
        
        # Should still match but indicate unavailable
        result = await matcher.match_item("California Roll")
        assert result is not None
        assert result["is_available"] is False
    
    @pytest.mark.asyncio
    async def test_caching(self, db_session, sample_menu_data, mock_redis):
        """Test menu caching functionality."""
        matcher = AsyncMenuMatcher(db_session, redis_client=mock_redis)
        
        # First call should hit database
        result1 = await matcher.match_item("California Roll")
        
        # Second call should use cache
        result2 = await matcher.match_item("California Roll")
        
        assert result1 == result2
        assert mock_redis.get.called  # Cache was checked
    
    @pytest.mark.asyncio
    async def test_batch_matching(self, db_session, sample_menu_data):
        """Test matching multiple items at once."""
        matcher = AsyncMenuMatcher(db_session)
        
        items_to_match = ["California Roll", "Spicy Tuna Roll", "Edamame"]
        results = await matcher.match_items_batch(items_to_match)
        
        assert len(results) == 3
        assert results[0]["plu"] == "CALI_001"
        assert results[1]["plu"] == "TUNA_001"
        assert results[2]["plu"] == "EDAM_001"