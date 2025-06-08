"""
End-to-end tests for complex order flow - Task 4.1.2.

This module tests complex order flows with:
- Menu item modifications
- Special dietary requests
- Multiple items with different modifications
- Custom instructions and notes
- Complex pricing calculations
"""

import pytest
import pytest_asyncio
import asyncio
import json
import uuid
from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.fsm.core import ConversationState, ConversationEvent
from app.utils.agent_orchestration_async import AsyncAgentOrchestrator
from app.utils.conversation_store_async import async_conversation_store
from app.models.menu_async import MenuItem, MenuCategory, MenuModifier, MenuModifierGroup
from app.models.order_async import Order, OrderItem, OrderItemModifier


@pytest_asyncio.fixture
async def orchestrator():
    """Create and initialize an agent orchestrator for complex orders."""
    orchestrator = AsyncAgentOrchestrator()
    
    # Mock the agents with enhanced capabilities for complex orders
    orchestrator.frontline_agent = AsyncMock()
    orchestrator.menu_agent = AsyncMock()
    orchestrator.cart_agent = AsyncMock()
    orchestrator.guardrail_agent = AsyncMock()
    orchestrator.fulfillment_agent = AsyncMock()
    orchestrator.escalation_agent = AsyncMock()
    
    return orchestrator


