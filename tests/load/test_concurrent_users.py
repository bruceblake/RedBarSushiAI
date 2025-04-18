"""
Load testing framework for the AI agent.
This file contains tests to simulate multiple concurrent users interacting with the system.
"""

import os
import asyncio
import time
import uuid
import random
import json
import pytest
import websockets
from unittest.mock import patch, MagicMock

# Create the directory if it doesn't exist
os.makedirs(os.path.dirname(os.path.abspath(__file__)), exist_ok=True)

# Sample user inputs for simulation
USER_INPUTS = [
    "I'd like to order a California Roll",
    "Do you have any vegetarian options?",
    "How much is the Spicy Tuna Roll?",
    "I'd like two Edamame and one Spicy Tuna Roll",
    "Can I get a California Roll and a Spicy Tuna Roll?",
    "What are your most popular items?",
    "Is the Salmon Nigiri available?",
    "I want to add a California Roll to my order",
    "Can I remove the Spicy Tuna Roll from my order?",
    "Is my order ready?",
]


class LoadTester:
    """Class to perform load testing on the AI agent."""

    def __init__(
        self, base_url, num_users=10, requests_per_user=5, delay_range=(0.5, 2.0)
    ):
        """
        Initialize the load tester.

        Args:
            base_url: The base URL for API requests
            num_users: Number of simulated users
            requests_per_user: Number of requests each user will make
            delay_range: Range of random delays between requests (min, max)
        """
        self.base_url = base_url
        self.num_users = num_users
        self.requests_per_user = requests_per_user
        self.delay_range = delay_range
        self.results = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "response_times": [],
            "errors": [],
        }

    async def simulate_user(self, user_id):
        """Simulate a single user making multiple requests."""
        session_id = f"load_test_{user_id}_{uuid.uuid4()}"

        try:
            # Connect to WebSocket
            uri = f"{self.base_url}/ws/realtime/{session_id}"

            # Print that we're starting to simulate this user
            print(f"User {user_id}: Starting simulation with session {session_id}")

            async with websockets.connect(uri) as websocket:
                # Make multiple requests
                for i in range(self.requests_per_user):
                    # Get a random user input
                    user_input = random.choice(USER_INPUTS)

                    # Measure response time
                    start_time = time.time()

                    # Send the request
                    await websocket.send(
                        json.dumps(
                            {
                                "text": user_input,
                                "session_id": session_id,
                            }
                        )
                    )

                    # Wait for response
                    await websocket.recv()

                    # Record response time
                    response_time = time.time() - start_time
                    self.results["response_times"].append(response_time)

                    # Update success counter
                    self.results["successful_requests"] += 1
                    self.results["total_requests"] += 1

                    # Print progress
                    print(
                        f"User {user_id}: Request {i+1}/{self.requests_per_user} - Response time: {response_time:.2f}s"
                    )

                    # Random delay between requests
                    await asyncio.sleep(random.uniform(*self.delay_range))

        except Exception as e:
            # Record error
            self.results["failed_requests"] += 1
            self.results["total_requests"] += 1
            self.results["errors"].append(str(e))
            print(f"User {user_id}: Error - {str(e)}")

    async def run(self):
        """Run the load test with multiple simulated users."""
        print(
            f"Starting load test with {self.num_users} users, {self.requests_per_user} requests per user"
        )

        # Create tasks for each user
        tasks = [self.simulate_user(i) for i in range(self.num_users)]

        # Run all tasks concurrently
        await asyncio.gather(*tasks)

        # Calculate statistics
        if self.results["response_times"]:
            self.results["avg_response_time"] = sum(
                self.results["response_times"]
            ) / len(self.results["response_times"])
            self.results["min_response_time"] = min(self.results["response_times"])
            self.results["max_response_time"] = max(self.results["response_times"])

        # Print results
        print("\nLoad Test Results:")
        print(f"Total Requests: {self.results['total_requests']}")
        print(f"Successful Requests: {self.results['successful_requests']}")
        print(f"Failed Requests: {self.results['failed_requests']}")

        if self.results["response_times"]:
            print(f"Average Response Time: {self.results['avg_response_time']:.2f}s")
            print(f"Min Response Time: {self.results['min_response_time']:.2f}s")
            print(f"Max Response Time: {self.results['max_response_time']:.2f}s")

        if self.results["errors"]:
            print(f"\nErrors ({len(self.results['errors'])} total):")
            for i, error in enumerate(
                self.results["errors"][:5]
            ):  # Show first 5 errors
                print(f"{i+1}. {error}")

            if len(self.results["errors"]) > 5:
                print(f"... and {len(self.results['errors']) - 5} more errors")

        return self.results


@pytest.mark.asyncio
@patch("websockets.connect")
async def test_load_simulation(mock_websocket_connect):
    """Test the load simulation with mocked WebSocket."""
    # Create mock WebSocket
    mock_ws = MagicMock()
    mock_ws.__aenter__.return_value = mock_ws
    mock_ws.send = AsyncMock()
    mock_ws.recv = AsyncMock(return_value=json.dumps({"text": "I'm the AI assistant"}))

    # Configure the mock
    mock_websocket_connect.return_value = mock_ws

    # Create a load tester with reduced parameters for testing
    load_tester = LoadTester(
        base_url="wss://staging.redbar-sushi.ai",
        num_users=3,
        requests_per_user=2,
        delay_range=(0.1, 0.2),
    )

    # Run the test
    results = await load_tester.run()

    # Verify results
    assert results["total_requests"] == 6  # 3 users * 2 requests
    assert results["successful_requests"] == 6
    assert results["failed_requests"] == 0
    assert len(results["response_times"]) == 6

    # Verify that WebSocket methods were called
    assert mock_ws.send.await_count == 6
    assert mock_ws.recv.await_count == 6


# Helper class for async mocking
class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


if __name__ == "__main__":
    # This allows running the load test directly
    import sys

    # Default parameters
    base_url = "wss://staging.redbar-sushi.ai"
    num_users = 10
    requests_per_user = 5

    # Parse command line arguments
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    if len(sys.argv) > 2:
        num_users = int(sys.argv[2])
    if len(sys.argv) > 3:
        requests_per_user = int(sys.argv[3])

    # Create and run the load tester
    load_tester = LoadTester(
        base_url=base_url, num_users=num_users, requests_per_user=requests_per_user
    )

    # Run the test
    asyncio.run(load_tester.run())
