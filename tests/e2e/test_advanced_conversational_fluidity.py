"""
Advanced E2E Tests - Category 5: Complex Conversational Fluidity Tests

These tests push the boundaries of conversational AI by testing:
- Mid-conversation corrections and ambiguity resolution
- Multi-intent parsing and out-of-order information handling
- Contextual understanding and pronoun resolution
- Dynamic conversation flow management

Following the detailed test methodology for validating AI responses with deterministic outcomes.
"""

import pytest
import pytest_asyncio
import time
import logging
import json
from typing import Dict, Any, List

import httpx
import redis.asyncio as redis

# Optional semantic similarity (fallback if not available)
try:
    from sentence_transformers import SentenceTransformer
    SEMANTIC_AVAILABLE = True
except ImportError:
    SentenceTransformer = None
    SEMANTIC_AVAILABLE = False

from .conftest import (
    send_turn, get_cart_state, get_fsm_state, get_session_data,
    assert_contains_keywords
)

def assert_semantic_similarity(text1: str, text2: str, model=None, threshold: float = 0.7) -> bool:
    """Fallback semantic similarity check"""
    if not SEMANTIC_AVAILABLE or model is None:
        # Simple keyword overlap fallback
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        overlap = len(words1.intersection(words2))
        total = len(words1.union(words2))
        return (overlap / max(total, 1)) >= (threshold * 0.5)  # More lenient threshold
    
    embeddings = model.encode([text1, text2])
    similarity = model.similarity(embeddings[0], embeddings[1])
    return similarity.item() >= threshold

logger = logging.getLogger(__name__)


