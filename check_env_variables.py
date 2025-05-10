#!/usr/bin/env python

import os
import sys

# Critical environment variables that must be set
CRITICAL_VARS = [
    "OPENAI_API_KEY",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_PHONE_NUMBER",
    "DATABASE_URL",
    "REDIS_URL"
]

# Important but not critical variables
IMPORTANT_VARS = [
    "STRIPE_API_KEY",
    "DELIVERECT_API_KEY",
    "DELIVERECT_CLIENT_ID",
    "DELIVERECT_CLIENT_SECRET",
    "BASE_URL"
]

def check_env_variables():
    print("\033[1m===== Environment Variable Check =====\033[0m")
    
    missing_critical = []
    missing_important = []
    present_vars = []
    
    # Check critical variables
    for var in CRITICAL_VARS:
        value = os.environ.get(var)
        if not value:
            missing_critical.append(var)
        else:
            # For API keys, show first 4 and last 4 characters only
            if "API_KEY" in var or "SID" in var or "TOKEN" in var:
                masked_value = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "[TOO SHORT - INVALID]"
                present_vars.append(f"{var}: {masked_value}")
            else:
                present_vars.append(f"{var}: {value}")
    
    # Check important variables
    for var in IMPORTANT_VARS:
        value = os.environ.get(var)
        if not value:
            missing_important.append(var)
        else:
            # For API keys, show first 4 and last 4 characters only
            if "API_KEY" in var or "SID" in var or "TOKEN" in var or "SECRET" in var:
                masked_value = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "[TOO SHORT - INVALID]"
                present_vars.append(f"{var}: {masked_value}")
            else:
                present_vars.append(f"{var}: {value}")
    
    # Print results
    if missing_critical:
        print("\033[31;1m❌ CRITICAL VARIABLES MISSING:\033[0m")
        for var in missing_critical:
            print(f"\033[31m   - {var}\033[0m")
        print("\033[31;1m   These variables are required for the application to function properly!\033[0m")
    
    if missing_important:
        print("\033[33;1m⚠️ IMPORTANT VARIABLES MISSING:\033[0m")
        for var in missing_important:
            print(f"\033[33m   - {var}\033[0m")
        print("\033[33m   These variables may be needed for some functionality.\033[0m")
    
    if present_vars:
        print("\033[32;1m✅ CONFIGURED VARIABLES:\033[0m")
        for var in present_vars:
            print(f"\033[32m   - {var}\033[0m")
    
    # OpenAI API key check
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        if not openai_key.startswith("sk-"):
            print("\033[31;1m❌ WARNING: OPENAI_API_KEY does not start with 'sk-' - it may be invalid!\033[0m")
        elif len(openai_key) < 20:
            print("\033[31;1m❌ WARNING: OPENAI_API_KEY seems too short to be valid!\033[0m")
    
    # Return status for script usage
    return len(missing_critical) == 0

if __name__ == "__main__":
    success = check_env_variables()
    if not success:
        print("\033[31;1m❌ Critical environment variables are missing. Application may not function correctly.\033[0m")
        sys.exit(1)
    else:
        if os.environ.get("OPENAI_API_KEY"):
            print("\033[32;1m✅ All critical environment variables are set. OpenAI API key is configured.\033[0m")
        else:
            print("\033[31;1m❌ OpenAI API key is missing. Voice functionality will not work.\033[0m")
            sys.exit(1)