"""
Test the health of all containers in the RedBarSushiAI stack.
"""

import os
import json
import requests
import time
from typing import Dict, Any, Optional, List

def call_mcp_tool(tool_name: str, **params) -> Dict[str, Any]:
    """
    Call a tool on the MCP server using the SSE API.
    
    Args:
        tool_name: The name of the tool to call
        **params: Tool parameters as keyword arguments
        
    Returns:
        The tool result as a dictionary
    """
    # Prepare the tool call payload
    tool_call = {
        "name": tool_name,
        "arguments": params
    }
    
    # Convert to query parameter
    import urllib.parse
    encoded_tool_call = urllib.parse.quote(json.dumps(tool_call))
    
    # Build URLs for different contexts
    mcp_port = os.environ.get("MCP_PORT", "4244")
    
    # Different URLs depending on where this code is running
    # 1. If running on host machine
    host_url = f"http://localhost:{mcp_port}/sse?tool_call={encoded_tool_call}"
    # 2. If running inside container in same Docker network
    container_url = f"http://redbarsushi_mcp:{mcp_port}/sse?tool_call={encoded_tool_call}"
    # 3. If running in arbitrary container that needs to call back to host
    host_docker_internal_url = f"http://host.docker.internal:{mcp_port}/sse?tool_call={encoded_tool_call}"
    
    # Detect environment to determine which URL to use
    # If we're running inside a container, we should use the container_url
    # Check for a container-specific environment variable
    in_container = os.environ.get("RUNNING_IN_CONTAINER", "false").lower() == "true"
    
    if in_container:
        url = container_url
        print(f"Running inside container, using URL: {url}")
    else:
        url = host_url
        print(f"Running on host, using URL: {url}")
    
    # Try different URLs if the primary one fails
    urls_to_try = [url]
    if url != host_docker_internal_url:
        urls_to_try.append(host_docker_internal_url)
    if url != container_url and url != host_url:
        urls_to_try.append(container_url)
        urls_to_try.append(host_url)
    
    # Try each URL until one works
    last_error = None
    for current_url in urls_to_try:
        try:
            # Make request with streaming
            response = requests.get(current_url, stream=True, timeout=15)
            response.raise_for_status()
            
            # Process SSE events
            result = None
            buffer = ""
            
            for line in response.iter_lines():
                if not line:
                    continue
                    
                line_str = line.decode('utf-8')
                if line_str.startswith("data: "):
                    data_str = line_str[6:]  # Remove "data: " prefix
                    try:
                        data = json.loads(data_str)
                        if data.get("type") == "tool_result":
                            result = data.get("result")
                            break
                    except json.JSONDecodeError:
                        pass
            
            # Close connection
            response.close()
            
            if result:
                # If this URL worked, remember it for future calls
                os.environ["MCP_WORKING_URL"] = current_url.split("?")[0]
                return result
            else:
                last_error = "No tool result received"
        
        except Exception as e:
            last_error = str(e)
            print(f"Failed to connect using {current_url}: {str(e)}")
            continue
    
    return {"error": last_error or "Failed to connect to MCP server using all available URLs"}

def test_container_status() -> Dict[str, str]:
    """
    Test the status of all containers.
    
    Returns:
        Dictionary mapping container names to their status
    """
    print("Checking container status...")
    result = call_mcp_tool("container_status")
    
    if "error" in result:
        print(f"❌ Failed to get container status: {result['error']}")
        return {}
    
    # Extract container status
    containers = {}
    for container in result.get("containers", []):
        name = container.get("name", "unknown")
        status = container.get("status", "unknown")
        health = container.get("health", "unknown")
        
        status_str = f"{status} ({health})" if health else status
        containers[name] = status_str
        
        if status == "running" and health in ["healthy", "starting"]:
            print(f"✅ Container {name} is {status_str}")
        else:
            print(f"❌ Container {name} has status: {status_str}")
    
    return containers