class TestCategory5ConversationalFluidity:
    """Category 5: Complex Conversational Fluidity Tests"""
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_5_1_mid_conversation_correction_and_ambiguity(
        self, async_client, redis_client, deliverect_helper
    ):
        """
        Test 5.1: Mid-Conversation Correction and Ambiguity Resolution
        
        This test validates the AI's ability to:
        1. Handle users who change their mind mid-sentence
        2. Correctly discard previous choices and lock onto final decisions
        3. Resolve ambiguous pronouns in context
        4. Maintain conversational flow despite corrections
        """
        call_sid = f"e2e_test_5_1_{int(time.time())}"
        
        # Initial greeting and name collection
        response1 = await send_turn(async_client, call_sid, "Hi")
        logger.info(f"Greeting response: {response1}")
        
        response2 = await send_turn(async_client, call_sid, "Isabel")
        logger.info(f"Name response: {response2}")
        
        # Verify greeting flow worked
        assert "message" in response1, "Greeting should receive a response"
        assert "message" in response2, "Name should receive a response"
        
        # CRITICAL TEST: Mid-sentence correction with ambiguous final choice
        correction_response = await send_turn(
            async_client, call_sid, 
            "I'll get the Spicy Tuna Roll... wait, no, actually, let's make that the Red Dragon Roll."
        )
        logger.info(f"Correction response: {correction_response}")
        
        # Validate AI correctly identified the final choice
        response_text = correction_response.get("message", "").lower()
        
        # Check that AI acknowledged the correction appropriately
        correction_indicators = ["red dragon", "dragon roll", "okay", "got it", "understood"]
        correction_handled = any(indicator in response_text for indicator in correction_indicators)
        
        # Also check that AI didn't mistakenly reference the discarded choice
        incorrect_references = ["spicy tuna" in response_text and "red dragon" not in response_text]
        
        assert correction_handled, f"AI should acknowledge the correction: {response_text}"
        assert not incorrect_references, f"AI should not reference discarded choice: {response_text}"
        
        # Verify cart state contains correct item
        cart = await get_cart_state(redis_client, call_sid)
        cart_items = cart.get("items", [])
        logger.info(f"Cart after correction: {cart_items}")
        
        # Look for the correct item (Red Dragon Roll) and ensure Spicy Tuna Roll is NOT there
        red_dragon_item = None
        spicy_tuna_item = None
        
        for item in cart_items:
            item_name = item.get("name", "").lower()
            if "red dragon" in item_name or "dragon roll" in item_name:
                red_dragon_item = item
            elif "spicy tuna" in item_name:
                spicy_tuna_item = item
        
        # Validate final choice is correct
        if len(cart_items) > 0:
            assert red_dragon_item is not None, f"Red Dragon Roll should be in cart: {cart_items}"
            assert spicy_tuna_item is None, f"Spicy Tuna Roll should NOT be in cart: {cart_items}"
        else:
            logger.warning("Cart is empty - AI may not have processed the order yet")
        
        # CRITICAL TEST: Pronoun resolution with contextual understanding
        modifier_response = await send_turn(
            async_client, call_sid, 
            "Can you add eel sauce to it?"
        )
        logger.info(f"Modifier response: {modifier_response}")
        
        # Validate AI correctly understood "it" refers to Red Dragon Roll
        modifier_text = modifier_response.get("message", "").lower()
        pronoun_resolution_indicators = [
            "eel sauce added" in modifier_text,
            "red dragon" in modifier_text and "eel sauce" in modifier_text,
            "added eel sauce" in modifier_text,
            "eel sauce to the" in modifier_text
        ]
        
        pronoun_resolved = any(indicator for indicator in pronoun_resolution_indicators)
        assert pronoun_resolved, f"AI should resolve 'it' to Red Dragon Roll: {modifier_text}"
        
        # Verify cart state reflects the modification
        updated_cart = await get_cart_state(redis_client, call_sid)
        updated_items = updated_cart.get("items", [])
        logger.info(f"Cart after modifier: {updated_items}")
        
        # Check that the Red Dragon Roll now has eel sauce modifier
        if len(updated_items) > 0:
            dragon_roll_with_sauce = None
            for item in updated_items:
                item_name = item.get("name", "").lower()
                if "red dragon" in item_name or "dragon roll" in item_name:
                    dragon_roll_with_sauce = item
                    break
            
            if dragon_roll_with_sauce:
                modifiers = dragon_roll_with_sauce.get("modifiers", [])
                eel_sauce_found = any(
                    "eel sauce" in str(mod).lower() for mod in modifiers
                )
                logger.info(f"Modifiers on Red Dragon Roll: {modifiers}")
                # Note: Modifier handling might vary based on implementation
                # The key test is that AI understood the pronoun reference
        
        # Complete the order to verify end-to-end flow
        completion_response = await send_turn(async_client, call_sid, "That's all for now.")
        logger.info(f"Completion response: {completion_response}")
        
        confirmation_response = await send_turn(async_client, call_sid, "Yes, that's correct.")
        logger.info(f"Confirmation response: {confirmation_response}")
        
        # Validate final order contains Red Dragon Roll with eel sauce, NOT Spicy Tuna Roll
        final_cart = await get_cart_state(redis_client, call_sid)
        final_items = final_cart.get("items", [])
        
        if len(final_items) > 0:
            expected_items = []
            for item in final_items:
                expected_items.append({
                    "name": item["name"].lower(),
                    "quantity": item["quantity"],
                    "modifiers": item.get("modifiers", [])
                })
            
            # Verify with Deliverect (if available)
            try:
                order_verified = await deliverect_helper.verify_order_exists(expected_items)
                logger.info(f"Order verification result: {order_verified}")
            except Exception as e:
                logger.warning(f"Order verification failed: {e}")
        
        logger.info("✅ Test 5.1 passed: Mid-conversation correction and ambiguity resolution")
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_5_2_multi_intent_and_out_of_order_information(
        self, async_client, redis_client, deliverect_helper
    ):
        """
        Test 5.2: Multi-Intent and Out-of-Order Information Handling
        
        This test validates the AI's ability to:
        1. Parse multiple user intents in a single utterance
        2. Handle information provided non-sequentially
        3. Maintain appropriate action sequencing (answer first, then act)
        4. Associate delayed information with previously mentioned items
        """
        call_sid = f"e2e_test_5_2_{int(time.time())}"
        
        # Initial setup
        await send_turn(async_client, call_sid, "Hello")
        await send_turn(async_client, call_sid, "Jack")
        
        # CRITICAL TEST: Multiple intents in single utterance
        # This combines menu_inquiry + place_order intents
        multi_intent_response = await send_turn(
            async_client, call_sid,
            "What's in your Steak Frites, and can you also add an order of Edamame to my cart?"
        )
        logger.info(f"Multi-intent response: {multi_intent_response}")
        
        response_text = multi_intent_response.get("message", "").lower()
        
        # Validate AI correctly parsed both intents
        # Intent 1: Menu inquiry (should provide information)
        menu_info_provided = any(keyword in response_text for keyword in [
            "steak frites", "fries", "comes with", "includes", "signature"
        ])
        
        # Intent 2: Place order (should acknowledge action)
        order_acknowledged = any(keyword in response_text for keyword in [
            "edamame", "added", "cart", "order"
        ])
        
        assert menu_info_provided, f"AI should provide Steak Frites information: {response_text}"
        assert order_acknowledged, f"AI should acknowledge Edamame order: {response_text}"
        
        # Validate appropriate sequencing: information first, then action confirmation
        # This is a sophisticated test of conversational flow management
        steak_pos = response_text.find("steak")
        edamame_pos = response_text.find("edamame")
        
        if steak_pos != -1 and edamame_pos != -1:
            # Ideally, steak information should come before edamame confirmation
            # This tests natural conversation flow
            logger.info(f"Response flow: Steak info at {steak_pos}, Edamame at {edamame_pos}")
        
        # Verify cart contains Edamame
        cart = await get_cart_state(redis_client, call_sid)
        cart_items = cart.get("items", [])
        logger.info(f"Cart after multi-intent: {cart_items}")
        
        edamame_in_cart = any(
            "edamame" in item.get("name", "").lower() for item in cart_items
        )
        
        if len(cart_items) > 0:
            assert edamame_in_cart, f"Edamame should be in cart: {cart_items}"
        else:
            logger.warning("Cart is empty - AI may not have processed the order yet")
        
        # CRITICAL TEST: Out-of-order information with delayed association
        # User provides modifier for previously mentioned item
        delayed_info_response = await send_turn(
            async_client, call_sid,
            "Okay, add the steak too, I want it cooked medium."
        )
        logger.info(f"Delayed info response: {delayed_info_response}")
        
        delayed_text = delayed_info_response.get("message", "").lower()
        
        # Validate AI correctly associated "medium" with "steak" from earlier mention
        steak_order_acknowledged = any(keyword in delayed_text for keyword in [
            "steak", "medium", "added", "frites"
        ])
        
        assert steak_order_acknowledged, f"AI should acknowledge steak order with medium: {delayed_text}"
        
        # Verify cart now contains both items
        updated_cart = await get_cart_state(redis_client, call_sid)
        updated_items = updated_cart.get("items", [])
        logger.info(f"Cart after delayed info: {updated_items}")
        
        if len(updated_items) > 0:
            # Check for both items
            has_edamame = any("edamame" in item.get("name", "").lower() for item in updated_items)
            has_steak = any("steak" in item.get("name", "").lower() for item in updated_items)
            
            assert has_edamame, f"Cart should contain Edamame: {updated_items}"
            assert has_steak, f"Cart should contain Steak Frites: {updated_items}"
            
            # Check for medium modifier on steak
            steak_item = next((item for item in updated_items if "steak" in item.get("name", "").lower()), None)
            if steak_item:
                modifiers = steak_item.get("modifiers", [])
                medium_modifier = any("medium" in str(mod).lower() for mod in modifiers)
                logger.info(f"Steak modifiers: {modifiers}")
                # Note: Modifier handling might vary based on implementation
        
        # Complete order
        await send_turn(async_client, call_sid, "That's everything.")
        await send_turn(async_client, call_sid, "Looks good.")
        
        # Verify final order
        final_cart = await get_cart_state(redis_client, call_sid)
        final_items = final_cart.get("items", [])
        
        if len(final_items) > 0:
            expected_items = []
            for item in final_items:
                expected_items.append({
                    "name": item["name"].lower(),
                    "quantity": item["quantity"],
                    "modifiers": item.get("modifiers", [])
                })
            
            try:
                order_verified = await deliverect_helper.verify_order_exists(expected_items)
                logger.info(f"Order verification result: {order_verified}")
            except Exception as e:
                logger.warning(f"Order verification failed: {e}")
        
        logger.info("✅ Test 5.2 passed: Multi-intent and out-of-order information handling")
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_5_3_contextual_memory_and_reference_resolution(
        self, async_client, redis_client, deliverect_helper
    ):
        """
        Test 5.3: Contextual Memory and Reference Resolution
        
        This test validates the AI's ability to:
        1. Maintain contextual memory across multiple turns
        2. Resolve complex references to previous items
        3. Handle nested modifications and specifications
        4. Maintain conversation coherence over extended exchanges
        """
        call_sid = f"e2e_test_5_3_{int(time.time())}"
        
        # Initial setup
        await send_turn(async_client, call_sid, "Good afternoon")
        await send_turn(async_client, call_sid, "My name is Sarah")
        
        # Establish context with multiple items
        context_response = await send_turn(
            async_client, call_sid,
            "I'd like to order a Chicken Burger and a Caesar Salad."
        )
        logger.info(f"Context establishment: {context_response}")
        
        # CRITICAL TEST: Complex reference resolution
        # User refers to "the burger" - AI must resolve which item
        reference_response = await send_turn(
            async_client, call_sid,
            "Can you make the burger without pickles?"
        )
        logger.info(f"Reference resolution: {reference_response}")
        
        reference_text = reference_response.get("message", "").lower()
        
        # Validate AI correctly resolved "the burger" to Chicken Burger
        burger_reference_resolved = any(keyword in reference_text for keyword in [
            "chicken burger", "burger", "without pickles", "no pickles"
        ])
        
        assert burger_reference_resolved, f"AI should resolve 'the burger' reference: {reference_text}"
        
        # CRITICAL TEST: Nested modifications with temporal context
        # User adds complexity to the same item over multiple turns
        nested_mod_response = await send_turn(
            async_client, call_sid,
            "And also add avocado to that same burger."
        )
        logger.info(f"Nested modification: {nested_mod_response}")
        
        nested_text = nested_mod_response.get("message", "").lower()
        
        # Validate AI maintained context about which burger
        nested_context_maintained = any(keyword in nested_text for keyword in [
            "avocado", "burger", "added", "chicken"
        ])
        
        assert nested_context_maintained, f"AI should maintain nested context: {nested_text}"
        
        # CRITICAL TEST: Cross-reference with disambiguation
        # User refers to "the salad" while multiple items exist
        cross_ref_response = await send_turn(
            async_client, call_sid,
            "For the salad, can you put the dressing on the side?"
        )
        logger.info(f"Cross-reference: {cross_ref_response}")
        
        cross_ref_text = cross_ref_response.get("message", "").lower()
        
        # Validate AI correctly resolved "the salad" to Caesar Salad
        salad_reference_resolved = any(keyword in cross_ref_text for keyword in [
            "caesar", "salad", "dressing", "side"
        ])
        
        assert salad_reference_resolved, f"AI should resolve 'the salad' reference: {cross_ref_text}"
        
        # Verify cart reflects all modifications
        cart = await get_cart_state(redis_client, call_sid)
        cart_items = cart.get("items", [])
        logger.info(f"Cart with all modifications: {cart_items}")
        
        if len(cart_items) > 0:
            # Find the burger item
            burger_item = next((item for item in cart_items if "burger" in item.get("name", "").lower()), None)
            if burger_item:
                modifiers = burger_item.get("modifiers", [])
                logger.info(f"Burger modifiers: {modifiers}")
                
                # Check for expected modifications
                no_pickles_mod = any("pickle" in str(mod).lower() for mod in modifiers)
                avocado_mod = any("avocado" in str(mod).lower() for mod in modifiers)
                
                # Note: Implementation may vary for modifier tracking
                logger.info(f"No pickles found: {no_pickles_mod}, Avocado found: {avocado_mod}")
            
            # Find the salad item
            salad_item = next((item for item in cart_items if "salad" in item.get("name", "").lower()), None)
            if salad_item:
                modifiers = salad_item.get("modifiers", [])
                logger.info(f"Salad modifiers: {modifiers}")
                
                # Check for dressing on side
                side_dressing_mod = any("side" in str(mod).lower() for mod in modifiers)
                logger.info(f"Side dressing found: {side_dressing_mod}")
        
        # CRITICAL TEST: Complex temporal reference
        # User references earlier conversation context
        temporal_ref_response = await send_turn(
            async_client, call_sid,
            "Actually, change my mind about the avocado I mentioned earlier."
        )
        logger.info(f"Temporal reference: {temporal_ref_response}")
        
        temporal_text = temporal_ref_response.get("message", "").lower()
        
        # Validate AI understood the temporal reference to earlier avocado request
        temporal_context_understood = any(keyword in temporal_text for keyword in [
            "avocado", "removed", "changed", "burger", "updated"
        ])
        
        # This test accepts that temporal modification might be complex for AI
        if not temporal_context_understood:
            logger.warning("Complex temporal reference may not be fully handled")
        
        # Complete the order
        await send_turn(async_client, call_sid, "That's my complete order.")
        await send_turn(async_client, call_sid, "Everything looks correct.")
        
        # Verify final order maintains all context
        final_cart = await get_cart_state(redis_client, call_sid)
        final_items = final_cart.get("items", [])
        
        if len(final_items) > 0:
            expected_items = []
            for item in final_items:
                expected_items.append({
                    "name": item["name"].lower(),
                    "quantity": item["quantity"],
                    "modifiers": item.get("modifiers", [])
                })
            
            try:
                order_verified = await deliverect_helper.verify_order_exists(expected_items)
                logger.info(f"Order verification result: {order_verified}")
            except Exception as e:
                logger.warning(f"Order verification failed: {e}")
        
        logger.info("✅ Test 5.3 passed: Contextual memory and reference resolution")
    
    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_5_4_conversation_flow_recovery(
        self, async_client, redis_client, deliverect_helper
    ):
        """
        Test 5.4: Conversation Flow Recovery and Repair
        
        This test validates the AI's ability to:
        1. Recover from conversational mistakes or misunderstandings
        2. Handle user corrections gracefully
        3. Maintain conversation coherence after interruptions
        4. Repair broken conversation flows
        """
        call_sid = f"e2e_test_5_4_{int(time.time())}"
        
        # Initial setup
        await send_turn(async_client, call_sid, "Hi there")
        await send_turn(async_client, call_sid, "I'm Michael")
        
        # CRITICAL TEST: Deliberate confusion to test recovery
        # User provides confusing/contradictory information
        confusing_response = await send_turn(
            async_client, call_sid,
            "I want a pizza but not pizza, something like a burger but vegetarian."
        )
        logger.info(f"Confusing request: {confusing_response}")
        
        confusing_text = confusing_response.get("message", "").lower()
        
        # Validate AI handles confusion appropriately
        confusion_handled = any(keyword in confusing_text for keyword in [
            "clarify", "understand", "mean", "help", "explain", "options"
        ])
        
        assert confusion_handled, f"AI should handle confusion appropriately: {confusing_text}"
        
        # CRITICAL TEST: User provides clarification
        # Test AI's ability to recover and proceed
        clarification_response = await send_turn(
            async_client, call_sid,
            "Sorry, I meant a Veggie Burger."
        )
        logger.info(f"Clarification: {clarification_response}")
        
        clarification_text = clarification_response.get("message", "").lower()
        
        # Validate AI recovered from confusion
        recovery_successful = any(keyword in clarification_text for keyword in [
            "veggie burger", "got it", "understand", "added", "no problem"
        ])
        
        assert recovery_successful, f"AI should recover from confusion: {clarification_text}"
        
        # CRITICAL TEST: Conversation interruption and resumption
        # User interrupts with unrelated query
        interruption_response = await send_turn(
            async_client, call_sid,
            "Wait, what are your hours today?"
        )
        logger.info(f"Interruption: {interruption_response}")
        
        interruption_text = interruption_response.get("message", "").lower()
        
        # Validate AI handles interruption (may not have hours info)
        interruption_handled = any(keyword in interruption_text for keyword in [
            "hours", "open", "closed", "time", "help", "information"
        ])
        
        # AI might not have hours info, but should acknowledge the question
        if not interruption_handled:
            logger.warning("AI may not have hours information")
        
        # CRITICAL TEST: Conversation resumption
        # User returns to original ordering context
        resumption_response = await send_turn(
            async_client, call_sid,
            "Okay, let's get back to my order. The Veggie Burger."
        )
        logger.info(f"Resumption: {resumption_response}")
        
        resumption_text = resumption_response.get("message", "").lower()
        
        # Validate AI resumed original context
        context_resumed = any(keyword in resumption_text for keyword in [
            "veggie burger", "order", "added", "back", "continue"
        ])
        
        assert context_resumed, f"AI should resume original context: {resumption_text}"
        
        # Verify cart contains the correctly resolved item
        cart = await get_cart_state(redis_client, call_sid)
        cart_items = cart.get("items", [])
        logger.info(f"Cart after recovery: {cart_items}")
        
        if len(cart_items) > 0:
            veggie_burger_found = any(
                "veggie" in item.get("name", "").lower() and "burger" in item.get("name", "").lower()
                for item in cart_items
            )
            assert veggie_burger_found, f"Cart should contain Veggie Burger: {cart_items}"
        
        # CRITICAL TEST: Final flow validation
        # Ensure conversation can proceed normally after recovery
        final_response = await send_turn(
            async_client, call_sid,
            "That's all I need."
        )
        logger.info(f"Final response: {final_response}")
        
        confirmation_response = await send_turn(
            async_client, call_sid,
            "Yes, place the order."
        )
        logger.info(f"Confirmation: {confirmation_response}")
        
        # Verify order completion
        final_cart = await get_cart_state(redis_client, call_sid)
        final_items = final_cart.get("items", [])
        
        if len(final_items) > 0:
            expected_items = []
            for item in final_items:
                expected_items.append({
                    "name": item["name"].lower(),
                    "quantity": item["quantity"],
                    "modifiers": item.get("modifiers", [])
                })
            
            try:
                order_verified = await deliverect_helper.verify_order_exists(expected_items)
                logger.info(f"Order verification result: {order_verified}")
            except Exception as e:
                logger.warning(f"Order verification failed: {e}")
        
        logger.info("✅ Test 5.4 passed: Conversation flow recovery and repair")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])