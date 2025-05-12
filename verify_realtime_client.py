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
