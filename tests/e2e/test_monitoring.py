"""
End-to-end tests for the monitoring endpoints.
These tests verify the functionality of the monitoring and health check endpoints.
"""

import json
import pytest
import requests
import logging
import sys
import os

# Set up logging
log_format = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(
    level=logging.DEBUG,
    format=log_format,
    handlers=[
        logging.FileHandler("e2e_monitoring_test_debug.log", mode="w"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("e2e_monitoring_tests")

# Get the base URL from environment
BASE_URL = os.getenv("BASE_URL", "https://redbarsushiai-staging.onrender.com")
logger.info(f"Running monitoring tests against: {BASE_URL}")

@pytest.mark.e2e
def test_monitoring_health_endpoint():
    """Test that the monitoring health endpoint returns valid data."""
    logger.info("Starting test_monitoring_health_endpoint test")
    
    response = requests.get(f"{BASE_URL}/monitoring/health")
    logger.debug(f"Health response: {response.text}")
    
    assert response.status_code == 200
    logger.debug(f"Response status code: {response.status_code}")
    
    # Parse the response as JSON
    health_data = response.json()
    
    # Check for required fields
    assert "status" in health_data
    assert "timestamp" in health_data
    assert "components" in health_data
    
    # Log the component statuses
    for component, status in health_data["components"].items():
        logger.info(f"Component {component}: {status.get('status')}")
    
    logger.info("test_monitoring_health_endpoint test completed successfully")

@pytest.mark.e2e
def test_monitoring_agents_health_endpoint():
    """Test that the agents health endpoint returns valid data."""
    logger.info("Starting test_monitoring_agents_health_endpoint test")
    
    response = requests.get(f"{BASE_URL}/monitoring/agents/health")
    logger.debug(f"Agents health response: {response.text}")
    
    assert response.status_code == 200
    logger.debug(f"Response status code: {response.status_code}")
    
    # Parse the response as JSON
    agent_health = response.json()
    
    # Check for required fields
    assert "status" in agent_health
    assert "timestamp" in agent_health
    assert "agents" in agent_health
    
    # Log the agent statuses
    for agent_name, status in agent_health["agents"].items():
        logger.info(f"Agent {agent_name}: {status.get('status')}")
    
    logger.info("test_monitoring_agents_health_endpoint test completed successfully")

@pytest.mark.e2e
def test_monitoring_metrics_endpoint():
    """Test that the metrics endpoint returns valid data."""
    logger.info("Starting test_monitoring_metrics_endpoint test")
    
    response = requests.get(f"{BASE_URL}/monitoring/metrics")
    
    assert response.status_code == 200
    logger.debug(f"Response status code: {response.status_code}")
    
    # Check content type - could be JSON or Prometheus format
    content_type = response.headers.get("Content-Type", "")
    logger.info(f"Metrics endpoint content type: {content_type}")
    
    if "application/json" in content_type:
        # Parse as JSON
        metrics_data = response.json()
        assert "timestamp" in metrics_data
        logger.info(f"JSON metrics returned with timestamp: {metrics_data.get('timestamp')}")
    else:
        # Assume Prometheus format
        assert len(response.text) > 0
        logger.info(f"Prometheus metrics returned, length: {len(response.text)}")
    
    logger.info("test_monitoring_metrics_endpoint test completed successfully")