#!/home/proxyie/MySoftware/RedBarSushiAI/venv/bin/python
"""
Detect if we are running inside a container and set an environment variable.
"""

import os
import sys

def detect_container():
    """
    Detect if we're running inside a container and return True/False.
    
    This checks for container-specific indicators:
    1. Check /.dockerenv file existence
    2. Check cgroup for docker mention
    3. Check hostname for container-like pattern
    """
    # Check for .dockerenv file
    if os.path.exists('/.dockerenv'):
        return True
    
    # Check cgroup
    try:
        with open('/proc/1/cgroup', 'r') as f:
            for line in f:
                if 'docker' in line or 'kubepods' in line:
                    return True
    except:
        pass
    
    # Check hostname
    try:
        with open('/proc/sys/kernel/hostname', 'r') as f:
            hostname = f.read().strip()
            if hostname and (
                hostname.startswith('docker-') or 
                hostname.startswith('k8s-') or
                hostname.startswith('ecs-') or
                len(hostname) == 12 and all(c in '0123456789abcdef' for c in hostname)
            ):
                return True
    except:
        pass
    
    return False

if __name__ == "__main__":
    in_container = detect_container()
    
    # Set environment variable
    os.environ["RUNNING_IN_CONTAINER"] = "true" if in_container else "false"
    
    # Print result if running directly
    if len(sys.argv) > 1 and sys.argv[1] == "--print":
        print(f"Running in container: {in_container}")
    
    # Set exit code based on container detection
    sys.exit(0 if in_container else 1)