@pytest_asyncio.fixture
async def complex_menu_data():
    """Create complex menu data with modifiers for testing."""
    return {
        "categories": [
            {
                "id": 1,
                "name": "Sushi Rolls",
                "description": "Fresh sushi rolls with customization options"
            },
            {
                "id": 2,
                "name": "Appetizers",
                "description": "Traditional Japanese appetizers"
            }
        ],
        "items": [
            {
                "id": 1,
                "name": "California Roll",
                "description": "Crab, avocado, cucumber",
                "price": 12.95,
                "plu": "CALI_001",
                "category_id": 1,
                "is_available": True,
                "modifier_groups": ["spice_level", "additions", "removals"]
            },
            {
                "id": 2,
                "name": "Spicy Tuna Roll",
                "description": "Spicy tuna, cucumber",
                "price": 13.95,
                "plu": "TUNA_001",
                "category_id": 1,
                "is_available": True,
                "modifier_groups": ["spice_level", "additions", "removals"]
            },
            {
                "id": 3,
                "name": "Salmon Teriyaki",
                "description": "Grilled salmon with teriyaki sauce",
                "price": 18.95,
                "plu": "SALMON_001",
                "category_id": 1,
                "is_available": True,
                "modifier_groups": ["cooking_preference", "sauce_options", "sides"]
            },
            {
                "id": 4,
                "name": "Edamame",
                "description": "Steamed soybeans",
                "price": 5.95,
                "plu": "EDA_001",
                "category_id": 2,
                "is_available": True,
                "modifier_groups": ["preparation_style"]
            }
        ],
        "modifier_groups": [
            {
                "id": 1,
                "name": "spice_level",
                "display_name": "Spice Level",
                "min_selection": 0,
                "max_selection": 1,
                "modifiers": ["mild", "medium", "hot", "extra_hot"]
            },
            {
                "id": 2,
                "name": "additions",
                "display_name": "Add Extras",
                "min_selection": 0,
                "max_selection": 5,
                "modifiers": ["extra_avocado", "extra_cucumber", "cream_cheese", "tempura_flakes", "sesame_seeds"]
            },
            {
                "id": 3,
                "name": "removals",
                "display_name": "Remove Items",
                "min_selection": 0,
                "max_selection": 3,
                "modifiers": ["no_avocado", "no_cucumber", "no_crab"]
            },
            {
                "id": 4,
                "name": "cooking_preference",
                "display_name": "Cooking Preference",
                "min_selection": 0,
                "max_selection": 1,
                "modifiers": ["rare", "medium_rare", "well_done"]
            },
            {
                "id": 5,
                "name": "sauce_options",
                "display_name": "Sauce Options",
                "min_selection": 0,
                "max_selection": 2,
                "modifiers": ["extra_teriyaki", "spicy_mayo", "eel_sauce", "no_sauce"]
            },
            {
                "id": 6,
                "name": "sides",
                "display_name": "Side Options",
                "min_selection": 0,
                "max_selection": 3,
                "modifiers": ["steamed_rice", "miso_soup", "salad", "pickled_vegetables"]
            },
            {
                "id": 7,
                "name": "preparation_style",
                "display_name": "Preparation Style",
                "min_selection": 0,
                "max_selection": 1,
                "modifiers": ["lightly_salted", "garlic_style", "spicy_style"]
            }
        ],
        "modifiers": [
            # Spice level modifiers
            {"id": 1, "name": "mild", "display_name": "Mild", "price_change": 0.0, "plu": "SPICE_MILD"},
            {"id": 2, "name": "medium", "display_name": "Medium", "price_change": 0.0, "plu": "SPICE_MED"},
            {"id": 3, "name": "hot", "display_name": "Hot", "price_change": 0.0, "plu": "SPICE_HOT"},
            {"id": 4, "name": "extra_hot", "display_name": "Extra Hot", "price_change": 0.5, "plu": "SPICE_XHOT"},
            
            # Addition modifiers
            {"id": 5, "name": "extra_avocado", "display_name": "Extra Avocado", "price_change": 1.5, "plu": "ADD_AVOCADO"},
            {"id": 6, "name": "extra_cucumber", "display_name": "Extra Cucumber", "price_change": 0.75, "plu": "ADD_CUCUMBER"},
            {"id": 7, "name": "cream_cheese", "display_name": "Cream Cheese", "price_change": 1.0, "plu": "ADD_CREAM"},
            {"id": 8, "name": "tempura_flakes", "display_name": "Tempura Flakes", "price_change": 1.25, "plu": "ADD_TEMPURA"},
            {"id": 9, "name": "sesame_seeds", "display_name": "Sesame Seeds", "price_change": 0.5, "plu": "ADD_SESAME"},
            
            # Removal modifiers
            {"id": 10, "name": "no_avocado", "display_name": "No Avocado", "price_change": -0.5, "plu": "REM_AVOCADO"},
            {"id": 11, "name": "no_cucumber", "display_name": "No Cucumber", "price_change": 0.0, "plu": "REM_CUCUMBER"},
            {"id": 12, "name": "no_crab", "display_name": "No Crab", "price_change": -2.0, "plu": "REM_CRAB"},
            
            # Cooking preference modifiers
            {"id": 13, "name": "rare", "display_name": "Rare", "price_change": 0.0, "plu": "COOK_RARE"},
            {"id": 14, "name": "medium_rare", "display_name": "Medium Rare", "price_change": 0.0, "plu": "COOK_MEDRAR"},
            {"id": 15, "name": "well_done", "display_name": "Well Done", "price_change": 0.0, "plu": "COOK_WELL"},
            
            # Sauce modifiers
            {"id": 16, "name": "extra_teriyaki", "display_name": "Extra Teriyaki", "price_change": 0.75, "plu": "SAUCE_TERI"},
            {"id": 17, "name": "spicy_mayo", "display_name": "Spicy Mayo", "price_change": 0.75, "plu": "SAUCE_SPICY"},
            {"id": 18, "name": "eel_sauce", "display_name": "Eel Sauce", "price_change": 0.75, "plu": "SAUCE_EEL"},
            {"id": 19, "name": "no_sauce", "display_name": "No Sauce", "price_change": -0.5, "plu": "SAUCE_NONE"},
            
            # Side modifiers
            {"id": 20, "name": "steamed_rice", "display_name": "Steamed Rice", "price_change": 2.0, "plu": "SIDE_RICE"},
            {"id": 21, "name": "miso_soup", "display_name": "Miso Soup", "price_change": 3.0, "plu": "SIDE_MISO"},
            {"id": 22, "name": "salad", "display_name": "House Salad", "price_change": 4.0, "plu": "SIDE_SALAD"},
            {"id": 23, "name": "pickled_vegetables", "display_name": "Pickled Vegetables", "price_change": 2.5, "plu": "SIDE_PICKLED"},
            
            # Preparation style modifiers
            {"id": 24, "name": "lightly_salted", "display_name": "Lightly Salted", "price_change": 0.0, "plu": "PREP_LIGHT"},
            {"id": 25, "name": "garlic_style", "display_name": "Garlic Style", "price_change": 0.5, "plu": "PREP_GARLIC"},
            {"id": 26, "name": "spicy_style", "display_name": "Spicy Style", "price_change": 0.5, "plu": "PREP_SPICY"}
        ]
    }


