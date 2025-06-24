#!/usr/bin/env python3
"""
Test script to demonstrate streaming AI responses for RedBarSushiAI.
This shows how streaming reduces perceived latency.
"""

import asyncio
import time
from typing import List, Tuple
from app.agents.frontline_async_ai import AsyncFrontlineVoiceAgentAI
from app.agents.ai_mixin import AIIntelligenceMixin

# Mock settings for testing
class MockSettings:
    OPENAI_API_KEY = "your-api-key-here"
    AI_MAX_TOKENS = 256
    FRONTEND_AGENT_MAX_TOKENS = 150
    DEFAULT_LLM_API_TIMEOUT = 10.0
    OPENAI_MAX_RETRIES = 1
    OPENAI_CLIENT_POOL_SIZE = 5
    RESTAURANT_NAME = "Red Bar Sushi"
    RESTAURANT_GREETING_NAME = "Sarah"


async def simulate_conversation():
    """Simulate a conversation comparing streaming vs non-streaming responses."""
    
    print("🍣 RedBarSushiAI Streaming Demo\n")
    print("This demo shows the difference between streaming and non-streaming AI responses.\n")
    
    # Test inputs
    test_inputs = [
        ("", {"first_interaction": True}),  # Initial greeting
        ("Hi, my name is John", {}),  # Name introduction
        ("I'd like to order some sushi", {}),  # Order intent
    ]
    
    # Create agent
    agent = AsyncFrontlineVoiceAgentAI()
    
    print("=" * 60)
    print("NON-STREAMING MODE (Traditional)")
    print("=" * 60)
    
    for input_text, context in test_inputs:
        print(f"\n👤 User: '{input_text}'" if input_text else "\n🎙️ [Call Connected]")
        
        start_time = time.time()
        
        # Non-streaming response
        response = await agent.process_voice_input(input_text, context)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"🤖 Agent: {response['text']}")
        print(f"⏱️  Response time: {duration:.2f}s (user waits entire time)")
    
    print("\n" + "=" * 60)
    print("STREAMING MODE (New Implementation)")
    print("=" * 60)
    
    # Reset agent state
    agent = AsyncFrontlineVoiceAgentAI()
    
    for input_text, context in test_inputs:
        print(f"\n👤 User: '{input_text}'" if input_text else "\n🎙️ [Call Connected]")
        
        start_time = time.time()
        first_chunk_time = None
        chunks_received = []
        
        # Streaming callback
        async def stream_callback(chunk: str, is_last: bool):
            nonlocal first_chunk_time
            if chunk and not first_chunk_time:
                first_chunk_time = time.time()
                print(f"🌊 First chunk received in: {first_chunk_time - start_time:.2f}s")
            
            if chunk:
                chunks_received.append((chunk, is_last))
                print(f"   → Chunk: '{chunk}' {'[FINAL]' if is_last else '[PARTIAL]'}")
        
        # Streaming response
        if input_text and "order" not in input_text.lower():  # Only stream non-tool responses
            response = await agent.process_voice_input(input_text, context, stream_callback)
        else:
            response = await agent.process_voice_input(input_text, context)
            print(f"🤖 Agent: {response['text']}")
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        if chunks_received:
            print(f"\n📊 Streaming Stats:")
            print(f"   - First response: {first_chunk_time - start_time:.2f}s")
            print(f"   - Total time: {total_duration:.2f}s")
            print(f"   - Chunks sent: {len(chunks_received)}")
            print(f"   - Perceived latency reduction: {((first_chunk_time - start_time) / total_duration * 100):.0f}% faster!")
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("✅ Streaming benefits:")
    print("   - Users hear the first part of response much faster")
    print("   - Natural conversation flow maintained")
    print("   - Better user experience with reduced perceived latency")
    print("   - Graceful fallback for tool-using responses")


async def demonstrate_chunking():
    """Demonstrate how responses are chunked for natural speech."""
    print("\n" + "=" * 60)
    print("CHUNKING DEMONSTRATION")
    print("=" * 60)
    
    test_response = """Thank you for calling Red Bar Sushi! I'm Sarah, your AI assistant. 
    I'd be happy to help you place an order today. We have amazing fresh sushi, 
    including California rolls, spicy tuna, and salmon sashimi. What sounds good to you?"""
    
    print(f"Full response ({len(test_response)} chars):")
    print(f'"{test_response}"\n')
    
    print("How it would be streamed:")
    
    # Simulate chunking logic
    chunks = []
    sentence_buffer = ""
    sentence_enders = [".", "!", "?", ":", "\n"]
    
    for char in test_response:
        sentence_buffer += char
        
        if any(ender in sentence_buffer for ender in sentence_enders):
            chunks.append(sentence_buffer.strip())
            sentence_buffer = ""
        elif len(sentence_buffer) > 50 and " " in sentence_buffer:
            # Find a good break point
            last_space = sentence_buffer.rfind(" ")
            if last_space > 20:
                chunks.append(sentence_buffer[:last_space].strip())
                sentence_buffer = sentence_buffer[last_space:].lstrip()
    
    if sentence_buffer.strip():
        chunks.append(sentence_buffer.strip())
    
    for i, chunk in enumerate(chunks):
        print(f"Chunk {i+1}: '{chunk}'")
    
    print(f"\nTotal chunks: {len(chunks)}")
    print("Each chunk is sent as soon as it's ready, creating natural speech flow!")


if __name__ == "__main__":
    print("Note: This is a demonstration script. In production, the streaming")
    print("functionality is integrated with Twilio ConversationRelay.\n")
    
    # Run demonstrations
    asyncio.run(simulate_conversation())
    asyncio.run(demonstrate_chunking())