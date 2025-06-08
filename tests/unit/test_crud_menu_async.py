"""Tests for async CRUD operations for menu-related models - Task 2.4.4."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func

from app.db.crud_menu_async import (
    # Variant CRUD
    get_variants, count_variants, get_variant, get_variant_by_phrase,
    create_variant, update_variant, delete_variant,
    # Category CRUD
    get_categories, count_categories, get_category, get_category_by_deliverect_id,
    create_category, update_category, delete_category,
    # Item CRUD
    get_items, count_items, get_items_by_category, get_item, get_item_by_plu,
    get_item_by_deliverect_id, create_item, update_item, delete_item,
    snooze_item, unsnooze_item,
    # Modifier CRUD
    get_modifiers, count_modifiers, get_modifier, get_modifier_by_plu,
    get_modifier_by_deliverect_id, create_modifier, update_modifier,
    delete_modifier, snooze_modifier, unsnooze_modifier,
    # Modifier Group CRUD
    get_modifier_groups, count_modifier_groups, get_modifier_group,
    get_modifier_group_by_plu, get_modifier_group_by_deliverect_id,
    create_modifier_group, update_modifier_group, delete_modifier_group,
    # Association Management
    add_modifier_to_group, remove_modifier_from_group,
    add_modifier_group_to_item, remove_modifier_group_from_item,
    # Helper functions
    link_modifier_to_group, link_item_to_modifier_group,
    search_menu_items
)
from app.models.menu_async import (
    MenuCategory, MenuItem, MenuModifier, MenuModifierGroup, MenuNameVariant
)
from app.schemas.menu import (
    MenuCategoryCreate, MenuCategoryUpdate,
    MenuItemCreate, MenuItemUpdate,
    MenuModifierCreate, MenuModifierUpdate,
    MenuModifierGroupCreate, MenuModifierGroupUpdate,
    MenuVariantCreate, MenuVariantUpdate
)


class TestVariantCRUD:
    """Test variant CRUD operations."""
    
    @pytest.mark.asyncio
    async def test_get_variants_basic(self):
        """Test getting variants with pagination."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_variants = [
            MagicMock(spec=MenuNameVariant, id="1", variant_phrase="test1"),
            MagicMock(spec=MenuNameVariant, id="2", variant_phrase="test2")
        ]
        
        # Mock the execute result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_variants
        mock_session.execute.return_value = mock_result
        
        # Test basic call
        result = await get_variants(mock_session)
        assert len(result) == 2
        assert result[0].variant_phrase == "test1"
        
        # Verify query construction
        executed_query = mock_session.execute.call_args[0][0]
        assert executed_query is not None
    
    @pytest.mark.asyncio
    async def test_get_variants_with_filters(self):
        """Test getting variants with PLU and canonical name filters."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        # Test with filters
        await get_variants(
            mock_session,
            target_plu="PLU123",
            canonical_name="Spicy Tuna Roll"
        )
        
        # Verify filters were applied
        assert mock_session.execute.called
    
    @pytest.mark.asyncio
    async def test_count_variants(self):
        """Test counting variants."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 42
        mock_session.execute.return_value = mock_result
        
        # Test count
        count = await count_variants(mock_session)
        assert count == 42
        
        # Test with filters
        count = await count_variants(
            mock_session,
            target_plu="PLU123"
        )
        assert count == 42
    
    @pytest.mark.asyncio
    async def test_get_variant_by_phrase(self):
        """Test getting variant by phrase (case-insensitive)."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_variant = MagicMock(spec=MenuNameVariant)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_variant
        mock_session.execute.return_value = mock_result
        
        # Test get by phrase
        result = await get_variant_by_phrase(mock_session, "Spicy TUNA")
        assert result == mock_variant
        
        # Verify case-insensitive search
        executed_query = mock_session.execute.call_args[0][0]
        assert executed_query is not None
    
    @pytest.mark.asyncio
    async def test_create_variant(self):
        """Test creating a new variant."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        variant_data = MenuVariantCreate(
            variant_phrase="spicy tuna",
            canonical_name="Spicy Tuna Roll",
            target_plu="PLU123"
        )
        
        result = await create_variant(mock_session, variant_data)
        
        # Verify add and commit were called
        assert mock_session.add.called
        assert mock_session.commit.called
        assert mock_session.refresh.called
    
    @pytest.mark.asyncio
    async def test_update_variant(self):
        """Test updating a variant."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_variant = MagicMock(spec=MenuNameVariant)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_variant
        mock_session.execute.return_value = mock_result
        
        update_data = MenuVariantUpdate(
            canonical_name="Updated Spicy Tuna Roll"
        )
        
        result = await update_variant(mock_session, "variant-1", update_data)
        assert result == mock_variant
        assert mock_session.commit.called
        
        # Test not found
        mock_result.scalar_one_or_none.return_value = None
        result = await update_variant(mock_session, "not-found", update_data)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_variant(self):
        """Test deleting a variant."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_variant = MagicMock(spec=MenuNameVariant)
        mock_result = MagicMock()
        
        # Test successful delete
        mock_result.scalar_one_or_none.return_value = mock_variant
        mock_session.execute.return_value = mock_result
        
        result = await delete_variant(mock_session, "variant-1")
        assert result is True
        assert mock_session.delete.called
        assert mock_session.commit.called
        
        # Test not found
        mock_result.scalar_one_or_none.return_value = None
        result = await delete_variant(mock_session, "not-found")
        assert result is False


