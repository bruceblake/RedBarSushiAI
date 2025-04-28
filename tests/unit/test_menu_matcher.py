import pytest
from unittest import mock

# Import the module to be tested
from app.utils.menu_matcher import (
    preprocess_menu_for_matching,
    match_query_to_menu_items,
    calculate_match_score
)

@pytest.mark.unit
def test_preprocess_menu_for_matching():
    """
    Test the preprocessing of menu data for matching.
    
    This tests that preprocess_menu_for_matching:
    1. Correctly extracts relevant item fields
    2. Creates a searchable index of menu items
    3. Handles different menu formats
    4. Properly normalizes item names for matching
    """
    # Create a test menu
    test_menu = {
        "items": [
            {
                "name": "California Roll",
                "description": "Crab, avocado, and cucumber",
                "price": 7.95,
                "plu": "CAL-ROLL",
                "available": True
            },
            {
                "name": "Spicy Tuna Roll",
                "description": "Fresh tuna with spicy mayo",
                "price": 8.95,
                "plu": "SPICY-TUNA",
                "available": True
            },
            {
                "name": "Unavailable Item",
                "description": "This item is not available",
                "price": 9.95,
                "plu": "UNAVAILABLE",
                "available": False
            }
        ],
        "modifiers": [],
        "modifierGroups": []
    }
    
    # Preprocess the menu
    indexed_menu = preprocess_menu_for_matching(test_menu)
    
    # Verify the indexed menu
    assert indexed_menu is not None
    assert "items" in indexed_menu
    assert len(indexed_menu["items"]) == 3  # Should include all items, even unavailable ones
    
    # Verify item data is correctly extracted
    item_map = {item["plu"]: item for item in indexed_menu["items"]}
    
    assert "CAL-ROLL" in item_map
    assert "SPICY-TUNA" in item_map
    
    # Verify item fields
    california_roll = item_map["CAL-ROLL"]
    assert california_roll["name"] == "California Roll"
    assert california_roll["description"] == "Crab, avocado, and cucumber"
    assert california_roll["price"] == 7.95
    assert california_roll["available"] is True
    
    # Verify names are converted to lowercase for search
    assert "name_lower" in california_roll
    assert california_roll["name_lower"] == "california roll"
    
    # Test with an empty menu
    empty_menu = {
        "items": [],
        "modifiers": [],
        "modifierGroups": []
    }
    
    empty_indexed = preprocess_menu_for_matching(empty_menu)
    assert empty_indexed is not None
    assert "items" in empty_indexed
    assert len(empty_indexed["items"]) == 0

@pytest.mark.unit
def test_calculate_match_score():
    """
    Test the calculation of match scores.
    
    This tests that calculate_match_score:
    1. Correctly calculates similarity between queries and items
    2. Handles exact matches
    3. Handles partial matches
    4. Returns appropriate scores for non-matches
    """
    # Test exact match
    exact_score = calculate_match_score("california roll", "california roll")
    assert exact_score == 1.0  # Perfect match should be 1.0
    
    # Test case insensitivity
    case_score = calculate_match_score("California Roll", "california roll")
    assert case_score == 1.0  # Case shouldn't matter
    
    # Test partial matches
    partial_score_1 = calculate_match_score("california", "california roll")
    assert 0.7 <= partial_score_1 < 1.0  # Should be high but not perfect
    
    partial_score_2 = calculate_match_score("cali roll", "california roll")
    assert 0.7 <= partial_score_2 < 1.0  # Should be high but not perfect
    
    # Test non-matches
    non_match_score = calculate_match_score("pizza", "california roll")
    assert non_match_score < 0.5  # Should be low
    
    # Test with empty strings
    empty_score_1 = calculate_match_score("", "california roll")
    assert empty_score_1 == 0.0  # Empty query should score 0
    
    empty_score_2 = calculate_match_score("california roll", "")
    assert empty_score_2 == 0.0  # Empty target should score 0
    
    # Test with special characters
    special_score = calculate_match_score("california (roll)", "california roll")
    assert special_score > 0.8  # Special characters shouldn't affect much

