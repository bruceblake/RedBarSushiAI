"""
Simplified conftest.py for E2E tests that only makes endpoint calls.
This file can replace the regular conftest.py for endpoint-only E2E tests.
"""
import os
import pytest

# Print environment info
BASE_URL = os.getenv("BASE_URL", "https://redbarsushiai-staging.onrender.com")
print(f"Using BASE_URL: {BASE_URL}")

# This is the minimal conftest needed for the E2E tests
# It doesn't include any database fixtures or setup