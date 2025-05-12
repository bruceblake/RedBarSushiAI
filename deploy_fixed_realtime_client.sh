#!/bin/bash
# Deploy the fixed Realtime API client

set -e

echo "===== Deploying Fixed OpenAI Realtime Client ====="

# Create a backup of the original file
ORIGINAL_FILE="app/utils/realtime_audio_async.py"
BACKUP_FILE="app/utils/realtime_audio_async.py.bak"
FIXED_FILE="app/utils/realtime_audio_async_fixed.py"

# Check if the fixed file exists
if [ ! -f "$FIXED_FILE" ]; then
    echo "❌ Error: Fixed file not found at $FIXED_FILE"
    exit 1
fi

# Check if the original file exists
if [ ! -f "$ORIGINAL_FILE" ]; then
    echo "❌ Error: Original file not found at $ORIGINAL_FILE"
    exit 1
fi

# Create backup if it doesn't exist
if [ ! -f "$BACKUP_FILE" ]; then
    echo "Creating backup of original file..."
    cp "$ORIGINAL_FILE" "$BACKUP_FILE"
    echo "✅ Backup created at $BACKUP_FILE"
else
    echo "Backup already exists, skipping backup creation"
fi

# Replace the original file with the fixed version
echo "Deploying fixed version..."
cp "$FIXED_FILE" "$ORIGINAL_FILE"
echo "✅ Fixed version deployed to $ORIGINAL_FILE"

# Create a verification script
echo "Creating verification script..."
cat > verify_realtime_client.py << 'EOF'
#!/usr/bin/env python3
"""
Verify that the OpenAI Realtime client has been properly updated.
"""

import os
import sys
import inspect
import importlib.util

def load_module(file_path, module_name):
    """Load a module from a file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def check_client_implementation(module):
    """Check if the client implementation has the necessary methods and features."""
    # Check for OpenAIRealtimeClient class
    if not hasattr(module, 'OpenAIRealtimeClient'):
        print("❌ OpenAIRealtimeClient class not found")
        return False
    
    client_class = module.OpenAIRealtimeClient
    
    # Check for process_messages method
    if not hasattr(client_class, 'process_messages'):
        print("❌ process_messages method missing from OpenAIRealtimeClient")
        return False
    
    # Check for task management attributes
    attrs_to_check = [
        ('_event_processing_task', "Task management attribute"),
        ('is_processing_loop_active', "Processing loop flag")
    ]
    
    all_attrs_present = True
    for attr, desc in attrs_to_check:
        if attr not in client_class.__init__.__code__.co_varnames:
            source = inspect.getsource(client_class.__init__)
            if attr not in source:
                print(f"❌ {desc} '{attr}' not found in OpenAIRealtimeClient.__init__")
                all_attrs_present = False
    
    # Look for async for in process_messages
    process_messages = getattr(client_class, 'process_messages')
    source = inspect.getsource(process_messages)
    
    if 'async for message in self.websocket' not in source:
        print("❌ process_messages is not using 'async for' pattern")
        all_attrs_present = False
    
    # Check for task cancellation in close method
    close_method = getattr(client_class, 'close')
    close_source = inspect.getsource(close_method)
    
    if 'self.is_processing_loop_active = False' not in close_source:
        print("❌ close method not setting is_processing_loop_active to False")
        all_attrs_present = False
        
    if '_event_processing_task.cancel()' not in close_source:
        print("❌ close method not cancelling _event_processing_task")
        all_attrs_present = False
    
    return all_attrs_present

def main():
    # Path to the deployed realtime client
    client_path = "app/utils/realtime_audio_async.py"
    
    if not os.path.exists(client_path):
        print(f"❌ Error: {client_path} not found")
        return 1
    
    # Load the module
    print(f"Loading module from {client_path}...")
    module = load_module(client_path, "realtime_audio_async")
    
    # Check client implementation
    print("Checking client implementation...")
    if check_client_implementation(module):
        print("✅ OpenAI Realtime client implementation is correct")
        print("✅ The process_messages method is properly implemented")
        print("✅ Task management is properly implemented")
        return 0
    else:
        print("❌ OpenAI Realtime client implementation has issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())
EOF
chmod +x verify_realtime_client.py

# Run the verification script
echo
echo "Verifying deployment..."
python verify_realtime_client.py

echo
echo "===== Deployment Complete ====="
echo
echo "The fixed OpenAI Realtime client has been deployed."
echo "This fix should resolve the 'cannot call recv while another coroutine is already waiting'"
echo "error by ensuring only one coroutine is reading from the WebSocket at a time."
echo
echo "Key improvements:"
echo "1. Using 'async for' to safely receive WebSocket messages"
echo "2. Added proper task management with _event_processing_task tracking"
echo "3. Added is_processing_loop_active flag to safely stop the message loop"
echo "4. Improved error handling and resource cleanup"
echo
echo "If you need to restore the original file:"
echo "  cp $BACKUP_FILE $ORIGINAL_FILE"