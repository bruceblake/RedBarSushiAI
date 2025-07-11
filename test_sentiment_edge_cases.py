#!/usr/bin/env python3
"""
Sentiment-Based Edge Case Testing with SentenceTransformers

This test suite specifically focuses on how the AI system handles 
various emotional states, negative sentiment, and edge cases using
advanced semantic analysis.
"""

import asyncio
import httpx
import json
import time
from typing import Dict, List, Any, Tuple
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Load model for semantic analysis
print("Loading SentenceTransformer model for sentiment edge case testing...")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("Model loaded successfully!")

class AdvancedSentimentTester:
    """Advanced sentiment testing with emotional intelligence validation."""
    
    def __init__(self):
        # Define emotional state categories with example phrases
        self.emotional_states = {
            "angry": [
                "I'm really angry about this",
                "This is completely unacceptable",
                "I'm furious with your service",
                "What the hell is going on?",
                "This is ridiculous and I'm mad",
                "I can't believe how bad this is"
            ],
            "frustrated": [
                "I'm so frustrated right now",
                "This is taking way too long",
                "Why is this so complicated?",
                "I just want to order food, why is this hard?",
                "I've been trying to order for 10 minutes",
                "This shouldn't be this difficult"
            ],
            "confused": [
                "I'm really confused about your menu",
                "I don't understand what you're asking",
                "This doesn't make any sense to me",
                "Can you explain this better?",
                "I'm lost, what do I do?",
                "I have no idea what's happening"
            ],
            "impatient": [
                "I need to order quickly",
                "I'm in a huge rush",
                "Can we speed this up?",
                "I don't have time for this",
                "Hurry up please",
                "I'm running late and need food fast"
            ],
            "disappointed": [
                "I'm really disappointed with this",
                "This isn't what I expected",
                "I thought you'd have better service",
                "Last time was much better",
                "I'm not happy with this experience",
                "This is not meeting my expectations"
            ],
            "anxious": [
                "I'm nervous about ordering",
                "I have food allergies, I'm worried",
                "I'm anxious about getting the wrong order",
                "Will this be safe for me to eat?",
                "I'm stressed about the delivery time",
                "I'm worried this won't work out"
            ],
            "demanding": [
                "I want to speak to your manager",
                "I demand better service",
                "You need to fix this right now",
                "I expect a discount for this",
                "This is unacceptable, I want compensation",
                "I'm going to leave a bad review"
            ],
            "sarcastic": [
                "Oh great, another problem",
                "Well this is just fantastic",
                "Sure, take your time",
                "Yeah, this is exactly what I wanted",
                "Perfect, just perfect",
                "Oh wonderful, more issues"
            ]
        }
        
        # Define expected AI response characteristics for each emotional state
        self.expected_responses = {
            "angry": {
                "required_elements": ["apologize", "sorry", "understand", "help"],
                "tone": "calm_professional",
                "avoid": ["rush", "quick", "fast"]
            },
            "frustrated": {
                "required_elements": ["understand", "help", "assist", "guide"],
                "tone": "patient_helpful",
                "avoid": ["complicated", "difficult"]
            },
            "confused": {
                "required_elements": ["explain", "help", "guide", "simple"],
                "tone": "clear_explanatory",
                "avoid": ["assume", "obviously", "simple"]
            },
            "impatient": {
                "required_elements": ["quickly", "right away", "immediately", "fast"],
                "tone": "efficient_helpful",
                "avoid": ["slow", "wait", "patience"]
            },
            "disappointed": {
                "required_elements": ["sorry", "improve", "better", "understand"],
                "tone": "empathetic_recovery",
                "avoid": ["excuse", "always", "never"]
            },
            "anxious": {
                "required_elements": ["safe", "careful", "check", "sure"],
                "tone": "reassuring_supportive",
                "avoid": ["worry", "problem", "issue"]
            },
            "demanding": {
                "required_elements": ["understand", "help", "resolve", "assist"],
                "tone": "professional_de_escalating",
                "avoid": ["cannot", "unable", "impossible"]
            },
            "sarcastic": {
                "required_elements": ["help", "assist", "positive", "good"],
                "tone": "patient_positive",
                "avoid": ["sarcasm", "match_tone"]
            }
        }
    
    async def test_emotional_response(self, call_sid: str, input_text: str, emotion: str) -> Dict[str, Any]:
        """Test AI response to specific emotional input."""
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
                        "emotion": emotion,
                        "input": input_text
                    }
                
                result = response.json()
                ai_response = result.get('message', '')
                
                # Analyze emotional intelligence in response
                emotional_analysis = self._analyze_emotional_intelligence(input_text, ai_response, emotion)
                
                # Calculate semantic appropriateness
                semantic_score = self._calculate_emotional_semantic_match(input_text, ai_response, emotion)
                
                # Check for specific response requirements
                requirement_check = self._check_response_requirements(ai_response, emotion)
                
                return {
                    "success": True,
                    "emotion": emotion,
                    "input": input_text,
                    "response": ai_response,
                    "emotional_analysis": emotional_analysis,
                    "semantic_score": semantic_score,
                    "requirement_check": requirement_check,
                    "overall_score": self._calculate_overall_emotional_score(emotional_analysis, semantic_score, requirement_check)
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "emotion": emotion,
                    "input": input_text
                }
    
    def _analyze_emotional_intelligence(self, user_input: str, ai_response: str, emotion: str) -> Dict[str, Any]:
        """Analyze the emotional intelligence of AI response."""
        response_lower = ai_response.lower()
        
        # Check for empathy indicators
        empathy_words = ["understand", "sorry", "apologize", "feel", "know how", "realize"]
        empathy_count = sum(1 for word in empathy_words if word in response_lower)
        
        # Check for professional handling
        professional_words = ["help", "assist", "resolve", "address", "handle", "take care"]
        professional_count = sum(1 for word in professional_words if word in professional_words)
        
        # Check for inappropriate responses
        inappropriate_words = ["calm down", "relax", "your fault", "not my problem", "deal with it"]
        inappropriate_count = sum(1 for word in inappropriate_words if word in response_lower)
        
        # Calculate emotional intelligence score
        empathy_score = min(empathy_count / 2, 1.0)  # Cap at 1.0
        professional_score = min(professional_count / 2, 1.0)
        inappropriate_penalty = inappropriate_count * 0.3
        
        emotional_intelligence_score = max(0, (empathy_score + professional_score) - inappropriate_penalty)
        
        return {
            "empathy_score": empathy_score,
            "professional_score": professional_score,
            "inappropriate_penalty": inappropriate_penalty,
            "emotional_intelligence_score": emotional_intelligence_score,
            "empathy_indicators": empathy_count,
            "professional_indicators": professional_count,
            "inappropriate_indicators": inappropriate_count
        }
    
    def _calculate_emotional_semantic_match(self, user_input: str, ai_response: str, emotion: str) -> float:
        """Calculate how semantically appropriate the response is for the emotional context."""
        try:
            # Create ideal response examples for this emotion
            ideal_responses = {
                "angry": "I apologize and understand your frustration. Let me help resolve this for you right away.",
                "frustrated": "I understand this can be frustrating. Let me guide you through this step by step.",
                "confused": "Let me explain this clearly and help you understand your options.",
                "impatient": "I understand you're in a hurry. Let me help you order quickly.",
                "disappointed": "I'm sorry this didn't meet your expectations. Let me help make this better.",
                "anxious": "I understand your concerns. Let me make sure everything is handled carefully for you.",
                "demanding": "I understand your concerns and I'm here to help resolve this for you.",
                "sarcastic": "I'm here to help make this a positive experience for you."
            }
            
            ideal_response = ideal_responses.get(emotion, "I'm here to help you with your order.")
            
            # Encode both the AI response and ideal response
            ai_embedding = model.encode([ai_response])
            ideal_embedding = model.encode([ideal_response])
            
            # Calculate similarity
            similarity = cosine_similarity(ai_embedding, ideal_embedding)[0][0]
            return float(similarity)
            
        except Exception as e:
            print(f"Error calculating emotional semantic match: {e}")
            return 0.0
    
    def _check_response_requirements(self, ai_response: str, emotion: str) -> Dict[str, Any]:
        """Check if response meets specific requirements for the emotional state."""
        if emotion not in self.expected_responses:
            return {"met_requirements": False, "missing_elements": [], "inappropriate_elements": []}
        
        requirements = self.expected_responses[emotion]
        response_lower = ai_response.lower()
        
        # Check required elements
        required_elements = requirements.get("required_elements", [])
        missing_elements = []
        found_elements = []
        
        for element in required_elements:
            if element in response_lower:
                found_elements.append(element)
            else:
                missing_elements.append(element)
        
        # Check elements to avoid
        avoid_elements = requirements.get("avoid", [])
        inappropriate_elements = []
        
        for element in avoid_elements:
            if element in response_lower:
                inappropriate_elements.append(element)
        
        # Calculate requirement score
        if required_elements:
            requirement_score = len(found_elements) / len(required_elements)
        else:
            requirement_score = 1.0
        
        # Penalty for inappropriate elements
        inappropriate_penalty = len(inappropriate_elements) * 0.2
        final_score = max(0, requirement_score - inappropriate_penalty)
        
        return {
            "met_requirements": len(missing_elements) == 0,
            "missing_elements": missing_elements,
            "found_elements": found_elements,
            "inappropriate_elements": inappropriate_elements,
            "requirement_score": final_score
        }
    
    def _calculate_overall_emotional_score(self, emotional_analysis: Dict, semantic_score: float, requirement_check: Dict) -> float:
        """Calculate overall score for emotional response appropriateness."""
        ei_score = emotional_analysis["emotional_intelligence_score"]
        req_score = requirement_check["requirement_score"]
        
        # Weighted average: 40% emotional intelligence, 30% semantic match, 30% requirements
        overall_score = (ei_score * 0.4) + (semantic_score * 0.3) + (req_score * 0.3)
        return min(max(overall_score, 0.0), 1.0)

