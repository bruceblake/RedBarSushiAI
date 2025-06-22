"""
Comprehensive performance test for RedBarSushiAI voice flow
Tests all aspects of the system with detailed timing
"""
import asyncio
import time
import statistics
import json
from typing import List, Tuple, Dict
import logging

# Configure logging to show warnings only
logging.basicConfig(level=logging.WARNING)

# Import after logging setup
from app.utils.agent_orchestration_async import async_agent_orchestrator

class PerformanceTest:
    def __init__(self):
        self.results = []
        self.target_times = {
            "greeting": 0.1,
            "name_recognition": 2.0,
            "menu_inquiry": 2.0,
            "order_start": 2.0,
            "add_item": 1.5,
            "order_completion": 1.5,
            "confirmation": 1.5
        }
    
    async def measure_response(self, call_sid: str, input_text: str, context=None) -> Tuple[float, Dict]:
        """Measure response time and return duration and full response"""
        start = time.time()
        response = await async_agent_orchestrator.process_voice_input(call_sid, input_text, context)
        duration = time.time() - start
        return duration, response
    
    def print_result(self, test_name: str, duration: float, response: Dict, target: float):
        """Print test result with color coding"""
        text = response.get("text", "")[:60] + "..."
        agent = response.get("agent", "Unknown")
        cached = response.get("from_cache", False)
        
        # Color coding
        if duration <= target:
            status = "✅ PASS"
            color = "\033[92m"  # Green
        elif duration <= target * 1.5:
            status = "⚠️  SLOW"
            color = "\033[93m"  # Yellow
        else:
            status = "❌ FAIL"
            color = "\033[91m"  # Red
        
        reset = "\033[0m"
        
        print(f"{color}{status}{reset} {test_name:25} {duration:6.2f}s (target: {target:.1f}s)")
        print(f"     Agent: {agent}, Cached: {cached}")
        print(f"     Response: {text}")
        print()
    
    async def run_conversation_flow(self, test_id: int) -> Dict:
        """Run a complete conversation flow and measure each step"""
        call_sid = f"PERF_TEST_{int(time.time())}_{test_id}"
        flow_results = {}
        
        print(f"\n{'='*60}")
        print(f"Test Run #{test_id + 1}")
        print(f"{'='*60}\n")
        
        # Test 1: Initial greeting
        duration, response = await self.measure_response(
            call_sid, "", {"first_interaction": True}
        )
        flow_results["greeting"] = duration
        self.print_result("Initial Greeting", duration, response, self.target_times["greeting"])
        
        # Test 2: Name recognition
        duration, response = await self.measure_response(call_sid, "Bruce")
        flow_results["name_recognition"] = duration
        self.print_result("Name Recognition", duration, response, self.target_times["name_recognition"])
        
        # Test 3: Menu inquiry
        duration, response = await self.measure_response(call_sid, "What's on the menu?")
        flow_results["menu_inquiry"] = duration
        self.print_result("Menu Inquiry", duration, response, self.target_times["menu_inquiry"])
        
        # Test 4: Start ordering
        duration, response = await self.measure_response(call_sid, "I want to order")
        flow_results["order_start"] = duration
        self.print_result("Start Ordering", duration, response, self.target_times["order_start"])
        
        # Test 5: Add items
        items = [
            ("Two california rolls", "add_item_1"),
            ("Add one spicy tuna roll", "add_item_2"),
            ("Three salmon sashimi", "add_item_3")
        ]
        
        for item, key in items:
            duration, response = await self.measure_response(call_sid, item)
            flow_results[key] = duration
            self.print_result(f"Add Item: {item[:20]}...", duration, response, self.target_times["add_item"])
        
        # Test 6: Complete order
        duration, response = await self.measure_response(call_sid, "That's all")
        flow_results["order_completion"] = duration
        self.print_result("Order Completion", duration, response, self.target_times["order_completion"])
        
        # Test 7: Confirm order
        duration, response = await self.measure_response(call_sid, "Yes that's correct")
        flow_results["confirmation"] = duration
        self.print_result("Order Confirmation", duration, response, self.target_times["confirmation"])
        
        return flow_results
    
    async def run_stress_test(self, num_concurrent: int = 3):
        """Run multiple conversations concurrently to test system under load"""
        print(f"\n{'='*60}")
        print(f"STRESS TEST: {num_concurrent} Concurrent Conversations")
        print(f"{'='*60}\n")
        
        tasks = []
        for i in range(num_concurrent):
            task = asyncio.create_task(self.run_conversation_flow(i))
            tasks.append(task)
            # Stagger starts slightly
            await asyncio.sleep(0.1)
        
        results = await asyncio.gather(*tasks)
        return results
    
    def print_summary(self, all_results: List[Dict]):
        """Print summary statistics"""
        print(f"\n{'='*60}")
        print("PERFORMANCE SUMMARY")
        print(f"{'='*60}\n")
        
        # Aggregate results by test type
        aggregated = {}
        for result in all_results:
            for test_name, duration in result.items():
                if test_name not in aggregated:
                    aggregated[test_name] = []
                aggregated[test_name].append(duration)
        
        # Print statistics
        print(f"{'Test':<25} {'Avg':>8} {'Min':>8} {'Max':>8} {'Target':>8} {'Status':<10}")
        print("-" * 75)
        
        for test_name, durations in aggregated.items():
            avg = statistics.mean(durations)
            min_time = min(durations)
            max_time = max(durations)
            target = self.target_times.get(test_name.split("_")[0], 2.0)
            
            if avg <= target:
                status = "✅ PASS"
            elif avg <= target * 1.5:
                status = "⚠️  SLOW"
            else:
                status = "❌ FAIL"
            
            print(f"{test_name:<25} {avg:>8.2f} {min_time:>8.2f} {max_time:>8.2f} {target:>8.2f} {status:<10}")
        
        # Overall assessment
        print(f"\n{'='*60}")
        total_tests = sum(len(durations) for durations in aggregated.values())
        passing = sum(1 for durations in aggregated.values() 
                     for d in durations 
                     if d <= self.target_times.get(test_name.split("_")[0], 2.0))
        pass_rate = (passing / total_tests) * 100 if total_tests > 0 else 0
        
        print(f"Total Tests: {total_tests}")
        print(f"Passing: {passing} ({pass_rate:.1f}%)")
        
        if pass_rate >= 90:
            print("\n🎉 EXCELLENT! System is performing well!")
        elif pass_rate >= 70:
            print("\n⚠️  GOOD, but some optimizations needed.")
        else:
            print("\n❌ NEEDS IMPROVEMENT. Many responses are too slow.")

async def main():
    print("🚀 RedBarSushiAI Comprehensive Performance Test")
    print("=" * 60)
    
    # Initialize the orchestrator
    print("\nInitializing system...")
    await async_agent_orchestrator.initialize()
    print("✅ System initialized")
    
    # Give connection pool time to warm up
    print("⏳ Warming up connections...")
    await asyncio.sleep(2)
    
    # Create test instance
    tester = PerformanceTest()
    
    # Run single conversation flow
    print("\n" + "="*60)
    print("SINGLE CONVERSATION TEST")
    print("="*60)
    
    single_result = await tester.run_conversation_flow(0)
    
    # Run stress test
    stress_results = await tester.run_stress_test(num_concurrent=3)
    
    # Combine all results
    all_results = [single_result] + stress_results
    
    # Print summary
    tester.print_summary(all_results)
    
    print("\n✅ Performance test complete!")

if __name__ == "__main__":
    asyncio.run(main())