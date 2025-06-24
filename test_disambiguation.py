#!/usr/bin/env python3
"""
Test script for disambiguation logic in RedBarSushiAI.

This script demonstrates how the system handles ambiguous menu requests
and guides users to clarify their choices.
"""

import asyncio
from typing import List, Dict, Any

from app.utils.disambiguation import (
    DisambiguationType,
    DisambiguationCandidate,
    DisambiguationContext,
    disambiguation_detector,
    disambiguation_resolver
)


def create_test_menu_items() -> List[Dict[str, Any]]:
    """Create test menu items that could cause ambiguity."""
    return [
        # Multiple salmon items
        {"id": "1", "name": "Salmon Roll", "price": 12.00, "category": "Rolls", "plu": "ROLL001"},
        {"id": "2", "name": "Salmon Nigiri", "price": 8.00, "category": "Nigiri", "plu": "NIGIRI001"},
        {"id": "3", "name": "Salmon Sashimi", "price": 14.00, "category": "Sashimi", "plu": "SASH001"},
        
        # Multiple spicy items
        {"id": "4", "name": "Spicy Tuna Roll", "price": 13.00, "category": "Rolls", "plu": "ROLL002"},
        {"id": "5", "name": "Spicy Salmon Roll", "price": 13.50, "category": "Rolls", "plu": "ROLL003"},
        {"id": "6", "name": "Spicy Yellowtail Roll", "price": 14.00, "category": "Rolls", "plu": "ROLL004"},
        
        # Multiple tempura items
        {"id": "7", "name": "Shrimp Tempura Roll", "price": 15.00, "category": "Rolls", "plu": "ROLL005"},
        {"id": "8", "name": "Vegetable Tempura", "price": 10.00, "category": "Appetizers", "plu": "APP001"},
        {"id": "9", "name": "Tempura Udon", "price": 16.00, "category": "Noodles", "plu": "NOOD001"},
        
        # Similar named items
        {"id": "10", "name": "California Roll", "price": 11.00, "category": "Rolls", "plu": "ROLL006"},
        {"id": "11", "name": "California Deluxe Roll", "price": 14.00, "category": "Rolls", "plu": "ROLL007"},
    ]


async def test_disambiguation_detection():
    """Test disambiguation detection with various queries."""
    print("Testing Disambiguation Detection\n" + "="*50 + "\n")
    
    test_cases = [
        ("salmon", "Customer wants 'salmon' - multiple types available"),
        ("spicy roll", "Customer wants 'spicy roll' - multiple options"),
        ("tempura", "Customer wants 'tempura' - different categories"),
        ("california", "Customer wants 'california' - similar names"),
        ("tuna", "Customer wants 'tuna' - should find one match"),
    ]
    
    menu_items = create_test_menu_items()
    
    for query, description in test_cases:
        print(f"Test: {description}")
        print(f"Query: '{query}'")
        
        # Simulate matches with confidence scores
        matches = []
        for item in menu_items:
            confidence = 0
            query_lower = query.lower()
            name_lower = item["name"].lower()
            
            if query_lower == name_lower:
                confidence = 1.0
            elif query_lower in name_lower:
                confidence = 0.8
            elif all(word in name_lower for word in query_lower.split()):
                confidence = 0.7
            elif any(word in name_lower for word in query_lower.split()):
                confidence = 0.6
                
            if confidence > 0.5:
                match = item.copy()
                match["confidence"] = confidence
                matches.append(match)
        
        # Check if disambiguation is needed
        needs_disambig, disambig_type = disambiguation_detector.needs_disambiguation(
            matches, query
        )
        
        print(f"Matches found: {len(matches)}")
        if matches:
            for m in matches[:3]:  # Show top 3
                print(f"  - {m['name']} (confidence: {m['confidence']:.2f})")
        
        print(f"Needs disambiguation: {needs_disambig}")
        if disambig_type:
            print(f"Type: {disambig_type.value}")
        
        # If disambiguation needed, show clarification
        if needs_disambig:
            context = disambiguation_detector.create_context(
                matches, query, disambig_type
            )
            clarification = disambiguation_resolver.generate_clarification(context)
            print(f"Clarification: {clarification}")
        
        print("-" * 50 + "\n")


async def test_disambiguation_resolution():
    """Test how the system resolves user responses to clarification."""
    print("\nTesting Disambiguation Resolution\n" + "="*50 + "\n")
    
    # Create a disambiguation context for "salmon"
    candidates = [
        DisambiguationCandidate(
            item_id="1", name="Salmon Roll", display_name="Salmon Roll",
            category="Rolls", price=12.00, confidence=0.8, plu="ROLL001"
        ),
        DisambiguationCandidate(
            item_id="2", name="Salmon Nigiri", display_name="Salmon Nigiri",
            category="Nigiri", price=8.00, confidence=0.8, plu="NIGIRI001"
        ),
        DisambiguationCandidate(
            item_id="3", name="Salmon Sashimi", display_name="Salmon Sashimi",
            category="Sashimi", price=14.00, confidence=0.8, plu="SASH001"
        ),
    ]
    
    context = DisambiguationContext(
        query="salmon",
        candidates=candidates,
        disambiguation_type=DisambiguationType.SIMILAR_NAMES
    )
    
    # Test various user responses
    test_responses = [
        ("the roll", "Should match Salmon Roll"),
        ("nigiri", "Should match Salmon Nigiri"),
        ("the $14 one", "Should match by price (Sashimi)"),
        ("the second one", "Should match by position (Nigiri)"),
        ("sashimi please", "Should match Salmon Sashimi"),
        ("the cheapest", "Not implemented but interesting case"),
        ("xyz", "Should not match anything"),
    ]
    
    print("Disambiguation context: Customer said 'salmon'")
    print(f"Clarification: {disambiguation_resolver.generate_clarification(context)}\n")
    
    for response, expected in test_responses:
        print(f"User response: '{response}' ({expected})")
        
        matched = disambiguation_resolver.match_response(response, context)
        if matched:
            print(f"✓ Matched: {matched.display_name} - ${matched.price:.2f}")
        else:
            print("✗ No match found")
        print()


async def test_conversation_flow():
    """Test a complete conversation flow with disambiguation."""
    print("\nTesting Complete Conversation Flow\n" + "="*50 + "\n")
    
    # Simulate a conversation
    conversation = [
        ("I'd like to order some salmon", "Initial ambiguous request"),
        ("the roll please", "Clarification response"),
        ("And add something spicy", "Another ambiguous request"),
        ("the spicy tuna", "Clarification response"),
    ]
    
    print("Simulated conversation with disambiguation:\n")
    
    for i, (utterance, description) in enumerate(conversation):
        print(f"Customer: {utterance}")
        print(f"({description})")
        
        if i % 2 == 0:  # Ambiguous request
            print("System: [Detects ambiguity and asks for clarification]")
        else:  # Clarification
            print("System: [Resolves disambiguation and confirms item]")
        print()


async def main():
    """Run all disambiguation tests."""
    await test_disambiguation_detection()
    await test_disambiguation_resolution()
    await test_conversation_flow()
    
    print("\nDisambiguation Implementation Summary\n" + "="*50)
    print("""
The disambiguation system helps ensure accurate order capture by:

1. Detecting when multiple items match a query
2. Generating natural clarification questions
3. Understanding various response types (name, price, position, category)
4. Limiting clarification attempts to avoid frustration
5. Maintaining conversation context during disambiguation

This creates a more natural ordering experience and reduces errors.
    """)


if __name__ == "__main__":
    asyncio.run(main()