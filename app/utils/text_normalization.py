"""
Text normalization module for TTS preparation.

This module processes AI-generated text to ensure natural-sounding
speech synthesis by handling numbers, dates, currency, and special characters.
"""

import re
import logging

logger = logging.getLogger(__name__)


class TextNormalizer:
    """Handles text normalization for TTS processing."""

    def __init__(self):
        """Initialize the text normalizer with conversion rules."""
        self.acronyms = {
            "ASAP": "as soon as possible",
            "ETA": "estimated time of arrival",
            "ID": "identification",
            "OK": "okay",
            "Dr.": "Doctor",
            "Mr.": "Mister",
            "Mrs.": "Missus",
            "Ms.": "Miss",
            "St.": "Street",
            "Ave.": "Avenue",
            "Blvd.": "Boulevard",
            "AM": "A M",
            "PM": "P M",
            "FAQ": "frequently asked questions",
            "CEO": "chief executive officer",
            "USA": "United States of America",
            "UK": "United Kingdom",
        }

        self.special_chars = {
            "&": "and",
            "%": "percent",
            "#": "number",
            "@": "at",
            "+": "plus",
            "-": "minus",
            "=": "equals",
            "$": "dollars",
            "€": "euros",
            "£": "pounds",
            "¥": "yen",
        }

    def normalize(self, text: str) -> str:
        """
        Normalize text for TTS processing.

        Args:
            text: Raw text from AI

        Returns:
            Normalized text ready for TTS
        """
        # Process in order of priority
        text = self._expand_acronyms(text)
        text = self._normalize_currency(text)
        text = self._normalize_numbers(text)
        text = self._normalize_phone_numbers(text)
        text = self._normalize_dates(text)
        text = self._normalize_times(text)
        text = self._replace_special_chars(text)
        text = self._add_appropriate_pauses(text)

        return text.strip()

    def _expand_acronyms(self, text: str) -> str:
        """Expand common acronyms and abbreviations."""
        for acronym, expansion in self.acronyms.items():
            # Match whole words only
            pattern = r"\b" + re.escape(acronym) + r"\b"
            text = re.sub(pattern, expansion, text, flags=re.IGNORECASE)
        return text

    def _normalize_currency(self, text: str) -> str:
        """Convert currency amounts to speakable format."""
        # Match currency patterns like $10.50, $1,234.56
        currency_pattern = r"\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)"

        def currency_replacer(match):
            amount = match.group(1)
            # Remove commas
            amount = amount.replace(",", "")

            if "." in amount:
                dollars, cents = amount.split(".")
                if cents == "00":
                    return f"{self._number_to_words(int(dollars))} dollars"
                else:
                    return f"{self._number_to_words(int(dollars))} dollars and {self._number_to_words(int(cents))} cents"
            else:
                return f"{self._number_to_words(int(amount))} dollars"

        text = re.sub(currency_pattern, currency_replacer, text)
        return text

    def _normalize_numbers(self, text: str) -> str:
        """Convert numbers to words for natural speech."""
        # Match standalone numbers (not part of dates, times, or phone numbers)
        # number_pattern = r'\b(\d+)\b' # Removed as unused

        def number_replacer(match):
            num = int(match.group(1))
            # For order numbers or IDs, read digit by digit
            if len(match.group(1)) > 4 or (
                len(match.group(1)) == 3 and match.group(1)[0] != "0"
            ):
                # Read as individual digits for things like order 123
                return " ".join(match.group(1))
            else:
                # Convert to words for small numbers
                return self._number_to_words(num)

        # Avoid replacing numbers in dates, times, and phone numbers
        # by using negative lookahead/lookbehind
        safe_number_pattern = r"(?<!\d)(?<!/)(\d{1,3})(?![\d:/])"
        text = re.sub(safe_number_pattern, number_replacer, text)

        return text

    def _normalize_phone_numbers(self, text: str) -> str:
        """Format phone numbers for natural speech."""
        # Match US phone numbers
        phone_patterns = [
            (r"\b(\d{3})[-.]?(\d{3})[-.]?(\d{4})\b", r"\1, \2, \3"),
            (r"\b1[-.]?(\d{3})[-.]?(\d{3})[-.]?(\d{4})\b", r"one, \1, \2, \3"),
        ]

        for pattern, replacement in phone_patterns:
            text = re.sub(pattern, replacement, text)

        return text

    def _normalize_dates(self, text: str) -> str:
        """Convert dates to speakable format."""
        # Match MM/DD/YYYY or MM-DD-YYYY
        date_pattern = r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b"

        def date_replacer(match):
            month, day, year = match.groups()
            month_names = [
                "",
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            ]

            try:
                month_name = month_names[int(month)]
                day_word = self._ordinal_number(int(day))
                # Split year for more natural speech
                if year.startswith("20"):
                    year_word = f"twenty {self._number_to_words(int(year[2:]))}"
                else:
                    year_word = self._number_to_words(int(year))

                return f"{month_name} {day_word}, {year_word}"
            except (ValueError, IndexError):
                return match.group(0)

        text = re.sub(date_pattern, date_replacer, text)
        return text

    def _normalize_times(self, text: str) -> str:
        """Convert times to speakable format."""
        # Match HH:MM format
        time_pattern = r"\b(\d{1,2}):(\d{2})(?:\s*(AM|PM))?\b"

        def time_replacer(match):
            hour, minute, ampm = match.groups()
            hour = int(hour)
            minute = int(minute)

            if ampm:
                ampm_text = "A M" if ampm.upper() == "AM" else "P M"
            else:
                ampm_text = ""

            # Convert 24-hour to 12-hour if needed
            if not ampm and hour > 12:
                hour -= 12
                ampm_text = "P M"
            elif not ampm and hour == 0:
                hour = 12
                ampm_text = "A M"

            hour_word = self._number_to_words(hour)

            if minute == 0:
                if ampm_text:
                    return f"{hour_word} {ampm_text}"
                else:
                    return f"{hour_word} o'clock"
            elif minute < 10:
                minute_word = f"oh {self._number_to_words(minute)}"
            else:
                minute_word = self._number_to_words(minute)

            return f"{hour_word} {minute_word} {ampm_text}".strip()

        text = re.sub(time_pattern, time_replacer, text)
        return text

    def _replace_special_chars(self, text: str) -> str:
        """Replace special characters with speakable equivalents."""
        for char, replacement in self.special_chars.items():
            text = text.replace(char, f" {replacement} ")

        # Clean up multiple spaces
        text = re.sub(r"\s+", " ", text)
        return text

    def _add_appropriate_pauses(self, text: str) -> str:
        """Add punctuation for natural pauses in speech."""
        # Add commas before conjunctions for natural pauses
        conjunctions = ["and", "or", "but", "so", "yet"]
        for conj in conjunctions:
            pattern = rf"(\w)\s+{conj}\s+"
            text = re.sub(pattern, rf"\1, {conj} ", text, flags=re.IGNORECASE)

        # Ensure sentences end with proper punctuation
        if text and text[-1] not in ".!?":
            text += "."

        return text

    def _number_to_words(self, num: int) -> str:
        """Convert a number to words."""
        if num == 0:
            return "zero"

        # Define word representations
        ones = [
            "",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
        ]
        teens = [
            "ten",
            "eleven",
            "twelve",
            "thirteen",
            "fourteen",
            "fifteen",
            "sixteen",
            "seventeen",
            "eighteen",
            "nineteen",
        ]
        tens = [
            "",
            "",
            "twenty",
            "thirty",
            "forty",
            "fifty",
            "sixty",
            "seventy",
            "eighty",
            "ninety",
        ]

        if num < 10:
            return ones[num]
        elif num < 20:
            return teens[num - 10]
        elif num < 100:
            return tens[num // 10] + ("" if num % 10 == 0 else " " + ones[num % 10])
        elif num < 1000:
            return (
                ones[num // 100]
                + " hundred"
                + ("" if num % 100 == 0 else " " + self._number_to_words(num % 100))
            )
        else:
            # For larger numbers, just return the digits
            return str(num)

    def _ordinal_number(self, num: int) -> str:
        """Convert a number to its ordinal form."""
        if 10 <= num % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(num % 10, "th")

        return self._number_to_words(num) + suffix


# Create a global instance
# text_normalizer = TextNormalizer() # Removed as normalize_for_tts is removed

# normalize_for_tts function removed as unused
