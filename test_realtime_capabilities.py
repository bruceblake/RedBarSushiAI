#!/usr/bin/env python3
"""
Test script to verify realtime audio capabilities and menu query functionality
"""
import os
import sys
import json
import requests
import logging
import argparse
from typing import Dict, Any

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_capabilities(base_url: str = "http://localhost:5000") -> Dict[str, Any]:
    """Test realtime audio capabilities by querying the server"""
    capabilities_url = f"{base_url}/api/ws/capabilities"
    
    try:
        response = requests.get(capabilities_url, timeout=5)
        response.raise_for_status()
        capabilities = response.json()
        
        # Print capabilities in a nice format
        print("\n=== REALTIME AUDIO CAPABILITIES ===")
        print(f"Processor type: {capabilities.get('processor_type', 'Unknown')}")
        print(f"WebSocket backend: {capabilities.get('backend', 'Unknown')}")
        print(f"Model: {capabilities.get('model', 'gpt-4.1-mini')}")
        print(f"Real-time STT: {'✅ YES' if capabilities.get('real_time_stt') else '❌ NO'}")
        print(f"Real-time TTS: {'✅ YES' if capabilities.get('real_time_tts') else '❌ NO'}")
        print(f"WebSockets available: {'✅ YES' if capabilities.get('websockets_available') else '❌ NO'}")
        
        # Determine overall status
        if capabilities.get('real_time_stt') and capabilities.get('real_time_tts'):
            print("\n✅ FULL REALTIME AUDIO CAPABILITY AVAILABLE")
        elif capabilities.get('real_time_stt') or capabilities.get('real_time_tts'):
            print("\n⚠️ PARTIAL REALTIME AUDIO CAPABILITY")
        else:
            print("\n❌ NO REALTIME AUDIO CAPABILITY")
            
        return capabilities
    except Exception as e:
        print(f"\n❌ ERROR: Could not connect to {capabilities_url}: {e}")
        print("Make sure the server is running and accessible.")
        return {}

def test_menu_queries(base_url: str = "http://localhost:5000") -> None:
    """Test menu query capabilities by making sample queries to the API"""
    analyze_url = f"{base_url}/api/analyze"
    sample_queries = [
        "What's on the menu?",
        "How much is the California Roll?",
        "Do you have vegetarian options?",
        "What are your most popular rolls?"
    ]
    
    print("\n=== MENU QUERY CAPABILITIES ===")
    
    try:
        for query in sample_queries:
            print(f"\nTesting query: '{query}'")
            response = requests.post(
                analyze_url, 
                json={"text": query},
                timeout=10
            )
            
            if response.status_code == 200:
                analysis = response.json()
                intent = analysis.get("intent", "unknown")
                print(f"Detected intent: {intent}")
                
                if intent in ["ask_menu", "get_menu_item_price", "describe_menu_item"]:
                    print("✅ Correctly identified as a menu query")
                    if "menu_items" in analysis:
                        print(f"Found {len(analysis['menu_items'])} menu items in response")
                        for item in analysis.get("menu_items", [])[:3]:  # Show up to 3 items
                            print(f"  - {item.get('name')}: ${item.get('price', 0):.2f}")
                else:
                    print("⚠️ Not identified as a menu query - may need model adjustment")
            else:
                print(f"❌ Error: Status code {response.status_code}")
                print(response.text)
                
    except Exception as e:
        print(f"\n❌ ERROR with menu query test: {e}")
        print("Make sure the server is running and the API endpoints are accessible.")

def main():
    # Only parse arguments when running as a script, not when imported by pytest
    if __name__ == "__main__":
        parser = argparse.ArgumentParser(description="Test realtime audio and menu query capabilities")
        parser.add_argument("--url", default="http://localhost:5000", help="Base URL of the server")
        args = parser.parse_args()
    else:
        # Define a dummy args object for when imported by pytest
        class Args:
            url = "http://localhost:5000"
        args = Args()
    
    print("\n=== REDBARSUSHIAI CAPABILITY TESTER ===")
    print(f"Testing server at: {args.url}")
    
    capabilities = test_capabilities(args.url)
    if capabilities:
        test_menu_queries(args.url)
    
    print("\nTesting complete!")

if __name__ == "__main__":
    main()