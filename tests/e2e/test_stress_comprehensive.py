"""
Comprehensive stress testing for the Red Bar Sushi AI system.
Tests system behavior under extreme load and edge cases.
"""
import asyncio
import time
import pytest
import json
import random
import string
from fastapi.testclient import TestClient
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics
import threading

from app.main import app

client = TestClient(app)

class TestComprehensiveStress:
    """Comprehensive stress tests for the entire system."""
    
    def test_endpoint_discovery_stress(self):
        """Test all discovered endpoints under stress."""
        endpoints = [
            "/health", "/docs", "/openapi.json", "/voice/", 
            "/api/deliverect/register", "/menu/categories", "/menu/items",
            "/order/take-order", "/order/checkout", "/order/status",
            "/api/conversation-relay"
        ]
        
        def stress_endpoint(endpoint_data):
            endpoint, method = endpoint_data
            results = []
            
            for i in range(10):  # 10 requests per endpoint
                start_time = time.time()
                try:
                    if method == "GET":
                        response = client.get(endpoint)
                    elif method == "POST":
                        if "voice" in endpoint:
                            # Voice webhook data
                            data = {
                                'CallSid': f'CA{random.randint(1000000000, 9999999999):030d}',
                                'AccountSid': 'ACb8391ed8d92871d85180ca9adea481b6',
                                'From': '+15551234567',
                                'To': '+17036467799',
                            }
                            response = client.post(endpoint, data=data)
                        else:
                            response = client.post(endpoint, json={})
                    else:
                        response = client.get(endpoint)  # Default to GET
                    
                    end_time = time.time()
                    results.append({
                        'endpoint': endpoint,
                        'status_code': response.status_code,
                        'response_time': end_time - start_time,
                        'success': response.status_code < 500
                    })
                except Exception as e:
                    end_time = time.time()
                    results.append({
                        'endpoint': endpoint,
                        'status_code': 0,
                        'response_time': end_time - start_time,
                        'success': False,
                        'error': str(e)
                    })
            
            return results
        
        # Prepare endpoint-method pairs
        endpoint_methods = [
            ("/health", "GET"), ("/docs", "GET"), ("/openapi.json", "GET"),
            ("/voice/", "POST"), ("/menu/categories", "GET"), ("/menu/items", "GET")
        ]
        
        # Run stress test on all endpoints concurrently
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(stress_endpoint, ep_method) for ep_method in endpoint_methods]
            all_results = []
            for future in as_completed(futures):
                all_results.extend(future.result())
        
        # Analyze results
        by_endpoint = {}
        for result in all_results:
            endpoint = result['endpoint']
            if endpoint not in by_endpoint:
                by_endpoint[endpoint] = []
            by_endpoint[endpoint].append(result)
        
        print("Stress test results by endpoint:")
        for endpoint, results in by_endpoint.items():
            success_count = sum(1 for r in results if r['success'])
            total_count = len(results)
            avg_time = statistics.mean(r['response_time'] for r in results)
            status_codes = [r['status_code'] for r in results]
            
            print(f"  {endpoint}: {success_count}/{total_count} successful, avg: {avg_time:.3f}s")
            print(f"    Status codes: {set(status_codes)}")
        
        # Overall assertions
        total_success = sum(1 for r in all_results if r['success'])
        total_requests = len(all_results)
        
        assert total_success >= total_requests * 0.7, f"Expected at least 70% success rate, got {total_success}/{total_requests}"
    
    def test_concurrent_voice_webhook_heavy_load(self):
        """Test voice webhook under heavy concurrent load."""
        def make_voice_request_with_variations(request_id):
            start_time = time.time()
            
            # Vary the request data to simulate real usage
            call_statuses = ['ringing', 'in-progress', 'completed']
            phone_numbers = ['+15551234567', '+15559876543', '+15555555555']
            
            twilio_data = {
                'CallSid': f'CA{request_id:030d}',
                'AccountSid': 'ACb8391ed8d92871d85180ca9adea481b6',
                'From': random.choice(phone_numbers),
                'To': '+17036467799',
                'CallStatus': random.choice(call_statuses),
                'Direction': 'inbound'
            }
            
            # Add speech data sometimes
            if random.random() < 0.3:
                twilio_data['SpeechResult'] = random.choice([
                    'I want California roll',
                    'Order salmon sushi',
                    'What do you have today',
                    'Cancel my order'
                ])
            
            response = client.post("/voice/", data=twilio_data)
            end_time = time.time()
            
            return {
                'request_id': request_id,
                'status_code': response.status_code,
                'response_time': end_time - start_time,
                'success': response.status_code == 200,
                'has_twiml': '<Response>' in response.text if response.status_code == 200 else False,
                'response_size': len(response.content)
            }
        
        # Run 50 concurrent voice requests
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(make_voice_request_with_variations, i) for i in range(50)]
            results = [future.result() for future in as_completed(futures)]
        
        # Analyze results
        success_count = sum(1 for r in results if r['success'])
        twiml_count = sum(1 for r in results if r['has_twiml'])
        response_times = [r['response_time'] for r in results]
        response_sizes = [r['response_size'] for r in results]
        
        avg_response_time = statistics.mean(response_times)
        max_response_time = max(response_times)
        min_response_time = min(response_times)
        p95_response_time = sorted(response_times)[int(len(response_times) * 0.95)]
        
        avg_response_size = statistics.mean(response_sizes)
        
        print(f"Heavy voice webhook load test (50 requests):")
        print(f"  Success rate: {success_count}/50 ({success_count/50*100:.1f}%)")
        print(f"  TwiML responses: {twiml_count}/50 ({twiml_count/50*100:.1f}%)")
        print(f"  Response times: avg={avg_response_time:.3f}s, min={min_response_time:.3f}s, max={max_response_time:.3f}s, p95={p95_response_time:.3f}s")
        print(f"  Average response size: {avg_response_size:.0f} bytes")
        
        # Assertions
        assert success_count >= 45, f"Expected at least 45/50 successful, got {success_count}"
        assert twiml_count >= 45, f"Expected at least 45/50 TwiML responses, got {twiml_count}"
        assert avg_response_time < 1.0, f"Average response time too slow: {avg_response_time:.3f}s"
        assert p95_response_time < 2.0, f"95th percentile response time too slow: {p95_response_time:.3f}s"
    
    def test_rapid_sequential_different_endpoints(self):
        """Test rapid switching between different endpoints."""
        endpoints_cycle = [
            ("/health", "GET"),
            ("/voice/", "POST"),
            ("/menu/categories", "GET"),
            ("/docs", "GET"),
            ("/openapi.json", "GET")
        ]
        
        results = []
        
        for i in range(100):  # 100 rapid requests
            endpoint, method = endpoints_cycle[i % len(endpoints_cycle)]
            start_time = time.time()
            
            try:
                if method == "GET":
                    response = client.get(endpoint)
                else:  # POST
                    data = {
                        'CallSid': f'CA{i:030d}',
                        'AccountSid': 'ACb8391ed8d92871d85180ca9adea481b6',
                        'From': '+15551234567',
                        'To': '+17036467799',
                    }
                    response = client.post(endpoint, data=data)
                
                end_time = time.time()
                results.append({
                    'request_id': i,
                    'endpoint': endpoint,
                    'status_code': response.status_code,
                    'response_time': end_time - start_time,
                    'success': response.status_code < 500
                })
            except Exception as e:
                end_time = time.time()
                results.append({
                    'request_id': i,
                    'endpoint': endpoint,
                    'status_code': 0,
                    'response_time': end_time - start_time,
                    'success': False,
                    'error': str(e)
                })
            
            # Small delay to simulate rapid but realistic usage
            time.sleep(0.005)
        
        # Analyze results
        success_count = sum(1 for r in results if r['success'])
        response_times = [r['response_time'] for r in results]
        avg_response_time = statistics.mean(response_times)
        
        # Check for consistency across endpoint types
        by_endpoint = {}
        for result in results:
            endpoint = result['endpoint']
            if endpoint not in by_endpoint:
                by_endpoint[endpoint] = []
            by_endpoint[endpoint].append(result)
        
        print(f"Rapid sequential endpoint switching (100 requests):")
        print(f"  Overall success rate: {success_count}/100 ({success_count/100*100:.1f}%)")
        print(f"  Average response time: {avg_response_time:.3f}s")
        
        for endpoint, ep_results in by_endpoint.items():
            ep_success = sum(1 for r in ep_results if r['success'])
            ep_total = len(ep_results)
            ep_avg_time = statistics.mean(r['response_time'] for r in ep_results)
            print(f"  {endpoint}: {ep_success}/{ep_total} successful, avg: {ep_avg_time:.3f}s")
        
        # Assertions
        assert success_count >= 90, f"Expected at least 90/100 successful, got {success_count}"
        assert avg_response_time < 0.5, f"Average response time too slow: {avg_response_time:.3f}s"
    
    def test_error_recovery_simulation(self):
        """Test system behavior with invalid inputs and error recovery."""
        error_scenarios = [
            # Invalid voice webhook data
            {"endpoint": "/voice/", "method": "POST", "data": {"invalid": "data"}},
            {"endpoint": "/voice/", "method": "POST", "data": {"CallSid": "invalid_sid"}},
            {"endpoint": "/voice/", "method": "POST", "data": {}},
            
            # Non-existent endpoints
            {"endpoint": "/nonexistent", "method": "GET", "data": None},
            {"endpoint": "/api/invalid", "method": "POST", "data": {}},
            
            # Malformed JSON
            {"endpoint": "/order/take-order", "method": "POST", "data": "invalid_json"},
        ]
        
        results = []
        
        for i, scenario in enumerate(error_scenarios * 5):  # Run each scenario 5 times
            start_time = time.time()
            
            try:
                if scenario["method"] == "GET":
                    response = client.get(scenario["endpoint"])
                else:
                    if isinstance(scenario["data"], str):
                        # Send raw string for malformed JSON test
                        response = client.post(
                            scenario["endpoint"], 
                            data=scenario["data"],
                            headers={"Content-Type": "application/json"}
                        )
                    elif scenario["data"] is None:
                        response = client.get(scenario["endpoint"])
                    else:
                        response = client.post(scenario["endpoint"], data=scenario["data"])
                
                end_time = time.time()
                results.append({
                    'scenario_id': i,
                    'endpoint': scenario["endpoint"],
                    'status_code': response.status_code,
                    'response_time': end_time - start_time,
                    'handled_gracefully': 400 <= response.status_code < 500 or response.status_code == 404,
                    'response_size': len(response.content)
                })
            except Exception as e:
                end_time = time.time()
                results.append({
                    'scenario_id': i,
                    'endpoint': scenario["endpoint"],
                    'status_code': 0,
                    'response_time': end_time - start_time,
                    'handled_gracefully': False,
                    'error': str(e)
                })
        
        # Analyze error handling
        graceful_count = sum(1 for r in results if r['handled_gracefully'])
        total_count = len(results)
        response_times = [r['response_time'] for r in results]
        avg_response_time = statistics.mean(response_times)
        
        print(f"Error recovery simulation ({total_count} error scenarios):")
        print(f"  Gracefully handled: {graceful_count}/{total_count} ({graceful_count/total_count*100:.1f}%)")
        print(f"  Average error response time: {avg_response_time:.3f}s")
        
        # Check specific status codes
        status_codes = [r['status_code'] for r in results]
        status_distribution = {code: status_codes.count(code) for code in set(status_codes)}
        print(f"  Status code distribution: {status_distribution}")
        
        # Assertions - errors should be handled gracefully, not crash the system
        assert graceful_count >= total_count * 0.8, f"Expected at least 80% graceful error handling, got {graceful_count}/{total_count}"
        assert avg_response_time < 1.0, f"Error response time too slow: {avg_response_time:.3f}s"
    
    def test_memory_leak_detection(self):
        """Test for potential memory leaks under sustained load."""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        print(f"Initial memory usage: {initial_memory:.1f} MB")
        
        # Run sustained load
        for batch in range(5):  # 5 batches
            batch_results = []
            
            # Each batch: 20 voice webhook calls
            for i in range(20):
                twilio_data = {
                    'CallSid': f'CA{batch * 20 + i:030d}',
                    'AccountSid': 'ACb8391ed8d92871d85180ca9adea481b6',
                    'From': '+15551234567',
                    'To': '+17036467799',
                    'SpeechResult': f'Test speech input {batch}-{i}'
                }
                
                response = client.post("/voice/", data=twilio_data)
                batch_results.append(response.status_code == 200)
            
            # Check memory after each batch
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = current_memory - initial_memory
            
            print(f"Batch {batch + 1}: Memory usage: {current_memory:.1f} MB (+{memory_increase:.1f} MB)")
            
            # Give system time to cleanup
            time.sleep(0.1)
        
        # Final memory check
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_memory_increase = final_memory - initial_memory
        
        print(f"Final memory usage: {final_memory:.1f} MB")
        print(f"Total memory increase: {total_memory_increase:.1f} MB")
        
        # Memory increase should be reasonable (less than 100MB for this test)
        assert total_memory_increase < 100, f"Potential memory leak detected: {total_memory_increase:.1f} MB increase"