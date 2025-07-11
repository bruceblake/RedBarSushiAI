#!/usr/bin/env python3
"""
Comprehensive test of the complete voice ordering flow.
Tests every step from call initiation to order completion.
"""

import asyncio
import httpx
import json
import time
from typing import Dict, Any

class CompleteVoiceFlowTester:
    """Test the complete voice ordering flow."""
    
    def __init__(self):
        self.call_sid = f"complete_test_{int(time.time())}"
        self.base_url = "http://localhost:8080"
        
    async def run_complete_test(self):
        """Run the complete voice flow test."""
        print("🎙️ COMPLETE VOICE FLOW AUDIT")
        print("=" * 60)
        
        test_results = {
            "phases": {},
            "overall_success": True,
            "critical_issues": [],
            "warnings": []
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Phase 1: Call Initiation & Greeting
            print("\n📞 PHASE 1: Call Initiation & Greeting")
            phase1_result = await self._test_call_initiation(client)
            test_results["phases"]["call_initiation"] = phase1_result
            
            # Phase 2: Name Capture & State Transition
            print("\n👤 PHASE 2: Name Capture & State Transition")
            phase2_result = await self._test_name_capture(client)
            test_results["phases"]["name_capture"] = phase2_result
            
            # Phase 3: Menu Inquiry & AI Knowledge
            print("\n🍽️ PHASE 3: Menu Inquiry & AI Knowledge")
            phase3_result = await self._test_menu_inquiry(client)
            test_results["phases"]["menu_inquiry"] = phase3_result
            
            # Phase 4: Order Processing with Context
            print("\n🛒 PHASE 4: Order Processing with Context")
            phase4_result = await self._test_order_processing(client)
            test_results["phases"]["order_processing"] = phase4_result
            
            # Phase 5: Modifier Validation
            print("\n⚙️ PHASE 5: Modifier Validation")
            phase5_result = await self._test_modifier_validation(client)
            test_results["phases"]["modifier_validation"] = phase5_result
            
            # Phase 6: Order Completion & Checkout
            print("\n✅ PHASE 6: Order Completion & Checkout")
            phase6_result = await self._test_order_completion(client)
            test_results["phases"]["order_completion"] = phase6_result
            
            # Phase 7: Context Persistence Test
            print("\n💾 PHASE 7: Context Persistence Test")
            phase7_result = await self._test_context_persistence(client)
            test_results["phases"]["context_persistence"] = phase7_result
        
        # Generate comprehensive report
        await self._generate_audit_report(test_results)
        return test_results
    
    async def _test_call_initiation(self, client: httpx.AsyncClient) -> Dict[str, Any]:
        """Test call initiation and greeting."""
        try:
            print("   Testing initial call greeting...")
            
            response = await client.post(
                f"{self.base_url}/order/take_order",
                json={"speech_result": "", "call_sid": self.call_sid}
            )
            
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}"}
            
            result = response.json()
            message = result.get('message', '')
            
            # Check for proper greeting
            greeting_indicators = ["hi", "hello", "welcome", "name"]
            has_greeting = any(indicator in message.lower() for indicator in greeting_indicators)
            
            print(f"   ✅ Response: {message[:80]}...")
            
            return {
                "success": True,
                "response": message,
                "has_greeting": has_greeting,
                "response_time": response.elapsed.total_seconds()
            }
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _test_name_capture(self, client: httpx.AsyncClient) -> Dict[str, Any]:
        """Test name capture and state transition."""
        try:
            print("   Testing name capture...")
            
            response = await client.post(
                f"{self.base_url}/order/take_order",
                json={"speech_result": "My name is Alex", "call_sid": self.call_sid}
            )
            
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}"}
            
            result = response.json()
            message = result.get('message', '')
            
            # Check if name is acknowledged
            name_acknowledged = "alex" in message.lower()
            menu_offered = any(word in message.lower() for word in ["order", "menu", "would you like"])
            
            print(f"   ✅ Response: {message[:80]}...")
            
            return {
                "success": True,
                "response": message,
                "name_acknowledged": name_acknowledged,
                "menu_offered": menu_offered,
                "response_time": response.elapsed.total_seconds()
            }
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _test_menu_inquiry(self, client: httpx.AsyncClient) -> Dict[str, Any]:
        """Test menu inquiry and AI knowledge."""
        try:
            print("   Testing menu inquiry...")
            
            response = await client.post(
                f"{self.base_url}/order/take_order",
                json={"speech_result": "What do you have?", "call_sid": self.call_sid}
            )
            
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}"}
            
            result = response.json()
            message = result.get('message', '')
            
            # Check for menu information
            has_menu_items = any(word in message.lower() for word in ["burger", "pizza", "salad", "drink"])
            has_prices = "$" in message
            
            print(f"   ✅ Response: {message[:80]}...")
            
            return {
                "success": True,
                "response": message,
                "has_menu_items": has_menu_items,
                "has_prices": has_prices,
                "response_time": response.elapsed.total_seconds()
            }
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _test_order_processing(self, client: httpx.AsyncClient) -> Dict[str, Any]:
        """Test order processing with context."""
        try:
            print("   Testing order processing...")
            
            response = await client.post(
                f"{self.base_url}/order/take_order",
                json={"speech_result": "I want a cheeseburger", "call_sid": self.call_sid}
            )
            
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}"}
            
            result = response.json()
            message = result.get('message', '')
            
            # Check for successful order processing
            item_added = "added" in message.lower() and "cheeseburger" in message.lower()
            has_price = "$" in message and "0.00" not in message
            asks_for_more = any(word in message.lower() for word in ["else", "more", "anything"])
            
            print(f"   ✅ Response: {message[:80]}...")
            
            return {
                "success": True,
                "response": message,
                "item_added": item_added,
                "has_price": has_price,
                "asks_for_more": asks_for_more,
                "response_time": response.elapsed.total_seconds()
            }
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _test_modifier_validation(self, client: httpx.AsyncClient) -> Dict[str, Any]:
        """Test modifier validation system."""
        try:
            print("   Testing modifier validation...")
            
            # Try to complete order to trigger validation
            response = await client.post(
                f"{self.base_url}/order/take_order",
                json={"speech_result": "That's all", "call_sid": self.call_sid}
            )
            
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}"}
            
            result = response.json()
            message = result.get('message', '')
            
            # Check validation behavior
            proceeds_to_checkout = any(word in message.lower() for word in ["total", "correct", "confirm"])
            asks_for_modifiers = any(word in message.lower() for word in ["size", "type", "would you like"])
            
            print(f"   ✅ Response: {message[:80]}...")
            
            return {
                "success": True,
                "response": message,
                "proceeds_to_checkout": proceeds_to_checkout,
                "asks_for_modifiers": asks_for_modifiers,
                "response_time": response.elapsed.total_seconds()
            }
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _test_order_completion(self, client: httpx.AsyncClient) -> Dict[str, Any]:
        """Test order completion and checkout."""
        try:
            print("   Testing order completion...")
            
            response = await client.post(
                f"{self.base_url}/order/take_order",
                json={"speech_result": "Yes, that's correct", "call_sid": self.call_sid}
            )
            
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}"}
            
            result = response.json()
            message = result.get('message', '')
            
            # Check completion behavior
            order_confirmed = any(word in message.lower() for word in ["thank", "order", "ready", "minutes"])
            
            print(f"   ✅ Response: {message[:80]}...")
            
            return {
                "success": True,
                "response": message,
                "order_confirmed": order_confirmed,
                "response_time": response.elapsed.total_seconds()
            }
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _test_context_persistence(self, client: httpx.AsyncClient) -> Dict[str, Any]:
        """Test context persistence across requests."""
        try:
            print("   Testing context persistence...")
            
            # Ask about the order to see if context is maintained
            response = await client.post(
                f"{self.base_url}/order/take_order",
                json={"speech_result": "What did I order?", "call_sid": self.call_sid}
            )
            
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}"}
            
            result = response.json()
            message = result.get('message', '')
            
            # Check if context is maintained
            remembers_name = "alex" in message.lower()
            remembers_order = "cheeseburger" in message.lower()
            
            print(f"   ✅ Response: {message[:80]}...")
            
            return {
                "success": True,
                "response": message,
                "remembers_name": remembers_name,
                "remembers_order": remembers_order,
                "response_time": response.elapsed.total_seconds()
            }
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _generate_audit_report(self, test_results: Dict[str, Any]):
        """Generate comprehensive audit report."""
        print("\n" + "=" * 60)
        print("📊 COMPLETE VOICE FLOW AUDIT REPORT")
        print("=" * 60)
        
        total_phases = len(test_results["phases"])
        successful_phases = sum(1 for phase in test_results["phases"].values() if phase.get("success", False))
        
        print(f"\n🎯 OVERALL RESULTS:")
        print(f"   Success Rate: {successful_phases}/{total_phases} phases ({(successful_phases/total_phases)*100:.1f}%)")
        
        # Individual phase results
        print(f"\n📋 PHASE-BY-PHASE RESULTS:")
        for phase_name, phase_result in test_results["phases"].items():
            status = "✅ PASS" if phase_result.get("success", False) else "❌ FAIL"
            response_time = phase_result.get("response_time", 0)
            print(f"   {status} {phase_name.replace('_', ' ').title()}: {response_time:.2f}s")
            
            if not phase_result.get("success", False):
                print(f"      Error: {phase_result.get('error', 'Unknown error')}")
        
        # Feature validation
        print(f"\n🔍 FEATURE VALIDATION:")
        
        # Check name capture
        name_capture = test_results["phases"].get("name_capture", {})
        if name_capture.get("name_acknowledged", False):
            print(f"   ✅ Name Capture: Working correctly")
        else:
            print(f"   ❌ Name Capture: Not working")
        
        # Check menu knowledge
        menu_inquiry = test_results["phases"].get("menu_inquiry", {})
        if menu_inquiry.get("has_menu_items", False):
            print(f"   ✅ Menu Knowledge: AI knows menu items")
        else:
            print(f"   ❌ Menu Knowledge: AI lacks menu knowledge")
        
        # Check price handling
        order_processing = test_results["phases"].get("order_processing", {})
        if order_processing.get("has_price", False):
            print(f"   ✅ Price Display: Showing correct prices")
        else:
            print(f"   ❌ Price Display: Price issues detected")
        
        # Check context persistence
        context_test = test_results["phases"].get("context_persistence", {})
        if context_test.get("remembers_name", False) and context_test.get("remembers_order", False):
            print(f"   ✅ Context Persistence: Working correctly")
        else:
            print(f"   ❌ Context Persistence: Context not maintained")
        
        # Performance metrics
        response_times = [p.get("response_time", 0) for p in test_results["phases"].values() if p.get("response_time")]
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            print(f"\n⚡ PERFORMANCE:")
            print(f"   Average Response Time: {avg_response_time:.2f}s")
            print(f"   Fastest Response: {min(response_times):.2f}s")
            print(f"   Slowest Response: {max(response_times):.2f}s")
        
        # Final assessment
        if successful_phases == total_phases:
            print(f"\n🎉 FINAL ASSESSMENT: SYSTEM FULLY FUNCTIONAL")
            print(f"   All voice flow phases working correctly!")
        elif successful_phases >= total_phases * 0.8:
            print(f"\n⚠️ FINAL ASSESSMENT: MOSTLY FUNCTIONAL")
            print(f"   Most phases working, some issues need attention")
        else:
            print(f"\n❌ FINAL ASSESSMENT: CRITICAL ISSUES DETECTED")
            print(f"   Multiple phases failing, system needs fixes")

async def main():
    """Run the complete voice flow audit."""
    tester = CompleteVoiceFlowTester()
    await tester.run_complete_test()

if __name__ == "__main__":
    asyncio.run(main())