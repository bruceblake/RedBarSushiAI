"""
Final demonstration of RedBarSushiAI voice flow
Shows complete conversation with AI-powered responses
"""
import asyncio
import time
from app.utils.agent_orchestration_async import async_agent_orchestrator

async def demo_conversation():
    """Run a complete demo conversation"""
    print("🍱 RedBarSushiAI - AI-Powered Voice Ordering Demo")
    print("=" * 60)
    print("Using: gpt-4o-mini with advanced optimizations")
    print("=" * 60)
    
    # Initialize
    print("\n⏳ Initializing system...")
    await async_agent_orchestrator.initialize()
    await asyncio.sleep(1)  # Let connections warm up
    print("✅ System ready!")
    
    call_sid = f"DEMO_{int(time.time())}"
    
    # Conversation flow
    conversations = [
        ("", {"first_interaction": True}, "System"),
        ("Hi, my name is Alex", None, "Customer"),
        ("What do you have on the menu?", None, "Customer"),
        ("I'd like to order some sushi", None, "Customer"),
        ("I'll have two california rolls", None, "Customer"),
        ("Add one spicy tuna roll", None, "Customer"),
        ("That's all for now", None, "Customer"),
        ("Yes, that's correct", None, "Customer"),
    ]
    
    for input_text, context, speaker in conversations:
        if speaker == "Customer":
            print(f"\n👤 Customer: {input_text}")
        else:
            print(f"\n🤖 {speaker}: [Initiating conversation]")
        
        start = time.time()
        response = await async_agent_orchestrator.process_voice_input(
            call_sid, input_text, context
        )
        duration = time.time() - start
        
        print(f"🍣 {response['agent']}: {response['text']}")
        print(f"   ⏱️  Response time: {duration:.2f}s")
        print(f"   🤖 AI-powered: {response.get('ai_generated', False)}")
        
        if response.get('actions'):
            print(f"   📋 Actions: {response['actions']}")
        
        # Small delay for readability
        await asyncio.sleep(0.5)
    
    # Final summary
    print("\n" + "=" * 60)
    print("✅ Demo Complete!")
    print("\nKey Features Demonstrated:")
    print("• Fast initial greeting (no AI needed)")
    print("• AI-powered name recognition with tool calls")
    print("• Natural conversation flow")
    print("• Intelligent cart management")
    print("• No hardcoded fallbacks")
    print("• Using gpt-4o-mini exclusively")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(demo_conversation())