async def run_sentiment_edge_case_tests():
    """Run comprehensive sentiment-based edge case tests."""
    print("🧠 Starting Advanced Sentiment & Emotional Intelligence Testing\n")
    
    tester = AdvancedSentimentTester()
    
    overall_results = {}
    
    for emotion, test_phrases in tester.emotional_states.items():
        print(f"{'='*60}")
        print(f"😤 Testing {emotion.upper()} emotional state")
        print(f"{'='*60}")
        
        emotion_results = {
            "total_tests": len(test_phrases),
            "passed_tests": 0,
            "failed_tests": 0,
            "emotional_scores": [],
            "semantic_scores": [],
            "requirement_scores": [],
            "overall_scores": [],
            "test_details": []
        }
        
        for i, phrase in enumerate(test_phrases, 1):
            call_sid = f"sentiment_{emotion}_{i}"
            
            print(f"   {i}. Testing {emotion} input: '{phrase[:60]}{'...' if len(phrase) > 60 else ''}'")
            
            result = await tester.test_emotional_response(call_sid, phrase, emotion)
            
            if result["success"]:
                emotion_results["passed_tests"] += 1
                
                # Collect scores
                emotional_analysis = result["emotional_analysis"]
                emotion_results["emotional_scores"].append(emotional_analysis["emotional_intelligence_score"])
                emotion_results["semantic_scores"].append(result["semantic_score"])
                emotion_results["requirement_scores"].append(result["requirement_check"]["requirement_score"])
                emotion_results["overall_scores"].append(result["overall_score"])
                
                # Display results
                ei_score = emotional_analysis["emotional_intelligence_score"]
                semantic_score = result["semantic_score"]
                req_score = result["requirement_check"]["requirement_score"]
                overall_score = result["overall_score"]
                
                # Determine performance level
                if overall_score >= 0.8:
                    performance = "🌟 EXCELLENT"
                elif overall_score >= 0.6:
                    performance = "✅ GOOD"
                elif overall_score >= 0.4:
                    performance = "⚠️ NEEDS IMPROVEMENT"
                else:
                    performance = "❌ POOR"
                
                print(f"      {performance} Response: '{result['response'][:80]}{'...' if len(result['response']) > 80 else ''}'")
                print(f"      📊 Emotional Intelligence: {ei_score:.2f} | Semantic Match: {semantic_score:.2f} | Requirements: {req_score:.2f}")
                print(f"      🎯 Overall Score: {overall_score:.2f}")
                
                # Show specific feedback
                req_check = result["requirement_check"]
                if req_check["missing_elements"]:
                    print(f"      🔍 Missing: {', '.join(req_check['missing_elements'])}")
                if req_check["inappropriate_elements"]:
                    print(f"      ⚠️ Inappropriate: {', '.join(req_check['inappropriate_elements'])}")
                
            else:
                emotion_results["failed_tests"] += 1
                print(f"      ❌ FAILED: {result.get('error', 'Unknown error')}")
            
            emotion_results["test_details"].append(result)
            print()
            
            # Small delay between tests
            await asyncio.sleep(0.3)
        
        # Calculate emotion-specific statistics
        if emotion_results["overall_scores"]:
            avg_overall = sum(emotion_results["overall_scores"]) / len(emotion_results["overall_scores"])
            avg_emotional = sum(emotion_results["emotional_scores"]) / len(emotion_results["emotional_scores"])
            avg_semantic = sum(emotion_results["semantic_scores"]) / len(emotion_results["semantic_scores"])
            avg_requirements = sum(emotion_results["requirement_scores"]) / len(emotion_results["requirement_scores"])
        else:
            avg_overall = avg_emotional = avg_semantic = avg_requirements = 0
        
        success_rate = (emotion_results["passed_tests"] / emotion_results["total_tests"]) * 100
        
        print(f"📊 {emotion.upper()} Emotional State Results:")
        print(f"   ✅ Success Rate: {success_rate:.1f}% ({emotion_results['passed_tests']}/{emotion_results['total_tests']})")
        print(f"   🧠 Avg Emotional Intelligence: {avg_emotional:.2f}")
        print(f"   🎯 Avg Semantic Appropriateness: {avg_semantic:.2f}")
        print(f"   📋 Avg Requirement Fulfillment: {avg_requirements:.2f}")
        print(f"   🌟 Overall Emotional Handling Score: {avg_overall:.2f}")
        
        # Provide specific recommendations
        if avg_overall < 0.6:
            print(f"   💡 Recommendation: System needs significant improvement for {emotion} emotions")
        elif avg_overall < 0.8:
            print(f"   💡 Recommendation: System handles {emotion} emotions adequately but could improve")
        else:
            print(f"   💡 Recommendation: System handles {emotion} emotions very well")
        
        overall_results[emotion] = emotion_results
        print()
    
    # Generate comprehensive emotional intelligence report
    print(f"{'='*80}")
    print(f"🧠 COMPREHENSIVE EMOTIONAL INTELLIGENCE ANALYSIS")
    print(f"{'='*80}")
    
    # Calculate system-wide emotional intelligence metrics
    all_overall_scores = []
    all_emotional_scores = []
    all_semantic_scores = []
    all_requirement_scores = []
    
    for emotion_data in overall_results.values():
        all_overall_scores.extend(emotion_data["overall_scores"])
        all_emotional_scores.extend(emotion_data["emotional_scores"])
        all_semantic_scores.extend(emotion_data["semantic_scores"])
        all_requirement_scores.extend(emotion_data["requirement_scores"])
    
    if all_overall_scores:
        system_emotional_intelligence = sum(all_overall_scores) / len(all_overall_scores)
        system_empathy = sum(all_emotional_scores) / len(all_emotional_scores)
        system_semantic_appropriateness = sum(all_semantic_scores) / len(all_semantic_scores)
        system_requirement_fulfillment = sum(all_requirement_scores) / len(all_requirement_scores)
    else:
        system_emotional_intelligence = system_empathy = system_semantic_appropriateness = system_requirement_fulfillment = 0
    
    total_sentiment_tests = sum(data["total_tests"] for data in overall_results.values())
    total_sentiment_passed = sum(data["passed_tests"] for data in overall_results.values())
    sentiment_success_rate = (total_sentiment_passed / total_sentiment_tests) * 100 if total_sentiment_tests > 0 else 0
    
    print(f"📈 System-Wide Emotional Intelligence Metrics:")
    print(f"   🎯 Overall Emotional Intelligence Score: {system_emotional_intelligence:.2f}/1.0")
    print(f"   💝 Empathy & Professional Handling: {system_empathy:.2f}/1.0")
    print(f"   🎭 Semantic Emotional Appropriateness: {system_semantic_appropriateness:.2f}/1.0")
    print(f"   📋 Emotional Requirement Fulfillment: {system_requirement_fulfillment:.2f}/1.0")
    print(f"   ✅ Sentiment Test Success Rate: {sentiment_success_rate:.1f}%")
    
    # Emotional state performance ranking
    emotion_performance = {}
    for emotion, data in overall_results.items():
        if data["overall_scores"]:
            emotion_performance[emotion] = sum(data["overall_scores"]) / len(data["overall_scores"])
    
    if emotion_performance:
        best_handled_emotion = max(emotion_performance, key=emotion_performance.get)
        worst_handled_emotion = min(emotion_performance, key=emotion_performance.get)
        
        print(f"\n🏆 Best Handled Emotion: {best_handled_emotion.upper()} ({emotion_performance[best_handled_emotion]:.2f})")
        print(f"⚠️ Needs Most Improvement: {worst_handled_emotion.upper()} ({emotion_performance[worst_handled_emotion]:.2f})")
    
    # Final recommendations
    print(f"\n💡 System Emotional Intelligence Recommendations:")
    
    if system_emotional_intelligence >= 0.8:
        print(f"   🌟 EXCELLENT: System demonstrates strong emotional intelligence across all emotional states")
    elif system_emotional_intelligence >= 0.6:
        print(f"   ✅ GOOD: System handles emotions well but has room for improvement")
        if system_empathy < 0.6:
            print(f"   📝 Focus on: Improving empathy and emotional recognition")
        if system_semantic_appropriateness < 0.6:
            print(f"   📝 Focus on: Better semantic matching for emotional contexts")
        if system_requirement_fulfillment < 0.6:
            print(f"   📝 Focus on: Meeting specific emotional response requirements")
    else:
        print(f"   ❌ NEEDS IMPROVEMENT: System emotional intelligence requires significant enhancement")
        print(f"   🔧 Priority fixes needed for emotional handling")
    
    # Edge case resilience assessment
    edge_case_emotions = ["angry", "demanding", "sarcastic"]
    edge_case_scores = [emotion_performance.get(emotion, 0) for emotion in edge_case_emotions if emotion in emotion_performance]
    
    if edge_case_scores:
        edge_case_average = sum(edge_case_scores) / len(edge_case_scores)
        print(f"\n🔥 Edge Case Emotion Handling: {edge_case_average:.2f}")
        if edge_case_average >= 0.7:
            print(f"   ✅ System handles difficult emotions well")
        else:
            print(f"   ⚠️ System struggles with challenging emotional states")
    
    print(f"\n🎯 CONCLUSION: System demonstrates {'strong' if system_emotional_intelligence >= 0.7 else 'moderate' if system_emotional_intelligence >= 0.5 else 'weak'} emotional intelligence capabilities")
    
    return overall_results

if __name__ == "__main__":
    asyncio.run(run_sentiment_edge_case_tests())