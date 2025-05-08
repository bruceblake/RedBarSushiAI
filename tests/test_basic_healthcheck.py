"""
Basic health check test to verify the web server is working correctly.
"""

import requests
import os

def test_web_healthcheck():
    """Test that the web server's /healthcheck endpoint is working."""
    web_port = os.environ.get("WEB_PORT", "8080")
    health_url = f"http://host.docker.internal:{web_port}/healthcheck"
    
    try:
        response = requests.get(health_url)
        response.raise_for_status()
        
        # Parse JSON response
        health_data = response.json()
        
        # Check basic structure
        assert "status" in health_data, "Missing status field"
        assert health_data["status"] == "ok", "Health status should be 'ok'"
        
        # Check checks
        assert "checks" in health_data, "Missing checks field"
        checks = health_data["checks"]
        
        # Verify core services
        assert "database" in checks, "Missing database check"
        assert "redis" in checks, "Missing redis check"
        
        print("✅ Web healthcheck passed")
        return True
    except Exception as e:
        print(f"❌ Web healthcheck failed: {str(e)}")
        return False

def test_mcp_connection():
    """Test that we can connect to the MCP server's SSE endpoint."""
    mcp_port = os.environ.get("MCP_PORT", "4244")
    mcp_url = f"http://host.docker.internal:{mcp_port}/sse"
    
    try:
        # Make a simple request to check connectivity
        response = requests.get(mcp_url, stream=True, timeout=2)
        
        # We should get a 200 OK and the connection should stay open
        assert response.status_code == 200, f"MCP SSE returned {response.status_code}"
        
        # Close the connection
        response.close()
        
        print("✅ MCP connection test passed")
        return True
    except Exception as e:
        print(f"❌ MCP connection test failed: {str(e)}")
        return False

if __name__ == "__main__":
    """Run the tests."""
    web_ok = test_web_healthcheck()
    mcp_ok = test_mcp_connection()
    
    if web_ok and mcp_ok:
        print("✅ All basic health checks passed")
        exit(0)
    else:
        print("❌ Some health checks failed")
        exit(1)