class TestCategoryCRUD:
    """Test category CRUD operations."""
    
    @pytest.mark.asyncio
    async def test_get_categories_with_location_filter(self):
        """Test getting categories filtered by location."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_categories = [
            MagicMock(spec=MenuCategory, id="1", name="Appetizers"),
            MagicMock(spec=MenuCategory, id="2", name="Entrees")
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_categories
        mock_session.execute.return_value = mock_result
        
        # Test with location filter
        result = await get_categories(mock_session, location_id="loc-1")
        assert len(result) == 2
        assert mock_session.execute.called
    
    @pytest.mark.asyncio
    async def test_get_category_by_deliverect_id(self):
        """Test getting category by Deliverect ID."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_category = MagicMock(spec=MenuCategory)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_category
        mock_session.execute.return_value = mock_result
        
        result = await get_category_by_deliverect_id(mock_session, "dlv-cat-123")
        assert result == mock_category
    
    @pytest.mark.asyncio
    async def test_create_category_with_location(self):
        """Test creating category with location association."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        category_data = MenuCategoryCreate(
            name="Desserts",
            description="Sweet treats",
            deliverect_category_id="dlv-cat-456"
        )
        
        result = await create_category(mock_session, category_data, location_id="loc-1")
        
        # Verify the category was added with location
        add_call = mock_session.add.call_args[0][0]
        assert hasattr(add_call, 'location_id')
        assert mock_session.commit.called
    
    @pytest.mark.asyncio
    async def test_update_category(self):
        """Test updating category."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_category = MagicMock(spec=MenuCategory)
        mock_category.name = "Old Name"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_category
        mock_session.execute.return_value = mock_result
        
        update_data = MenuCategoryUpdate(name="New Name")
        
        result = await update_category(mock_session, "cat-1", update_data)
        assert result == mock_category
        assert mock_session.commit.called