def check_postgres_connection() -> bool:
    """
    Check if the database connection is working.
    
    Returns:
        True if the connection is working, False otherwise
    """
    print("Checking PostgreSQL connection...")
    result = call_mcp_tool("sql", query="SELECT 1 AS test")
    
    if "error" in result:
        print(f"❌ PostgreSQL connection failed: {result['error']}")
        return False
    
    if isinstance(result, list) and len(result) > 0 and result[0].get("test") == 1:
        print("✅ PostgreSQL connection successful")
        return True
    
    print(f"❌ Unexpected PostgreSQL result: {result}")
    return False

def check_redis_connection() -> bool:
    """
    Check if the Redis connection is working.
    
    Returns:
        True if the connection is working, False otherwise
    """
    print("Checking Redis connection...")
    result = call_mcp_tool("redis_ping")
    
    if "error" in result:
        print(f"❌ Redis connection failed: {result['error']}")
        return False
    
    if result.get("result") == "PONG":
        print("✅ Redis connection successful")
        return True
    
    print(f"❌ Unexpected Redis result: {result}")
    return False

def check_web_api() -> bool:
    """
    Check if the web API is working.
    
    Returns:
        True if the API is working, False otherwise
    """
    print("Checking web API...")
    
    # Determine the appropriate web API URL based on context
    web_port = os.environ.get("WEB_PORT", "8080")
    in_container = os.environ.get("RUNNING_IN_CONTAINER", "false").lower() == "true"
    
    # Build URLs for different contexts
    if in_container:
        # If running inside a container, use the container hostname
        base_url = f"http://redbarsushi_web:{web_port}"
    else:
        # If running on the host, use localhost
        base_url = f"http://localhost:{web_port}"
    
    # Always have a fallback to host.docker.internal
    urls_to_try = [
        base_url,
        f"http://host.docker.internal:{web_port}"
    ]
    
    # Try each URL
    for url in urls_to_try:
        print(f"Trying web API URL: {url}")
        result = call_mcp_tool("http_get", path="/healthcheck", base_url=url)
        
        if "error" not in result:
            # This URL worked
            if result.get("status") == "ok":
                print(f"✅ Web API health check passed using {url}")
                return True
        else:
            print(f"❌ Web API check failed using {url}: {result['error']}")
    
    print("❌ All web API URLs failed")
    return False

def autonomous_fix(container_name: Optional[str] = None) -> bool:
    """
    Attempt to autonomously fix a container or all containers.
    
    Args:
        container_name: The name of the container to fix, or None to fix all
        
    Returns:
        True if the fix was successful, False otherwise
    """
    if container_name:
        print(f"Attempting to fix container {container_name}...")
        result = call_mcp_tool("auto_fix_container", container_name=container_name)
    else:
        print("Attempting to fix all containers...")
        result = call_mcp_tool("autonomous_fix_all")
    
    if "error" in result:
        print(f"❌ Fix attempt failed: {result['error']}")
        return False
    
    if result.get("success", False):
        print(f"✅ Fix completed successfully: {result.get('message', '')}")
        return True
    
    print(f"❌ Fix failed: {result.get('message', '')}")
    return False

if __name__ == "__main__":
    # Check container status
    containers = test_container_status()
    
    # Check database
    db_ok = check_postgres_connection()
    
    # Check Redis
    redis_ok = check_redis_connection()
    
    # Check web API
    web_ok = check_web_api()
    
    # Summarize
    all_ok = db_ok and redis_ok and web_ok
    
    if all_ok:
        print("\n✅ All health checks passed!")
    else:
        print("\n❌ Some health checks failed")
        
        # Try to fix any issues
        fix_result = autonomous_fix()
        if fix_result:
            print("🔄 Autonomous fix completed, rechecking...")
            time.sleep(5)  # Wait for changes to take effect
            
            # Recheck
            containers = test_container_status()
            db_ok = check_postgres_connection()
            redis_ok = check_redis_connection()
            web_ok = check_web_api()
            
            all_ok = db_ok and redis_ok and web_ok
            if all_ok:
                print("\n✅ All health checks now pass after auto-fix!")
            else:
                print("\n❌ Some health checks still failing after auto-fix")
        else:
            print("❌ Autonomous fix failed")
    
    # Exit with appropriate code
    exit(0 if all_ok else 1)