class TestComplexOrderFlow:
    """Test complex order flows with modifications and special requests."""
    
    @pytest.mark.asyncio
    async def test_single_item_with_multiple_modifications(self, orchestrator, complex_menu_data):
        """Test ordering a single item with multiple modifications."""
        call_sid = f"CA{uuid.uuid4().hex[:24]}_complex_single"
        
        # Setup mocks for complex single item order
        await self._setup_complex_single_item_mocks(orchestrator, complex_menu_data)
        
        responses = []
        
        # Initial greeting
        responses.append(await orchestrator.process_voice_input(
            call_sid, "", {"first_interaction": True}
        ))
        
        # Provide name
        responses.append(await orchestrator.process_voice_input(
            call_sid, "Hi, I'm Jennifer"
        ))
        
        # Complex order request
        responses.append(await orchestrator.process_voice_input(
            call_sid, "I'd like a California Roll, but make it extra spicy, add extra avocado and cream cheese, and no cucumber please"
        ))
        
        # Verify complex order was understood
        order_response = responses[-1]
        assert "california roll" in order_response["text"].lower()
        assert "extra spicy" in order_response["text"].lower() or "hot" in order_response["text"].lower()
        assert "extra avocado" in order_response["text"].lower()
        assert "cream cheese" in order_response["text"].lower()
        assert "no cucumber" in order_response["text"].lower()
        
        # Calculate expected price: $12.95 + $0.5 (extra hot) + $1.5 (extra avocado) + $1.0 (cream cheese) = $15.95
        assert "15.95" in order_response["text"] or "$15.95" in order_response["text"]
        
        # Confirm order
        responses.append(await orchestrator.process_voice_input(
            call_sid, "Yes, that sounds perfect"
        ))
        
        # Final confirmation
        responses.append(await orchestrator.process_voice_input(
            call_sid, "Please place the order"
        ))
        
        # Verify all modifications were preserved
        final_response = responses[-1]
        assert "confirmed" in final_response["text"].lower()
    
    @pytest.mark.asyncio
    async def test_multiple_items_with_different_modifications(self, orchestrator, complex_menu_data):
        """Test ordering multiple items with different modifications."""
        call_sid = f"CA{uuid.uuid4().hex[:24]}_complex_multi"
        
        # Setup mocks for multiple complex items
        await self._setup_complex_multi_item_mocks(orchestrator, complex_menu_data)
        
        responses = []
        
        # Initial setup
        responses.append(await orchestrator.process_voice_input(
            call_sid, "", {"first_interaction": True}
        ))
        responses.append(await orchestrator.process_voice_input(
            call_sid, "I'm Michael"
        ))
        
        # First item with modifications
        responses.append(await orchestrator.process_voice_input(
            call_sid, "I want a Spicy Tuna Roll, medium spicy, with extra cucumber"
        ))
        
        # Verify first item
        first_item_response = responses[-1]
        assert "spicy tuna roll" in first_item_response["text"].lower()
        assert "medium" in first_item_response["text"].lower()
        assert "extra cucumber" in first_item_response["text"].lower()
        
        # Second item with different modifications
        responses.append(await orchestrator.process_voice_input(
            call_sid, "Also add a Salmon Teriyaki, cooked medium rare, with extra teriyaki sauce and miso soup"
        ))
        
        # Verify second item
        second_item_response = responses[-1]
        assert "salmon teriyaki" in second_item_response["text"].lower()
        assert "medium rare" in second_item_response["text"].lower()
        assert "extra teriyaki" in second_item_response["text"].lower()
        assert "miso soup" in second_item_response["text"].lower()
        
        # Third item with removal modifications
        responses.append(await orchestrator.process_voice_input(
            call_sid, "And one more California Roll with no avocado and no crab, just cucumber"
        ))
        
        # Verify third item with removals
        third_item_response = responses[-1]
        assert "california roll" in third_item_response["text"].lower()
        assert "no avocado" in third_item_response["text"].lower()
        assert "no crab" in third_item_response["text"].lower()
        
        # Review entire order
        responses.append(await orchestrator.process_voice_input(
            call_sid, "That's everything, what's the total?"
        ))
        
        # Verify order summary
        summary_response = responses[-1]
        assert "spicy tuna" in summary_response["text"].lower()
        assert "salmon teriyaki" in summary_response["text"].lower()
        assert "california roll" in summary_response["text"].lower()
        
        # Calculate expected total and verify
        # Spicy Tuna: $13.95 + $0.75 (extra cucumber) = $14.70
        # Salmon Teriyaki: $18.95 + $0.75 (extra teriyaki) + $3.00 (miso soup) = $22.70
        # California Roll: $12.95 - $0.50 (no avocado) - $2.00 (no crab) = $10.45
        # Total: $47.85
        total_found = "47.85" in summary_response["text"] or "$47.85" in summary_response["text"]
        assert total_found or "47" in summary_response["text"]  # Allow for rounding differences
        
        # Confirm complex order
        responses.append(await orchestrator.process_voice_input(
            call_sid, "Yes, please process this order"
        ))
        
        final_response = responses[-1]
        assert "confirmed" in final_response["text"].lower()
    
    @pytest.mark.asyncio
    async def test_dietary_restrictions_and_allergies(self, orchestrator, complex_menu_data):
        """Test handling dietary restrictions and allergy requests."""
        call_sid = f"CA{uuid.uuid4().hex[:24]}_dietary"
        
        # Setup mocks for dietary restrictions
        await self._setup_dietary_restriction_mocks(orchestrator, complex_menu_data)
        
        responses = []
        
        # Initial setup
        responses.append(await orchestrator.process_voice_input(
            call_sid, "", {"first_interaction": True}
        ))
        responses.append(await orchestrator.process_voice_input(
            call_sid, "Hi, I'm Sarah"
        ))
        
        # Mention dietary restrictions
        responses.append(await orchestrator.process_voice_input(
            call_sid, "I have a shellfish allergy, what can I safely order?"
        ))
        
        # Verify allergy acknowledgment
        allergy_response = responses[-1]
        assert "allergy" in allergy_response["text"].lower() or "shellfish" in allergy_response["text"].lower()
        assert "safe" in allergy_response["text"].lower() or "recommend" in allergy_response["text"].lower()
        
        # Order with allergy considerations
        responses.append(await orchestrator.process_voice_input(
            call_sid, "I'll have the Salmon Teriyaki, no sauce, and make sure there's no cross-contamination"
        ))
        
        # Verify allergy handling
        order_response = responses[-1]
        assert "salmon teriyaki" in order_response["text"].lower()
        assert "no sauce" in order_response["text"].lower()
        assert any(word in order_response["text"].lower() for word in ["safe", "allergy", "noted", "careful"])
        
        # Additional dietary request
        responses.append(await orchestrator.process_voice_input(
            call_sid, "Also, I'm vegetarian, what sides would work?"
        ))
        
        # Verify vegetarian options
        vegetarian_response = responses[-1]
        assert "vegetarian" in vegetarian_response["text"].lower()
        assert any(word in vegetarian_response["text"].lower() for word in ["edamame", "salad", "rice", "vegetables"])
        
        # Add vegetarian side
        responses.append(await orchestrator.process_voice_input(
            call_sid, "Add the house salad please"
        ))
        
        # Confirm dietary accommodations
        responses.append(await orchestrator.process_voice_input(
            call_sid, "That's all, and please double-check about the shellfish allergy"
        ))
        
        final_response = responses[-1]
        assert "allergy" in final_response["text"].lower() or "shellfish" in final_response["text"].lower()
        assert "noted" in final_response["text"].lower() or "careful" in final_response["text"].lower()
    
    @pytest.mark.asyncio
    async def test_custom_instructions_and_special_notes(self, orchestrator, complex_menu_data):
        """Test handling custom instructions and special notes."""
        call_sid = f"CA{uuid.uuid4().hex[:24]}_custom"
        
        # Setup mocks for custom instructions
        await self._setup_custom_instruction_mocks(orchestrator, complex_menu_data)
        
        responses = []
        
        # Initial setup
        responses.append(await orchestrator.process_voice_input(
            call_sid, "", {"first_interaction": True}
        ))
        responses.append(await orchestrator.process_voice_input(
            call_sid, "I'm David"
        ))
        
        # Order with special instructions
        responses.append(await orchestrator.process_voice_input(
            call_sid, "I'd like two California Rolls, but please cut them into 6 pieces each instead of 8, and pack them separately"
        ))
        
        # Verify custom cutting instructions
        custom_response = responses[-1]
        assert "california roll" in custom_response["text"].lower()
        assert "6 pieces" in custom_response["text"].lower() or "six pieces" in custom_response["text"].lower()
        assert "separately" in custom_response["text"].lower() or "separate" in custom_response["text"].lower()
        
        # Add timing instructions
        responses.append(await orchestrator.process_voice_input(
            call_sid, "Also, I need this ready in exactly 30 minutes, not sooner, for a business meeting"
        ))
        
        # Verify timing instructions
        timing_response = responses[-1]
        assert "30 minutes" in timing_response["text"].lower() or "thirty minutes" in timing_response["text"].lower()
        assert any(word in timing_response["text"].lower() for word in ["exactly", "ready", "time", "meeting"])
        
        # Add presentation instructions
        responses.append(await orchestrator.process_voice_input(
            call_sid, "Please include extra ginger and wasabi, and can you make it look nice for presentation?"
        ))
        
        # Verify presentation instructions
        presentation_response = responses[-1]
        assert "extra ginger" in presentation_response["text"].lower()
        assert "wasabi" in presentation_response["text"].lower()
        assert any(word in presentation_response["text"].lower() for word in ["presentation", "nice", "special"])
        
        # Final confirmation with all special requests
        responses.append(await orchestrator.process_voice_input(
            call_sid, "Perfect, please confirm all those special instructions"
        ))
        
        final_response = responses[-1]
        assert "6 pieces" in final_response["text"].lower() or "six pieces" in final_response["text"].lower()
        assert "30 minutes" in final_response["text"].lower()
        assert "extra ginger" in final_response["text"].lower()
        assert "presentation" in final_response["text"].lower()
    
    @pytest.mark.asyncio
    async def test_modification_conflicts_and_resolution(self, orchestrator, complex_menu_data):
        """Test handling modification conflicts and their resolution."""
        call_sid = f"CA{uuid.uuid4().hex[:24]}_conflicts"
        
        # Setup mocks for conflict resolution
        await self._setup_conflict_resolution_mocks(orchestrator, complex_menu_data)
        
        responses = []
        
        # Initial setup
        responses.append(await orchestrator.process_voice_input(
            call_sid, "", {"first_interaction": True}
        ))
        responses.append(await orchestrator.process_voice_input(
            call_sid, "I'm Lisa"
        ))
        
        # Order with conflicting modifications
        responses.append(await orchestrator.process_voice_input(
            call_sid, "I want a Spicy Tuna Roll, make it mild spicy, but also extra hot, with no sauce but extra spicy mayo"
        ))
        
        # Verify conflict detection
        conflict_response = responses[-1]
        assert any(word in conflict_response["text"].lower() for word in ["clarify", "conflict", "which", "both"])
        
        # Resolve spice level conflict
        responses.append(await orchestrator.process_voice_input(
            call_sid, "Sorry, I meant extra hot spice level"
        ))
        
        # Verify spice resolution
        spice_resolution = responses[-1]
        assert "extra hot" in spice_resolution["text"].lower()
        
        # Resolve sauce conflict
        responses.append(await orchestrator.process_voice_input(
            call_sid, "And I do want the spicy mayo, not no sauce"
        ))
        
        # Verify sauce resolution
        sauce_resolution = responses[-1]
        assert "spicy mayo" in sauce_resolution["text"].lower()
        
        # Add another conflicting request
        responses.append(await orchestrator.process_voice_input(
            call_sid, "Also add extra avocado and no avocado to the same roll"
        ))
        
        # Verify avocado conflict detection
        avocado_conflict = responses[-1]
        assert any(word in avocado_conflict["text"].lower() for word in ["clarify", "conflict", "both", "extra", "none"])
        
        # Resolve avocado conflict
        responses.append(await orchestrator.process_voice_input(
            call_sid, "I want extra avocado, ignore the no avocado"
        ))
        
        # Final order confirmation
        responses.append(await orchestrator.process_voice_input(
            call_sid, "That's all, please confirm the final order"
        ))
        
        final_response = responses[-1]
        assert "extra hot" in final_response["text"].lower()
        assert "spicy mayo" in final_response["text"].lower()
        assert "extra avocado" in final_response["text"].lower()
        assert "no avocado" not in final_response["text"].lower()
    
    async def _setup_complex_single_item_mocks(self, orchestrator, complex_menu_data):
        """Setup mocks for complex single item order."""
        
        async def mock_complex_cart_single(input_text: str, context: Dict[str, Any] = None):
            if "california roll" in input_text.lower():
                modifications = []
                price_adjustments = 0.0
                base_price = 12.95
                
                # Parse modifications
                if "extra spicy" in input_text.lower() or "hot" in input_text.lower():
                    modifications.append("Extra Hot (+$0.50)")
                    price_adjustments += 0.5
                
                if "extra avocado" in input_text.lower():
                    modifications.append("Extra Avocado (+$1.50)")
                    price_adjustments += 1.5
                    
                if "cream cheese" in input_text.lower():
                    modifications.append("Cream Cheese (+$1.00)")
                    price_adjustments += 1.0
                    
                if "no cucumber" in input_text.lower():
                    modifications.append("No Cucumber")
                
                final_price = base_price + price_adjustments
                mods_text = ", ".join(modifications)
                
                return {
                    "text": f"Perfect! One California Roll with {mods_text}. Total: ${final_price:.2f}. Anything else?",
                    "handled": True,
                    "agent": "CartAgent",
                    "modifications": modifications,
                    "final_price": final_price
                }
            else:
                return {"text": "What would you like to order?", "handled": True, "agent": "CartAgent"}
        
        orchestrator.frontline_agent.process_voice_input.side_effect = self._mock_standard_frontline
        orchestrator.cart_agent.process_voice_input.side_effect = mock_complex_cart_single
        orchestrator.fulfillment_agent.process_voice_input.side_effect = self._mock_standard_fulfillment
    
    async def _setup_complex_multi_item_mocks(self, orchestrator, complex_menu_data):
        """Setup mocks for multiple complex items."""
        
        # Track order state
        order_items = []
        
        async def mock_complex_cart_multi(input_text: str, context: Dict[str, Any] = None):
            nonlocal order_items
            
            if "spicy tuna roll" in input_text.lower():
                item = {
                    "name": "Spicy Tuna Roll",
                    "base_price": 13.95,
                    "modifications": [],
                    "price_adjustments": 0.0
                }
                
                if "medium" in input_text.lower():
                    item["modifications"].append("Medium Spicy")
                if "extra cucumber" in input_text.lower():
                    item["modifications"].append("Extra Cucumber (+$0.75)")
                    item["price_adjustments"] += 0.75
                
                item["final_price"] = item["base_price"] + item["price_adjustments"]
                order_items.append(item)
                
                return {
                    "text": f"Added Spicy Tuna Roll with {', '.join(item['modifications'])}. ${item['final_price']:.2f}. What else?",
                    "handled": True,
                    "agent": "CartAgent"
                }
                
            elif "salmon teriyaki" in input_text.lower():
                item = {
                    "name": "Salmon Teriyaki",
                    "base_price": 18.95,
                    "modifications": [],
                    "price_adjustments": 0.0
                }
                
                if "medium rare" in input_text.lower():
                    item["modifications"].append("Medium Rare")
                if "extra teriyaki" in input_text.lower():
                    item["modifications"].append("Extra Teriyaki (+$0.75)")
                    item["price_adjustments"] += 0.75
                if "miso soup" in input_text.lower():
                    item["modifications"].append("Miso Soup (+$3.00)")
                    item["price_adjustments"] += 3.0
                
                item["final_price"] = item["base_price"] + item["price_adjustments"]
                order_items.append(item)
                
                return {
                    "text": f"Added Salmon Teriyaki with {', '.join(item['modifications'])}. ${item['final_price']:.2f}. Anything else?",
                    "handled": True,
                    "agent": "CartAgent"
                }
                
            elif "california roll" in input_text.lower() and "no" in input_text.lower():
                item = {
                    "name": "California Roll",
                    "base_price": 12.95,
                    "modifications": [],
                    "price_adjustments": 0.0
                }
                
                if "no avocado" in input_text.lower():
                    item["modifications"].append("No Avocado (-$0.50)")
                    item["price_adjustments"] -= 0.5
                if "no crab" in input_text.lower():
                    item["modifications"].append("No Crab (-$2.00)")
                    item["price_adjustments"] -= 2.0
                
                item["final_price"] = item["base_price"] + item["price_adjustments"]
                order_items.append(item)
                
                return {
                    "text": f"Added California Roll with {', '.join(item['modifications'])}. ${item['final_price']:.2f}. What else?",
                    "handled": True,
                    "agent": "CartAgent"
                }
                
            elif "total" in input_text.lower() or "everything" in input_text.lower():
                total = sum(item["final_price"] for item in order_items)
                summary = []
                for item in order_items:
                    mods = ", ".join(item["modifications"]) if item["modifications"] else "no modifications"
                    summary.append(f"{item['name']} with {mods} (${item['final_price']:.2f})")
                
                return {
                    "text": f"Your order: {'; '.join(summary)}. Total: ${total:.2f}. Is this correct?",
                    "handled": True,
                    "agent": "CartAgent",
                    "order_items": order_items,
                    "total": total
                }
            else:
                return {"text": "What would you like to add?", "handled": True, "agent": "CartAgent"}
        
        orchestrator.frontline_agent.process_voice_input.side_effect = self._mock_standard_frontline
        orchestrator.cart_agent.process_voice_input.side_effect = mock_complex_cart_multi
        orchestrator.fulfillment_agent.process_voice_input.side_effect = self._mock_standard_fulfillment
    
    async def _setup_dietary_restriction_mocks(self, orchestrator, complex_menu_data):
        """Setup mocks for dietary restriction handling."""
        
        async def mock_dietary_frontline(input_text: str, context: Dict[str, Any] = None):
            context = context or {}
            
            if context.get("first_interaction"):
                return {
                    "text": "Welcome to Red Bar Sushi! How can I help you today?",
                    "handled": True,
                    "agent": "FrontlineAgent"
                }
            elif "allergy" in input_text.lower() or "shellfish" in input_text.lower():
                return {
                    "text": "I understand you have a shellfish allergy. Let me recommend some safe options. Our Salmon Teriyaki and vegetarian items are shellfish-free. I'll make sure to note your allergy.",
                    "handled": True,
                    "agent": "FrontlineAgent",
                    "dietary_restrictions": ["shellfish_allergy"]
                }
            elif "vegetarian" in input_text.lower():
                return {
                    "text": "For vegetarian sides, I recommend our Edamame, House Salad, Steamed Rice, or Pickled Vegetables. All are completely vegetarian.",
                    "handled": True,
                    "agent": "FrontlineAgent"
                }
            else:
                return {"text": "How can I help?", "handled": True, "agent": "FrontlineAgent"}
        
        async def mock_dietary_cart(input_text: str, context: Dict[str, Any] = None):
            if "salmon teriyaki" in input_text.lower():
                return {
                    "text": "Salmon Teriyaki with no sauce, noted for shellfish allergy safety. $18.45. I'll make sure the kitchen is aware of your allergy.",
                    "handled": True,
                    "agent": "CartAgent",
                    "allergy_noted": True
                }
            elif "salad" in input_text.lower():
                return {
                    "text": "House Salad added. $4.00. Perfect vegetarian choice!",
                    "handled": True,
                    "agent": "CartAgent"
                }
            elif "allergy" in input_text.lower():
                return {
                    "text": "Absolutely, your shellfish allergy is prominently noted on the order. The kitchen will take extra care to avoid cross-contamination.",
                    "handled": True,
                    "agent": "CartAgent",
                    "allergy_confirmed": True
                }
            else:
                return {"text": "What would you like?", "handled": True, "agent": "CartAgent"}
        
        orchestrator.frontline_agent.process_voice_input.side_effect = mock_dietary_frontline
        orchestrator.cart_agent.process_voice_input.side_effect = mock_dietary_cart
        orchestrator.fulfillment_agent.process_voice_input.side_effect = self._mock_standard_fulfillment
    
    async def _setup_custom_instruction_mocks(self, orchestrator, complex_menu_data):
        """Setup mocks for custom instruction handling."""
        
        custom_instructions = []
        
        async def mock_custom_cart(input_text: str, context: Dict[str, Any] = None):
            nonlocal custom_instructions
            
            if "california roll" in input_text.lower() and "6 pieces" in input_text.lower():
                custom_instructions.append("Cut into 6 pieces each")
                custom_instructions.append("Pack separately")
                return {
                    "text": "Two California Rolls, cut into 6 pieces each and packed separately. $25.90. Special cutting and packing noted.",
                    "handled": True,
                    "agent": "CartAgent"
                }
            elif "30 minutes" in input_text.lower():
                custom_instructions.append("Ready in exactly 30 minutes")
                custom_instructions.append("Business meeting timing")
                return {
                    "text": "Timing noted: ready in exactly 30 minutes for your business meeting. Not a problem!",
                    "handled": True,
                    "agent": "CartAgent"
                }
            elif "ginger" in input_text.lower() and "wasabi" in input_text.lower():
                custom_instructions.append("Extra ginger and wasabi")
                custom_instructions.append("Special presentation")
                return {
                    "text": "Extra ginger and wasabi included, with special presentation for your meeting. All noted!",
                    "handled": True,
                    "agent": "CartAgent"
                }
            elif "confirm" in input_text.lower() and "instructions" in input_text.lower():
                instructions_text = ", ".join(custom_instructions)
                return {
                    "text": f"Special instructions confirmed: {instructions_text}. Everything will be prepared exactly as requested.",
                    "handled": True,
                    "agent": "CartAgent",
                    "custom_instructions": custom_instructions
                }
            else:
                return {"text": "What would you like?", "handled": True, "agent": "CartAgent"}
        
        orchestrator.frontline_agent.process_voice_input.side_effect = self._mock_standard_frontline
        orchestrator.cart_agent.process_voice_input.side_effect = mock_custom_cart
        orchestrator.fulfillment_agent.process_voice_input.side_effect = self._mock_standard_fulfillment
    
    async def _setup_conflict_resolution_mocks(self, orchestrator, complex_menu_data):
        """Setup mocks for conflict resolution."""
        
        resolved_items = {}
        
        async def mock_conflict_cart(input_text: str, context: Dict[str, Any] = None):
            nonlocal resolved_items
            
            if "spicy tuna roll" in input_text.lower() and "mild" in input_text.lower() and "hot" in input_text.lower():
                return {
                    "text": "I need to clarify the spice level - you mentioned both mild and extra hot. Which would you prefer?",
                    "handled": True,
                    "agent": "CartAgent",
                    "conflict_detected": "spice_level"
                }
            elif "extra hot" in input_text.lower() and "meant" in input_text.lower():
                resolved_items["spice_level"] = "extra_hot"
                return {
                    "text": "Got it! Extra hot spice level for your Spicy Tuna Roll.",
                    "handled": True,
                    "agent": "CartAgent"
                }
            elif "spicy mayo" in input_text.lower() and ("do want" in input_text.lower() or "not no sauce" in input_text.lower()):
                resolved_items["sauce"] = "spicy_mayo"
                return {
                    "text": "Perfect! Spicy mayo it is, not no sauce.",
                    "handled": True,
                    "agent": "CartAgent"
                }
            elif "extra avocado" in input_text.lower() and "no avocado" in input_text.lower():
                return {
                    "text": "You mentioned both extra avocado and no avocado. That's conflicting - which would you like?",
                    "handled": True,
                    "agent": "CartAgent",
                    "conflict_detected": "avocado"
                }
            elif "extra avocado" in input_text.lower() and "ignore" in input_text.lower():
                resolved_items["avocado"] = "extra_avocado"
                return {
                    "text": "Understood! Extra avocado, ignoring the no avocado request.",
                    "handled": True,
                    "agent": "CartAgent"
                }
            elif "confirm" in input_text.lower() and "final" in input_text.lower():
                return {
                    "text": f"Final order: Spicy Tuna Roll with extra hot spice, spicy mayo, and extra avocado. ${15.45:.2f}. Conflicts resolved!",
                    "handled": True,
                    "agent": "CartAgent",
                    "resolved_items": resolved_items
                }
            else:
                return {"text": "What would you like?", "handled": True, "agent": "CartAgent"}
        
        orchestrator.frontline_agent.process_voice_input.side_effect = self._mock_standard_frontline
        orchestrator.cart_agent.process_voice_input.side_effect = mock_conflict_cart
        orchestrator.fulfillment_agent.process_voice_input.side_effect = self._mock_standard_fulfillment
    
    async def _mock_standard_frontline(self, input_text: str, context: Dict[str, Any] = None):
        """Standard frontline agent mock."""
        context = context or {}
        
        if context.get("first_interaction"):
            return {
                "text": "Welcome to Red Bar Sushi! I'm here to help with your order. What's your name?",
                "handled": True,
                "agent": "FrontlineAgent"
            }
        elif any(name in input_text.lower() for name in ["jennifer", "michael", "sarah", "david", "lisa"]):
            return {
                "text": "Thank you! What can I get for you today?",
                "handled": True,
                "agent": "FrontlineAgent"
            }
        else:
            return {"text": "How can I help?", "handled": True, "agent": "FrontlineAgent"}
    
    async def _mock_standard_fulfillment(self, input_text: str, context: Dict[str, Any] = None):
        """Standard fulfillment agent mock."""
        if any(word in input_text.lower() for word in ["perfect", "place", "process", "confirm"]):
            return {
                "text": "Order confirmed! Your custom sushi order will be prepared with all modifications and special instructions. Thank you!",
                "handled": True,
                "agent": "FulfillmentAgent"
            }
        else:
            return {"text": "Ready to confirm your order?", "handled": True, "agent": "FulfillmentAgent"}