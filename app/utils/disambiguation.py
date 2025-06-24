"""
Disambiguation utilities for handling ambiguous user requests.

This module provides functionality for detecting and resolving ambiguous
menu item requests in natural conversation.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from app.utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class DisambiguationType(Enum):
    """Types of disambiguation scenarios."""
    MULTIPLE_EXACT = "multiple_exact"  # Multiple items with same name
    SIMILAR_NAMES = "similar_names"    # Items with similar names
    CATEGORY_AMBIGUOUS = "category"    # Ambiguous category reference
    MODIFIER_AMBIGUOUS = "modifier"    # Ambiguous modifier
    SIZE_AMBIGUOUS = "size"           # Ambiguous size
    QUANTITY_AMBIGUOUS = "quantity"   # Unclear quantity


@dataclass
class DisambiguationCandidate:
    """Represents a potential match for disambiguation."""
    item_id: str
    name: str
    display_name: str
    category: str
    price: float
    confidence: float
    plu: Optional[str] = None
    description: Optional[str] = None
    modifiers: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "item_id": self.item_id,
            "name": self.name,
            "display_name": self.display_name,
            "category": self.category,
            "price": self.price,
            "confidence": self.confidence,
            "plu": self.plu,
            "description": self.description,
            "modifiers": self.modifiers
        }


@dataclass
class DisambiguationContext:
    """Context for an ongoing disambiguation."""
    query: str
    candidates: List[DisambiguationCandidate]
    disambiguation_type: DisambiguationType
    attempt_count: int = 0
    max_attempts: int = 2
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "query": self.query,
            "candidates": [c.to_dict() for c in self.candidates],
            "disambiguation_type": self.disambiguation_type.value,
            "attempt_count": self.attempt_count,
            "max_attempts": self.max_attempts
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DisambiguationContext":
        """Create from dictionary representation."""
        candidates = [
            DisambiguationCandidate(**c) for c in data.get("candidates", [])
        ]
        return cls(
            query=data["query"],
            candidates=candidates,
            disambiguation_type=DisambiguationType(data["disambiguation_type"]),
            attempt_count=data.get("attempt_count", 0),
            max_attempts=data.get("max_attempts", 2)
        )


class DisambiguationDetector:
    """Detects when disambiguation is needed."""
    
    def __init__(
        self,
        similarity_threshold: float = 0.7,
        ambiguity_threshold: float = 0.85
    ):
        """
        Initialize the disambiguation detector.
        
        Args:
            similarity_threshold: Minimum confidence for considering items similar
            ambiguity_threshold: Maximum confidence difference to trigger disambiguation
        """
        self.similarity_threshold = similarity_threshold
        self.ambiguity_threshold = ambiguity_threshold
    
    def needs_disambiguation(
        self,
        matches: List[Dict[str, Any]],
        query: str
    ) -> Tuple[bool, Optional[DisambiguationType]]:
        """
        Determine if disambiguation is needed.
        
        Args:
            matches: List of potential matches with confidence scores
            query: Original user query
            
        Returns:
            Tuple of (needs_disambiguation, disambiguation_type)
        """
        if not matches:
            return False, None
        
        # Filter matches above similarity threshold
        viable_matches = [
            m for m in matches 
            if m.get("confidence", 0) >= self.similarity_threshold
        ]
        
        if len(viable_matches) <= 1:
            return False, None
        
        # Check for multiple exact matches
        exact_matches = [m for m in viable_matches if m.get("confidence", 0) >= 0.95]
        if len(exact_matches) > 1:
            logger.info(
                f"Multiple exact matches found for '{query}' (count: {len(exact_matches)})"
            )
            return True, DisambiguationType.MULTIPLE_EXACT
        
        # Check if top matches are too close in confidence
        sorted_matches = sorted(
            viable_matches,
            key=lambda x: x.get("confidence", 0),
            reverse=True
        )
        
        if len(sorted_matches) >= 2:
            top_confidence = sorted_matches[0].get("confidence", 0)
            second_confidence = sorted_matches[1].get("confidence", 0)
            
            if top_confidence - second_confidence < (1 - self.ambiguity_threshold):
                logger.info(
                    f"Similar confidence scores for '{query}' (top: {top_confidence}, second: {second_confidence})"
                )
                return True, DisambiguationType.SIMILAR_NAMES
        
        # Check for category ambiguity
        query_lower = query.lower()
        category_terms = ["roll", "sushi", "sashimi", "appetizer", "drink", "special"]
        if any(term in query_lower for term in category_terms) and len(viable_matches) > 3:
            return True, DisambiguationType.CATEGORY_AMBIGUOUS
        
        return False, None
    
    def create_context(
        self,
        matches: List[Dict[str, Any]],
        query: str,
        disambiguation_type: DisambiguationType
    ) -> DisambiguationContext:
        """
        Create a disambiguation context from matches.
        
        Args:
            matches: List of potential matches
            query: Original user query
            disambiguation_type: Type of disambiguation needed
            
        Returns:
            DisambiguationContext object
        """
        # Convert matches to candidates
        candidates = []
        for match in matches:
            candidate = DisambiguationCandidate(
                item_id=match.get("id", ""),
                name=match.get("name", ""),
                display_name=match.get("display_name", match.get("name", "")),
                category=match.get("category", ""),
                price=float(match.get("price", 0)),
                confidence=float(match.get("confidence", 0)),
                plu=match.get("plu"),
                description=match.get("description"),
                modifiers=match.get("modifiers", [])
            )
            candidates.append(candidate)
        
        # Sort by confidence
        candidates.sort(key=lambda x: x.confidence, reverse=True)
        
        # Limit to top candidates for clarity
        max_candidates = 3 if disambiguation_type == DisambiguationType.SIMILAR_NAMES else 5
        candidates = candidates[:max_candidates]
        
        return DisambiguationContext(
            query=query,
            candidates=candidates,
            disambiguation_type=disambiguation_type
        )


class DisambiguationResolver:
    """Generates clarification questions and processes responses."""
    
    def generate_clarification(
        self,
        context: DisambiguationContext
    ) -> str:
        """
        Generate a natural clarification question.
        
        Args:
            context: The disambiguation context
            
        Returns:
            Natural language clarification question
        """
        candidates = context.candidates
        query = context.query
        
        if context.disambiguation_type == DisambiguationType.MULTIPLE_EXACT:
            # Multiple items with exact same name
            if all(c.category == candidates[0].category for c in candidates):
                # Same category, differentiate by price or description
                return self._generate_price_disambiguation(candidates, query)
            else:
                # Different categories
                return self._generate_category_disambiguation(candidates, query)
        
        elif context.disambiguation_type == DisambiguationType.SIMILAR_NAMES:
            # Similar but not exact matches
            return self._generate_similar_items_disambiguation(candidates, query)
        
        elif context.disambiguation_type == DisambiguationType.CATEGORY_AMBIGUOUS:
            # User mentioned a category
            return self._generate_category_list_disambiguation(candidates, query)
        
        else:
            # Generic disambiguation
            return self._generate_generic_disambiguation(candidates, query)
    
    def _generate_price_disambiguation(
        self,
        candidates: List[DisambiguationCandidate],
        query: str
    ) -> str:
        """Generate disambiguation based on price differences."""
        if len(candidates) == 2:
            return (
                f"I found two {candidates[0].display_name} options. "
                f"Did you want the one for ${candidates[0].price:.2f} "
                f"or the one for ${candidates[1].price:.2f}?"
            )
        else:
            options = [f"${c.price:.2f}" for c in candidates[:3]]
            return (
                f"We have several {candidates[0].display_name} options "
                f"at different prices: {', '.join(options)}. "
                f"Which price point would you prefer?"
            )
    
    def _generate_category_disambiguation(
        self,
        candidates: List[DisambiguationCandidate],
        query: str
    ) -> str:
        """Generate disambiguation based on categories."""
        if len(candidates) == 2:
            return (
                f"Did you mean the {candidates[0].display_name} "
                f"from our {candidates[0].category} menu, "
                f"or the {candidates[1].display_name} "
                f"from our {candidates[1].category} selection?"
            )
        else:
            categories = list(set(c.category for c in candidates))
            return (
                f"I found '{query}' in multiple categories: "
                f"{', '.join(categories)}. "
                f"Which type were you looking for?"
            )
    
    def _generate_similar_items_disambiguation(
        self,
        candidates: List[DisambiguationCandidate],
        query: str
    ) -> str:
        """Generate disambiguation for similar items."""
        if len(candidates) == 2:
            return (
                f"Did you mean the {candidates[0].display_name} "
                f"or the {candidates[1].display_name}?"
            )
        else:
            names = [c.display_name for c in candidates[:3]]
            return (
                f"I found several items similar to '{query}'. "
                f"Did you mean: {', '.join(names[:-1])}, or {names[-1]}?"
            )
    
    def _generate_category_list_disambiguation(
        self,
        candidates: List[DisambiguationCandidate],
        query: str
    ) -> str:
        """Generate list of items in a category."""
        category = candidates[0].category if candidates else "items"
        names_with_prices = [
            f"{c.display_name} (${c.price:.2f})" 
            for c in candidates[:4]
        ]
        
        list_text = ", ".join(names_with_prices[:-1])
        if len(candidates) > 4:
            return (
                f"We have several {category}s including: {list_text}, "
                f"and {names_with_prices[-1]}. "
                f"Which one would you like?"
            )
        else:
            return (
                f"Our {category} options include: {list_text}, "
                f"and {names_with_prices[-1]}. "
                f"Which sounds good to you?"
            )
    
    def _generate_generic_disambiguation(
        self,
        candidates: List[DisambiguationCandidate],
        query: str
    ) -> str:
        """Generate generic disambiguation."""
        names = [c.display_name for c in candidates[:3]]
        if len(names) == 2:
            return f"Did you mean {names[0]} or {names[1]}?"
        else:
            return (
                f"I found several options. Did you mean: "
                f"{', '.join(names[:-1])}, or {names[-1]}?"
            )
    
    def match_response(
        self,
        response: str,
        context: DisambiguationContext
    ) -> Optional[DisambiguationCandidate]:
        """
        Match user's clarification response to a candidate.
        
        Args:
            response: User's clarification response
            context: The disambiguation context
            
        Returns:
            Matched candidate or None
        """
        response_lower = response.lower().strip()
        
        # Check for price mentions
        import re
        price_match = re.search(r'\$?(\d+\.?\d*)', response)
        if price_match:
            target_price = float(price_match.group(1))
            # Find closest price match
            best_match = min(
                context.candidates,
                key=lambda c: abs(c.price - target_price)
            )
            if abs(best_match.price - target_price) < 1.0:  # Within $1
                logger.info(
                    f"Matched by price: ${target_price}",
                    item=best_match.name
                )
                return best_match
        
        # Check for category mentions
        for candidate in context.candidates:
            if candidate.category.lower() in response_lower:
                logger.info(
                    f"Matched by category: {candidate.category}",
                    item=candidate.name
                )
                return candidate
        
        # Check for name mentions
        for candidate in context.candidates:
            # Check display name
            if candidate.display_name.lower() in response_lower:
                logger.info(
                    f"Matched by display name: {candidate.display_name}",
                    item=candidate.name
                )
                return candidate
            
            # Check partial matches
            name_words = candidate.display_name.lower().split()
            if any(word in response_lower for word in name_words if len(word) > 3):
                logger.info(
                    f"Matched by partial name: {candidate.display_name}",
                    item=candidate.name
                )
                return candidate
        
        # Check for position words (first, second, last)
        position_words = {
            "first": 0, "1st": 0, "one": 0,
            "second": 1, "2nd": 1, "two": 1,
            "third": 2, "3rd": 2, "three": 2,
            "last": -1
        }
        
        for word, index in position_words.items():
            if word in response_lower and abs(index) < len(context.candidates):
                logger.info(
                    f"Matched by position: {word}",
                    item=context.candidates[index].name
                )
                return context.candidates[index]
        
        return None


# Singleton instances
disambiguation_detector = DisambiguationDetector()
disambiguation_resolver = DisambiguationResolver()