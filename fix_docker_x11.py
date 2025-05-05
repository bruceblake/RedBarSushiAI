#!/usr/bin/env python
"""
Fix X11 display configuration issues in Docker environment for RedBarSushiAI.
This script addresses the OpenAI Realtime client's X11 display requirements.
"""

import os
import sys
import logging
import subprocess
import time
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger("x11_fix")

def check_docker_environment():
    """Check if we're running in a Docker environment."""
    in_docker = os.path.exists('/.dockerenv') or os.environ.get('DOCKER') == 'true'
    logger.info(f"Running in Docker environment: {in_docker}")
    return in_docker

def check_x11_packages():
    """Check if necessary X11 packages are installed."""
    required_packages = ['Xvfb', 'xdpyinfo', 'xauth']
    missing_packages = []
    
    for package in required_packages:
        try:
            subprocess.run(['which', package], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info(f"✅ {package} is installed")
        except subprocess.CalledProcessError:
            logger.warning(f"❌ {package} is not installed")
            missing_packages.append(package)
    
    return missing_packages

def install_x11_packages(missing_packages):
    """Install missing X11 packages."""
    if not missing_packages:
        logger.info("All required X11 packages are already installed")
        return True
    
    logger.info(f"Installing missing packages: {', '.join(missing_packages)}")
    
    try:
        package_map = {
            'Xvfb': 'xvfb',
            'xdpyinfo': 'x11-utils',
            'xauth': 'xauth'
        }
        
        # Create a list of actual package names to install
        packages_to_install = [package_map.get(p, p) for p in missing_packages]
        
        # Add additional required packages
        additional_packages = ['libxrender1', 'libxtst6', 'libxi6', 'dbus-x11']
        packages_to_install.extend(additional_packages)
        
        # Remove duplicates
        packages_to_install = list(set(packages_to_install))
        
        # Install packages
        cmd = ['apt-get', 'update', '-y']
        subprocess.run(cmd, check=True)
        
        cmd = ['apt-get', 'install', '-y'] + packages_to_install
        subprocess.run(cmd, check=True)
        
        logger.info("✅ Successfully installed X11 packages")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to install X11 packages: {str(e)}")
        return False

def find_free_display():
    """Find a free X11 display number."""
    # Try display numbers in this order (prioritize lower numbers)
    display_numbers = [2, 1, 3, 4, 5, 99, 0]
    
    # Check already set DISPLAY environment variable first
    current_display = os.environ.get('DISPLAY')
    if current_display and current_display.startswith(':'):
        try:
            # Extract the display number
            display_num = int(current_display[1:].split('.')[0])
            # Check if it's already in our list
            if display_num in display_numbers:
                # Move it to the front
                display_numbers.remove(display_num)
                display_numbers.insert(0, display_num)
            else:
                # Add it to the front
                display_numbers.insert(0, display_num)
        except (ValueError, IndexError):
            pass
    
    for display_num in display_numbers:
        # Check if display is already in use
        lock_file = f"/tmp/.X{display_num}-lock"
        if os.path.exists(lock_file):
            logger.info(f"Display :{display_num} is already in use (lock file exists)")
            continue
        
        return display_num
    
    # If all standard display numbers are taken, use a random high number
    return random.randint(10, 50)

def start_xvfb(display_num):
    """Start Xvfb on the specified display."""
    try:
        # Kill any existing Xvfb process on this display
        try:
            subprocess.run(
                f"pkill -f 'Xvfb :{display_num}'", 
                shell=True, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
        except subprocess.CalledProcessError:
            pass  # It's okay if there's no process to kill
        
        # Start Xvfb with enhanced parameters
        cmd = [
            'Xvfb', f':{display_num}', 
            '-screen', '0', '1280x720x24', 
            '-ac', '+extension', 'GLX', 
            '+render', '-noreset'
        ]
        
        # Start Xvfb in the background
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        
        # Give Xvfb time to start
        time.sleep(2)
        
        # Check if Xvfb is running
        if process.poll() is not None:
            stderr = process.stderr.read().decode('utf-8')
            logger.error(f"❌ Xvfb failed to start on display :{display_num}: {stderr}")
            return None
        
        logger.info(f"✅ Started Xvfb on display :{display_num} with PID {process.pid}")
        return process.pid
    except Exception as e:
        logger.error(f"❌ Failed to start Xvfb: {str(e)}")
        return None

def test_display(display_num):
    """Test if the X11 display is working."""
    try:
        # Set DISPLAY environment variable
        os.environ['DISPLAY'] = f':{display_num}'
        
        # Run xdpyinfo to test the display
        result = subprocess.run(
            ['xdpyinfo'], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            env=os.environ
        )
        
        if result.returncode == 0:
            logger.info(f"✅ Display :{display_num} is working")
            # Get some basic display info
            display_info = result.stdout.decode('utf-8').split('\n')[0]
            logger.info(f"Display information: {display_info}")
            return True
        else:
            logger.error(f"❌ Display :{display_num} test failed: {result.stderr.decode('utf-8')}")
            return False
    except Exception as e:
        logger.error(f"❌ Error testing display :{display_num}: {str(e)}")
        return False

def setup_openai_environment(display_num):
    """Set up environment variables for OpenAI Realtime client."""
    # Set environment variables
    env_vars = {
        'DISPLAY': f':{display_num}',
        'PYNPUT_HEADLESS': '0',
        'NO_X11': '0',
        'HEADLESS': '0',
        'OPENAI_REALTIME_NO_DISPLAY': '0',
        'X11_SETUP_SUCCESS': 'true',
        'OPENAI_REALTIME_AVAILABLE': '1',
        'USE_XVFB': 'true'
    }
    
    # Update environment variables
    for key, value in env_vars.items():
        os.environ[key] = value
        logger.info(f"Set environment variable: {key}={value}")
    
    # Create a bash script to set environment variables for future processes
    script_path = '/tmp/x11_env.sh'
    with open(script_path, 'w') as f:
        f.write('#!/bin/bash\n')
        for key, value in env_vars.items():
            f.write(f'export {key}="{value}"\n')
    
    os.chmod(script_path, 0o755)
    logger.info(f"Created environment variables script at {script_path}")
    
    # If .bashrc exists, add the script to it
    bashrc_path = os.path.expanduser('~/.bashrc')
    if os.path.exists(bashrc_path):
        with open(bashrc_path, 'a') as f:
            f.write(f'\n# Added by RedBarSushiAI X11 fix script\n')
            f.write(f'if [ -f "{script_path}" ]; then\n')
            f.write(f'    source "{script_path}"\n')
            f.write(f'fi\n')
        logger.info(f"Added environment script to {bashrc_path}")
    
    return env_vars

def create_startup_script(display_num):
    """Create a startup script to ensure Xvfb starts on container restart."""
    script_path = '/usr/local/bin/start-xvfb.sh'
    script_content = f"""#!/bin/bash
# Start Xvfb for OpenAI Realtime client
pkill -f "Xvfb :{display_num}" 2>/dev/null || true
Xvfb :{display_num} -screen 0 1280x720x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!
echo "Started Xvfb with PID $XVFB_PID"

# Set environment variables
export DISPLAY=:{display_num}
export PYNPUT_HEADLESS=0
export NO_X11=0
export HEADLESS=0
export OPENAI_REALTIME_NO_DISPLAY=0
export X11_SETUP_SUCCESS=true
export OPENAI_REALTIME_AVAILABLE=1
export USE_XVFB=true
"""
    
    try:
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        os.chmod(script_path, 0o755)
        logger.info(f"✅ Created Xvfb startup script at {script_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to create startup script: {str(e)}")
        return False

def setup_headless_mode():
    """Set up headless mode environment variables as a fallback."""
    # Set environment variables for headless mode
    env_vars = {
        'PYNPUT_HEADLESS': '1',
        'NO_X11': '1',
        'HEADLESS': '1',
        'OPENAI_REALTIME_NO_DISPLAY': '1',
        'X11_SETUP_SUCCESS': 'false',
        'OPENAI_REALTIME_AVAILABLE': '1',  # Still mark realtime as available for custom implementation
    }
    
    # Update environment variables
    for key, value in env_vars.items():
        os.environ[key] = value
        logger.info(f"Set environment variable: {key}={value}")
    
    # If DISPLAY is set, unset it
    if 'DISPLAY' in os.environ:
        del os.environ['DISPLAY']
        logger.info("Unset DISPLAY environment variable")
    
    # Create a bash script to set environment variables for future processes
    script_path = '/tmp/headless_env.sh'
    with open(script_path, 'w') as f:
        f.write('#!/bin/bash\n')
        for key, value in env_vars.items():
            f.write(f'export {key}="{value}"\n')
        f.write('unset DISPLAY\n')
    
    os.chmod(script_path, 0o755)
    logger.info(f"Created headless environment variables script at {script_path}")
    
    # If .bashrc exists, add the script to it
    bashrc_path = os.path.expanduser('~/.bashrc')
    if os.path.exists(bashrc_path):
        with open(bashrc_path, 'a') as f:
            f.write(f'\n# Added by RedBarSushiAI X11 fix script (headless mode)\n')
            f.write(f'if [ -f "{script_path}" ]; then\n')
            f.write(f'    source "{script_path}"\n')
            f.write(f'fi\n')
        logger.info(f"Added headless environment script to {bashrc_path}")
    
    logger.info("💻 Set up for headless mode operation")
    logger.info("⚠️ OpenAI Realtime client will use fallback WebSocket implementation")
    
    return env_vars

def main():
    """Main function to fix X11 display configuration."""
    logger.info("Starting X11 display configuration fix")
    
    # Check if we're running in Docker
    in_docker = check_docker_environment()
    if not in_docker:
        logger.warning("Not running in Docker environment, but continuing anyway")
    
    # Check and install X11 packages
    missing_packages = check_x11_packages()
    if missing_packages:
        success = install_x11_packages(missing_packages)
        if not success:
            logger.warning("Failed to install some X11 packages, but continuing with available packages")
    
    # Find a free display number
    display_num = find_free_display()
    logger.info(f"Selected display number: {display_num}")
    
    # Start Xvfb
    xvfb_pid = start_xvfb(display_num)
    if xvfb_pid is None:
        logger.error("Failed to start Xvfb, falling back to headless mode")
        setup_headless_mode()
        return False
    
    # Test display
    if not test_display(display_num):
        logger.error("X11 display test failed, falling back to headless mode")
        setup_headless_mode()
        return False
    
    # Set up environment variables
    setup_openai_environment(display_num)
    
    # Create startup script
    create_startup_script(display_num)
    
    logger.info(f"✅ X11 display configuration fix completed successfully with display :{display_num}")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)