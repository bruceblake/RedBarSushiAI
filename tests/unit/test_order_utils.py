"""
Comprehensive unit tests for order utilities and validation helpers - Task 2.3.4.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return Mock(spec=AsyncSession)

@pytest.fixture
def mock_menu_matcher():
    """Create a mock menu matcher."""
    matcher = Mock()
    matcher.match_item = AsyncMock()
    return matcher

@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return Mock(spec=AsyncSession)

@pytest.fixture
def mock_menu_data():
    """Create mock menu data."""
    return {
        "items": [
            {
                "plu": "CALI_001",
                "name": "California Roll",
                "is_available": True,
                "snoozed": False
            },
            {
                "plu": "TUNA_001",
                "name": "Spicy Tuna Roll",
                "is_available": False,
                "snoozed": False
            },
            {
                "plu": "SALM_001",
                "name": "Salmon Sashimi",
                "is_available": True,
                "snoozed": True  # Snoozed items are unavailable
            }
        ],
        "modifiers": [
            {
                "plu": "MOD_AVO",
                "name": "Extra Avocado",
                "is_available": True,
                "snoozed": False
            },
            {
                "plu": "MOD_SPICY",
                "name": "Extra Spicy",
                "is_available": False,
                "snoozed": False
            }
        ]
    }

@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return Mock(spec=AsyncSession)

This module tests order utility functions including:
- Menu item finding and matching
- Order description building
- Bill amount calculation
- Item availability checking
- Modifier validation
- PLU reference handling
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.order_utils_async import (
    find_menu_item_async,
    build_order_description_async,
    calculate_bill_amount_async,
    mark_unavailable_items_async,
    validate_modifiers_async
)


class TestFindMenuItemAsync:
    """Test menu item finding functionality."""
    
    @pytest.mark.asyncio
    async def test_find_menu_item_exact_match(self, mock_db_session):
        """Test finding menu item with exact match."""
        mock_item = {
            "plu": "CALI_001",
            "name": "California Roll",
            "price": 8.99,
            "category": "Sushi Rolls"
        }
        
        with patch('app.utils.order_utils_async.get_cached_async_menu_matcher') as mock_get_matcher:
            mock_matcher = Mock()
            mock_matcher.match_item = AsyncMock(return_value=(mock_item, 95))
            mock_get_matcher.return_value = mock_matcher
            
            result, score = await find_menu_item_async(mock_db_session, "California Roll")
            
            assert result == mock_item
            assert score == 95
            mock_matcher.match_item.assert_called_once_with("California Roll")
    
    @pytest.mark.asyncio
    async def test_find_menu_item_no_match(self, mock_db_session):
        """Test finding menu item when no match found."""
        with patch('app.utils.order_utils_async.get_cached_async_menu_matcher') as mock_get_matcher:
            mock_matcher = Mock()
            mock_matcher.match_item = AsyncMock(return_value=(None, None))
            mock_get_matcher.return_value = mock_matcher
            
            result, score = await find_menu_item_async(mock_db_session, "Dragon Roll")
            
            assert result is None
            assert score is None
    
    @pytest.mark.asyncio
    async def test_find_menu_item_with_threshold(self, mock_db_session):
        """Test finding menu item with custom threshold."""
        mock_item = {"plu": "TUNA_001", "name": "Spicy Tuna Roll"}
        
        with patch('app.utils.order_utils_async.get_cached_async_menu_matcher') as mock_get_matcher:
            mock_matcher = Mock()
            mock_matcher.match_item = AsyncMock(return_value=(mock_item, 75))
            mock_get_matcher.return_value = mock_matcher
            
            result, score = await find_menu_item_async(
                mock_db_session, "Spicy Tuna", threshold=50
            )
            
            assert result == mock_item
            assert score == 75
    
    @pytest.mark.asyncio
    async def test_find_menu_item_with_context(self, mock_db_session):
        """Test finding menu item with context for AI matching."""
        mock_item = {"plu": "SALM_001", "name": "Salmon Sashimi"}
        context = {"conversation_history": ["I want sashimi"]}
        
        with patch('app.utils.order_utils_async.get_cached_async_menu_matcher') as mock_get_matcher:
            mock_matcher = Mock()
            mock_matcher.match_item = AsyncMock(return_value=(mock_item, 85))
            mock_get_matcher.return_value = mock_matcher
            
            result, score = await find_menu_item_async(
                mock_db_session, "salmon", context=context
            )
            
            assert result == mock_item
            assert score == 85
    
    @pytest.mark.asyncio
    async def test_find_menu_item_matcher_exception(self, mock_db_session):
        """Test handling when menu matcher raises exception."""
        with patch('app.utils.order_utils_async.get_cached_async_menu_matcher') as mock_get_matcher:
            mock_matcher = Mock()
            mock_matcher.match_item = AsyncMock(side_effect=Exception("Matcher error"))
            mock_get_matcher.return_value = mock_matcher
            
            with pytest.raises(Exception):
                await find_menu_item_async(mock_db_session, "test item")


class TestBuildOrderDescriptionAsync:
    """Test order description building functionality."""
    
    @pytest.mark.asyncio
    async def test_build_description_empty_order(self):
        """Test building description for empty order."""
        result = await build_order_description_async([])
        assert result == "Empty order"
    
    @pytest.mark.asyncio
    async def test_build_description_single_item(self):
        """Test building description for single item."""
        order_items = [
            {
                "name": "California Roll",
                "quantity": 1,
                "price": 8.99
            }
        ]
        
        result = await build_order_description_async(order_items)
        assert result == "California Roll"
    
    @pytest.mark.asyncio
    async def test_build_description_multiple_quantities(self):
        """Test building description with multiple quantities."""
        order_items = [
            {
                "name": "California Roll",
                "quantity": 2,
                "price": 8.99
            },
            {
                "name": "Spicy Tuna Roll",
                "quantity": 3,
                "price": 9.99
            }
        ]
        
        result = await build_order_description_async(order_items)
        assert result == "2x California Roll, 3x Spicy Tuna Roll"
    
    @pytest.mark.asyncio
    async def test_build_description_with_modifiers(self):
        """Test building description with modifiers."""
        order_items = [
            {
                "name": "California Roll",
                "quantity": 1,
                "modifiers": [
                    {"name": "Extra Avocado", "quantity": 1},
                    {"name": "No Cucumber", "quantity": 1}
                ]
            }
        ]
        
        result = await build_order_description_async(order_items)
        assert result == "California Roll with Extra Avocado, No Cucumber"
    
    @pytest.mark.asyncio
    async def test_build_description_multiple_modifier_quantities(self):
        """Test building description with multiple modifier quantities."""
        order_items = [
            {
                "name": "Sushi Platter",
                "quantity": 1,
                "modifiers": [
                    {"name": "Extra Wasabi", "quantity": 2},
                    {"name": "Soy Sauce", "quantity": 1}
                ]
            }
        ]
        
        result = await build_order_description_async(order_items)
        assert result == "Sushi Platter with 2x Extra Wasabi, Soy Sauce"
    
    @pytest.mark.asyncio
    async def test_build_description_complex_order(self):
        """Test building description for complex order."""
        order_items = [
            {
                "name": "California Roll",
                "quantity": 2,
                "modifiers": [
                    {"name": "Extra Avocado", "quantity": 1}
                ]
            },
            {
                "name": "Miso Soup",
                "quantity": 1
            },
            {
                "name": "Salmon Sashimi",
                "quantity": 3,
                "modifiers": [
                    {"name": "Extra Ginger", "quantity": 2},
                    {"name": "Wasabi", "quantity": 1}
                ]
            }
        ]
        
        result = await build_order_description_async(order_items)
        expected = "2x California Roll with Extra Avocado, Miso Soup, 3x Salmon Sashimi with 2x Extra Ginger, Wasabi"
        assert result == expected
    
    @pytest.mark.asyncio
    async def test_build_description_missing_fields(self):
        """Test building description with missing fields."""
        order_items = [
            {
                # Missing name
                "quantity": 1
            },
            {
                "name": "Test Item"
                # Missing quantity (should default to 1)
            }
        ]
        
        result = await build_order_description_async(order_items)
        assert result == "Unknown item, Test Item"


class TestCalculateBillAmountAsync:
    """Test bill amount calculation functionality."""
    
    @pytest.mark.asyncio
    async def test_calculate_empty_order(self):
        """Test calculating bill for empty order."""
        result = await calculate_bill_amount_async([])
        assert result == 0.0
    
    @pytest.mark.asyncio
    async def test_calculate_single_item(self):
        """Test calculating bill for single item."""
        order_items = [
            {
                "name": "California Roll",
                "price": 8.99,
                "quantity": 1
            }
        ]
        
        result = await calculate_bill_amount_async(order_items)
        assert result == 8.99
    
    @pytest.mark.asyncio
    async def test_calculate_multiple_items(self):
        """Test calculating bill for multiple items."""
        order_items = [
            {
                "name": "California Roll",
                "price": 8.99,
                "quantity": 2
            },
            {
                "name": "Miso Soup",
                "price": 3.50,
                "quantity": 1
            }
        ]
        
        result = await calculate_bill_amount_async(order_items)
        assert result == 21.48  # (8.99 * 2) + 3.50
    
    @pytest.mark.asyncio
    async def test_calculate_with_modifiers(self):
        """Test calculating bill with modifiers."""
        order_items = [
            {
                "name": "California Roll",
                "price": 8.99,
                "quantity": 1,
                "modifiers": [
                    {
                        "name": "Extra Avocado",
                        "price_change": 2.00,
                        "quantity": 1
                    },
                    {
                        "name": "Extra Spicy",
                        "price_change": 0.50,
                        "quantity": 1
                    }
                ]
            }
        ]
        
        result = await calculate_bill_amount_async(order_items)
        assert result == 11.49  # 8.99 + 2.00 + 0.50
    
    @pytest.mark.asyncio
    async def test_calculate_modifier_quantities(self):
        """Test calculating with modifier quantities."""
        order_items = [
            {
                "name": "Sushi Platter",
                "price": 15.99,
                "quantity": 2,
                "modifiers": [
                    {
                        "name": "Extra Wasabi",
                        "price_change": 0.75,
                        "quantity": 3
                    }
                ]
            }
        ]
        
        result = await calculate_bill_amount_async(order_items)
        # (15.99 * 2) + (0.75 * 3 * 2) = 31.98 + 4.50 = 36.48
        assert result == 36.48
    
    @pytest.mark.asyncio
    async def test_calculate_negative_modifier_prices(self):
        """Test calculating with negative modifier prices (discounts)."""
        order_items = [
            {
                "name": "Special Roll",
                "price": 12.99,
                "quantity": 1,
                "modifiers": [
                    {
                        "name": "No Avocado",
                        "price_change": -1.50,
                        "quantity": 1
                    }
                ]
            }
        ]
        
        result = await calculate_bill_amount_async(order_items)
        assert result == 11.49  # 12.99 - 1.50
    
    @pytest.mark.asyncio
    async def test_calculate_missing_fields_defaults(self):
        """Test calculation with missing price/quantity fields."""
        order_items = [
            {
                "name": "Test Item"
                # Missing price and quantity
            },
            {
                "name": "Another Item",
                "price": 5.99
                # Missing quantity (should default to 1)
            }
        ]
        
        result = await calculate_bill_amount_async(order_items)
        assert result == 5.99  # 0 + 5.99
    
    @pytest.mark.asyncio
    async def test_calculate_rounding(self):
        """Test that result is properly rounded to 2 decimal places."""
        order_items = [
            {
                "name": "Test Item",
                "price": 1.333,  # Should round to 1.33
                "quantity": 3
            }
        ]
        
        result = await calculate_bill_amount_async(order_items)
        assert result == 3.99  # 1.333 * 3 = 3.999, rounded to 3.99


class TestMarkUnavailableItemsAsync:
    """Test item availability checking functionality."""
    
    @pytest.mark.asyncio
    async def test_mark_unavailable_all_available(self, mock_db_session, mock_menu_data):
        """Test marking when all items are available."""
        order_items = [
            {
                "plu": "CALI_001",
                "name": "California Roll",
                "modifiers": [
                    {"plu": "MOD_AVO", "name": "Extra Avocado"}
                ]
            }
        ]
        
        with patch('app.utils.order_utils_async.load_menu_data') as mock_load, \
             patch('app.utils.order_utils_async.is_item_available') as mock_available:
            
            mock_load.return_value = mock_menu_data
            mock_available.side_effect = lambda item: item.get("is_available", True) and not item.get("snoozed", False)
            
            updated_items, unavailable = await mark_unavailable_items_async(mock_db_session, order_items)
            
            assert len(updated_items) == 1
            assert updated_items[0]["available"] is True
            assert updated_items[0]["modifiers"][0]["available"] is True
            assert len(unavailable) == 0
    
    @pytest.mark.asyncio
    async def test_mark_unavailable_item_not_available(self, mock_db_session, mock_menu_data):
        """Test marking when item is not available."""
        order_items = [
            {
                "plu": "TUNA_001",
                "name": "Spicy Tuna Roll"
            }
        ]
        
        with patch('app.utils.order_utils_async.load_menu_data') as mock_load, \
             patch('app.utils.order_utils_async.is_item_available') as mock_available:
            
            mock_load.return_value = mock_menu_data
            mock_available.side_effect = lambda item: item.get("is_available", True) and not item.get("snoozed", False)
            
            updated_items, unavailable = await mark_unavailable_items_async(mock_db_session, order_items)
            
            assert len(updated_items) == 1
            assert updated_items[0]["available"] is False
            assert "Spicy Tuna Roll" in unavailable
    
    @pytest.mark.asyncio
    async def test_mark_unavailable_snoozed_item(self, mock_db_session, mock_menu_data):
        """Test marking when item is snoozed."""
        order_items = [
            {
                "plu": "SALM_001",
                "name": "Salmon Sashimi"
            }
        ]
        
        with patch('app.utils.order_utils_async.load_menu_data') as mock_load, \
             patch('app.utils.order_utils_async.is_item_available') as mock_available:
            
            mock_load.return_value = mock_menu_data
            mock_available.side_effect = lambda item: item.get("is_available", True) and not item.get("snoozed", False)
            
            updated_items, unavailable = await mark_unavailable_items_async(mock_db_session, order_items)
            
            assert len(updated_items) == 1
            assert updated_items[0]["available"] is False
            assert "Salmon Sashimi" in unavailable
    
    @pytest.mark.asyncio
    async def test_mark_unavailable_modifier_not_available(self, mock_db_session, mock_menu_data):
        """Test marking when modifier is not available."""
        order_items = [
            {
                "plu": "CALI_001",
                "name": "California Roll",
                "modifiers": [
                    {"plu": "MOD_SPICY", "name": "Extra Spicy"}
                ]
            }
        ]
        
        with patch('app.utils.order_utils_async.load_menu_data') as mock_load, \
             patch('app.utils.order_utils_async.is_item_available') as mock_available:
            
            mock_load.return_value = mock_menu_data
            mock_available.side_effect = lambda item: item.get("is_available", True) and not item.get("snoozed", False)
            
            updated_items, unavailable = await mark_unavailable_items_async(mock_db_session, order_items)
            
            assert len(updated_items) == 1
            assert updated_items[0]["available"] is False  # Item marked unavailable due to modifier
            assert updated_items[0]["modifiers"][0]["available"] is False
            assert "California Roll with Extra Spicy" in unavailable
    
    @pytest.mark.asyncio
    async def test_mark_unavailable_missing_plu(self, mock_db_session, mock_menu_data):
        """Test handling of items with missing PLU."""
        order_items = [
            {
                "name": "Unknown Item"
                # Missing PLU
            }
        ]
        
        with patch('app.utils.order_utils_async.load_menu_data') as mock_load:
            mock_load.return_value = mock_menu_data
            
            updated_items, unavailable = await mark_unavailable_items_async(mock_db_session, order_items)
            
            assert len(updated_items) == 1
            assert len(unavailable) == 0  # Should not mark as unavailable, just skip
    
    @pytest.mark.asyncio
    async def test_mark_unavailable_item_not_in_menu(self, mock_db_session, mock_menu_data):
        """Test handling of items not found in menu data."""
        order_items = [
            {
                "plu": "MISSING_001",
                "name": "Missing Item"
            }
        ]
        
        with patch('app.utils.order_utils_async.load_menu_data') as mock_load:
            mock_load.return_value = mock_menu_data
            
            updated_items, unavailable = await mark_unavailable_items_async(mock_db_session, order_items)
            
            assert len(updated_items) == 1
            assert updated_items[0]["available"] is False
            assert "Missing Item" in unavailable


class TestValidateModifiersAsync:
    """Test modifier validation functionality."""
    
    @pytest.mark.asyncio
    async def test_validate_modifiers_no_items(self, mock_db_session):
        """Test validation with no items."""
        with patch('app.utils.order_utils_async.load_menu_data') as mock_load:
            mock_load.return_value = {"items": [], "modifiers": [], "modifier_groups": []}
            
            is_valid, errors = await validate_modifiers_async(mock_db_session, [])
            
            assert is_valid is True
            assert len(errors) == 0
    
    @pytest.mark.asyncio
    async def test_validate_modifiers_no_plu(self, mock_db_session):
        """Test validation with items missing PLU."""
        order_items = [
            {
                "name": "Test Item"
                # Missing PLU
            }
        ]
        
        with patch('app.utils.order_utils_async.load_menu_data') as mock_load:
            mock_load.return_value = {"items": [], "modifiers": [], "modifier_groups": []}
            
            is_valid, errors = await validate_modifiers_async(mock_db_session, order_items)
            
            assert is_valid is True  # Should skip items without PLU
            assert len(errors) == 0
    
    @pytest.mark.asyncio
    async def test_validate_modifiers_stub_implementation(self, mock_db_session):
        """Test current stub implementation of modifier validation."""
        order_items = [
            {
                "plu": "TEST_001",
                "name": "Test Item",
                "modifiers": [
                    {"plu": "MOD_001", "name": "Test Modifier"}
                ]
            }
        ]
        
        with patch('app.utils.order_utils_async.load_menu_data') as mock_load:
            mock_load.return_value = {
                "items": [{"plu": "TEST_001", "name": "Test Item"}],
                "modifiers": [{"plu": "MOD_001", "name": "Test Modifier"}],
                "modifier_groups": []
            }
            
            # Note: Current implementation appears to be incomplete
            # This test documents the current behavior
            result = await validate_modifiers_async(mock_db_session, order_items)
            
            # Should return a tuple
            assert isinstance(result, tuple)
            assert len(result) == 2


class TestOrderUtilsEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.mark.asyncio
    async def test_database_connection_failure(self):
        """Test handling of database connection failures."""
        mock_session = Mock(spec=AsyncSession)
        
        with patch('app.utils.order_utils_async.load_menu_data') as mock_load:
            mock_load.side_effect = Exception("Database connection failed")
            
            with pytest.raises(Exception):
                await mark_unavailable_items_async(mock_session, [])
    
    @pytest.mark.asyncio
    async def test_invalid_order_item_structure(self):
        """Test handling of invalid order item structures."""
        # Test with None values
        invalid_items = [
            None,
            {},
            {"invalid": "structure"}
        ]
        
        # Should not crash
        result = await build_order_description_async(invalid_items)
        assert isinstance(result, str)
        
        total = await calculate_bill_amount_async(invalid_items)
        assert isinstance(total, float)
    
    @pytest.mark.asyncio
    async def test_unicode_in_order_items(self):
        """Test handling of Unicode characters in order items."""
        order_items = [
            {
                "name": "Sashimi Moriawase (刺身盛り合わせ)",
                "price": 15.99,
                "quantity": 1,
                "modifiers": [
                    {"name": "Extra Wasabi (わさび)", "price_change": 0.50}
                ]
            }
        ]
        
        description = await build_order_description_async(order_items)
        assert "刺身盛り合わせ" in description
        assert "わさび" in description
        
        total = await calculate_bill_amount_async(order_items)
        assert total == 16.49
    
    @pytest.mark.asyncio
    async def test_very_large_quantities(self):
        """Test handling of very large quantities."""
        order_items = [
            {
                "name": "Bulk Order",
                "price": 1.00,
                "quantity": 999999
            }
        ]
        
        total = await calculate_bill_amount_async(order_items)
        assert total == 999999.00
        
        description = await build_order_description_async(order_items)
        assert "999999x" in description
    
    @pytest.mark.asyncio
    async def test_precision_edge_cases(self):
        """Test floating point precision edge cases."""
        order_items = [
            {
                "name": "Precision Test",
                "price": 0.01,
                "quantity": 1
            },
            {
                "name": "Another Item",
                "price": 0.02,
                "quantity": 1
            }
        ]
        
        total = await calculate_bill_amount_async(order_items)
        assert total == 0.03  # Should handle small amounts correctly