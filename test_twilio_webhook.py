#!/usr/bin/env python
"""
Test script to verify Twilio webhooks are working with the staging environment.

Usage:
    python test_twilio_webhook.py --url https://redbarsushi-staging.onrender.com

This script:
1. Makes a request to the root endpoint to check basic connectivity
2. Makes a request to the /environment endpoint to get environment details
3. Makes a request to the /staging-test endpoint to simulate a Twilio call
4. Makes a request to the /voice endpoint to simulate a real Twilio call

The requests are formatted like Twilio webhook requests to properly test the endpoints.
"""
import argparse
import requests
import json
from xml.etree import ElementTree as ET

def test_root_endpoint(base_url):
    """Test the root endpoint to check basic connectivity."""
    url = f"{base_url}"
    print(f"\nTesting root endpoint: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            
            # Check if we can determine the environment
            if "environment" in data:
                print(f"ENVIRONMENT: {data['environment']}")
                return data["environment"]
            else:
                print("Environment not specified in response")
                return None
        else:
            print(f"Error: Received status code {response.status_code}")
            return None
    except Exception as e:
        print(f"Error connecting to {url}: {e}")
        return None

def test_environment_endpoint(base_url):
    """Test the environment endpoint to get detailed info about the environment."""
    url = f"{base_url}/environment"
    print(f"\nTesting environment endpoint: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response (truncated):")
            for key, value in list(data.items())[:10]:  # Show first 10 items only
                print(f"  {key}: {value}")
            
            print("...")
            
            # Extract useful information
            env = data.get("environment", "not set")
            is_staging = data.get("is_staging", False)
            host = data.get("host", "unknown")
            
            print(f"ENVIRONMENT: {env}")
            print(f"IS_STAGING: {is_staging}")
            print(f"HOST: {host}")
            
            return env
        else:
            print(f"Error: Received status code {response.status_code}")
            return None
    except Exception as e:
        print(f"Error connecting to {url}: {e}")
        return None

def test_staging_test_endpoint(base_url):
    """Test the staging-test endpoint to simulate a Twilio call."""
    url = f"{base_url}/staging-test"
    print(f"\nTesting staging-test Twilio endpoint: {url}")
    
    # Simulate Twilio parameters
    data = {
        "From": "+12025550123",
        "To": "+12025550456",
        "CallSid": "CA123456789012345678901234567890ab",
    }
    
    try:
        response = requests.post(url, data=data, timeout=10)
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            print("Response: (TwiML)")
            print(response.text)
            
            # Parse the TwiML to extract the say element
            try:
                root = ET.fromstring(response.text)
                say_element = root.find(".//Say")
                if say_element is not None and say_element.text:
                    print(f"Voice message: {say_element.text}")
                    # Check if staging is mentioned
                    if "STAGING" in say_element.text:
                        print("✅ CONFIRMED: This is the STAGING environment")
                        return "staging"
                    elif "PRODUCTION" in say_element.text:
                        print("❌ WARNING: This is the PRODUCTION environment!")
                        return "production"
                    else:
                        print("⚠️ UNKNOWN: Could not determine environment from voice message")
                        return None
                else:
                    print("No Say element found in TwiML")
                    return None
            except Exception as e:
                print(f"Error parsing TwiML: {e}")
                return None
        else:
            print(f"Error: Received status code {response.status_code}")
            return None
    except Exception as e:
        print(f"Error connecting to {url}: {e}")
        return None

def test_voice_endpoint(base_url):
    """Test the voice endpoint to simulate a real Twilio call."""
    url = f"{base_url}/voice"
    print(f"\nTesting main voice endpoint: {url}")
    
    # Simulate Twilio parameters
    data = {
        "From": "+12025550123",
        "To": "+12025550456",
        "CallSid": "CA123456789012345678901234567890ab",
    }
    
    try:
        response = requests.post(url, data=data, timeout=10)
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            print("Response: (TwiML)")
            print(response.text)
            
            # Parse the TwiML to extract the say element
            try:
                root = ET.fromstring(response.text)
                gather_element = root.find(".//Gather")
                if gather_element is not None:
                    say_element = gather_element.find(".//Say")
                    if say_element is not None and say_element.text:
                        print(f"Voice message: {say_element.text}")
                        # Check if staging is mentioned
                        if "STAGING" in say_element.text:
                            print("✅ CONFIRMED: This is the STAGING environment")
                            return "staging"
                        elif "PRODUCTION" in say_element.text:
                            print("❌ WARNING: This is the PRODUCTION environment!")
                            return "production"
                        else:
                            print("⚠️ UNKNOWN: Could not determine environment from voice message")
                            return None
                    else:
                        print("No Say element found in Gather element")
                        return None
                else:
                    print("No Gather element found in TwiML")
                    return None
            except Exception as e:
                print(f"Error parsing TwiML: {e}")
                return None
        else:
            print(f"Error: Received status code {response.status_code}")
            return None
    except Exception as e:
        print(f"Error connecting to {url}: {e}")
        return None

def print_problem_solving_guidance(results):
    """Print guidance based on test results."""
    print("\n" + "="*60)
    print("DIAGNOSIS AND RECOMMENDATIONS")
    print("="*60)
    
    if all(env == "staging" for env in results.values() if env is not None):
        print("✅ SUCCESS! All endpoints are correctly identifying as the STAGING environment.")
        print("\nYour Twilio webhook configuration appears to be correct.")
        print("You can confidently update your Twilio phone number to point to:")
        print(f"https://{args.url}/voice")
        print("\nChecklist for final verification:")
        print("1. Make a test call to your Twilio number")
        print("2. Verify in logs that your staging server is processing the call")
        print("3. Confirm the automated voice says 'This is the STAGING environment'")
    elif any(env == "production" for env in results.values()):
        print("❌ CRITICAL ISSUE: Some endpoints are identifying as PRODUCTION")
        print("\nPossible causes and solutions:")
        print("1. The staging environment variables are not correctly set")
        print("   - Ensure IS_STAGING=true is set in your Render environment variables")
        print("   - Ensure FLASK_ENV=staging is set in your Render environment variables")
        print("\n2. There might be a proxy or redirect happening")
        print("   - Check your Render service settings for redirects")
        print("   - Check your DNS settings")
        print("\n3. The changes may not have been deployed yet")
        print("   - Verify the commit was pushed to the staging branch")
        print("   - Check if the Render service is correctly deploying from the staging branch")
        print("   - Try manually deploying the service from the Render dashboard")
    else:
        print("⚠️ INCONCLUSIVE: Could not definitely determine the environment")
        print("\nPlease check:")
        print("1. Network connectivity to the staging environment")
        print("2. Verify the application is running properly")
        print("3. Check your application logs for errors")
        print("4. Make sure the endpoints are implemented correctly")
    
    print("\nFor better diagnostics:")
    print(f"1. Check the logs in your staging environment")
    print(f"2. Try visiting {args.url}/environment in your browser")
    print(f"3. Verify that your Render service is correctly configured to deploy from the 'staging' branch")

# Only parse arguments when running as a script, not when imported by pytest
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Twilio webhook configuration with staging environment")
    parser.add_argument("--url", required=True, help="Base URL of the staging environment (e.g., https://redbarsushi-staging.onrender.com)")
    args = parser.parse_args()
else:
    # Define a dummy args object for when imported by pytest
    class Args:
        url = "https://redbarsushi-staging.onrender.com"
    args = Args()

# Clean up the URL
base_url = args.url.rstrip("/")
if not base_url.startswith("http"):
    base_url = "https://" + base_url
    
    print("="*60)
    print(f"TESTING TWILIO WEBHOOKS FOR: {base_url}")
    print("="*60)
    
    # Run all tests and collect results
    results = {
        "root": test_root_endpoint(base_url),
        "environment": test_environment_endpoint(base_url),
        "staging_test": test_staging_test_endpoint(base_url),
        "voice": test_voice_endpoint(base_url)
    }
    
    # Print guidance based on results
    print_problem_solving_guidance(results)