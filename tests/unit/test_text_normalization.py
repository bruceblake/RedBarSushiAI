"""
Comprehensive unit tests for text normalization - Task 2.3.2.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.utils.text_normalization import TextNormalizer


@pytest.fixture
def normalizer():
    """Create a TextNormalizer instance."""
    return TextNormalizer()


class TestTextNormalizerBasics:
    """Test basic text normalization functionality."""
    
    def test_empty_and_whitespace(self, normalizer):
        """Test handling of empty strings and whitespace."""
        assert normalizer.normalize("") == ""
        # Whitespace gets stripped and a period added if no punctuation
        assert normalizer.normalize("   ") == "."
        assert normalizer.normalize("\n\t") == "."
    
    def test_no_normalization_needed(self, normalizer):
        """Test text that doesn't need normalization."""
        text = "Hello world, this is a test."
        assert normalizer.normalize(text) == text
        
        # Text without ending punctuation gets a period added
        text = "The quick brown fox jumps over the lazy dog"
        assert normalizer.normalize(text) == text + "."


class TestCurrencyNormalization:
    """Test currency normalization for TTS."""
    
    def test_basic_currency(self, normalizer):
        """Test basic currency formatting."""
        assert normalizer.normalize("$10") == "ten dollars"
        assert normalizer.normalize("$1") == "one dollar"
        assert normalizer.normalize("$25") == "twenty five dollars"
        assert normalizer.normalize("$100") == "one hundred dollars"
    
    def test_currency_with_cents(self, normalizer):
        """Test currency with cents."""
        assert normalizer.normalize("$10.50") == "ten dollars and fifty cents"
        assert normalizer.normalize("$1.01") == "one dollar and one cent"
        assert normalizer.normalize("$0.99") == "ninety nine cents"
        assert normalizer.normalize("$0.01") == "one cent"
        assert normalizer.normalize("$25.00") == "twenty five dollars"
    
    def test_large_amounts(self, normalizer):
        """Test large currency amounts."""
        assert normalizer.normalize("$1,000") == "one thousand dollars"
        assert normalizer.normalize("$1,234.56") == "one thousand two hundred thirty four dollars and fifty six cents"
        assert normalizer.normalize("$999.99") == "nine hundred ninety nine dollars and ninety nine cents"
    
    def test_edge_cases(self, normalizer):
        """Test edge cases for currency."""
        assert normalizer.normalize("$0") == "zero dollars"
        assert normalizer.normalize("$0.00") == "zero dollars"
        assert normalizer.normalize("$.50") == "fifty cents"
        
    def test_currency_in_context(self, normalizer):
        """Test currency normalization within sentences."""
        assert normalizer.normalize("Your total is $15.50") == "Your total is fifteen dollars and fifty cents"
        assert normalizer.normalize("Save $5 on your order") == "Save five dollars on your order"


class TestNumberNormalization:
    """Test number to words conversion."""
    
    def test_basic_numbers(self, normalizer):
        """Test basic number conversion."""
        assert normalizer.normalize("0") == "zero"
        assert normalizer.normalize("1") == "one"
        assert normalizer.normalize("10") == "ten"
        assert normalizer.normalize("25") == "twenty five"
        assert normalizer.normalize("100") == "one hundred"
    
    def test_teen_numbers(self, normalizer):
        """Test teen numbers (11-19)."""
        assert normalizer.normalize("11") == "eleven"
        assert normalizer.normalize("12") == "twelve"
        assert normalizer.normalize("13") == "thirteen"
        assert normalizer.normalize("15") == "fifteen"
        assert normalizer.normalize("18") == "eighteen"
        assert normalizer.normalize("19") == "nineteen"
    
    def test_compound_numbers(self, normalizer):
        """Test compound numbers."""
        assert normalizer.normalize("21") == "twenty one"
        assert normalizer.normalize("45") == "forty five"
        assert normalizer.normalize("99") == "ninety nine"
        assert normalizer.normalize("101") == "one hundred one"
        assert normalizer.normalize("256") == "two hundred fifty six"
    
    def test_numbers_in_context(self, normalizer):
        """Test numbers within sentences."""
        assert normalizer.normalize("I need 2 rolls") == "I need two rolls"
        assert normalizer.normalize("Table for 4 people") == "Table for four people"
        assert normalizer.normalize("Order number 123") == "Order number one hundred twenty three"
    
    def test_ordinal_numbers(self, normalizer):
        """Test ordinal number conversion."""
        assert normalizer.normalize("1st") == "first"
        assert normalizer.normalize("2nd") == "second"
        assert normalizer.normalize("3rd") == "third"
        assert normalizer.normalize("4th") == "fourth"
        assert normalizer.normalize("21st") == "twenty first"
        assert normalizer.normalize("32nd") == "thirty second"
        assert normalizer.normalize("43rd") == "forty third"


