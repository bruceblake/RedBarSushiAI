#!/usr/bin/env python3
"""
Debug menu item matching to understand why 'classic burger' maps to 'chicken burger'
"""

import difflib
import re

def normalize_for_matching(text):
    """Normalize text for menu matching."""
    # Remove special characters and normalize spacing
    text = re.sub(r'[^\w\s]', '', text)
    text = ' '.join(text.split())  # Normalize whitespace
    return text.lower()

def test_menu_matching():
    """Test menu matching logic with actual burger items."""
    
    # Menu items from the seed file
    burger_items = [
        "Chicken Burger",
        "Cheeseburger", 
        "Veggie Burger"
    ]
    
    search_term = "classic burger"
    print(f"🔍 Testing search for: '{search_term}'\n")
    
    search_term_lower = search_term.lower()
    normalized_search = normalize_for_matching(search_term_lower)
    print(f"Normalized search: '{normalized_search}'\n")
    
    matches = []
    
    for item_name in burger_items:
        print(f"📋 Testing against: '{item_name}'")
        
        item_name_lower = item_name.lower()
        normalized_item = normalize_for_matching(item_name_lower)
        print(f"   Normalized item: '{normalized_item}'")
        
        # Calculate different types of matching scores
        exact_match = 1.0 if search_term_lower == item_name_lower or normalized_search == normalized_item else 0.0
        contains_match = 0.8 if search_term_lower in item_name_lower or normalized_search in normalized_item else 0.0
        reverse_contains = 0.7 if item_name_lower in search_term_lower or normalized_item in normalized_search else 0.0
        
        # Word-level matching for better semantic accuracy
        search_words = set(normalized_search.split())
        item_words = set(normalized_item.split())
        
        # Calculate word overlap
        common_words = search_words.intersection(item_words)
        word_overlap_score = len(common_words) / max(len(search_words), 1) if search_words else 0.0
        
        # Use difflib for sequence matching BUT only if word overlap is reasonable
        sequence_similarity = difflib.SequenceMatcher(None, normalized_search, normalized_item).ratio()
        
        # Penalize pure sequence similarity when there's no meaningful word overlap
        if word_overlap_score < 0.5 and sequence_similarity < 0.8:
            sequence_similarity *= 0.3  # Heavy penalty for misleading matches
        
        # Calculate final confidence score
        confidence = max(
            exact_match,
            contains_match,
            reverse_contains,
            word_overlap_score * 0.9,  # High weight for word-level matching
            sequence_similarity * 0.6  # Reduced weight for sequence matching
        )
        
        print(f"   📊 Scores:")
        print(f"      Exact match: {exact_match}")
        print(f"      Contains match: {contains_match}")
        print(f"      Reverse contains: {reverse_contains}")
        print(f"      Word overlap: {word_overlap_score:.3f} (common: {common_words})")
        print(f"      Sequence similarity: {sequence_similarity:.3f}")
        print(f"      Weighted word overlap: {word_overlap_score * 0.9:.3f}")
        print(f"      Weighted sequence: {sequence_similarity * 0.6:.3f}")
        print(f"      🎯 Final confidence: {confidence:.3f}")
        
        if confidence >= 0.4:
            matches.append({
                'item': item_name,
                'confidence': confidence
            })
        print()
    
    # Sort by confidence
    matches.sort(key=lambda x: x['confidence'], reverse=True)
    
    print("🏆 FINAL RANKING:")
    for i, match in enumerate(matches, 1):
        print(f"   {i}. {match['item']} (confidence: {match['confidence']:.3f})")
    
    if matches:
        print(f"\n🎯 Best match: '{matches[0]['item']}' with confidence {matches[0]['confidence']:.3f}")
    else:
        print("\n❌ No matches found")

if __name__ == "__main__":
    test_menu_matching()