@pytest.mark.unit
def test_match_query_to_menu_items():
    """
    Test matching queries to menu items.
    
    This tests that match_query_to_menu_items:
    1. Returns the best matching items for a query
    2. Respects the max_results parameter
    3. Filters by availability if requested
    4. Returns scores for each match
    5. Handles empty queries and menus
    """
    # Create a test indexed menu
    indexed_menu = {
        "items": [
            {
                "name": "California Roll",
                "name_lower": "california roll",
                "description": "Crab, avocado, and cucumber",
                "price": 7.95,
                "plu": "CAL-ROLL",
                "available": True
            },
            {
                "name": "Spicy California Roll",
                "name_lower": "spicy california roll",
                "description": "Spicy crab, avocado, and cucumber",
                "price": 8.95,
                "plu": "SPICY-CAL",
                "available": True
            },
            {
                "name": "Spicy Tuna Roll",
                "name_lower": "spicy tuna roll",
                "description": "Fresh tuna with spicy mayo",
                "price": 9.95,
                "plu": "SPICY-TUNA",
                "available": True
            },
            {
                "name": "Unavailable Roll",
                "name_lower": "unavailable roll",
                "description": "This roll is not available",
                "price": 10.95,
                "plu": "UNAVAILABLE",
                "available": False
            }
        ]
    }
    
    # Test exact match
    exact_matches = match_query_to_menu_items("California Roll", indexed_menu)
    assert len(exact_matches) > 0
    assert exact_matches[0]["plu"] == "CAL-ROLL"
    assert exact_matches[0]["score"] == 1.0
    
    # Test partial match
    partial_matches = match_query_to_menu_items("california", indexed_menu)
    assert len(partial_matches) >= 2  # Should match both california rolls
    assert partial_matches[0]["plu"] in ["CAL-ROLL", "SPICY-CAL"]
    assert partial_matches[0]["score"] >= 0.7
    
    # Test with max_results
    limited_matches = match_query_to_menu_items("roll", indexed_menu, max_results=2)
    assert len(limited_matches) == 2  # Should only return 2 results
    
    # Test with only_available
    available_matches = match_query_to_menu_items("roll", indexed_menu, only_available=True)
    assert all(match["available"] for match in available_matches)
    assert not any(match["plu"] == "UNAVAILABLE" for match in available_matches)
    
    # Test with an empty query
    empty_query_matches = match_query_to_menu_items("", indexed_menu)
    assert len(empty_query_matches) == 0  # Should return no matches
    
    # Test with an empty menu
    empty_menu_matches = match_query_to_menu_items("california", {"items": []})
    assert len(empty_menu_matches) == 0  # Should return no matches
    
    # Test with a non-matching query
    non_match = match_query_to_menu_items("pizza", indexed_menu)
    assert len(non_match) == 0  # Should return no matches if score is below threshold

@pytest.mark.unit
def test_menu_matcher_integration():
    """
    Test the integration between menu matcher components.
    
    This tests:
    1. The full pipeline from preprocessing to matching
    2. Handling of various query types
    3. Mock menu_utils to focus on the matcher logic
    """
    # Create a test menu
    test_menu = {
        "items": [
            {
                "name": "California Roll",
                "description": "Crab, avocado, and cucumber",
                "price": 7.95,
                "plu": "CAL-ROLL",
                "available": True
            },
            {
                "name": "Spicy Tuna Roll",
                "description": "Fresh tuna with spicy mayo",
                "price": 8.95,
                "plu": "SPICY-TUNA",
                "available": True
            },
            {
                "name": "Salmon Nigiri",
                "description": "Fresh salmon on rice",
                "price": 6.95,
                "plu": "SALMON-NIGIRI",
                "available": True
            },
            {
                "name": "Dragon Roll",
                "description": "Eel, crab, and avocado",
                "price": 12.95,
                "plu": "DRAGON",
                "available": False
            }
        ],
        "modifiers": [],
        "modifierGroups": []
    }
    
    # Test the full pipeline
    # Step 1: Preprocess the menu
    indexed_menu = preprocess_menu_for_matching(test_menu)
    
    # Step 2: Match various queries
    exact_query = "California Roll"
    partial_query = "tuna"
    broad_query = "roll"
    non_match_query = "cheeseburger"
    
    # Test exact matching
    exact_matches = match_query_to_menu_items(exact_query, indexed_menu)
    assert len(exact_matches) >= 1
    assert exact_matches[0]["plu"] == "CAL-ROLL"
    assert exact_matches[0]["score"] == 1.0
    
    # Test partial matching
    partial_matches = match_query_to_menu_items(partial_query, indexed_menu)
    assert len(partial_matches) >= 1
    assert partial_matches[0]["plu"] == "SPICY-TUNA"
    assert partial_matches[0]["score"] >= 0.7
    
    # Test broad matching
    broad_matches = match_query_to_menu_items(broad_query, indexed_menu)
    assert len(broad_matches) >= 3  # Should match all rolls
    # Ensure rolls are in the results
    match_plus = [m["plu"] for m in broad_matches]
    assert "CAL-ROLL" in match_plus
    assert "SPICY-TUNA" in match_plus
    
    # Test with only available items
    available_matches = match_query_to_menu_items(broad_query, indexed_menu, only_available=True)
    assert len(available_matches) >= 2  # Should match available rolls
    assert not any(match["plu"] == "DRAGON" for match in available_matches)
    
    # Test non-matching query
    non_matches = match_query_to_menu_items(non_match_query, indexed_menu)
    assert len(non_matches) == 0  # Should return no matches