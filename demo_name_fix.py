#!/usr/bin/env python3
"""Demonstrate the name recognition fix."""

import re
from typing import Optional

def extract_name_with_regex(text: str) -> Optional[str]:
    """Extract name from text using regex patterns."""
    print(f"\nAttempting regex name extraction from: '{text}'")
    
    # Normalize text
    text = text.strip()
    
    # Pattern 1: Just a single name (e.g., "Bruce", "Sarah")
    if re.match(r'^[A-Z][a-z]+$', text):
        print(f"✓ Regex matched single name pattern: '{text}'")
        return text
    
    # Pattern 2: "My name is X" variations
    patterns = [
        r"my name is ([A-Z][a-z]+)",
        r"i'm ([A-Z][a-z]+)",
        r"i am ([A-Z][a-z]+)",
        r"this is ([A-Z][a-z]+)",
        r"it's ([A-Z][a-z]+)",
        r"([A-Z][a-z]+) here",
        r"call me ([A-Z][a-z]+)",
        r"i go by ([A-Z][a-z]+)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).capitalize()
            print(f"✓ Regex matched pattern '{pattern}': '{name}'")
            return name
    
    # Pattern 3: Look for any capitalized word that could be a name
    words = text.split()
    for word in words:
        # Check if it's a capitalized word that looks like a name
        if re.match(r'^[A-Z][a-z]+$', word) and len(word) > 1:
            print(f"✓ Regex found potential name: '{word}'")
            return word
    
    print("✗ No name found via regex")
    return None

# Test cases
test_inputs = [
    "Bruce",
    "My name is Sarah",
    "I'm John",
    "This is Mike",
    "It's David",
    "bruce",  # lowercase
    "Hi, I'm Jennifer",
    "Hello, my name is Robert",
    "Hello there",  # No name
    "123",  # Not a name
]

print("=" * 60)
print("NAME EXTRACTION DEMO")
print("=" * 60)

for test_input in test_inputs:
    result = extract_name_with_regex(test_input)
    if result:
        print(f"➜ Extracted: '{result}'")
        print(f"➜ Response would be: 'Nice to meet you, {result}! How can I help you today?'")
    else:
        print(f"➜ No name found - would ask again")
    print("-" * 40)