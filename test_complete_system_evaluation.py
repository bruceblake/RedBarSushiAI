#!/usr/bin/env python3
"""
Complete System Evaluation with SentenceTransformers

This comprehensive test suite evaluates the entire AI system across:
1. Agent capabilities and responsibilities 
2. Sentiment analysis and emotional intelligence
3. Edge cases and system resilience
4. AI-first architecture verification
5. Overall system performance
"""

import asyncio
import httpx
import json
import time
import statistics
from typing import Dict, List, Any, Tuple
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Load model for comprehensive analysis
print("Loading SentenceTransformer model for complete system evaluation...")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("Model loaded successfully!")

class CompleteSystemEvaluator:
    """Comprehensive system evaluation framework."""
    
    def __init__(self):
        self.test_results = {}
        self.performance_metrics = {}
        
    async def run_complete_evaluation(self):
        """Run the complete system evaluation."""
        print("🔬 COMPLETE AI SYSTEM EVALUATION")
        print("="*80)
        
        evaluation_results = {}
        
        # 1. Core Agent Capability Testing
        print("\n📋 PHASE 1: Core Agent Capabilities")
        core_results = await self._test_core_agent_capabilities()
        evaluation_results["core_capabilities"] = core_results
        
        # 2. Sentiment & Emotional Intelligence Testing
        print("\n🧠 PHASE 2: Emotional Intelligence")
        sentiment_results = await self._test_emotional_intelligence()
        evaluation_results["emotional_intelligence"] = sentiment_results
        
        # 3. System Resilience & Edge Cases
        print("\n🛡️ PHASE 3: System Resilience")
        resilience_results = await self._test_system_resilience()
        evaluation_results["resilience"] = resilience_results
        
        # 4. AI-First Architecture Verification
        print("\n🤖 PHASE 4: AI-First Architecture")
        ai_first_results = await self._test_ai_first_architecture()
        evaluation_results["ai_first"] = ai_first_results
        
        # 5. Performance & Response Quality
        print("\n⚡ PHASE 5: Performance Analysis")
        performance_results = await self._test_performance_quality()
        evaluation_results["performance"] = performance_results
        
        # Generate comprehensive report
        print("\n📊 GENERATING COMPREHENSIVE SYSTEM REPORT")
        final_report = self._generate_system_report(evaluation_results)
        
        return final_report
    
    async def _test_core_agent_capabilities(self) -> Dict[str, Any]:
        """Test core agent capabilities across all scenarios."""
        
        capability_tests = [
            # Frontline Agent Core Tests
            ("Hello, I'm new here", ["greeting", "personalization", "guidance"]),
            ("My name is Alex Johnson", ["name_handling", "conversation_flow", "next_steps"]),
            ("I want to place an order", ["order_initiation", "menu_guidance", "process_flow"]),
            
            # Menu Agent Core Tests  
            ("What food do you have?", ["menu_display", "category_listing", "information_provision"]),
            ("How much is a chicken burger?", ["price_lookup", "item_information", "accuracy"]),
            ("Do you have vegetarian options?", ["menu_filtering", "dietary_accommodation", "helpfulness"]),
            
            # Cart Agent Core Tests
            ("Add a burger to my order", ["item_addition", "cart_management", "confirmation"]),
            ("Make that 2 burgers instead of 1", ["quantity_modification", "order_accuracy", "update_confirmation"]),
            ("What's in my cart so far?", ["cart_review", "order_summary", "price_calculation"]),
            
            # Order Processing Tests
            ("That's all for my order", ["order_completion", "final_review", "next_steps"]),
            ("Yes, the order is correct", ["order_confirmation", "processing", "customer_satisfaction"]),
            ("When will it be ready?", ["fulfillment_information", "time_estimation", "customer_service"])
        ]
        
        results = {
            "total_tests": len(capability_tests),
            "passed": 0,
            "failed": 0,
            "capability_scores": {},
            "response_quality": [],
            "test_details": []
        }
        
        for i, (test_input, expected_capabilities) in enumerate(capability_tests, 1):
            call_sid = f"capability_test_{i}"
            
            print(f"   Testing: {test_input[:50]}{'...' if len(test_input) > 50 else ''}")
            
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "http://localhost:8080/order/take_order",
                        json={"speech_result": test_input, "call_sid": call_sid},
                        timeout=15.0
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        ai_response = result.get('message', '')
                        
                        # Evaluate response quality
                        quality_score = self._evaluate_response_quality(test_input, ai_response, expected_capabilities)
                        results["response_quality"].append(float(quality_score))
                        
                        # Track capability performance
                        for capability in expected_capabilities:
                            if capability not in results["capability_scores"]:
                                results["capability_scores"][capability] = []
                            
                            cap_score = self._assess_capability_demonstration(ai_response, capability)
                            results["capability_scores"][capability].append(cap_score)
                        
                        results["passed"] += 1
                        results["test_details"].append({
                            "input": test_input,
                            "response": ai_response,
                            "quality_score": quality_score,
                            "capabilities": expected_capabilities,
                            "success": True
                        })
                        
                    else:
                        results["failed"] += 1
                        results["test_details"].append({
                            "input": test_input,
                            "error": f"HTTP {response.status_code}",
                            "capabilities": expected_capabilities,
                            "success": False
                        })
                        
            except Exception as e:
                results["failed"] += 1
                results["test_details"].append({
                    "input": test_input,
                    "error": str(e),
                    "capabilities": expected_capabilities,
                    "success": False
                })
            
            await asyncio.sleep(0.2)
        
        # Calculate summary statistics
        results["success_rate"] = (results["passed"] / results["total_tests"]) * 100
        results["avg_response_quality"] = statistics.mean(results["response_quality"]) if results["response_quality"] else 0
        
        # Calculate capability averages
        capability_averages = {}
        for capability, scores in results["capability_scores"].items():
            if scores:
                capability_averages[capability] = statistics.mean(scores)
        results["capability_averages"] = capability_averages
        
        print(f"   ✅ Core Capabilities: {results['success_rate']:.1f}% success rate")
        print(f"   📊 Avg Response Quality: {results['avg_response_quality']:.2f}")
        
        return results
    
    async def _test_emotional_intelligence(self) -> Dict[str, Any]:
        """Test emotional intelligence across various emotional states."""
        
        emotional_tests = [
            # Positive emotions
            ("I'm so excited to try your food!", "positive_enthusiasm"),
            ("This sounds amazing, thank you!", "positive_gratitude"),
            ("Great service, I'm really happy!", "positive_satisfaction"),
            
            # Negative emotions
            ("I'm disappointed with my last order", "negative_disappointment"),
            ("I'm frustrated, this is taking too long", "negative_frustration"),
            ("I'm angry about the service quality", "negative_anger"),
            
            # Neutral/Professional
            ("I need to place a business order", "neutral_professional"),
            ("Can you help me understand the menu?", "neutral_inquiry"),
            ("I have specific dietary requirements", "neutral_requirements"),
            
            # Complex emotions
            ("I'm nervous about ordering, I have allergies", "complex_anxious"),
            ("I'm confused and getting impatient", "complex_mixed"),
            ("I'm happy but in a rush", "complex_urgency")
        ]
        
        results = {
            "total_tests": len(emotional_tests),
            "passed": 0,
            "failed": 0,
            "emotional_scores": {},
            "empathy_scores": [],
            "appropriateness_scores": [],
            "test_details": []
        }
        
        for i, (test_input, emotion_type) in enumerate(emotional_tests, 1):
            call_sid = f"emotion_test_{i}"
            
            print(f"   Testing {emotion_type}: {test_input[:40]}{'...' if len(test_input) > 40 else ''}")
            
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "http://localhost:8080/order/take_order",
                        json={"speech_result": test_input, "call_sid": call_sid},
                        timeout=15.0
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        ai_response = result.get('message', '')
                        
                        # Evaluate emotional intelligence
                        empathy_score = self._assess_empathy(test_input, ai_response)
                        appropriateness_score = self._assess_emotional_appropriateness(test_input, ai_response, emotion_type)
                        
                        results["empathy_scores"].append(empathy_score)
                        results["appropriateness_scores"].append(appropriateness_score)
                        
                        if emotion_type not in results["emotional_scores"]:
                            results["emotional_scores"][emotion_type] = []
                        results["emotional_scores"][emotion_type].append((empathy_score + appropriateness_score) / 2)
                        
                        results["passed"] += 1
                        results["test_details"].append({
                            "input": test_input,
                            "response": ai_response,
                            "emotion_type": emotion_type,
                            "empathy_score": empathy_score,
                            "appropriateness_score": appropriateness_score,
                            "success": True
                        })
                        
                    else:
                        results["failed"] += 1
                        
            except Exception as e:
                results["failed"] += 1
            
            await asyncio.sleep(0.2)
        
        # Calculate summary statistics
        results["success_rate"] = (results["passed"] / results["total_tests"]) * 100
        results["avg_empathy"] = statistics.mean(results["empathy_scores"]) if results["empathy_scores"] else 0
        results["avg_appropriateness"] = statistics.mean(results["appropriateness_scores"]) if results["appropriateness_scores"] else 0
        
        print(f"   ✅ Emotional Intelligence: {results['success_rate']:.1f}% success rate")
        print(f"   💝 Avg Empathy Score: {results['avg_empathy']:.2f}")
        print(f"   🎭 Avg Appropriateness: {results['avg_appropriateness']:.2f}")
        
        return results
    
    async def _test_system_resilience(self) -> Dict[str, Any]:
        """Test system resilience against edge cases and difficult inputs."""
        
        resilience_tests = [
            # Edge case inputs
            ("", "empty_input"),
            (" ", "whitespace_only"),
            ("🍕🍔🍟🥤", "emoji_only"),
            ("a" * 1000, "very_long_input"),
            
            # Problematic inputs
            ("ERROR ERROR ERROR", "error_keywords"),
            ("CANCEL CANCEL CANCEL", "cancel_spam"),
            ("null undefined None", "programming_keywords"),
            ("SELECT * FROM users", "sql_injection"),
            
            # Confusing instructions
            ("No I don't want yes maybe", "contradictory"),
            ("I want a pizza burger taco salad", "too_many_items"),
            ("Make it hot cold spicy mild", "contradictory_modifiers"),
            
            # System stress tests
            ("Help help help help help", "repeated_keywords"),
            ("What what what what what", "question_spam"),
            ("I want I want I want I want", "phrase_repetition")
        ]
        
        results = {
            "total_tests": len(resilience_tests),
            "passed": 0,
            "failed": 0,
            "crashes": 0,
            "recovery_scores": [],
            "edge_case_handling": {},
            "test_details": []
        }
        
        for i, (test_input, test_type) in enumerate(resilience_tests, 1):
            call_sid = f"resilience_test_{i}"
            
            print(f"   Testing {test_type}: {repr(test_input[:30])}")
            
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "http://localhost:8080/order/take_order",
                        json={"speech_result": test_input, "call_sid": call_sid},
                        timeout=15.0
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        ai_response = result.get('message', '')
                        
                        # Evaluate system recovery
                        recovery_score = self._assess_system_recovery(test_input, ai_response, test_type)
                        results["recovery_scores"].append(recovery_score)
                        
                        if test_type not in results["edge_case_handling"]:
                            results["edge_case_handling"][test_type] = []
                        results["edge_case_handling"][test_type].append(recovery_score)
                        
                        results["passed"] += 1
                        results["test_details"].append({
                            "input": test_input,
                            "response": ai_response,
                            "test_type": test_type,
                            "recovery_score": recovery_score,
                            "success": True
                        })
                        
                    elif response.status_code == 500:
                        results["crashes"] += 1
                        results["test_details"].append({
                            "input": test_input,
                            "test_type": test_type,
                            "error": "System crash (500)",
                            "success": False
                        })
                        
                    else:
                        results["failed"] += 1
                        results["test_details"].append({
                            "input": test_input,
                            "test_type": test_type,
                            "error": f"HTTP {response.status_code}",
                            "success": False
                        })
                        
            except Exception as e:
                results["crashes"] += 1
                results["test_details"].append({
                    "input": test_input,
                    "test_type": test_type,
                    "error": str(e),
                    "success": False
                })
            
            await asyncio.sleep(0.2)
        
        # Calculate summary statistics
        results["success_rate"] = (results["passed"] / results["total_tests"]) * 100
        results["crash_rate"] = (results["crashes"] / results["total_tests"]) * 100
        results["avg_recovery"] = statistics.mean(results["recovery_scores"]) if results["recovery_scores"] else 0
        
        print(f"   ✅ Resilience: {results['success_rate']:.1f}% success rate")
        print(f"   💥 Crash Rate: {results['crash_rate']:.1f}%")
        print(f"   🔄 Avg Recovery Score: {results['avg_recovery']:.2f}")
        
        return results
    
    async def _test_ai_first_architecture(self) -> Dict[str, Any]:
        """Verify the AI-first architecture with no hardcoded responses."""
        
        ai_first_tests = [
            # Test for dynamic responses (same input should vary)
            ("Hello", "greeting_variation"),
            ("Hello", "greeting_variation"),
            ("Hello", "greeting_variation"),
            
            # Test for intelligent adaptation
            ("I'm a vegetarian", "adaptive_response"),
            ("I have food allergies", "adaptive_response"),
            ("I'm in a wheelchair", "adaptive_response"),
            
            # Test for contextual intelligence
            ("That's expensive", "context_awareness"),
            ("I don't understand", "context_awareness"),
            ("I've changed my mind", "context_awareness"),
            
            # Test for no fallback responses
            ("xyzabc123nonsense", "no_fallback"),
            ("blahblahblah", "no_fallback"),
            ("randomstring999", "no_fallback")
        ]
        
        results = {
            "total_tests": len(ai_first_tests),
            "passed": 0,
            "failed": 0,
            "variation_scores": [],
            "intelligence_scores": [],
            "no_fallback_verified": True,
            "test_details": []
        }
        
        greeting_responses = []
        
        for i, (test_input, test_type) in enumerate(ai_first_tests, 1):
            call_sid = f"ai_first_test_{i}"
            
            print(f"   Testing {test_type}: {test_input}")
            
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "http://localhost:8080/order/take_order",
                        json={"speech_result": test_input, "call_sid": call_sid},
                        timeout=15.0
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        ai_response = result.get('message', '')
                        
                        # Check for AI-first characteristics
                        intelligence_score = self._assess_ai_intelligence(ai_response, test_type)
                        results["intelligence_scores"].append(intelligence_score)
                        
                        # Collect greeting variations
                        if test_type == "greeting_variation":
                            greeting_responses.append(ai_response)
                        
                        # Check for hardcoded fallbacks
                        if self._detect_hardcoded_response(ai_response):
                            results["no_fallback_verified"] = False
                        
                        results["passed"] += 1
                        results["test_details"].append({
                            "input": test_input,
                            "response": ai_response,
                            "test_type": test_type,
                            "intelligence_score": intelligence_score,
                            "success": True
                        })
                        
                    else:
                        results["failed"] += 1
                        
            except Exception as e:
                results["failed"] += 1
            
            await asyncio.sleep(0.2)
        
        # Calculate variation in greeting responses
        if len(greeting_responses) >= 2:
            variation_score = self._calculate_response_variation(greeting_responses)
            results["variation_scores"].append(variation_score)
        
        # Calculate summary statistics
        results["success_rate"] = (results["passed"] / results["total_tests"]) * 100
        results["avg_intelligence"] = statistics.mean(results["intelligence_scores"]) if results["intelligence_scores"] else 0
        results["avg_variation"] = statistics.mean(results["variation_scores"]) if results["variation_scores"] else 0
        
        print(f"   ✅ AI-First: {results['success_rate']:.1f}% success rate")
        print(f"   🧠 Avg Intelligence Score: {results['avg_intelligence']:.2f}")
        print(f"   🔄 Response Variation: {results['avg_variation']:.2f}")
        print(f"   🚫 No Hardcoded Fallbacks: {results['no_fallback_verified']}")
        
        return results
    
    async def _test_performance_quality(self) -> Dict[str, Any]:
        """Test system performance and response quality."""
        
        performance_tests = [
            ("Hello, I want to order food", "standard_order"),
            ("What's your most popular item?", "information_request"),
            ("I want a chicken burger with fries", "complex_order"),
            ("Can you help me choose something?", "assistance_request"),
            ("I need to modify my order", "modification_request")
        ]
        
        results = {
            "total_tests": len(performance_tests),
            "response_times": [],
            "semantic_quality": [],
            "completeness_scores": [],
            "professionalism_scores": [],
            "test_details": []
        }
        
        for i, (test_input, test_type) in enumerate(performance_tests, 1):
            call_sid = f"performance_test_{i}"
            
            print(f"   Testing {test_type}: {test_input}")
            
            start_time = time.time()
            
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "http://localhost:8080/order/take_order",
                        json={"speech_result": test_input, "call_sid": call_sid},
                        timeout=15.0
                    )
                    
                    response_time = time.time() - start_time
                    results["response_times"].append(response_time)
                    
                    if response.status_code == 200:
                        result = response.json()
                        ai_response = result.get('message', '')
                        
                        # Evaluate response quality metrics
                        semantic_quality = self._assess_semantic_quality(test_input, ai_response)
                        completeness = self._assess_completeness(ai_response, test_type)
                        professionalism = self._assess_professionalism(ai_response)
                        
                        results["semantic_quality"].append(semantic_quality)
                        results["completeness_scores"].append(completeness)
                        results["professionalism_scores"].append(professionalism)
                        
                        results["test_details"].append({
                            "input": test_input,
                            "response": ai_response,
                            "test_type": test_type,
                            "response_time": response_time,
                            "semantic_quality": semantic_quality,
                            "completeness": completeness,
                            "professionalism": professionalism,
                            "success": True
                        })
                        
            except Exception as e:
                response_time = time.time() - start_time
                results["response_times"].append(response_time)
                results["test_details"].append({
                    "input": test_input,
                    "test_type": test_type,
                    "response_time": response_time,
                    "error": str(e),
                    "success": False
                })
            
            await asyncio.sleep(0.2)
        
        # Calculate summary statistics
        results["avg_response_time"] = statistics.mean(results["response_times"]) if results["response_times"] else 0
        results["avg_semantic_quality"] = statistics.mean(results["semantic_quality"]) if results["semantic_quality"] else 0
        results["avg_completeness"] = statistics.mean(results["completeness_scores"]) if results["completeness_scores"] else 0
        results["avg_professionalism"] = statistics.mean(results["professionalism_scores"]) if results["professionalism_scores"] else 0
        
        print(f"   ⚡ Avg Response Time: {results['avg_response_time']:.2f}s")
        print(f"   🎯 Avg Semantic Quality: {results['avg_semantic_quality']:.2f}")
        print(f"   📝 Avg Completeness: {results['avg_completeness']:.2f}")
        print(f"   👔 Avg Professionalism: {results['avg_professionalism']:.2f}")
        
        return results
    
    def _evaluate_response_quality(self, user_input: str, ai_response: str, capabilities: List[str]) -> float:
        """Evaluate overall response quality."""
        # Simple quality assessment based on response characteristics
        if not ai_response:
            return 0.0
        
        score = 0.5  # Base score
        
        # Check for appropriate length (not too short, not too long)
        if 20 <= len(ai_response) <= 200:
            score += 0.2
        
        # Check for professional tone indicators
        professional_indicators = ["please", "thank you", "help", "assist", "certainly"]
        if any(indicator in ai_response.lower() for indicator in professional_indicators):
            score += 0.2
        
        # Check semantic relevance using sentence transformers
        try:
            user_embedding = model.encode([user_input])
            response_embedding = model.encode([ai_response])
            similarity = cosine_similarity(user_embedding, response_embedding)[0][0]
            score += min(float(similarity), 0.3)  # Cap at 0.3 contribution
        except:
            pass
        
        return min(score, 1.0)
    
    def _assess_capability_demonstration(self, response: str, capability: str) -> float:
        """Assess how well the response demonstrates a specific capability."""
        capability_indicators = {
            "greeting": ["hello", "hi", "welcome", "good"],
            "personalization": ["name", "you", "your"],
            "guidance": ["help", "assist", "guide", "let me"],
            "menu_display": ["menu", "categories", "items", "have"],
            "price_lookup": ["$", "price", "cost"],
            "item_addition": ["add", "cart", "order"],
            "order_confirmation": ["confirm", "correct", "yes"],
            "empathy": ["understand", "sorry", "apologize"],
            "professional": ["certainly", "please", "thank you"]
        }
        
        indicators = capability_indicators.get(capability, [capability.lower()])
        response_lower = response.lower()
        
        matches = sum(1 for indicator in indicators if indicator in response_lower)
        return min(matches / len(indicators), 1.0)
    
    def _assess_empathy(self, user_input: str, ai_response: str) -> float:
        """Assess empathy in AI response."""
        empathy_words = ["understand", "sorry", "apologize", "feel", "know", "realize"]
        response_lower = ai_response.lower()
        
        empathy_count = sum(1 for word in empathy_words if word in response_lower)
        return min(empathy_count / 3, 1.0)  # Normalize to 0-1
    
    def _assess_emotional_appropriateness(self, user_input: str, ai_response: str, emotion_type: str) -> float:
        """Assess emotional appropriateness of response."""
        # Simple assessment based on emotion type
        response_lower = ai_response.lower()
        
        if "positive" in emotion_type:
            positive_words = ["great", "wonderful", "excellent", "happy", "glad"]
            score = min(sum(1 for word in positive_words if word in response_lower) / 2, 1.0)
        elif "negative" in emotion_type:
            supportive_words = ["sorry", "understand", "help", "assist", "apologize"]
            score = min(sum(1 for word in supportive_words if word in response_lower) / 2, 1.0)
        else:
            professional_words = ["help", "assist", "certainly", "please"]
            score = min(sum(1 for word in professional_words if word in response_lower) / 2, 1.0)
        
        return score
    
    def _assess_system_recovery(self, test_input: str, ai_response: str, test_type: str) -> float:
        """Assess how well the system recovers from edge cases."""
        if not ai_response:
            return 0.0
        
        # Basic recovery assessment
        score = 0.5  # Base score for not crashing
        
        # Check for helpful response even with problematic input
        helpful_indicators = ["help", "assist", "try", "please"]
        if any(indicator in ai_response.lower() for indicator in helpful_indicators):
            score += 0.3
        
        # Check for appropriate length
        if 10 <= len(ai_response) <= 300:
            score += 0.2
        
        return min(score, 1.0)
    
    def _assess_ai_intelligence(self, ai_response: str, test_type: str) -> float:
        """Assess AI intelligence in response."""
        if not ai_response:
            return 0.0
        
        # Check for dynamic, intelligent characteristics
        score = 0.0
        
        # Contextual awareness
        if len(ai_response) > 20:
            score += 0.3
        
        # Natural language quality
        if any(word in ai_response.lower() for word in ["help", "assist", "understand", "can", "would"]):
            score += 0.4
        
        # Avoidance of robotic responses
        robotic_phrases = ["error", "system", "process", "function"]
        if not any(phrase in ai_response.lower() for phrase in robotic_phrases):
            score += 0.3
        
        return min(score, 1.0)
    
    def _detect_hardcoded_response(self, response: str) -> bool:
        """Detect if response appears to be hardcoded."""
        hardcoded_indicators = [
            "error 404", "system error", "function not available",
            "please try again later", "service unavailable"
        ]
        
        response_lower = response.lower()
        return any(indicator in response_lower for indicator in hardcoded_indicators)
    
    def _calculate_response_variation(self, responses: List[str]) -> float:
        """Calculate variation in responses."""
        if len(responses) < 2:
            return 0.0
        
        # Calculate semantic diversity
        embeddings = model.encode(responses)
        similarities = []
        
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                similarity = cosine_similarity([embeddings[i]], [embeddings[j]])[0][0]
                similarities.append(similarity)
        
        # Higher variation = lower average similarity
        avg_similarity = statistics.mean(similarities)
        variation_score = 1.0 - avg_similarity
        
        return max(0.0, min(variation_score, 1.0))
    
    def _assess_semantic_quality(self, user_input: str, ai_response: str) -> float:
        """Assess semantic quality of response."""
        try:
            user_embedding = model.encode([user_input])
            response_embedding = model.encode([ai_response])
            similarity = cosine_similarity(user_embedding, response_embedding)[0][0]
            return float(similarity)
        except:
            return 0.0
    
    def _assess_completeness(self, response: str, test_type: str) -> float:
        """Assess completeness of response."""
        # Check if response addresses the request type appropriately
        if not response:
            return 0.0
        
        score = 0.5  # Base score
        
        # Length-based completeness
        if len(response) >= 30:
            score += 0.3
        
        # Content-based completeness
        if "?" in response:  # Asking follow-up questions
            score += 0.2
        
        return min(score, 1.0)
    
    def _assess_professionalism(self, response: str) -> float:
        """Assess professionalism of response."""
        if not response:
            return 0.0
        
        professional_indicators = ["please", "thank you", "certainly", "may i", "i'd be happy", "of course"]
        response_lower = response.lower()
        
        professional_count = sum(1 for indicator in professional_indicators if indicator in response_lower)
        
        # Check for appropriate capitalization and punctuation
        proper_format = response[0].isupper() if response else False
        
        score = min(professional_count / 3, 0.8)  # Up to 0.8 for professional language
        if proper_format:
            score += 0.2
        
        return min(score, 1.0)
    
    def _generate_system_report(self, evaluation_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive system evaluation report."""
        
        print("\n" + "="*80)
        print("📊 COMPREHENSIVE SYSTEM EVALUATION REPORT")
        print("="*80)
        
        # Calculate overall scores
        overall_scores = {}
        
        for phase_name, phase_results in evaluation_results.items():
            if "success_rate" in phase_results:
                overall_scores[phase_name] = phase_results["success_rate"]
        
        system_score = statistics.mean(overall_scores.values()) if overall_scores else 0
        
        print(f"\n🎯 OVERALL SYSTEM SCORE: {system_score:.1f}/100")
        
        # Phase-by-phase breakdown
        print(f"\n📋 PHASE BREAKDOWN:")
        for phase_name, score in overall_scores.items():
            emoji = "🌟" if score >= 90 else "✅" if score >= 80 else "⚠️" if score >= 70 else "❌"
            print(f"   {emoji} {phase_name.replace('_', ' ').title()}: {score:.1f}%")
        
        # Key insights
        print(f"\n💡 KEY INSIGHTS:")
        
        # Core capabilities
        core_results = evaluation_results.get("core_capabilities", {})
        if core_results.get("avg_response_quality", 0) >= 0.8:
            print(f"   ✅ Strong core agent capabilities")
        else:
            print(f"   ⚠️ Core capabilities need improvement")
        
        # Emotional intelligence
        ei_results = evaluation_results.get("emotional_intelligence", {})
        if ei_results.get("avg_empathy", 0) >= 0.7:
            print(f"   💝 Good emotional intelligence")
        else:
            print(f"   🧠 Emotional intelligence needs enhancement")
        
        # System resilience
        resilience_results = evaluation_results.get("resilience", {})
        if resilience_results.get("crash_rate", 100) <= 5:
            print(f"   🛡️ System is resilient to edge cases")
        else:
            print(f"   💥 System resilience needs improvement")
        
        # AI-first architecture
        ai_results = evaluation_results.get("ai_first", {})
        if ai_results.get("no_fallback_verified", False):
            print(f"   🤖 AI-first architecture verified")
        else:
            print(f"   🔧 Some hardcoded responses detected")
        
        # Performance
        perf_results = evaluation_results.get("performance", {})
        if perf_results.get("avg_response_time", 10) <= 3:
            print(f"   ⚡ Good performance (avg {perf_results.get('avg_response_time', 0):.1f}s)")
        else:
            print(f"   🐌 Performance could be improved")
        
        # Final recommendations
        print(f"\n🎯 RECOMMENDATIONS:")
        
        if system_score >= 90:
            print(f"   🌟 EXCELLENT: System demonstrates strong AI capabilities across all areas")
        elif system_score >= 80:
            print(f"   ✅ GOOD: System performs well with some areas for improvement")
        elif system_score >= 70:
            print(f"   ⚠️ ADEQUATE: System needs focused improvements in weak areas")
        else:
            print(f"   ❌ NEEDS WORK: System requires significant improvements")
        
        # Specific improvement areas
        weak_areas = [name for name, score in overall_scores.items() if score < 80]
        if weak_areas:
            print(f"   🔧 Focus improvement on: {', '.join(weak_areas)}")
        
        # Create final report structure
        final_report = {
            "overall_score": system_score,
            "phase_scores": overall_scores,
            "evaluation_results": evaluation_results,
            "timestamp": time.time(),
            "recommendations": []
        }
        
        return final_report

async def main():
    """Run complete system evaluation."""
    evaluator = CompleteSystemEvaluator()
    report = await evaluator.run_complete_evaluation()
    
    print(f"\n🎉 EVALUATION COMPLETE!")
    print(f"📄 Full report available in returned data structure")
    
    return report

if __name__ == "__main__":
    asyncio.run(main())