class TestPhoneNumberNormalization:
    """Test phone number formatting."""
    
    def test_standard_formats(self, normalizer):
        """Test standard phone number formats."""
        assert normalizer.normalize("555-1234") == "five five five, one two three four"
        assert normalizer.normalize("(555) 123-4567") == "five five five, one two three, four five six seven"
        assert normalizer.normalize("555.123.4567") == "five five five, one two three, four five six seven"
        assert normalizer.normalize("5551234567") == "five five five, one two three, four five six seven"
    
    def test_with_country_code(self, normalizer):
        """Test phone numbers with country code."""
        assert normalizer.normalize("+1 555-123-4567") == "plus one, five five five, one two three, four five six seven"
        assert normalizer.normalize("1-555-123-4567") == "one, five five five, one two three, four five six seven"
    
    def test_phone_in_context(self, normalizer):
        """Test phone numbers in sentences."""
        assert normalizer.normalize("Call us at 555-1234") == "Call us at five five five, one two three four"
        assert normalizer.normalize("My number is (555) 123-4567") == "My number is five five five, one two three, four five six seven"


class TestDateTimeNormalization:
    """Test date and time formatting."""
    
    def test_date_formats(self, normalizer):
        """Test various date formats."""
        assert normalizer.normalize("01/15/2024") == "January fifteenth, twenty twenty four"
        assert normalizer.normalize("12/25/2023") == "December twenty fifth, twenty twenty three"
        assert normalizer.normalize("03/01/2024") == "March first, twenty twenty four"
        assert normalizer.normalize("2/14/2024") == "February fourteenth, twenty twenty four"
    
    def test_time_formats(self, normalizer):
        """Test time formatting."""
        assert normalizer.normalize("10:30") == "ten thirty"
        assert normalizer.normalize("10:30 AM") == "ten thirty A M"
        assert normalizer.normalize("2:45 PM") == "two forty five P M"
        assert normalizer.normalize("12:00 PM") == "twelve P M"
        assert normalizer.normalize("12:00 AM") == "twelve A M"
        assert normalizer.normalize("9:05") == "nine oh five"
    
    def test_datetime_in_context(self, normalizer):
        """Test dates and times in sentences."""
        assert normalizer.normalize("Your order will be ready at 3:30 PM") == "Your order will be ready at three thirty P M"
        assert normalizer.normalize("We're open until 10:00 PM") == "We're open until ten P M"


class TestAcronymExpansion:
    """Test acronym and abbreviation expansion."""
    
    def test_common_acronyms(self, normalizer):
        """Test common acronym expansion."""
        assert normalizer.normalize("ASAP") == "A S A P"
        assert normalizer.normalize("FAQ") == "F A Q"
        assert normalizer.normalize("USA") == "U S A"
        assert normalizer.normalize("PM") == "P M"
        assert normalizer.normalize("AM") == "A M"
    
    def test_mixed_case_preservation(self, normalizer):
        """Test that mixed case words are preserved."""
        assert normalizer.normalize("iPhone") == "iPhone"
        assert normalizer.normalize("McDonald's") == "McDonald's"
        assert normalizer.normalize("RedBar") == "RedBar"
    
    def test_acronyms_in_context(self, normalizer):
        """Test acronyms within sentences."""
        assert normalizer.normalize("Please respond ASAP") == "Please respond A S A P"
        assert normalizer.normalize("Check our FAQ page") == "Check our F A Q page"


