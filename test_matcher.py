"""
Test script for the menu matcher fuzzy matching.
"""

import sys
import json

# Create a test menu data 
test_menu = {
    'items': [
        {'name': 'Ham Burger', 'price': 12.99, 'is_category': False},
        {'name': 'California Roll', 'price': 9.99, 'is_category': False},
        {'name': 'Spicy Tuna Roll', 'price': 10.99, 'is_category': False},
        {'name': 'Philadelphia Roll', 'price': 11.99, 'is_category': False},
        {'name': 'Vegetable Tempura', 'price': 8.99, 'is_category': False},
        {'name': 'Chicken Teriyaki', 'price': 13.99, 'is_category': False},
        {'name': 'Main Menu', 'is_category': True}
    ]
}

class TestMenuMatcher:
    def __init__(self, menu_data):
        self.menu_data = menu_data
    
    def find_menu_item(self, item_name):
        print(f'Searching for: {item_name}')
        
        # Try exact match
        exact_match = self._find_exact_match(item_name)
        if exact_match:
            print(f'Found exact match: {exact_match["name"]}')
            return exact_match
            
        # Try normalized match
        normalized_match = self._find_normalized_match(item_name)
        if normalized_match:
            print(f'Found normalized match: {normalized_match["name"]} (spaces removed)')
            return normalized_match
            
        # Try term-based match
        term_match = self._find_term_match(item_name)
        if term_match:
            print(f'Found term-based match: {term_match["name"]}')
            return term_match
            
        # Try Levenshtein-based match
        lev_match = self._find_levenshtein_match(item_name)
        if lev_match:
            print(f'Found similarity match: {lev_match["name"]}')
            return lev_match
            
        print('No match found')
        return None
    
    def _find_exact_match(self, item_name):
        item_name_lower = item_name.lower()
        for item in self.menu_data['items']:
            if not item.get('is_category', False) and item.get('name', '').lower() == item_name_lower:
                return item
        return None
    
    def _find_normalized_match(self, item_name):
        item_name_normalized = item_name.lower().replace(' ', '')
        for item in self.menu_data['items']:
            if not item.get('is_category', False):
                menu_item_normalized = item.get('name', '').lower().replace(' ', '')
                if menu_item_normalized == item_name_normalized:
                    return item
        return None
    
    def _find_term_match(self, item_name):
        item_terms = set(item_name.lower().split())
        best_match = None
        best_score = 0
        
        for item in self.menu_data['items']:
            if not item.get('is_category', False):
                menu_terms = set(item.get('name', '').lower().split())
                common_terms = item_terms.intersection(menu_terms)
                
                if common_terms:
                    score = len(common_terms) / max(len(item_terms), len(menu_terms))
                    if score > best_score and score >= 0.5:
                        best_score = score
                        best_match = item
        
        return best_match
    
    def _levenshtein_distance(self, s1, s2):
        if s1 == s2:
            return 0
        
        if len(s1) == 0:
            return len(s2)
        if len(s2) == 0:
            return len(s1)
        
        # Create matrix
        matrix = [[0 for _ in range(len(s2) + 1)] for _ in range(len(s1) + 1)]
        
        # Fill first row and column
        for i in range(len(s1) + 1):
            matrix[i][0] = i
        for j in range(len(s2) + 1):
            matrix[0][j] = j
        
        # Fill the rest
        for i in range(1, len(s1) + 1):
            for j in range(1, len(s2) + 1):
                cost = 0 if s1[i-1] == s2[j-1] else 1
                matrix[i][j] = min(
                    matrix[i-1][j] + 1,      # deletion
                    matrix[i][j-1] + 1,      # insertion
                    matrix[i-1][j-1] + cost  # substitution
                )
        
        return matrix[len(s1)][len(s2)]
    
    def _calculate_similarity(self, s1, s2):
        distance = self._levenshtein_distance(s1, s2)
        max_len = max(len(s1), len(s2))
        if max_len == 0:
            return 0.0
        return 1.0 - (distance / max_len)
    
    def _find_levenshtein_match(self, item_name):
        item_name_lower = item_name.lower()
        best_match = None
        best_similarity = 0
        
        for item in self.menu_data['items']:
            if not item.get('is_category', False):
                menu_item_lower = item.get('name', '').lower()
                
                # Only calculate similarity if length difference is not too large
                if abs(len(menu_item_lower) - len(item_name_lower)) <= min(len(menu_item_lower), len(item_name_lower)):
                    similarity = self._calculate_similarity(menu_item_lower, item_name_lower)
                    if similarity > best_similarity and similarity >= 0.7:
                        best_similarity = similarity
                        best_match = item
        
        return best_match

def main():
    # Create a matcher with our test menu
    matcher = TestMenuMatcher(test_menu)
    
    # Test cases
    test_cases = [
        'hamburger',          # Should match 'Ham Burger' (normalized)
        'cali roll',          # Should match 'California Roll' (term-based)
        'spcy tuna',          # Should match 'Spicy Tuna Roll' (typo + term-based)
        'phili roll',         # Should match 'Philadelphia Roll' (abbreviation + term-based)
        'hambarger',          # Should match 'Ham Burger' (typo - Levenshtein)
        'vegetable tempora',  # Should match 'Vegetable Tempura' (typo - Levenshtein)
    ]
    
    print('Testing menu matching with optimized fuzzy matching:')
    print('---------------------------------------------------')
    for i, test in enumerate(test_cases):
        print(f'\nTest {i+1}: "{test}"')
        result = matcher.find_menu_item(test)
        match = result.get('name') if result else 'No match found'
        price = f'${result.get("price", 0):.2f}' if result else 'N/A'
        print(f'Result: "{match}" - {price}\n')

if __name__ == "__main__":
    main()