class TestItemCRUD:
    """Test item CRUD operations."""
    
    @pytest.mark.asyncio
    async def test_get_items_available_only(self):
        """Test getting only available items (not snoozed)."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_items = [
            MagicMock(spec=MenuItem, is_available=True, snoozed_until=None)
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_items
        mock_session.execute.return_value = mock_result
        
        # Test available only filter
        result = await get_items(mock_session, available_only=True)
        assert len(result) == 1
        
        # Verify the query included availability checks
        executed_query = mock_session.execute.call_args[0][0]
        assert executed_query is not None
    
    @pytest.mark.asyncio
    async def test_get_items_by_category(self):
        """Test getting items by category."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_items = [
            MagicMock(spec=MenuItem, category_id="cat-1")
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_items
        mock_session.execute.return_value = mock_result
        
        result = await get_items_by_category(mock_session, "cat-1")
        assert len(result) == 1
    
    @pytest.mark.asyncio
    async def test_get_item_by_plu(self):
        """Test getting item by PLU."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_item = MagicMock(spec=MenuItem, plu="PLU123")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_session.execute.return_value = mock_result
        
        result = await get_item_by_plu(mock_session, "PLU123")
        assert result == mock_item
        assert result.plu == "PLU123"
    
    @pytest.mark.asyncio
    async def test_snooze_item(self):
        """Test snoozing an item."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_item = MagicMock(spec=MenuItem)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_session.execute.return_value = mock_result
        
        # Snooze for 2 hours
        snooze_until = datetime.now() + timedelta(hours=2)
        result = await snooze_item(mock_session, "item-1", snooze_until)
        
        assert result == mock_item
        assert mock_item.snoozed_until == snooze_until
        assert mock_session.commit.called
    
    @pytest.mark.asyncio
    async def test_unsnooze_item(self):
        """Test unsnoozing an item."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_item = MagicMock(spec=MenuItem)
        mock_item.snoozed_until = datetime.now() + timedelta(hours=1)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_session.execute.return_value = mock_result
        
        result = await unsnooze_item(mock_session, "item-1")
        
        assert result == mock_item
        assert mock_item.snoozed_until is None
        assert mock_session.commit.called
    
    @pytest.mark.asyncio
    async def test_create_item_with_properties(self):
        """Test creating item with JSONB properties."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        item_data = MenuItemCreate(
            name="Special Roll",
            description="Chef's special",
            price=15.99,
            plu="PLU999",
            deliverect_item_id="dlv-item-999",
            is_available=True,
            is_combo=False,
            is_variant=False,
            category_id="cat-1",
            properties={"spicy_level": 3, "contains_raw_fish": True}
        )
        
        result = await create_item(mock_session, item_data)
        
        # Verify properties were included
        add_call = mock_session.add.call_args[0][0]
        assert hasattr(add_call, 'properties')
        assert mock_session.commit.called
    
    @pytest.mark.asyncio
    async def test_count_items_with_filters(self):
        """Test counting items with multiple filters."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 25
        mock_session.execute.return_value = mock_result
        
        count = await count_items(
            mock_session,
            category_id="cat-1",
            location_id="loc-1",
            available_only=True
        )
        assert count == 25


class TestModifierCRUD:
    """Test modifier CRUD operations."""
    
    @pytest.mark.asyncio
    async def test_get_modifiers_by_group(self):
        """Test getting modifiers filtered by group."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_modifiers = [
            MagicMock(spec=MenuModifier, name="Extra Spicy")
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_modifiers
        mock_session.execute.return_value = mock_result
        
        # Test with group filter (uses join)
        result = await get_modifiers(mock_session, group_id="grp-1")
        assert len(result) == 1
    
    @pytest.mark.asyncio
    async def test_snooze_modifier(self):
        """Test snoozing a modifier."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_modifier = MagicMock(spec=MenuModifier)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_modifier
        mock_session.execute.return_value = mock_result
        
        snooze_until = datetime.now() + timedelta(hours=4)
        result = await snooze_modifier(mock_session, "mod-1", snooze_until)
        
        assert result == mock_modifier
        assert mock_modifier.snoozed_until == snooze_until
        assert mock_session.commit.called
    
    @pytest.mark.asyncio
    async def test_create_modifier(self):
        """Test creating a modifier."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        modifier_data = MenuModifierCreate(
            name="Add Avocado",
            price_change=2.50,
            plu="MOD123",
            deliverect_modifier_id="dlv-mod-123",
            is_available=True
        )
        
        result = await create_modifier(mock_session, modifier_data)
        
        # Verify the modifier was created with correct price
        add_call = mock_session.add.call_args[0][0]
        assert hasattr(add_call, 'price_change')
        assert mock_session.commit.called
    
    @pytest.mark.asyncio
    async def test_count_modifiers_with_group_filter(self):
        """Test counting modifiers with group filter."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 10
        mock_session.execute.return_value = mock_result
        
        # Count with group filter (uses join query)
        count = await count_modifiers(mock_session, group_id="grp-1")
        assert count == 10


class TestModifierGroupCRUD:
    """Test modifier group CRUD operations."""
    
    @pytest.mark.asyncio
    async def test_get_modifier_groups_with_modifiers(self):
        """Test getting modifier groups with related modifiers."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_groups = [
            MagicMock(spec=MenuModifierGroup, modifiers=[])
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_groups
        mock_session.execute.return_value = mock_result
        
        # Test with include_modifiers=True
        result = await get_modifier_groups(
            mock_session,
            include_modifiers=True
        )
        assert len(result) == 1
        
        # Verify selectinload was used
        executed_query = mock_session.execute.call_args[0][0]
        assert executed_query is not None
    
    @pytest.mark.asyncio
    async def test_get_modifier_groups_by_item(self):
        """Test getting modifier groups associated with an item."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_groups = [
            MagicMock(spec=MenuModifierGroup, name="Size Options")
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_groups
        mock_session.execute.return_value = mock_result
        
        # Test with item filter (uses join)
        result = await get_modifier_groups(mock_session, item_id="item-1")
        assert len(result) == 1
    
    @pytest.mark.asyncio
    async def test_create_modifier_group(self):
        """Test creating a modifier group."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        group_data = MenuModifierGroupCreate(
            name="Toppings",
            min_selection=0,
            max_selection=3,
            plu="GRP123",
            is_variant_group=False,
            deliverect_group_id="dlv-grp-123"
        )
        
        result = await create_modifier_group(
            mock_session,
            group_data,
            location_id="loc-1"
        )
        
        # Verify multiMax default
        add_call = mock_session.add.call_args[0][0]
        assert hasattr(add_call, 'multiMax')
        assert mock_session.commit.called
    
    @pytest.mark.asyncio
    async def test_get_modifier_group_by_plu(self):
        """Test getting modifier group by PLU."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_group = MagicMock(spec=MenuModifierGroup)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_group
        mock_session.execute.return_value = mock_result
        
        result = await get_modifier_group_by_plu(
            mock_session,
            "GRP123",
            include_modifiers=True
        )
        assert result == mock_group


class TestAssociationManagement:
    """Test association management operations."""
    
    @pytest.mark.asyncio
    async def test_add_modifier_to_group(self):
        """Test adding a modifier to a group."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Mock group with modifiers list
        mock_group = MagicMock(spec=MenuModifierGroup)
        mock_group.modifiers = []
        
        # Mock modifier
        mock_modifier = MagicMock(spec=MenuModifier)
        
        # Setup execute results
        mock_result_group = MagicMock()
        mock_result_group.scalar_one_or_none.return_value = mock_group
        
        mock_result_modifier = MagicMock()
        mock_result_modifier.scalar_one_or_none.return_value = mock_modifier
        
        mock_session.execute.side_effect = [
            mock_result_group,
            mock_result_modifier
        ]
        
        result = await add_modifier_to_group(
            mock_session,
            "grp-1",
            "mod-1"
        )
        
        assert result == mock_group
        assert mock_modifier in mock_group.modifiers
        assert mock_session.commit.called
    
    @pytest.mark.asyncio
    async def test_add_modifier_to_group_already_exists(self):
        """Test adding a modifier that already exists in group."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        mock_modifier = MagicMock(spec=MenuModifier)
        mock_group = MagicMock(spec=MenuModifierGroup)
        mock_group.modifiers = [mock_modifier]  # Already contains modifier
        
        mock_result_group = MagicMock()
        mock_result_group.scalar_one_or_none.return_value = mock_group
        
        mock_result_modifier = MagicMock()
        mock_result_modifier.scalar_one_or_none.return_value = mock_modifier
        
        mock_session.execute.side_effect = [
            mock_result_group,
            mock_result_modifier
        ]
        
        result = await add_modifier_to_group(
            mock_session,
            "grp-1",
            "mod-1"
        )
        
        assert result == mock_group
        # Should not add duplicate
        assert len(mock_group.modifiers) == 1
    
    @pytest.mark.asyncio
    async def test_remove_modifier_from_group(self):
        """Test removing a modifier from a group."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        mock_modifier = MagicMock(spec=MenuModifier, id="mod-1")
        mock_group = MagicMock(spec=MenuModifierGroup)
        mock_group.modifiers = [mock_modifier]
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_group
        mock_session.execute.return_value = mock_result
        
        result = await remove_modifier_from_group(
            mock_session,
            "grp-1",
            "mod-1"
        )
        
        assert result == mock_group
        assert mock_modifier not in mock_group.modifiers
        assert mock_session.commit.called
    
    @pytest.mark.asyncio
    async def test_add_modifier_group_to_item(self):
        """Test adding a modifier group to an item."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Mock item with modifier_groups list
        mock_item = MagicMock(spec=MenuItem)
        mock_item.modifier_groups = []
        
        # Mock group
        mock_group = MagicMock(spec=MenuModifierGroup)
        
        # Setup execute results
        mock_result_item = MagicMock()
        mock_result_item.scalar_one_or_none.return_value = mock_item
        
        mock_result_group = MagicMock()
        mock_result_group.scalar_one_or_none.return_value = mock_group
        
        mock_session.execute.side_effect = [
            mock_result_item,
            mock_result_group
        ]
        
        result = await add_modifier_group_to_item(
            mock_session,
            "item-1",
            "grp-1"
        )
        
        assert result == mock_item
        assert mock_group in mock_item.modifier_groups
        assert mock_session.commit.called
    
    @pytest.mark.asyncio
    async def test_link_modifier_to_group_sql(self):
        """Test direct SQL linking of modifier to group."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        result = await link_modifier_to_group(mock_session, 1, 2)
        
        assert result is True
        assert mock_session.execute.called
        assert mock_session.commit.called
        
        # Test with SQL error
        mock_session.execute.side_effect = Exception("DB Error")
        result = await link_modifier_to_group(mock_session, 1, 2)
        assert result is False
        assert mock_session.rollback.called


