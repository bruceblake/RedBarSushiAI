#!/usr/bin/env python3
"""
Comprehensive AI Agent Capability Testing with Sentiment Analysis

This test suite uses SentenceTransformers to analyze sentiment and ensures
each AI agent can handle all their responsibilities across various emotional states.
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

# Load sentence transformer model for semantic analysis
print("Loading SentenceTransformer model for semantic analysis...")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("Model loaded successfully!")

class SentimentAnalyzer:
    """Analyzes sentiment and emotional intelligence in AI responses."""
    
    def __init__(self):
        self.positive_phrases = [
            "happy to help", "great choice", "excellent", "wonderful", 
            "perfect", "thank you", "pleasure", "delighted"
        ]
        self.negative_phrases = [
            "sorry", "apologize", "unfortunately", "problem", 
            "issue", "trouble", "difficult", "cannot"
        ]
        self.professional_phrases = [
            "I understand", "let me help", "I can assist", "certainly",
            "of course", "I'd be happy to", "let me check", "please"
        ]
    
    def analyze_sentiment(self, text: str) -> Dict[str, float]:
        """Analyze sentiment of AI response."""
        text_lower = text.lower()
        
        # Count sentiment indicators
        positive_count = sum(1 for phrase in self.positive_phrases if phrase in text_lower)
        negative_count = sum(1 for phrase in self.negative_phrases if phrase in text_lower)
        professional_count = sum(1 for phrase in self.professional_phrases if phrase in text_lower)
        
        # Calculate sentiment scores
        total_words = len(text.split())
        
        return {
            "positive_score": positive_count / max(total_words, 1),
            "negative_score": negative_count / max(total_words, 1),
            "professional_score": professional_count / max(total_words, 1),
            "overall_sentiment": "positive" if positive_count > negative_count else "negative" if negative_count > 0 else "neutral"
        }
    
    def check_emotional_intelligence(self, user_input: str, ai_response: str) -> Dict[str, Any]:
        """Check if AI response shows appropriate emotional intelligence."""
        user_sentiment = self.analyze_sentiment(user_input)
        ai_sentiment = self.analyze_sentiment(ai_response)
        
        # Check if AI responds appropriately to user's emotional state
        user_emotion = user_sentiment["overall_sentiment"]
        ai_emotion = ai_sentiment["overall_sentiment"]
        
        appropriate_response = False
        reasoning = ""
        
        if user_emotion == "negative":
            # For negative user input, AI should be empathetic and helpful
            if ai_sentiment["professional_score"] > 0 or "help" in ai_response.lower():
                appropriate_response = True
                reasoning = "AI showed empathy/professionalism to negative user input"
            else:
                reasoning = "AI should be more empathetic to negative user input"
        elif user_emotion == "positive":
            # For positive user input, AI should maintain positive tone
            if ai_emotion in ["positive", "neutral"]:
                appropriate_response = True
                reasoning = "AI maintained appropriate positive/neutral tone"
            else:
                reasoning = "AI should maintain positive tone with positive user input"
        else:
            # For neutral input, professional tone is appropriate
            if ai_sentiment["professional_score"] > 0 or ai_emotion == "neutral":
                appropriate_response = True
                reasoning = "AI maintained professional tone"
            else:
                reasoning = "AI should maintain professional tone"
        
        return {
            "appropriate_response": appropriate_response,
            "reasoning": reasoning,
            "user_sentiment": user_sentiment,
            "ai_sentiment": ai_sentiment
        }

class AgentCapabilityTester:
    """Tests each AI agent's specific capabilities."""
    
    def __init__(self):
        self.sentiment_analyzer = SentimentAnalyzer()
        self.test_results = {}
    
    async def test_agent_response(self, call_sid: str, input_text: str, expected_capabilities: List[str]) -> Dict[str, Any]:
        """Test an agent's response and analyze its capabilities."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "http://localhost:8080/order/take_order",
                    json={"speech_result": input_text, "call_sid": call_sid},
                    timeout=15.0
                )
                
                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}",
                        "input": input_text,
                        "capabilities_tested": expected_capabilities
                    }
                
                result = response.json()
                ai_response = result.get('message', '')
                
                # Analyze sentiment and emotional intelligence
                sentiment_analysis = self.sentiment_analyzer.check_emotional_intelligence(input_text, ai_response)
                
                # Check if response demonstrates expected capabilities
                capability_results = self._check_capabilities(ai_response, expected_capabilities)
                
                # Use semantic similarity to verify response quality
                semantic_score = self._calculate_semantic_relevance(input_text, ai_response)
                
                return {
                    "success": True,
                    "input": input_text,
                    "response": ai_response,
                    "sentiment_analysis": sentiment_analysis,
                    "capability_results": capability_results,
                    "semantic_relevance": semantic_score,
                    "response_length": len(ai_response),
                    "capabilities_tested": expected_capabilities,
                    "http_status": response.status_code
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "input": input_text,
                    "capabilities_tested": expected_capabilities
                }
    
    def _check_capabilities(self, response: str, expected_capabilities: List[str]) -> Dict[str, bool]:
        """Check if response demonstrates expected capabilities."""
        response_lower = response.lower()
        results = {}
        
        capability_indicators = {
            "greeting": ["hello", "hi", "welcome", "good", "name"],
            "menu_knowledge": ["menu", "item", "food", "drink", "category", "available"],
            "cart_management": ["add", "cart", "order", "total", "item", "quantity"],
            "order_taking": ["would you like", "anything else", "what can", "how can"],
            "price_awareness": ["$", "price", "cost", "total", "amount"],
            "personalization": ["name", "customer", "you", "your"],
            "error_handling": ["sorry", "apologize", "try again", "help", "assist"],
            "confirmation": ["confirm", "correct", "verify", "sure", "right"],
            "emotional_intelligence": ["understand", "help", "assist", "sorry", "great"],
            "professional_tone": ["please", "thank you", "certainly", "of course", "I'd be happy"]
        }
        
        for capability in expected_capabilities:
            if capability in capability_indicators:
                indicators = capability_indicators[capability]
                results[capability] = any(indicator in response_lower for indicator in indicators)
            else:
                # Default check - just see if capability keyword appears
                results[capability] = capability.lower() in response_lower
        
        return results
    
    def _calculate_semantic_relevance(self, user_input: str, ai_response: str) -> float:
        """Calculate semantic relevance between user input and AI response."""
        try:
            # Encode both texts
            user_embedding = model.encode([user_input])
            response_embedding = model.encode([ai_response])
            
            # Calculate cosine similarity
            similarity = cosine_similarity(user_embedding, response_embedding)[0][0]
            return float(similarity)
        except Exception as e:
            print(f"Error calculating semantic similarity: {e}")
            return 0.0

# Test scenarios for each agent type
FRONTLINE_AGENT_TESTS = [
    # Basic greeting scenarios
    ("Hello", ["greeting", "personalization", "professional_tone"]),
    ("Hi there!", ["greeting", "emotional_intelligence"]),
    ("Good morning", ["greeting", "professional_tone"]),
    
    # Name collection scenarios
    ("My name is Sarah", ["personalization", "order_taking"]),
    ("I'm John Smith", ["personalization", "professional_tone"]),
    ("Call me Mike", ["personalization", "emotional_intelligence"]),
    
    # Emotional state variations
    ("I'm really hungry and need food fast!", ["emotional_intelligence", "order_taking", "professional_tone"]),
    ("I'm not sure what I want to eat", ["emotional_intelligence", "menu_knowledge", "order_taking"]),
    ("This is my first time calling", ["emotional_intelligence", "professional_tone", "order_taking"]),
    
    # Difficult scenarios
    ("I can't hear you very well", ["error_handling", "professional_tone"]),
    ("I'm in a hurry", ["emotional_intelligence", "order_taking"]),
    ("I don't know what you have", ["menu_knowledge", "order_taking", "professional_tone"])
]

MENU_AGENT_TESTS = [
    # Category queries
    ("What drinks do you have?", ["menu_knowledge", "professional_tone"]),
    ("Show me your food menu", ["menu_knowledge", "order_taking"]),
    ("What's in the appetizer section?", ["menu_knowledge", "professional_tone"]),
    
    # Specific item queries
    ("Do you have chicken burgers?", ["menu_knowledge", "price_awareness"]),
    ("Tell me about your steaks", ["menu_knowledge", "professional_tone"]),
    ("What's your most popular item?", ["menu_knowledge", "emotional_intelligence"]),
    
    # Price and details
    ("How much is a chicken burger?", ["menu_knowledge", "price_awareness", "professional_tone"]),
    ("What comes with the combo meals?", ["menu_knowledge", "professional_tone"]),
    ("Do you have any vegetarian options?", ["menu_knowledge", "emotional_intelligence"]),
    
    # Challenging queries
    ("I'm allergic to nuts, what can I eat?", ["menu_knowledge", "emotional_intelligence", "professional_tone"]),
    ("What's the healthiest thing on your menu?", ["menu_knowledge", "emotional_intelligence"]),
    ("I only have $10, what can I get?", ["menu_knowledge", "price_awareness", "emotional_intelligence"])
]

CART_AGENT_TESTS = [
    # Adding items
    ("I want a chicken burger", ["cart_management", "order_taking", "professional_tone"]),
    ("Add two steaks to my order", ["cart_management", "order_taking"]),
    ("I'll take a large combo meal", ["cart_management", "order_taking", "price_awareness"]),
    
    # Modifications
    ("Make that burger medium rare", ["cart_management", "order_taking", "professional_tone"]),
    ("Can I get extra cheese on that?", ["cart_management", "professional_tone"]),
    ("Hold the onions please", ["cart_management", "professional_tone"]),
    
    # Quantity and totals
    ("How much is my order so far?", ["cart_management", "price_awareness", "professional_tone"]),
    ("Change that to 3 burgers instead of 2", ["cart_management", "order_taking"]),
    ("Remove the fries from my order", ["cart_management", "professional_tone"]),
    
    # Complex scenarios
    ("I want to start my order over", ["cart_management", "error_handling", "professional_tone"]),
    ("That's not what I wanted", ["cart_management", "error_handling", "emotional_intelligence"]),
    ("Can you repeat my order back to me?", ["cart_management", "confirmation", "professional_tone"])
]

VALIDATION_AGENT_TESTS = [
    # Order confirmation
    ("Yes, that's correct", ["confirmation", "professional_tone"]),
    ("No, I wanted medium not well done", ["error_handling", "cart_management", "professional_tone"]),
    ("Can you change the drink to Coke?", ["cart_management", "professional_tone"]),
    
    # Customer information
    ("My phone number is 555-1234", ["personalization", "professional_tone"]),
    ("I want it for pickup", ["order_taking", "professional_tone"]),
    ("Delivery to 123 Main Street", ["order_taking", "professional_tone"]),
    
    # Final checks
    ("How long will it take?", ["professional_tone", "order_taking"]),
    ("What payment methods do you accept?", ["professional_tone", "order_taking"]),
    ("Is my order correct now?", ["confirmation", "professional_tone"])
]

FULFILLMENT_AGENT_TESTS = [
    # Payment processing
    ("I'll pay with credit card", ["professional_tone", "order_taking"]),
    ("Cash on delivery please", ["professional_tone", "order_taking"]),
    ("Do you accept Apple Pay?", ["professional_tone", "order_taking"]),
    
    # Delivery coordination
    ("When will my order be ready?", ["professional_tone", "order_taking"]),
    ("Can you call me when it's ready?", ["professional_tone", "personalization"]),
    ("I'll pick it up in 30 minutes", ["professional_tone", "order_taking"]),
    
    # Order completion
    ("Thank you for the order", ["professional_tone", "emotional_intelligence"]),
    ("Great, see you soon", ["professional_tone", "emotional_intelligence"]),
    ("Perfect, have a good day", ["professional_tone", "emotional_intelligence"])
]

async def run_comprehensive_agent_tests():
    """Run comprehensive tests for all AI agents."""
    print("🧪 Starting Comprehensive AI Agent Capability Testing with Sentiment Analysis\n")
    
    tester = AgentCapabilityTester()
    
    # Test suites for each agent focus area
    test_suites = {
        "Frontline Agent": FRONTLINE_AGENT_TESTS,
        "Menu Agent": MENU_AGENT_TESTS,
        "Cart Agent": CART_AGENT_TESTS,
        "Validation Agent": VALIDATION_AGENT_TESTS,
        "Fulfillment Agent": FULFILLMENT_AGENT_TESTS
    }
    
    overall_results = {}
    
    for agent_name, test_cases in test_suites.items():
        print(f"{'='*60}")
        print(f"🤖 Testing {agent_name}")
        print(f"{'='*60}")
        
        agent_results = {
            "total_tests": len(test_cases),
            "passed_tests": 0,
            "failed_tests": 0,
            "sentiment_scores": [],
            "semantic_scores": [],
            "capability_scores": {},
            "test_details": []
        }
        
        for i, (input_text, expected_capabilities) in enumerate(test_cases, 1):
            call_sid = f"{agent_name.lower().replace(' ', '_')}_test_{i}"
            
            print(f"   {i:2d}. Testing: '{input_text[:50]}{'...' if len(input_text) > 50 else ''}'")
            
            # Run the test
            result = await tester.test_agent_response(call_sid, input_text, expected_capabilities)
            
            if result["success"]:
                agent_results["passed_tests"] += 1
                
                # Collect metrics
                sentiment = result["sentiment_analysis"]
                agent_results["sentiment_scores"].append(sentiment["appropriate_response"])
                agent_results["semantic_scores"].append(result["semantic_relevance"])
                
                # Track capability performance
                for capability, demonstrated in result["capability_results"].items():
                    if capability not in agent_results["capability_scores"]:
                        agent_results["capability_scores"][capability] = []
                    agent_results["capability_scores"][capability].append(demonstrated)
                
                # Show result
                sentiment_emoji = "✅" if sentiment["appropriate_response"] else "⚠️"
                semantic_score = result["semantic_relevance"]
                print(f"      {sentiment_emoji} Response: '{result['response'][:60]}{'...' if len(result['response']) > 60 else ''}'")
                print(f"      📊 Sentiment: {sentiment['reasoning']}")
                print(f"      🎯 Semantic Relevance: {semantic_score:.3f}")
                
                # Show capability results
                capability_summary = []
                for cap, demonstrated in result["capability_results"].items():
                    emoji = "✅" if demonstrated else "❌"
                    capability_summary.append(f"{emoji}{cap}")
                print(f"      🔧 Capabilities: {', '.join(capability_summary)}")
                
            else:
                agent_results["failed_tests"] += 1
                print(f"      ❌ FAILED: {result.get('error', 'Unknown error')}")
            
            agent_results["test_details"].append(result)
            print()
            
            # Small delay between tests
            await asyncio.sleep(0.5)
        
        # Calculate agent summary statistics
        success_rate = (agent_results["passed_tests"] / agent_results["total_tests"]) * 100
        
        if agent_results["sentiment_scores"]:
            sentiment_success_rate = (sum(agent_results["sentiment_scores"]) / len(agent_results["sentiment_scores"])) * 100
        else:
            sentiment_success_rate = 0
        
        if agent_results["semantic_scores"]:
            avg_semantic_score = statistics.mean(agent_results["semantic_scores"])
        else:
            avg_semantic_score = 0
        
        print(f"📊 {agent_name} Results:")
        print(f"   ✅ Success Rate: {success_rate:.1f}% ({agent_results['passed_tests']}/{agent_results['total_tests']})")
        print(f"   😊 Sentiment Appropriateness: {sentiment_success_rate:.1f}%")
        print(f"   🎯 Average Semantic Relevance: {avg_semantic_score:.3f}")
        
        # Capability breakdown
        print(f"   🔧 Capability Performance:")
        for capability, scores in agent_results["capability_scores"].items():
            if scores:
                cap_success = (sum(scores) / len(scores)) * 100
                print(f"      {capability}: {cap_success:.1f}%")
        
        overall_results[agent_name] = agent_results
        print()
    
    # Overall system summary
    print(f"{'='*60}")
    print(f"🎯 OVERALL SYSTEM CAPABILITY ANALYSIS")
    print(f"{'='*60}")
    
    total_tests = sum(r["total_tests"] for r in overall_results.values())
    total_passed = sum(r["passed_tests"] for r in overall_results.values())
    overall_success_rate = (total_passed / total_tests) * 100
    
    print(f"📈 System-Wide Statistics:")
    print(f"   Total Tests Run: {total_tests}")
    print(f"   Total Passed: {total_passed}")
    print(f"   Overall Success Rate: {overall_success_rate:.1f}%")
    
    # Identify strongest and weakest areas
    agent_performance = {}
    for agent_name, results in overall_results.items():
        if results["total_tests"] > 0:
            agent_performance[agent_name] = (results["passed_tests"] / results["total_tests"]) * 100
    
    if agent_performance:
        best_agent = max(agent_performance, key=agent_performance.get)
        worst_agent = min(agent_performance, key=agent_performance.get)
        
        print(f"\n🏆 Best Performing Agent: {best_agent} ({agent_performance[best_agent]:.1f}%)")
        print(f"⚠️  Needs Improvement: {worst_agent} ({agent_performance[worst_agent]:.1f}%)")
    
    # System recommendations
    print(f"\n💡 System Recommendations:")
    
    all_sentiment_scores = []
    all_semantic_scores = []
    
    for results in overall_results.values():
        all_sentiment_scores.extend(results["sentiment_scores"])
        all_semantic_scores.extend(results["semantic_scores"])
    
    if all_sentiment_scores:
        overall_sentiment = (sum(all_sentiment_scores) / len(all_sentiment_scores)) * 100
        if overall_sentiment < 80:
            print(f"   📝 Improve emotional intelligence (current: {overall_sentiment:.1f}%)")
        else:
            print(f"   ✅ Emotional intelligence is strong ({overall_sentiment:.1f}%)")
    
    if all_semantic_scores:
        overall_semantic = statistics.mean(all_semantic_scores)
        if overall_semantic < 0.5:
            print(f"   📝 Improve response relevance (current: {overall_semantic:.3f})")
        else:
            print(f"   ✅ Response relevance is good ({overall_semantic:.3f})")
    
    if overall_success_rate < 85:
        print(f"   📝 System needs overall capability improvements")
        print(f"   🔧 Focus on areas with <80% success rates")
    else:
        print(f"   🎉 System demonstrates strong AI capabilities across all agents!")
    
    return overall_results

if __name__ == "__main__":
    asyncio.run(run_comprehensive_agent_tests())