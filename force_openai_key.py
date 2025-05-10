#!/usr/bin/env python
"""
Force set the OpenAI API key for debugging purposes.
This script is for local development and testing only.
"""

import os
import sys
import subprocess
import argparse

def main():
    parser = argparse.ArgumentParser(description="Force set OpenAI API key for debugging")
    parser.add_argument("--key", help="OpenAI API key to set (if not provided, will prompt)")
    parser.add_argument("--export", action="store_true", help="Print export commands instead of setting variables")
    args = parser.parse_args()
    
    # Get API key
    api_key = args.key
    if not api_key:
        api_key = input("Enter your OpenAI API key (starts with 'sk-'): ")
    
    if not api_key.startswith("sk-"):
        print("Warning: API key doesn't start with 'sk-', which is unusual")
        confirm = input("Continue anyway? (y/N): ")
        if confirm.lower() != 'y':
            sys.exit(1)
    
    # Set environment variables
    if args.export:
        print("\n# Run these commands in your terminal:")
        print(f"export OPENAI_API_KEY='{api_key}'")
        print("export OPENAI_REALTIME_MODEL='gpt-4o-realtime-preview-2024-10-01'")
        print("export OPENAI_REALTIME_VOICE='shimmer'")
    else:
        os.environ["OPENAI_API_KEY"] = api_key
        os.environ["OPENAI_REALTIME_MODEL"] = "gpt-4o-realtime-preview-2024-10-01"
        os.environ["OPENAI_REALTIME_VOICE"] = "shimmer"
        
        print(f"Environment variables set:")
        print(f"OPENAI_API_KEY: {api_key[:4]}...{api_key[-4:]}")
        print(f"OPENAI_REALTIME_MODEL: {os.environ.get('OPENAI_REALTIME_MODEL')}")
        print(f"OPENAI_REALTIME_VOICE: {os.environ.get('OPENAI_REALTIME_VOICE')}")
    
    # Verify with a subprocess call
    print("\nVerifying API key with a simple call:")
    try:
        cmd = [
            sys.executable, "-c", 
            "import os, requests; "
            "resp = requests.get('https://api.openai.com/v1/models', "
            f"headers={{'Authorization': 'Bearer {api_key}', 'Content-Type': 'application/json'}}); "
            "print(f'API Status: {resp.status_code}'); "
            "print('Success!' if resp.status_code == 200 else f'Error: {resp.text}')"
        ]
        subprocess.run(cmd)
    except Exception as e:
        print(f"Error testing API key: {str(e)}")

if __name__ == "__main__":
    main()