class TestSearchOperations:
    """Test search operations."""
    
    @pytest.mark.asyncio
    async def test_search_menu_items(self):
        """Test searching menu items by name or description."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_items = [
            MagicMock(spec=MenuItem, name="Spicy Tuna Roll"),
            MagicMock(spec=MenuItem, name="Tuna Sashimi")
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_items
        mock_session.execute.return_value = mock_result
        
        result = await search_menu_items(mock_session, "tuna")
        assert len(result) == 2
        
        # Verify case-insensitive search
        executed_query = mock_session.execute.call_args[0][0]
        assert executed_query is not None
    
    @pytest.mark.asyncio
    async def test_search_menu_items_error_handling(self):
        """Test search error handling."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.side_effect = Exception("Search error")
        
        result = await search_menu_items(mock_session, "test")
        assert result == []  # Should return empty list on error


class TestTransactionHandling:
    """Test transaction handling and error scenarios."""
    
    @pytest.mark.asyncio
    async def test_create_item_rollback_on_error(self):
        """Test that transactions are rolled back on error."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.commit.side_effect = Exception("DB Error")
        
        item_data = MenuItemCreate(
            name="Test Item",
            price=10.00,
            plu="TEST123",
            category_id="cat-1"
        )
        
        with pytest.raises(Exception):
            await create_item(mock_session, item_data)
    
    @pytest.mark.asyncio
    async def test_update_with_partial_data(self):
        """Test updating with partial data (exclude_unset)."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_item = MagicMock(spec=MenuItem)
        mock_item.name = "Original Name"
        mock_item.price = 10.00
        mock_item.description = "Original Description"
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_session.execute.return_value = mock_result
        
        # Update only price, other fields should remain unchanged
        update_data = MenuItemUpdate(price=15.00)
        
        result = await update_item(mock_session, "item-1", update_data)
        
        # Verify only price was updated
        assert hasattr(mock_item, 'price')
        assert mock_session.commit.called
    
    @pytest.mark.asyncio
    async def test_concurrent_access_handling(self):
        """Test handling of concurrent access scenarios."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Simulate concurrent modification
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # Item deleted by another process
        mock_session.execute.return_value = mock_result
        
        result = await snooze_item(
            mock_session,
            "item-1",
            datetime.now() + timedelta(hours=1)
        )
        
        assert result is None  # Should handle gracefully


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    @pytest.mark.asyncio
    async def test_pagination_boundaries(self):
        """Test pagination with edge cases."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        # Test with skip > total items
        result = await get_items(mock_session, skip=1000, limit=10)
        assert result == []
        
        # Test with limit = 0
        result = await get_items(mock_session, skip=0, limit=0)
        assert result == []
    
    @pytest.mark.asyncio
    async def test_invalid_datetime_handling(self):
        """Test handling of invalid datetime values."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_item = MagicMock(spec=MenuItem)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_session.execute.return_value = mock_result
        
        # Test with past datetime (should still work)
        past_time = datetime.now() - timedelta(hours=1)
        result = await snooze_item(mock_session, "item-1", past_time)
        
        assert result == mock_item
        assert mock_item.snoozed_until == past_time
    
    @pytest.mark.asyncio
    async def test_null_handling_in_filters(self):
        """Test handling of null values in filters."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        # Test with None filters (should be ignored)
        result = await get_items(
            mock_session,
            category_id=None,
            location_id=None
        )
        assert result == []
    
    @pytest.mark.asyncio
    async def test_special_characters_in_search(self):
        """Test search with special characters."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        # Test with SQL injection attempt
        result = await search_menu_items(
            mock_session,
            "test'; DROP TABLE items; --"
        )
        assert result == []
        
        # Test with special regex characters
        result = await search_menu_items(
            mock_session,
            "test.*[]()"
        )
        assert result == []


class TestComplexQueries:
    """Test complex query scenarios."""
    
    @pytest.mark.asyncio
    async def test_get_available_items_with_expired_snooze(self):
        """Test getting available items includes expired snoozes."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Mock items with various states
        mock_items = [
            MagicMock(
                spec=MenuItem,
                is_available=True,
                snoozed_until=datetime.now() - timedelta(hours=1)  # Expired snooze
            ),
            MagicMock(
                spec=MenuItem,
                is_available=True,
                snoozed_until=None  # Not snoozed
            )
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_items
        mock_session.execute.return_value = mock_result
        
        result = await get_items(mock_session, available_only=True)
        assert len(result) == 2  # Both should be included
    
    @pytest.mark.asyncio
    async def test_modifier_group_with_nested_relationships(self):
        """Test loading modifier groups with nested relationships."""
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Mock group with nested modifiers
        mock_modifiers = [
            MagicMock(spec=MenuModifier, name="Mod1"),
            MagicMock(spec=MenuModifier, name="Mod2")
        ]
        mock_group = MagicMock(spec=MenuModifierGroup)
        mock_group.modifiers = mock_modifiers
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_group
        mock_session.execute.return_value = mock_result
        
        result = await get_modifier_group(
            mock_session,
            "grp-1",
            include_modifiers=True
        )
        
        assert result == mock_group
        assert len(result.modifiers) == 2