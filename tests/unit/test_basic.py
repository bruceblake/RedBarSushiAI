"""
Basic unit tests that don't require app imports.
"""
import pytest


class TestBasic:
    """Basic tests without app dependencies."""
    
    def test_arithmetic(self):
        """Test basic arithmetic."""
        assert 2 + 2 == 4
        assert 10 - 5 == 5
        assert 3 * 4 == 12
        assert 10 / 2 == 5
    
    def test_string_operations(self):
        """Test string operations."""
        text = "Hello World"
        assert text.lower() == "hello world"
        assert text.upper() == "HELLO WORLD"
        assert len(text) == 11
        assert "World" in text
    
    def test_list_operations(self):
        """Test list operations."""
        items = [1, 2, 3, 4, 5]
        assert len(items) == 5
        assert sum(items) == 15
        assert max(items) == 5
        assert min(items) == 1
    
    def test_dictionary_operations(self):
        """Test dictionary operations."""
        data = {"name": "Test", "value": 100}
        assert data["name"] == "Test"
        assert data.get("value") == 100
        assert data.get("missing", "default") == "default"
        assert len(data) == 2
    
    @pytest.mark.asyncio
    async def test_async_basic(self):
        """Test basic async functionality."""
        async def get_value():
            return 42
        
        result = await get_value()
        assert result == 42
    
    def test_exceptions(self):
        """Test exception handling."""
        with pytest.raises(ZeroDivisionError):
            1 / 0
        
        with pytest.raises(KeyError):
            {}["nonexistent"]
        
        with pytest.raises(IndexError):
            [][0]