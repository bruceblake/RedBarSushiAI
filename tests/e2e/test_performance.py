"""
Performance and stress testing for the Red Bar Sushi AI system.
Tests concurrent operations and load handling.
"""
import asyncio
import time
import pytest
from fastapi.testclient import TestClient
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics

from app.main import app

client = TestClient(app)

class TestPerformance:
    """Performance tests for key system endpoints."""
    
    def test_concurrent_health_checks(self):
        """Test multiple concurrent health check requests."""
        def make_health_request():
            start_time = time.time()
            response = client.get("/health")
            end_time = time.time()
            return {
                'status_code': response.status_code,
                'response_time': end_time - start_time,
                'success': response.status_code == 200
            }
        
        # Run 20 concurrent health checks
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_health_request) for _ in range(20)]
            results = [future.result() for future in as_completed(futures)]
        
        # Analyze results
        success_count = sum(1 for r in results if r['success'])
        response_times = [r['response_time'] for r in results]
        avg_response_time = statistics.mean(response_times)
        max_response_time = max(response_times)
        
        print(f"Concurrent health checks: {success_count}/20 successful")
        print(f"Average response time: {avg_response_time:.3f}s")
        print(f"Max response time: {max_response_time:.3f}s")
        
        # Assertions
        assert success_count >= 18, f"Expected at least 18/20 successful, got {success_count}"
        assert avg_response_time < 1.0, f"Average response time too slow: {avg_response_time:.3f}s"
        assert max_response_time < 2.0, f"Max response time too slow: {max_response_time:.3f}s"
    
    def test_concurrent_voice_webhooks(self):
        """Test multiple concurrent voice webhook requests."""
        def make_voice_request(call_id):
            start_time = time.time()
            twilio_data = {
                'CallSid': f'CA{call_id:030d}',
                'AccountSid': 'ACb8391ed8d92871d85180ca9adea481b6',
                'From': '+15551234567',
                'To': '+17036467799',
                'CallStatus': 'in-progress'
            }
            response = client.post("/voice/", data=twilio_data)
            end_time = time.time()
            return {
                'call_id': call_id,
                'status_code': response.status_code,
                'response_time': end_time - start_time,
                'success': response.status_code == 200,
                'has_twiml': '<Response>' in response.text if response.status_code == 200 else False
            }
        
        # Run 15 concurrent voice webhook calls
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(make_voice_request, i) for i in range(15)]
            results = [future.result() for future in as_completed(futures)]
        
        # Analyze results
        success_count = sum(1 for r in results if r['success'])
        twiml_count = sum(1 for r in results if r['has_twiml'])
        response_times = [r['response_time'] for r in results]
        avg_response_time = statistics.mean(response_times)
        max_response_time = max(response_times)
        
        print(f"Concurrent voice webhooks: {success_count}/15 successful")
        print(f"TwiML responses: {twiml_count}/15")
        print(f"Average response time: {avg_response_time:.3f}s")
        print(f"Max response time: {max_response_time:.3f}s")
        
        # Assertions
        assert success_count >= 13, f"Expected at least 13/15 successful, got {success_count}"
        assert twiml_count >= 13, f"Expected at least 13/15 TwiML responses, got {twiml_count}"
        assert avg_response_time < 2.0, f"Average response time too slow: {avg_response_time:.3f}s"
        assert max_response_time < 5.0, f"Max response time too slow: {max_response_time:.3f}s"
    
    def test_menu_endpoint_performance(self):
        """Test menu endpoint performance under load."""
        def make_menu_request():
            start_time = time.time()
            response = client.get("/menu/categories")
            end_time = time.time()
            return {
                'status_code': response.status_code,
                'response_time': end_time - start_time,
                'success': response.status_code == 200,
                'has_data': len(response.json()) > 0 if response.status_code == 200 else False
            }
        
        # Run 25 concurrent menu requests
        with ThreadPoolExecutor(max_workers=12) as executor:
            futures = [executor.submit(make_menu_request) for _ in range(25)]
            results = [future.result() for future in as_completed(futures)]
        
        # Analyze results
        success_count = sum(1 for r in results if r['success'])
        data_count = sum(1 for r in results if r['has_data'])
        response_times = [r['response_time'] for r in results]
        avg_response_time = statistics.mean(response_times)
        max_response_time = max(response_times)
        
        print(f"Concurrent menu requests: {success_count}/25 successful")
        print(f"Data responses: {data_count}/25")
        print(f"Average response time: {avg_response_time:.3f}s")
        print(f"Max response time: {max_response_time:.3f}s")
        
        # Assertions
        assert success_count >= 20, f"Expected at least 20/25 successful, got {success_count}"
        assert avg_response_time < 1.5, f"Average response time too slow: {avg_response_time:.3f}s"
        assert max_response_time < 3.0, f"Max response time too slow: {max_response_time:.3f}s"
    
    def test_rapid_sequential_requests(self):
        """Test rapid sequential requests to detect race conditions."""
        results = []
        
        # Make 30 rapid sequential requests
        for i in range(30):
            start_time = time.time()
            response = client.get("/health")
            end_time = time.time()
            
            results.append({
                'request_id': i,
                'status_code': response.status_code,
                'response_time': end_time - start_time,
                'success': response.status_code == 200
            })
            
            # Small delay to avoid overwhelming the system
            time.sleep(0.01)
        
        # Analyze results
        success_count = sum(1 for r in results if r['success'])
        response_times = [r['response_time'] for r in results]
        avg_response_time = statistics.mean(response_times)
        
        print(f"Rapid sequential requests: {success_count}/30 successful")
        print(f"Average response time: {avg_response_time:.3f}s")
        
        # Check for consistency
        status_codes = [r['status_code'] for r in results]
        unique_status_codes = set(status_codes)
        
        print(f"Status code distribution: {dict((code, status_codes.count(code)) for code in unique_status_codes)}")
        
        # Assertions
        assert success_count >= 28, f"Expected at least 28/30 successful, got {success_count}"
        assert len(unique_status_codes) <= 2, f"Too many different status codes: {unique_status_codes}"
        assert avg_response_time < 0.5, f"Average response time too slow: {avg_response_time:.3f}s"
    
    def test_mixed_endpoint_load(self):
        """Test mixed load across different endpoints."""
        def make_mixed_request(request_type):
            start_time = time.time()
            
            if request_type == 'health':
                response = client.get("/health")
            elif request_type == 'menu':
                response = client.get("/menu/categories")
            elif request_type == 'voice':
                twilio_data = {
                    'CallSid': f'CA{int(time.time() * 1000000) % 1000000:030d}',
                    'AccountSid': 'ACb8391ed8d92871d85180ca9adea481b6',
                    'From': '+15551234567',
                    'To': '+17036467799',
                }
                response = client.post("/voice/", data=twilio_data)
            else:
                response = client.get("/docs")
            
            end_time = time.time()
            return {
                'type': request_type,
                'status_code': response.status_code,
                'response_time': end_time - start_time,
                'success': response.status_code == 200
            }
        
        # Mix of different request types
        request_types = ['health'] * 8 + ['menu'] * 6 + ['voice'] * 4 + ['docs'] * 2
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_mixed_request, req_type) for req_type in request_types]
            results = [future.result() for future in as_completed(futures)]
        
        # Analyze by request type
        by_type = {}
        for result in results:
            req_type = result['type']
            if req_type not in by_type:
                by_type[req_type] = []
            by_type[req_type].append(result)
        
        print("Mixed endpoint load test results:")
        for req_type, type_results in by_type.items():
            success_count = sum(1 for r in type_results if r['success'])
            total_count = len(type_results)
            avg_time = statistics.mean(r['response_time'] for r in type_results)
            print(f"  {req_type}: {success_count}/{total_count} successful, avg: {avg_time:.3f}s")
        
        # Overall assertions
        total_success = sum(1 for r in results if r['success'])
        total_requests = len(results)
        
        assert total_success >= total_requests * 0.85, f"Expected at least 85% success rate, got {total_success}/{total_requests}"