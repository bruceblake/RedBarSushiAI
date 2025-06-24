#!/usr/bin/env python3
"""
Generate test sessions for Redis performance analysis.
"""

import asyncio
import json
import random
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.redis_async import get_redis_client
from app.fsm.core import ConversationState
from app.utils.fsm_async import AsyncFSMManager
from app.utils.conversation_store_async import async_conversation_store


async def generate_test_sessions(count: int = 20):
    """Generate test FSM sessions with varying sizes."""
    redis = await get_redis_client()
    fsm_manager = AsyncFSMManager(redis_client=redis)
    
    print(f"Generating {count} test sessions...")
    
    menu_items = [
        {"name": "California Roll", "price": 12.95, "plu": "CAL001"},
        {"name": "Spicy Tuna Roll", "price": 14.95, "plu": "STU001"},
        {"name": "Salmon Sashimi", "price": 16.95, "plu": "SAL001"},
        {"name": "Miso Soup", "price": 3.95, "plu": "MSO001"},
        {"name": "Edamame", "price": 5.95, "plu": "EDA001"},
    ]
    
    states = [
        ConversationState.GREETING,
        ConversationState.MAIN_MENU,
        ConversationState.ORDERING,
        ConversationState.VALIDATION,
        ConversationState.CONFIRMATION
    ]
    
    for i in range(count):
        session_id = f"test_session_{i:03d}"
        
        # Create FSM
        fsm = await fsm_manager.get_fsm(session_id)
        
        # Random state
        state = random.choice(states)
        if state != ConversationState.GREETING:
            fsm.current_state = state
        
        # Build context
        context = {
            "customer_name": f"Test User {i}",
            "session_start": datetime.now().isoformat(),
        }
        
        # Add cart for some sessions
        if state in [ConversationState.ORDERING, ConversationState.VALIDATION, ConversationState.CONFIRMATION]:
            cart_size = random.randint(1, 5)
            cart = []
            for _ in range(cart_size):
                item = random.choice(menu_items).copy()
                item["quantity"] = random.randint(1, 3)
                item["modifications"] = []
                if random.random() > 0.7:
                    item["modifications"] = ["no wasabi", "extra ginger"]
                cart.append(item)
            context["cart"] = cart
            context["order_total"] = sum(item["price"] * item["quantity"] for item in cart)
        
        # Add conversation history for some
        if random.random() > 0.5:
            history_size = random.randint(2, 10)
            history = []
            for j in range(history_size):
                role = "user" if j % 2 == 0 else "assistant"
                history.append({
                    "role": role,
                    "content": f"Test message {j}",
                    "timestamp": datetime.now().isoformat()
                })
            context["conversation_history"] = history
        
        # Update FSM
        await fsm.update_context(context)
        await fsm_manager.save_fsm(session_id, fsm)
        
        # Also create conversation store for some
        if random.random() > 0.6:
            conv_data = {
                "id": session_id,
                "created_at": datetime.now().timestamp(),
                "messages": context.get("conversation_history", []),
                "context": {"menu_query": "test"},
                "resolved": False
            }
            await async_conversation_store.save_conversation(session_id, conv_data)
        
        if (i + 1) % 5 == 0:
            print(f"  Generated {i + 1} sessions...")
    
    print(f"✓ Generated {count} test sessions")
    await redis.close()


async def main():
    """Generate sessions and run analysis."""
    # Generate test data
    await generate_test_sessions(20)
    
    print("\nWaiting 2 seconds for data to settle...")
    await asyncio.sleep(2)
    
    # Run analysis
    from analyze_redis_sessions import analyze_redis_sessions
    print("\n" + "="*50 + "\n")
    await analyze_redis_sessions()


if __name__ == "__main__":
    asyncio.run(main())