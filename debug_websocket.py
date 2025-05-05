#\!/usr/bin/env python3
"""
Debug script to check WebSocket setup on the server.
Prints detailed debugging information about the WebSocket configuration.
"""

import os
import sys
import socket
import subprocess
import platform
import json
import importlib

def check_module(module_name):
    """Check if a module is installed and get its version."""
    try:
        module = importlib.import_module(module_name)
        version = getattr(module, '__version__', 'Unknown')
        return True, version
    except ImportError:
        return False, None

def run_command(command):
    """Run a shell command and return its output."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        return {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
            "success": result.returncode == 0
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"Error running command: {str(e)}",
            "returncode": -1,
            "success": False
        }

def check_network():
    """Check network configuration and open ports."""
    result = {
        "hostname": socket.gethostname(),
        "ip_address": "",
        "open_ports": [],
        "open_ports_error": None,
        "listening_sockets": []
    }
    
    # Get IP address
    try:
        result["ip_address"] = socket.gethostbyname(socket.gethostname())
    except Exception as e:
        result["ip_address"] = f"Error: {str(e)}"
    
    # Check for open ports
    try:
        netstat = run_command("netstat -tuln")
        result["netstat_output"] = netstat["stdout"] if netstat["success"] else netstat["stderr"]
        
        # Parse listening sockets from netstat
        if netstat["success"]:
            lines = netstat["stdout"].split('\n')
            for line in lines:
                if "LISTEN" in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        address = parts[3]
                        result["listening_sockets"].append(address)
    except Exception as e:
        result["open_ports_error"] = str(e)
    
    return result

def check_render_config():
    """Check Render-specific configuration."""
    result = {
        "is_render": "RENDER" in os.environ or "RENDER_SERVICE_ID" in os.environ,
        "render_env_vars": {},
        "render_internal_hostname": None,
        "render_external_hostname": None
    }
    
    # Get Render-specific environment variables
    for key, value in os.environ.items():
        if key.startswith("RENDER_"):
            result["render_env_vars"][key] = value
    
    # Check for render external hostname
    result["render_internal_hostname"] = os.environ.get("RENDER_INTERNAL_HOSTNAME")
    result["render_external_hostname"] = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    
    return result

def check_flask_websocket():
    """Check Flask and WebSocket packages."""
    result = {
        "flask": check_module("flask"),
        "flask_sock": check_module("flask_sock"),
        "simple_websocket": check_module("simple_websocket"),
        "werkzeug": check_module("werkzeug"),
        "gevent": check_module("gevent"),
        "websockets": check_module("websockets"),
    }
    return result

def check_process_env():
    """Check process environment."""
    result = {
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "user": run_command("whoami")["stdout"],
        "running_as_service": run_command("ps -o comm= -p 1")["stdout"] == "systemd",
        "process_tree": run_command(f"ps -f --forest -o pid,ppid,user,cmd {os.getpid()}")["stdout"],
    }
    return result

def get_environment_info():
    """Collect environment information."""
    info = {
        "system": {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "is_64bit": sys.maxsize > 2**32,
        },
        "flask_websocket": check_flask_websocket(),
        "network": check_network(),
        "render": check_render_config(),
        "process": check_process_env(),
        "environment_variables": {
            k: v for k, v in os.environ.items()
            if not any(secret in k.lower() for secret in ["key", "password", "secret", "token"])
        }
    }
    return info

if __name__ == "__main__":
    info = get_environment_info()
    print("======== WEBSOCKET DEBUG INFORMATION ========")
    print(json.dumps(info, indent=2))
    print("=============================================")
    
    # Check for red flags
    print("\n======== POTENTIAL ISSUES ========")
    
    # Check if flask_sock is installed
    flask_sock_installed, flask_sock_version = info["flask_websocket"]["flask_sock"]
    if not flask_sock_installed:
        print("❌ flask_sock is not installed, which is required for WebSockets")
    else:
        print(f"✅ flask_sock is installed (version {flask_sock_version})")
    
    # Check if WebSockets are being properly handled
    simple_websocket_installed, simple_websocket_version = info["flask_websocket"]["simple_websocket"]
    if not simple_websocket_installed:
        print("❌ simple_websocket is not installed, which is needed by flask_sock")
    else:
        print(f"✅ simple_websocket is installed (version {simple_websocket_version})")
    
    # Check for port 80/443 availability
    has_http_port = False
    has_https_port = False
    for socket_addr in info["network"]["listening_sockets"]:
        if ":80" in socket_addr:
            has_http_port = True
        if ":443" in socket_addr:
            has_https_port = True
    
    if not (has_http_port or has_https_port):
        print("⚠️ Neither port 80 (HTTP) nor 443 (HTTPS) appears to be open")
    else:
        if has_http_port:
            print("✅ Port 80 (HTTP) is open")
        if has_https_port:
            print("✅ Port 443 (HTTPS) is open")
    
    # Check Render-specific configuration
    if info["render"]["is_render"]:
        print("✅ Running on Render")
        if not info["render"]["render_external_hostname"]:
            print("⚠️ RENDER_EXTERNAL_HOSTNAME is not set, which might affect WebSocket URL generation")
        else:
            print(f"✅ RENDER_EXTERNAL_HOSTNAME is set to {info['render']['render_external_hostname']}")
    else:
        print("ℹ️ Not running on Render")
        
    print("=================================")