class TestSpecialCharacterHandling:
    """Test handling of special characters and punctuation."""
    
    def test_punctuation_preservation(self, normalizer):
        """Test that punctuation is preserved."""
        assert normalizer.normalize("Hello, world!") == "Hello, world!"
        assert normalizer.normalize("What's your name?") == "What's your name?"
        assert normalizer.normalize("Well... let me think.") == "Well... let me think."
    
    def test_special_symbols(self, normalizer):
        """Test special symbol handling."""
        assert normalizer.normalize("50% off") == "fifty percent off"
        assert normalizer.normalize("A & B") == "A & B"
        assert normalizer.normalize("email@example.com") == "email@example.com"
        assert normalizer.normalize("#1 choice") == "#one choice"
    
    def test_unicode_handling(self, normalizer):
        """Test Unicode character handling."""
        assert normalizer.normalize("Café") == "Café"
        assert normalizer.normalize("Sushi 🍣") == "Sushi 🍣"
        assert normalizer.normalize("10°C") == "ten°C"


class TestComplexScenarios:
    """Test complex normalization scenarios."""
    
    def test_multiple_normalizations(self, normalizer):
        """Test text requiring multiple normalizations."""
        text = "Your order #42 totals $35.50 and will be ready at 2:30 PM"
        expected = "Your order #forty two totals thirty five dollars and fifty cents and will be ready at two thirty P M"
        assert normalizer.normalize(text) == expected
    
    def test_menu_descriptions(self, normalizer):
        """Test normalization of menu-related text."""
        text = "2 California rolls for $16.99"
        expected = "two California rolls for sixteen dollars and ninety nine cents"
        assert normalizer.normalize(text) == expected
        
        text = "Save 15% on orders over $50"
        expected = "Save fifteen percent on orders over fifty dollars"
        assert normalizer.normalize(text) == expected
    
    def test_order_confirmations(self, normalizer):
        """Test order confirmation messages."""
        text = "Order #123 confirmed for 12/25/2023 at 6:00 PM. Total: $45.00"
        expected = "Order #one hundred twenty three confirmed for December twenty fifth, twenty twenty three at six P M. Total: forty five dollars"
        assert normalizer.normalize(text) == expected
    
    def test_error_messages(self, normalizer):
        """Test error message normalization."""
        text = "Error: Item unavailable. Please call 555-1234 for assistance."
        expected = "Error: Item unavailable. Please call five five five, one two three four for assistance."
        assert normalizer.normalize(text) == expected


class TestEdgeCasesAndErrors:
    """Test edge cases and error conditions."""
    
    def test_invalid_dates(self, normalizer):
        """Test handling of invalid date formats."""
        # Invalid dates should pass through unchanged
        assert normalizer.normalize("13/45/2023") == "13/45/2023"
        assert normalizer.normalize("00/00/0000") == "00/00/0000"
    
    def test_very_large_numbers(self, normalizer):
        """Test handling of very large numbers."""
        # Numbers > 999 might not be fully spelled out
        text = "Order number 123456"
        result = normalizer.normalize(text)
        assert "Order number" in result
    
    def test_malformed_currency(self, normalizer):
        """Test malformed currency strings."""
        assert normalizer.normalize("$") == "$"
        assert normalizer.normalize("$.") == "$."
        assert normalizer.normalize("$abc") == "$abc"
    
    def test_mixed_formats(self, normalizer):
        """Test mixed format edge cases."""
        # Time without colon
        assert normalizer.normalize("1030 AM") == "1030 A M"
        
        # Partial phone numbers
        assert normalizer.normalize("Call 555") == "Call five hundred fifty five"
        
        # Multiple currency symbols
        assert normalizer.normalize("$$10") == "$$ten"
    
    def test_none_input(self, normalizer):
        """Test None input handling."""
        with pytest.raises(AttributeError):
            normalizer.normalize(None)
    
    def test_performance_with_long_text(self, normalizer):
        """Test performance with long text."""
        # Create a long text with multiple items to normalize
        long_text = " ".join([
            f"Item #{i} costs ${i}.99 and"
            for i in range(1, 101)
        ])
        
        result = normalizer.normalize(long_text)
        
        # Should complete without hanging
        assert len(result) > len(long_text)  # Should be longer due to number expansion
        assert "one dollar and ninety nine cents" in result
        assert "one hundred dollars and ninety nine cents" in result