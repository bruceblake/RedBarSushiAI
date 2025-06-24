#!/usr/bin/env python3
"""
Performance testing script for RedBarSushiAI voice flow.
Measures response times for various interactions.
"""

import asyncio
import time
import json
from typing import Dict, Any, List

# Add the app directory to Python path
import sys
sys.path.insert(0, '/app')

from app.utils.agent_orchestration_async import AsyncAgentOrchestrator
from app.db_async import get_db


async def measure_response_time(orchestrator: AsyncAgentOrchestrator, 
                               call_sid: str, 
                               input_text: str, 
                               context: Dict[str, Any] = None) -> tuple[float, Dict[str, Any]]:
    """Measure the response time for a single interaction."""
    start_time = time.time()
    response = await orchestrator.process_voice_input(call_sid, input_text, context)
    end_time = time.time()
    
    duration = end_time - start_time
    return duration, response


async def run_performance_test():
    """Run a complete voice flow and measure response times."""
    print("🚀 Starting RedBarSushiAI Performance Test")
    print("=" * 60)
    
    # Initialize database
    async for db in get_db():
        # Initialize orchestrator
        orchestrator = AsyncAgentOrchestrator()
        await orchestrator.initialize(db)
        
        # Test call SID
        call_sid = f"TEST_PERF_{int(time.time())}"
        
        # Store timings
        timings = []
        
        # Test cases for a typical conversation flow
        test_cases = [
            ("", {"first_interaction": True}, "Initial greeting"),
            ("Bruce", None, "Name recognition"),
            ("I want to order", None, "Start ordering"),
            ("Two california rolls", None, "Add items to cart"),
            ("Add one spicy tuna roll", None, "Add more items"),
            ("That's all", None, "Complete order"),
            ("Yes that's correct", None, "Confirm order")
        ]
        
        print(f"Running {len(test_cases)} test cases...\n")
        
        for input_text, context, description in test_cases:
            print(f"📍 Test: {description}")
            print(f"   Input: '{input_text}'")
            
            duration, response = await measure_response_time(
                orchestrator, call_sid, input_text, context
            )
            
            timings.append({
                "description": description,
                "input": input_text,
                "duration": duration,
                "response_preview": response.get("text", "")[:100] + "..." if len(response.get("text", "")) > 100 else response.get("text", ""),
                "state": response.get("state", ""),
                "agent": response.get("agent", "")
            })
            
            print(f"   Response time: {duration:.2f}s")
            print(f"   State: {response.get('state', 'N/A')}")
            print(f"   Agent: {response.get('agent', 'N/A')}")
            print(f"   Response: {response.get('text', '')[:80]}...")
            print()
            
            # Small delay between requests
            await asyncio.sleep(0.1)
        
        break  # Exit after first db session
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 PERFORMANCE SUMMARY")
    print("=" * 60)
    
    total_time = sum(t["duration"] for t in timings)
    avg_time = total_time / len(timings) if timings else 0
    
    print(f"Total interactions: {len(timings)}")
    print(f"Total time: {total_time:.2f}s")
    print(f"Average response time: {avg_time:.2f}s")
    print(f"Fastest response: {min(t['duration'] for t in timings):.2f}s")
    print(f"Slowest response: {max(t['duration'] for t in timings):.2f}s")
    
    print("\n📈 Detailed Timings:")
    for timing in timings:
        print(f"  - {timing['description']}: {timing['duration']:.2f}s")
    
    # Identify slow interactions
    slow_threshold = 2.0  # seconds
    slow_interactions = [t for t in timings if t["duration"] > slow_threshold]
    
    if slow_interactions:
        print(f"\n⚠️  WARNING: {len(slow_interactions)} interactions took longer than {slow_threshold}s:")
        for timing in slow_interactions:
            print(f"  - {timing['description']}: {timing['duration']:.2f}s")
    else:
        print(f"\n✅ All interactions completed in under {slow_threshold}s!")
    
    # Save results to file
    with open("/app/performance_results.json", "w") as f:
        json.dump({
            "test_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "timings": timings,
            "summary": {
                "total_interactions": len(timings),
                "total_time": total_time,
                "average_time": avg_time,
                "min_time": min(t["duration"] for t in timings) if timings else 0,
                "max_time": max(t["duration"] for t in timings) if timings else 0
            }
        }, f, indent=2)
    
    print("\n💾 Results saved to performance_results.json")


if __name__ == "__main__":
    # Run the async test
    asyncio.run(run_performance_test())