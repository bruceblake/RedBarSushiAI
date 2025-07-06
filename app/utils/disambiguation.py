"""
Disambiguation utilities for handling ambiguous user inputs.

This module provides utilities for resolving ambiguous menu item names,
quantities, and other user inputs in the ordering conversation.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DisambiguationType(Enum):
    """Types of disambiguation scenarios."""
    MENU_ITEM = "menu_item"
    MODIFIER = "modifier"
    QUANTITY = "quantity"
    GENERAL = "general"


@dataclass
class DisambiguationContext:
    """Context for disambiguation scenarios."""
    type: DisambiguationType
    original_input: str
    conversation_history: Optional[List[Dict[str, Any]]] = None
    current_cart: Optional[List[Dict[str, Any]]] = None
    available_options: Optional[List[Dict[str, Any]]] = None


@dataclass
class DisambiguationOption:
    """Represents a disambiguation option for the user to choose from."""
    id: str
    display_name: str
    description: Optional[str] = None
    price: Optional[float] = None
    context: Optional[Dict[str, Any]] = None


@dataclass
class DisambiguationResult:
    """Result of disambiguation process."""
    resolved: bool
    selected_option: Optional[DisambiguationOption] = None
    options: Optional[List[DisambiguationOption]] = None
    error_message: Optional[str] = None


class DisambiguationHelper:
    """Helper class for handling disambiguation scenarios."""
    
    def __init__(self):
        self.max_options = 5  # Maximum number of options to present
    
    def create_menu_disambiguation(
        self,
        ambiguous_name: str,
        matching_items: List[Dict[str, Any]]
    ) -> DisambiguationResult:
        """
        Create disambiguation options for ambiguous menu item names.
        
        Args:
            ambiguous_name: The ambiguous name the user provided
            matching_items: List of menu items that could match
            
        Returns:
            DisambiguationResult with options for the user to choose from
        """
        if not matching_items:
            return DisambiguationResult(
                resolved=False,
                error_message=f"No menu items found matching '{ambiguous_name}'"
            )
        
        if len(matching_items) == 1:
            # No disambiguation needed
            item = matching_items[0]
            option = DisambiguationOption(
                id=item.get('plu', ''),
                display_name=item.get('name', ''),
                description=item.get('description', ''),
                price=item.get('price', 0) / 100.0 if item.get('price') else None,
                context={'item': item}
            )
            return DisambiguationResult(
                resolved=True,
                selected_option=option
            )
        
        # Multiple matches - need disambiguation
        options = []
        for item in matching_items[:self.max_options]:
            option = DisambiguationOption(
                id=item.get('plu', ''),
                display_name=item.get('name', ''),
                description=item.get('description', ''),
                price=item.get('price', 0) / 100.0 if item.get('price') else None,
                context={'item': item}
            )
            options.append(option)
        
        return DisambiguationResult(
            resolved=False,
            options=options
        )
    
    def create_quantity_disambiguation(
        self,
        ambiguous_quantity: str
    ) -> DisambiguationResult:
        """
        Handle ambiguous quantity inputs.
        
        Args:
            ambiguous_quantity: The ambiguous quantity string
            
        Returns:
            DisambiguationResult with resolved or disambiguation options
        """
        # Common quantity mappings
        quantity_mappings = {
            'one': 1, 'a': 1, 'an': 1, 'single': 1,
            'two': 2, 'couple': 2, 'pair': 2,
            'three': 3, 'few': 3,
            'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
            'dozen': 12, 'half dozen': 6
        }
        
        # Try to parse as number
        try:
            quantity = int(ambiguous_quantity)
            if 1 <= quantity <= 99:  # Reasonable quantity range
                option = DisambiguationOption(
                    id=str(quantity),
                    display_name=str(quantity),
                    context={'quantity': quantity}
                )
                return DisambiguationResult(
                    resolved=True,
                    selected_option=option
                )
        except ValueError:
            pass
        
        # Try word mappings
        normalized = ambiguous_quantity.lower().strip()
        if normalized in quantity_mappings:
            quantity = quantity_mappings[normalized]
            option = DisambiguationOption(
                id=str(quantity),
                display_name=str(quantity),
                context={'quantity': quantity}
            )
            return DisambiguationResult(
                resolved=True,
                selected_option=option
            )
        
        # Could not resolve
        return DisambiguationResult(
            resolved=False,
            error_message=f"Could not understand quantity '{ambiguous_quantity}'"
        )
    
    def create_modifier_disambiguation(
        self,
        ambiguous_modifier: str,
        available_modifiers: List[Dict[str, Any]]
    ) -> DisambiguationResult:
        """
        Handle ambiguous modifier inputs.
        
        Args:
            ambiguous_modifier: The ambiguous modifier name
            available_modifiers: List of available modifiers for the item
            
        Returns:
            DisambiguationResult with options for the user to choose from
        """
        if not available_modifiers:
            return DisambiguationResult(
                resolved=False,
                error_message=f"No modifiers available for '{ambiguous_modifier}'"
            )
        
        # Simple fuzzy matching - look for partial matches
        matches = []
        normalized_input = ambiguous_modifier.lower().strip()
        
        for modifier in available_modifiers:
            modifier_name = modifier.get('name', '').lower()
            if normalized_input in modifier_name or modifier_name in normalized_input:
                matches.append(modifier)
        
        if not matches:
            # No matches found
            return DisambiguationResult(
                resolved=False,
                error_message=f"No modifiers found matching '{ambiguous_modifier}'"
            )
        
        if len(matches) == 1:
            # Single match - resolved
            modifier = matches[0]
            option = DisambiguationOption(
                id=modifier.get('plu', ''),
                display_name=modifier.get('name', ''),
                description=modifier.get('description', ''),
                price=modifier.get('price', 0) / 100.0 if modifier.get('price') else None,
                context={'modifier': modifier}
            )
            return DisambiguationResult(
                resolved=True,
                selected_option=option
            )
        
        # Multiple matches - need disambiguation
        options = []
        for modifier in matches[:self.max_options]:
            option = DisambiguationOption(
                id=modifier.get('plu', ''),
                display_name=modifier.get('name', ''),
                description=modifier.get('description', ''),
                price=modifier.get('price', 0) / 100.0 if modifier.get('price') else None,
                context={'modifier': modifier}
            )
            options.append(option)
        
        return DisambiguationResult(
            resolved=False,
            options=options
        )
    
    def format_disambiguation_prompt(
        self,
        ambiguous_input: str,
        options: List[DisambiguationOption],
        context_type: str = "item"
    ) -> str:
        """
        Format a disambiguation prompt for the user.
        
        Args:
            ambiguous_input: The original ambiguous input
            options: List of disambiguation options
            context_type: Type of disambiguation (item, modifier, etc.)
            
        Returns:
            Formatted prompt string
        """
        if not options:
            return f"I couldn't find any {context_type}s matching '{ambiguous_input}'."
        
        prompt = f"I found multiple {context_type}s matching '{ambiguous_input}'. Which one did you mean?\n\n"
        
        for i, option in enumerate(options, 1):
            line = f"{i}. {option.display_name}"
            if option.price is not None:
                line += f" (${option.price:.2f})"
            if option.description:
                line += f" - {option.description}"
            prompt += line + "\n"
        
        prompt += f"\nPlease say the number of your choice (1-{len(options)})."
        return prompt
    
    def resolve_user_choice(
        self,
        user_input: str,
        options: List[DisambiguationOption]
    ) -> DisambiguationResult:
        """
        Resolve user's choice from disambiguation options.
        
        Args:
            user_input: User's response to disambiguation prompt
            options: Available options to choose from
            
        Returns:
            DisambiguationResult with selected option or error
        """
        if not options:
            return DisambiguationResult(
                resolved=False,
                error_message="No options available for selection"
            )
        
        # Try to parse as number
        try:
            choice_num = int(user_input.strip())
            if 1 <= choice_num <= len(options):
                selected = options[choice_num - 1]
                return DisambiguationResult(
                    resolved=True,
                    selected_option=selected
                )
            else:
                return DisambiguationResult(
                    resolved=False,
                    error_message=f"Please choose a number between 1 and {len(options)}"
                )
        except ValueError:
            pass
        
        # Try to match by name
        normalized_input = user_input.lower().strip()
        for option in options:
            if normalized_input in option.display_name.lower():
                return DisambiguationResult(
                    resolved=True,
                    selected_option=option
                )
        
        return DisambiguationResult(
            resolved=False,
            error_message=f"I didn't understand '{user_input}'. Please choose a number from the list."
        )


# Global disambiguation helper instance
disambiguation_helper = DisambiguationHelper()


async def disambiguation_detector(
    user_input: str,
    context: Optional[DisambiguationContext] = None
) -> bool:
    """
    Detect if user input requires disambiguation.
    
    Args:
        user_input: The user's input text
        context: Optional disambiguation context
        
    Returns:
        bool: True if disambiguation is needed, False otherwise
    """
    # Simple heuristics for detecting ambiguous inputs
    ambiguous_indicators = [
        "which", "what do you mean", "clarify", "not sure",
        "multiple", "several", "few", "some", "any",
        "the", "that one", "this one"
    ]
    
    normalized_input = user_input.lower().strip()
    
    # Check for ambiguous language
    for indicator in ambiguous_indicators:
        if indicator in normalized_input:
            return True
    
    # Check if input is very short/vague
    if len(normalized_input.split()) <= 2 and len(normalized_input) <= 10:
        return True
    
    return False


async def disambiguation_resolver(
    user_input: str,
    context: DisambiguationContext,
    available_options: Optional[List[Dict[str, Any]]] = None
) -> DisambiguationResult:
    """
    Resolve disambiguation based on user input and context.
    
    Args:
        user_input: The user's disambiguating input
        context: Disambiguation context
        available_options: Available options to choose from
        
    Returns:
        DisambiguationResult with resolution
    """
    if context.type == DisambiguationType.MENU_ITEM:
        return disambiguation_helper.create_menu_disambiguation(
            context.original_input,
            available_options or context.available_options or []
        )
    elif context.type == DisambiguationType.QUANTITY:
        return disambiguation_helper.create_quantity_disambiguation(
            context.original_input
        )
    elif context.type == DisambiguationType.MODIFIER:
        return disambiguation_helper.create_modifier_disambiguation(
            context.original_input,
            available_options or context.available_options or []
        )
    else:
        # General disambiguation
        return DisambiguationResult(
            resolved=False,
            error_message=f"Could not resolve disambiguation for '{context.original_input}'"
        )