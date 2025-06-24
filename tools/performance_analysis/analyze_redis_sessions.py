#!/usr/bin/env python3
"""
Quick Redis session analysis script for RedBarSushiAI.

This script analyzes current Redis session storage to determine if
optimization is needed.
"""

import asyncio
import json
import sys
import os
from typing import Dict, Any, List
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.redis_async import get_redis_client
from app.config import settings


async def analyze_redis_sessions():
    """Analyze Redis session storage patterns and sizes."""
    redis = await get_redis_client()
    
    print("=== Redis Session Analysis ===\n")
    
    try:
        # Get Redis info
        info = await redis.info("memory")
        print(f"Redis Memory Usage:")
        print(f"  Used Memory: {info['used_memory_human']}")
        print(f"  Used Memory RSS: {info['used_memory_rss_human']}")
        print(f"  Peak Memory: {info['used_memory_peak_human']}")
        print()
        
        # Analyze FSM sessions
        print("FSM Session Analysis:")
        fsm_pattern = "fsm:*"
        fsm_keys = []
        cursor = 0
        
        while True:
            cursor, keys = await redis.scan(cursor, match=fsm_pattern, count=100)
            fsm_keys.extend(keys)
            if cursor == 0:
                break
        
        print(f"  Total FSM sessions: {len(fsm_keys)}")
        
        if fsm_keys:
            # Sample session sizes
            sample_size = min(10, len(fsm_keys))
            total_size = 0
            sizes = []
            
            for key in fsm_keys[:sample_size]:
                data = await redis.get(key)
                if data:
                    size = len(data)
                    sizes.append(size)
                    total_size += size
                    
                    # Parse to check structure
                    try:
                        session_data = json.loads(data)
                        print(f"\n  Sample session '{key.decode()}':")
                        print(f"    Size: {size} bytes")
                        print(f"    State: {session_data.get('current_state', 'unknown')}")
                        print(f"    Context keys: {list(session_data.get('context', {}).keys())}")
                        
                        # Check cart size if present
                        cart = session_data.get('context', {}).get('cart', [])
                        if cart:
                            print(f"    Cart items: {len(cart)}")
                            cart_size = len(json.dumps(cart))
                            print(f"    Cart data size: {cart_size} bytes ({cart_size/size*100:.1f}% of session)")
                    except:
                        pass
            
            if sizes:
                avg_size = sum(sizes) / len(sizes)
                print(f"\n  Average session size (sample): {avg_size:.0f} bytes")
                print(f"  Largest session (sample): {max(sizes)} bytes")
                print(f"  Smallest session (sample): {min(sizes)} bytes")
                
                # Estimate total memory for sessions
                estimated_total = avg_size * len(fsm_keys)
                print(f"\n  Estimated total FSM memory: {estimated_total/1024/1024:.2f} MB")
        
        # Analyze conversation store
        print("\n\nConversation Store Analysis:")
        conv_pattern = "conv:*"
        conv_keys = []
        cursor = 0
        
        while True:
            cursor, keys = await redis.scan(cursor, match=conv_pattern, count=100)
            conv_keys.extend(keys)
            if cursor == 0:
                break
        
        print(f"  Total conversation stores: {len(conv_keys)}")
        
        if conv_keys:
            # Sample conversation sizes
            sample_size = min(5, len(conv_keys))
            conv_sizes = []
            
            for key in conv_keys[:sample_size]:
                data = await redis.get(key)
                if data:
                    size = len(data)
                    conv_sizes.append(size)
                    
                    try:
                        conv_data = json.loads(data)
                        messages = conv_data.get('messages', [])
                        print(f"\n  Sample conversation '{key.decode()}':")
                        print(f"    Size: {size} bytes")
                        print(f"    Messages: {len(messages)}")
                        if messages:
                            msg_size = len(json.dumps(messages))
                            print(f"    Message data size: {msg_size} bytes ({msg_size/size*100:.1f}% of conversation)")
                    except:
                        pass
            
            if conv_sizes:
                avg_conv_size = sum(conv_sizes) / len(conv_sizes)
                print(f"\n  Average conversation size (sample): {avg_conv_size:.0f} bytes")
        
        # Check for any large keys
        print("\n\nLarge Key Analysis:")
        # This would require Redis 4.0+ with MEMORY USAGE command
        # For now, we'll check known patterns
        
        large_keys = []
        for pattern in ["fsm:*", "conv:*", "cache:*"]:
            cursor = 0
            while True:
                cursor, keys = await redis.scan(cursor, match=pattern, count=20)
                for key in keys:
                    data = await redis.get(key)
                    if data and len(data) > 10000:  # 10KB threshold
                        large_keys.append((key.decode(), len(data)))
                if cursor == 0:
                    break
        
        if large_keys:
            large_keys.sort(key=lambda x: x[1], reverse=True)
            print(f"  Found {len(large_keys)} keys > 10KB:")
            for key, size in large_keys[:5]:
                print(f"    {key}: {size/1024:.1f} KB")
        else:
            print("  No keys larger than 10KB found")
        
        # Performance recommendations
        print("\n\n=== Performance Recommendations ===")
        
        recommendations = []
        
        # Check average session size
        if fsm_keys and sizes and avg_size > 5000:
            recommendations.append(
                "- Session sizes are relatively large (>5KB avg). Consider:\n"
                "  * Storing large cart data separately with references\n"
                "  * Implementing compression for session data\n"
                "  * Moving conversation history to separate keys"
            )
        
        # Check total memory usage
        if fsm_keys and sizes:
            estimated_total = avg_size * len(fsm_keys)
            if estimated_total > 100 * 1024 * 1024:  # 100MB
                recommendations.append(
                    "- Total session memory usage is significant (>100MB). Consider:\n"
                    "  * Implementing session expiration/cleanup\n"
                    "  * Using Redis Hash data type for better memory efficiency\n"
                    "  * Partitioning session data across multiple keys"
                )
        
        # Check for large individual sessions
        if sizes and max(sizes) > 50000:  # 50KB
            recommendations.append(
                "- Some sessions are very large (>50KB). Consider:\n"
                "  * Setting limits on cart size\n"
                "  * Archiving old conversation data\n"
                "  * Implementing pagination for large data sets"
            )
        
        if recommendations:
            for rec in recommendations:
                print(rec)
        else:
            print("✓ No immediate optimization needed - session sizes are reasonable")
            print("✓ Current Redis usage appears efficient for typical load")
        
        # Final verdict
        print("\n=== Verdict ===")
        if not recommendations:
            print("Redis session storage is performing well. No optimization needed at this time.")
            return False
        else:
            print("Redis session optimization could provide benefits based on current usage patterns.")
            return True
            
    except Exception as e:
        print(f"Error analyzing Redis: {e}")
        return None
    finally:
        await redis.close()


async def main():
    """Run the analysis."""
    needs_optimization = await analyze_redis_sessions()
    
    print("\n" + "="*50)
    if needs_optimization is None:
        print("Analysis incomplete due to errors.")
    elif needs_optimization:
        print("Recommendation: Consider implementing Redis session optimization.")
    else:
        print("Recommendation: Current performance is adequate. Optimization can be deferred.")


if __name__ == "__main__":
    asyncio.run(main())